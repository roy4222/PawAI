# `pawai face` CLI 改善提案（研究稿，待 Roy 審）

> **狀態**：RESEARCH ONLY — 未動任何 code、未碰 demo/Jetson。實作延後，Roy 先審。
> **日期**：2026-06-14
> **範圍**：只評估既有 `pawai face` 子命令（list/enroll/delete/rebuild/test）的可用性，提最小改善。
> **結論先講**：CLI **已經有完整的 face enroll 流程**，不是缺命令；缺的是「驗證閉環」與「ghost dir 防呆」。

---

## 1. 現況表（每個命令做什麼 / gap）

真相來源：`tools/pawai_cli/pawai_cli/main.py:1944-2062`、`scripts/face_identity_enroll_cv.py`、
`face_perception/face_perception/face_identity_node.py`。所有 DB 操作都走 `shell.run_remote` SSH 到 Jetson（`/home/jetson/face_db`），不在開發機本機跑。

| 命令 | 程式位置 | 實際送出的遠端動作 | Flags | Gap |
|------|---------|------------------|-------|-----|
| `face list` | `main.py:1949` | SSH 跑 inline python 掃 `/home/jetson/face_db`，每個子目錄列 `.png` 樣本數；名稱含 `_backup`/`old`/`_old`/`backup` 標 `⚠ 疑似備份目錄` | 無 | ✅ 已有 ghost dir 警告（**唯一一個有的命令**）。但只是「列出時」警告，不阻擋訓練 |
| `face enroll` | `main.py:2025` | SSH source ROS env → 跑 `scripts/face_identity_enroll_cv.py --person-name X --samples N --output-dir /home/jetson/face_db --headless`（timeout 300s） | `--person-name`(必填)、`--samples`(預設 30) | **無 sim 驗證**；不檢查 camera topic 是否被佔用；不檢查 face_db 是否存在 ghost dir；**人名沒過 `_clean_face_name`**（delete 有、enroll 沒有，路徑注入不對稱） |
| `face delete <name>` | `main.py:1990` | `_clean_face_name` 擋路徑逃逸 → 可選二次確認（先 probe 樣本數）→ `rm -rf face_db/<name>` + `rm -f model_sface.pkl model_sface.npz` | `name`(arg)、`-y/--yes` | ✅ 防呆最完整（注入防護 + 確認 + .npz purge）。無 gap |
| `face rebuild` | `main.py:2041` | `rm -f model_sface.pkl model_sface.npz`，提示「重啟 face_identity_node 重訓」 | 無 | 只刪 cache，不重啟 node、不驗證。功能正確但名字會誤導（不是「rebuild」是「invalidate cache」） |
| `face test` | `main.py:2054` | SSH source ROS env → `pytest face_perception/test -v` | 無 | **這是跑單元測試，不是 sim 驗證**。CLAUDE.md/README 的 SOP「enroll → rebuild → test」裡的 test **不會量 sim≥0.7**，操作員可能誤以為驗證過了 |

**enroll 的採樣機制（從 `face_identity_enroll_cv.py` 確認）**：
- 訂 `/camera/camera/color/image_raw`（與 face_identity_node 預設 `color_topic` 同一個，`face_identity_node.py:238`）。
- 每幀跑 YuNet 偵測 → 取最大臉 → `alignCrop` → resize 112×112 → 每 `capture_interval`(0.25s) 存一張 PNG，存滿 N 張 `rclpy.shutdown()`。
- headless 模式把預覽寫 `/tmp/face_enroll_debug.jpg`（1Hz），CLI 端看不到。

---

## 2. ENROLL 流程可用性評估（逐題回答 Roy 的問）

**Q: enroll 有引導採集嗎（幾張、哪個 topic、會不會跟 demo camera 衝突）？**
- 張數：有（`--samples` 預設 30，存滿自動結束）。
- Topic：`/camera/camera/color/image_raw`（D435 RGB），enroll 與 face_identity_node 訂**同一個** topic。ROS pub/sub 多訂閱者本來就可共存，所以 enroll 與 demo camera **不會搶獨佔**（CLAUDE.md 6/8 SOP 也是這樣寫的）。**但**：D435 driver 必須已經在跑（enroll 自己不啟 camera），且 enroll node 名 `face_identity_enroll_cv` 與正式 node 不撞名 — 這點 OK。**真正風險不是 camera，是 face_db 寫入**：enroll 邊存 PNG、face_identity_node 若正在跑會在下次重訓時讀到半套樣本（race），但因為要手動 rebuild + 重啟才重訓，實務上不會中招。

**Q: enroll 後有驗證 sim≥0.7 嗎，還是要另外 `face test`？**
- **沒有任何地方驗 sim**。`face test` 是 pytest 單元測試，與 sim 無關。要看 sim 只能：重啟 face node → 對鏡頭走動 → `ros2 topic echo /state/perception/face` 看 `tracks[].sim`，CLI 沒包這步。**這是最大 gap**：CLAUDE.md 6/8 寫「re-enroll 後 0.73-0.81」，但 CLI 給不出這個數字，操作員無法在 demo 前自證 enroll 成功。

**Q: 有沒有「re-enroll + rebuild + test」三合一？**
- **沒有**。操作員手動串 3 個命令：`face enroll … && face rebuild && (重啟 node) && (手動看 sim)`。其中重啟 node 與看 sim 完全不在 CLI 內。

**Q: 錯誤處理（camera 忙 / face_db 缺 / 採集中沒偵測到臉）？**
- Camera 忙 / D435 沒起：enroll 訂閱不到 frame → 卡到 300s timeout → CLI 報 `face enroll failed (code …)`，但訊息無法區分「沒臉」「沒 camera」「topic 名錯」。
- face_db 缺：`face_identity_enroll_cv.py` 用 `mkdir(parents=True, exist_ok=True)` 自建子目錄，OK。
- 採集中沒偵測到臉：enroll 不會存圖、`saved` 停在 0，最後 timeout 才失敗 — **沒有「N 秒沒偵測到臉就早退並提示」**，操作員白等。

**Q: face_db hygiene — 有命令防 ghost backup dir 嗎？**
- **train 的根因確認**：`face_identity_node.list_face_images`（`face_identity_node.py:50-59`）**無條件 iterate `face_db` 內所有子目錄**，`train_model`（:488-530）把每個子目錄名當一個身份訓進 pkl。所以 `_backup*`/`old*` 一定變幽靈身份稀釋 centroid，與 CLAUDE.md 6/8 描述一致。
- **目前防護**：只有 `face list` 會「警告」（不阻擋）。`enroll`/`rebuild` 在執行前**完全不檢查** ghost dir — 操作員 enroll 完 rebuild 完，幽靈身份照樣被訓進去，CLI 不吭聲。
- `.npz` cache purge 已在 T5-1 補上（delete + rebuild 都 `rm -f …pkl …npz`，有 4 條測試守，`test_face_commands.py`）。這塊已修，**不要重做**。

---

## 3. 提案（最小改動，全部 P 標 + 工時 + 風險）

> 原則：不改 runtime 行為、不改 face_identity_node、不引入 Typer/Rich、不破壞既有 218 測試。全部只在 CLI 層加「檢查 / 提示 / 串接」。

### P0-A — `face rebuild` / `face enroll` 前印 ghost-dir 警告（最高 CP）
- **做什麼**：enroll 與 rebuild 執行前，先跑一次跟 `face list` 同款的掃描，若有 `_backup*`/`old*`/`*backup*` 子目錄，stderr 印一行紅字警告「這些目錄會被訓成幽靈身份，建議移出 face_db」，**不阻擋**（純提示，保持 byte-level runtime 不變）。
- **為何 P0**：ghost dir 是 6/8 實機已踩過的坑（Roy 舊圖 sim 掉到 0.2），而 enroll/rebuild 正是操作員「重訓前」最後一關，現在這關完全沉默。
- **工時**：~30 分（抽出 list 的掃描邏輯成 helper，兩處呼叫）。
- **風險**：低。只多印 stderr，exit code 與遠端命令不變，現有測試不受影響。

### P0-B — `face enroll` 人名套用 `_clean_face_name`
- **做什麼**：enroll 的 `--person-name` 跟 delete 一樣過 `_clean_face_name`（擋 `/`、`.`、`..`、leading dot）。
- **為何 P0**：delete 有防護、enroll 沒有，這是不對稱的注入面（enroll 的 name 直接進 `shlex.quote` 進路徑，雖然 quote 擋了 shell 注入，但 `../foo` 仍可能寫到 face_db 外）。
- **工時**：~10 分（一行呼叫 + 1 條測試）。
- **風險**：極低。合法名字行為不變。

### P1-A — `face verify`（新子命令，sim 驗證閉環）
- **做什麼**：新增 `pawai face verify [--person X] [--seconds 10] [--min-sim 0.7]`，SSH 上 Jetson `ros2 topic echo /state/perception/face` 收 ~N 秒，解析 `tracks[].stable_name / sim`，印每人最高 sim 與 pass/fail（sim≥min-sim）。**前提是 face node 已在跑**（不啟 node、不改 runtime）。
- **為何 P1 不是 P0**：這是 CLAUDE.md SOP 真正缺的「test sim≥0.7」步驟，價值最高；但需要 face node 在跑、要解析 topic JSON、要寫測試，工時較大，且 demo 前才用得到。
- **工時**：~2-3 小時（含 mock SSH 測試）。
- **風險**：中（純讀 topic，不發命令，但要小心 timeout 與 JSON 解析 edge case）。

### P1-B — `face enroll` 採集早退提示
- **做什麼**：給 enroll script 加一個「連續 K 秒沒偵測到臉就早退並印提示」的選項（CLI 端傳 flag）。**注意**：這要改 `scripts/face_identity_enroll_cv.py`，已越過「純 CLI 層」邊界 → 標 P1 並單獨評估，**本提案不主推**。
- **工時**：~1 小時。
- **風險**：中（碰到採集 script，需重新上機驗證）。**若要保守，先不做，靠 P1-A 的事後 sim 驗證補。**

### P2 — 文件對齊（README 命令表補 enroll/rebuild/test）
- **做什麼**：`docs/pawai_cli/README.md:143-144` 的命令表只列了 `face list`/`face delete`，補上 `enroll`/`rebuild`/`test`，並在 face db 段寫明「`face test` 是單元測試、不是 sim 驗證」。
- **工時**：~15 分。
- **風險**：無（純文件）。

---

## 4. 明確「不要做」

- **不要改 runtime 行為**：不碰 `face_identity_node.py`、不改 hysteresis 閾值、不改 train_model、不改 `.npz`/`.pkl` 格式。這是 CLI-support 層。
- **不要破壞既有 218 個 CLI 測試**（`tools/pawai_cli/tests/`，已驗 collect 218）。新提案一律加測試、不改既有斷言。特別是 `test_face_commands.py` 的 4 條 `.npz` purge 守門測試不准動。
- **不要重做 `.npz` purge**（T5-1 已完成）。
- **不要 Typer/Rich 大改寫**、不引新依賴、不重排 click group 結構。
- **不要讓 enroll/rebuild「阻擋」ghost dir**（只警告）— 阻擋會改變 exit code 與既有流程，破壞 byte-level 相容。
- **不要在 CLI 裡自動重啟 face_identity_node**（會搶 demo lock、改 runtime 狀態，超出支援層）。

---

## 5. 五行總結 + 最有價值的單一改善

1. CLI **已經有完整 face enroll 流程**（list/enroll/delete/rebuild/test 全在 `main.py:1944-2062`），不缺命令。
2. 缺的是**驗證閉環**：`face test` 跑的是單元測試、不是 sim≥0.7，操作員無法在 demo 前自證 enroll 成功。
3. 缺的是 **ghost-dir 防呆**：只有 `face list` 警告，enroll/rebuild 重訓前完全沉默，而 train 會把所有子目錄訓成身份。
4. 小漏洞：enroll 人名沒過 `_clean_face_name`（delete 有），不對稱。
5. **單一最有價值改善 = P0-A**：enroll/rebuild 前印 ghost-dir 警告（30 分、低風險、直接擋掉 6/8 實機踩過的 sim 掉到 0.2 的坑）；若還有預算再上 **P1-A `face verify`** 補真正的 sim 閉環。
