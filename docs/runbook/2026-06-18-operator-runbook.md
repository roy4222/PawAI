# 2026-06-18 Operator Runbook（操作員手冊）

> 日期：2026-06-13 起草｜狀態：DRAFT — 待 P4-11 dry-run + Roy 終驗（P4-12 HITL）
> 來源計畫：`docs/archive/superpowers-legacy/plans/2026-06-13-plan4-operator-controls-studio-runbook.md`（P4-5~P4-13）
> 對外 claim 一律走 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-618-claim-wording.md`（S1–S8 可講 / F1–F10 禁講）

---

## 誠實底線（先讀，不可違反）

- **AFK / 純軟體完成**只能說「code merged + 單測綠（needs-HITL）」。
- **proven** 只有「Roy 在場真機 HITL 過」才算（見 §7）。
- 對外講話只用 nav-618-claim-wording 的 **S1–S8 可講句**；**禁 F1–F10**（自由巡邏 / 動態繞障 / D435 已融合 / auto-resume / 「聽懂就走到身邊」 / 未經 n=3 的「可靠導航」 / 1.0m+ 連續導航 / 三鏡頭導航 / 即時恢復）。
- 不宣稱：自主導航 / 全自動 live demo / 跌倒偵測 / 2m 物體 / 可靠顏色 / 19 色。**6/18 永不押在 auto-advance**（auto-advance 是加值，manual FLOOR 是保證）。

### 能力分級（每幕）

| 幕 | 分級 | 依據 |
|---|---|---|
| S1 移動進場 | **FAILED / NOT_DEMO_READY** | 6/13 goto_relative 0.3m 走歪撞牆（nav incident plan）；退遙控 + 影片 |
| S2 認人問候 | needs-HITL | greet gate 6/8 改進場觸發（commit `f2a0df4`） |
| S3 姿勢/物體 | needs-HITL | sitting / cup 0.7m |
| S4 手勢 | needs-HITL | confirm 路徑（thumbs_up 目標未驗、peace 驗過） |
| S5 安全拒絕 | **proven**（6/10） | SafetyLayer reject 端到端 |

---

## 重要契約備註（操作員與技術人員都讀）

1. **canonical phase 名 vs 現行 brain 表**：本手冊操作步驟一律用 **5 幕 canonical 名**：
   `s1_nav / s2_greet / s3_pose_object / s4_gesture / s5_safety`。
   **但 brain 端現行 `interaction_state.PHASE_ALLOWED_KINDS`（`interaction_executive/interaction_executive/interaction_state.py:33`）今天只有**：
   ```python
   {"all", "s2_face", "s3_object", "s4_gesture", "quiet"}
   ```
   也就是說 **`s1_nav` / `s2_greet` / `s3_pose_object` / `s5_safety` 這四個 canonical 名目前 brain 還沒收進表**（由 plan2 平行新增）。在 plan2 合進之前，`ros2 param set /brain_node demo_phase s2_greet` 會被 brain 以「unknown demo_phase — keep 舊值」拒絕（`brain_node.py:311-320`）。**現行等效對照（plan2 合進前的 backup 用）**：
   | canonical（手冊/Studio 鈕） | brain 現行等效 param | 語義 |
   |---|---|---|
   | `s2_greet` | `s2_face` | 只放行 greet |
   | `s3_pose_object` | `s3_object` | 只放行 object |
   | `s4_gesture` | `s4_gesture` | 只放行 gesture（已存在） |
   | `s1_nav` / `s5_safety` | （現行無，退 `all`） | nav/safety 段沒有專屬 scene-mask |
   > **Studio 隱藏五幕鈕**（gateway `/api/demo_phase`）的 server 白名單**已含** canonical 5 名 + 兩 alias，會把 canonical 名照原樣發給 brain；brain 收進表前，操作員若要立刻生效請改用上表的 **brain 現行等效 param**。
2. **`/brain/demo_phase` String subscriber 由 plan2 提供**：Studio 隱藏鈕的 gateway publisher 已就緒並對該 topic 發布；**brain 端 subscriber 在 plan2 合進前不存在** → 現場以 `ros2 param set /brain_node demo_phase <p>` 為準（§4 backup 表）。
3. **`offline_mode` 由 plan3 擁有**：gateway `/api/offline_mode` publisher 結構就緒，但 brain 端如何消費（param vs topic）由 plan3 定。落地前 offline **退「啟動前 env override」**（proven，§5）。
4. **`emergency_stop.py` 真實路徑 = `nav_capability/scripts/emergency_stop.py`**（非 `scripts/`）。`engage` 鎖死所有 cmd_vel（mux priority 255），`release` 解鎖。**禁 Damp(1001)**（會讓移動中 Go2 失控）。

---

## §0　開場安全前置（任一步不過即停）

> 6/13 EOD 即時狀態：Jetson nav stack 仍在跑（tmux `nav-cap-demo`，9 windows）；剛發生 goto_relative 0.3m 走歪撞牆、Roy e-stop；D435 Right MIPI / Hardware Error；nav stack 與 brain demo stack **8GB 互斥不可同跑**。

1. **確認 Go2 停穩**。若仍在動 → `python3 nav_capability/scripts/emergency_stop.py engage`（**禁 Damp(1001)**）；停穩後 `python3 nav_capability/scripts/emergency_stop.py release`。
2. **清掉前一個 stack**：`pawai demo stop`；殘留 → `pawai demo stop --force`，再逐一：
   ```bash
   pkill -9 go2_driver; pkill -9 reactive_stop; pkill -9 nav2; pkill -9 robot_state; pkill -9 sllidar; pkill -9 pointcloud; pkill -9 joy_node; pkill -9 twist_mux
   ```
   （`killall python3` 只殺 launch parent，C++ 子 process 會殘留搶 WebRTC/topic。）`tmux ls` 確認 `nav-cap-demo` **不在**。
3. **清 orphaned active goal**（若剛跑過 nav）：重啟 navcap launch 清除（single-goal server 會留 orphan，後續 goto 全被拒）。**本 demo 不跑 goto_relative**，此步只在你剛中斷過 nav 時做。
4. **8GB stack 交接決策**（依 plan1 co-run profiling，見 §0 末「8GB 交接決策樹」）：決定 S1（nav 段）與 S2–S5（brain 段）是分段切換還是常駐。**plan1 結果未出前一律走保守路徑：分段切換**。
5. **D435 健康**：`ros2 topic hz /camera/camera/color/image_raw`（無輸出 / MIPI error → 重插 USB 換 port）。**nav 不需 D435；S2/S3 face/pose/object 需要**。
6. **e-stop 就位**：確認 `nav_capability/scripts/emergency_stop.py` 可一鍵 engage（操作員手指放 Enter）。
7. **demo mode 決策**：線上模式直接起；offline 用**啟動前 env override**（§5），CLI `pawai demo mode` 為 **PLANNED**（不可用）。
8. **`pawai demo start` 後不要只信 CLI `✓ Demo running`**（假成功有前科）：
   ```bash
   tmux ls            # 確認 session 真的在
   ros2 node list     # 數 node（brain_node / tts / asr / 5 perception 該在）
   ```
9. **拔 6/9 卡死真兇 + 鎖幕**：
   ```bash
   ros2 param set /brain_node stranger_alert_enabled false
   ros2 param get /brain_node demo_phase    # 應為 all（開場全開）
   ```

### `.env` CRLF false-positive 檢查（6/4 教訓，必做）

`.env` 若是 Windows CRLF → `start_full_demo_tmux.sh` 的 `source .env` 撞 `$'\r'` + `set -euo pipefail` **整腳本靜默 abort、tmux session 從沒建起**，但 `pawai demo start` 仍回 `✓ Demo running`（假成功）。開場必跑：
```bash
ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"
# 若 Jetson 只有 .env.local（真 keys）：cp .env.local .env
```
起 demo 後**務必** `tmux ls` + `ros2 node list` 數 node，不要只信 CLI。

### 8GB 交接決策樹（P4-13，TEMPLATE — 待 plan1 profiling）

> **S1 stack layout: TBD — pending plan1 profiling**（plan1 擁有 P0 no-motion co-run gate，config A/B/C）。本手冊**只消費** plan1 結論，不自行 profiling。

```
plan1 co-run profiling 結果：
├─ config C 穩（nav + brain 同 8GB 可共存）
│     → S1 免 swap；S1 仍【不用 goto_relative】，map/LiDAR/pose 當「視覺證據」展示
├─ config B 穩、C 不穩
│     → brain 常駐 + 另開 raw LiDAR / Foxglove；S1 由操作員輔助（遙控）
├─ config B 不穩
│     → S1 純第三人稱（人帶 Go2 / 影片）+ Studio brain；不談 nav stack
└─ brain baseline 都不穩
      → 先修 brain demo，本場不談 nav

【plan1 結果未出前的預設】= 保守路徑：
  S1 nav 段與 S2–S5 brain 段【分段切換】（中間約 1 分鐘 stack 交接空檔，
  操作員口頭過場 + Studio 展示前段 trace 證據填補，不讓觀眾以為當機）。
```

---

## §1　五幕六欄 SOP

> 切 phase 用 **Studio 隱藏五幕鈕**（FLOOR）；掛了退 `ros2 param set`（§4）。
> 每幕 `max_wait_s` 超時 → 先自動/手動播該幕 canned（never dead air，§5 四階階梯）。
> **三層語音**：Layer1 規則快觸發（0s）｜Layer2 LLM ≤1.5–2s｜Layer3 canned（保底）。

### S1 移動進場（能力：FAILED / NOT_DEMO_READY · max_wait_s ≈ 10–20s）

| 欄 | 內容 |
|---|---|
| 切 phase | Studio 鈕「S1 移動進場」/ backup `ros2 param set /brain_node demo_phase all`（brain 現行無 s1_nav，退 all） |
| 預期 TTS(online) | 無台詞硬依賴；進場由人/遙控帶位 |
| 預期 TTS(offline) | 同上（nav 段不靠 LLM） |
| 驗證點 | **不跑 goto_relative**；若展示 nav 證據 → Foxglove map + `/scan_rplidar` + `/amcl_pose`（唯讀，不送 motion） |
| trace reason | nav 段無 brain trace（純展示）；若誤觸自發社交 → 看 `/brain/trace` suppressed gate |
| rollback | **走歪/撞** → `nav_capability/scripts/emergency_stop.py engage` → `pawai demo stop` → **影片**。S1 退路就是遙控 + Studio 證據 → 影片，**不押自主移動** |

> **S1 講話只能用 nav-618-claim-wording S1 句**：「室內已知地圖、操作員下令的短距自主移動（0.3–0.5m）」+ 標「單點」；**n=3 重驗前禁加「可靠」**。本場若退影片，明說是「先前錄製的移動片段」。

### S2 認人問候（能力：needs-HITL · max_wait_s ≈ 3–5s）

| 欄 | 內容 |
|---|---|
| 切 phase | Studio 鈕「S2 認人問候」/ backup `ros2 param set /brain_node demo_phase s2_face`（現行等效，只放行 greet） |
| 預期 TTS(online) | 具名問候（LLM，≤1.5–2s）。**重現 greet 需遮臉/離框 ~5s 再回來**（只在 unknown→known 進場觸發，§2.1） |
| 預期 TTS(offline) | canned 具名問候句（plan3 §9 五句之一） |
| 驗證點 | `/event/face_identity` identity_stable=true；`/state/perception/face`；Studio chat 出現問候 |
| trace reason | 沒觸發看 `/brain/trace` → `greet_cooldown` / `greet_require_sitting`（§2.1 workaround） |
| rollback | sim<0.7 → 退 generic greet；sitting 不穩 → `ros2 param set /brain_node greet_require_sitting false` |

### S3 姿勢 / 物體（能力：needs-HITL · max_wait_s ≈ 5–8s）

| 欄 | 內容 |
|---|---|
| 切 phase | Studio 鈕「S3 姿勢/物體」/ backup `ros2 param set /brain_node demo_phase s3_object`（現行等效，只放行 object） |
| 預期 TTS(online) | 物體評論（cup 0.7m）/ 姿勢回應（sitting 當 bonus，見 §2.1） |
| 預期 TTS(offline) | canned 物體/姿勢句 |
| 驗證點 | `/event/object_detected`（cup）；`/event/pose_detected`（sitting）；Studio chat |
| trace reason | 物體被別流污染看 dedup；不觸發看 `/brain/trace` |
| rollback | 物體不穩 → 拉近到 0.7m / 重試；姿勢退 bonus（不擋幕） |

### S4 手勢（能力：needs-HITL · max_wait_s ≈ 8–10s · **Go2 會動，e-stop 就位**）

| 欄 | 內容 |
|---|---|
| 切 phase | Studio 鈕「S4 手勢」/ backup `ros2 param set /brain_node demo_phase s4_gesture`（現行已存在） |
| 預期 TTS(online) | confirm 路徑：目標 `thumbs_up→OK→wiggle`（未驗）；退 `peace→OK→WeGo`（HITL#2 驗過） |
| 預期 TTS(offline) | canned 確認句 |
| 驗證點 | `/event/gesture_detected`；PendingConfirm 進 CONFIRM_PENDING；Go2 wiggle |
| trace reason | 誤觸 → `ros2 param set /brain_node gesture_enabled false`（cancel in-flight confirm，`brain_node.py:426-428`） |
| rollback | confirm 黑洞？PendingConfirm 30s timeout 自解（`brain_node.py:186`）；**Go2 走偏 → e-stop** |

> **手勢段必須 `gesture_backend:=recognizer`**（demo 主線啟動腳本已 override；rtmpose backend 不餵 WaveDetector，wave 永不觸發）。

### S5 安全拒絕（能力：**proven** 6/10 · max_wait_s ≈ 3–5s）

| 欄 | 內容 |
|---|---|
| 切 phase | Studio 鈕「S5 安全拒絕」/ backup `ros2 param set /brain_node demo_phase all`（現行無 s5_safety；skill_request **不受 phase 影響**，`brain_node.py:329`） |
| 預期 TTS(online) | SafetyLayer reject 台詞（拒絕「翻跟斗/後空翻/倒立/backflip」等危險動作） |
| 預期 TTS(offline) | canned 安全拒絕句 |
| 驗證點 | 用 Studio **skill_request 或文字輸入**送「翻跟斗」→ brain 兩 plan：say_canned 拒絕 + request_backflip 觸發 SafetyLayer（`brain_node.py:1085-1086`）；Go2 **不執行**危險動作 |
| trace reason | `/brain/trace` SafetyLayer reject reason |
| rollback | 已 proven；異常退 `demo_phase=all` + reset_context |

> **觸發是 explicit input（phase-independent）**：S5 不靠切幕，靠 Studio skill_request / 文字輸入，任何幕都能觸發。

---

## §2　三洞段（face / confirm / nav）+ Gotcha

### §2.1　S2 greet 兩個 Gotcha（必讀）

1. **greet 只在 unknown→known 進場觸發、非 steady-state**（`brain_node._on_face`，6/8 commit `f2a0df4`）。
   - **後果**：auto-advance 進 S2 時 Roy 早已是 known → greet **不會重觸發**。
   - **重現 workaround**：遮臉 / 離框 ~5s 再回來。
   - **缺口歸屬**：「phase-entry-when-known-face-present 觸發」是 **plan2 / Lane1 要處理**的（本手冊只記錄 + 提供操作 workaround，**不改 brain code**）。
2. **greet 目前硬依賴 sitting**（commit `f2a0df4`）。Q4 把 sitting 當 bonus → S2 設：
   ```bash
   ros2 param set /brain_node greet_require_sitting false   # face-only 觸發
   ```
   sitting 移到 **S3 當 bonus**，不當 greet 硬閘。

### §2.2　confirm 路徑差異（S4）

- 目標 `thumbs_up→OK→wiggle`（**未驗**） vs HITL#2 **驗過** `peace→OK→WeGo`。
- **現場先試目標、失敗立刻退 peace**。
- PendingConfirm 30s timeout **不黑洞**（`brain_node.py:186` `timeout_s=30.0`，自動 cancel）。
- 誤觸 → `ros2 param set /brain_node gesture_enabled false`（cancel in-flight confirm，`brain_node.py:426-428`）。

### §2.3　face_db 衛生 + `.npz` HITL ls SOP（Gotcha #3）

- **`pawai face delete` / `face rebuild` 目前只刪 `.pkl`**（`tools/pawai_cli/pawai_cli/main.py:2018/2045`），**不刪 `.npz`**。
- **`.npz` 是 Jetson runtime 訓練產物**（`face_perception/face_identity_node.py:75/77` 確認用 `.npz`；**repo 內無此檔**）。
- **HITL 第一步必 `ls /home/jetson/face_db/`** 確認真實 embedding-cache 檔名**後**才定刪除清單。
  - ⚠ **未上機 ls 前不可斷言 `.npz` 一定存在 / 一定叫這名**。
  - workaround（若 ls 證實存在）：`rm -f /home/jetson/face_db/model_sface.npz`。
- **幽靈目錄** `_backup*` / `old*` 會被當人名訓進 centroid 稀釋 → **移到 `face_db` 外**。
- 發表日早上 SOP：`pawai face enroll --person-name roy` → `pawai face rebuild`（刪 pkl）→ 重啟 face node 重訓 → `pawai face test` **sim ≥ 0.7**。
- **CLI 自動刪 `.npz` 歸 Lane 3**（本手冊只給 HITL 手動 SOP）。

### §2.4　nav motion FAILED（引 nav incident plan，不重做）

- 6/13 **goto_relative 0.3m 走歪撞牆**。根因多因（見 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-motion-incident-root-cause-plan.md`）：
  - **T0** `go2.urdf` 把 map→odom / odom→base_link 當 fixed joint 發 `/tf_static`，與 AMCL/driver 雙 authority 衝突（**CO-PRIMARY，先 `ros2 topic echo /tf_static` 排除**）。
  - **R1** AMCL yaw 注入 forward／**R2** 0.5m→1.04m 超衝／**R5** reactive slow-band 沉默 + yaw-blind gate。
- **本 demo 不靠 goto_relative**。live-motion 僅在 nav incident plan 的 **T0 fix + D1–D5 綠 + θ_error<5° + e-stop + n=3** 全過後才用 **DriveOnHeading（body-frame）**；否則 **S1 退遙控 + Studio 證據 → 影片**。
- **禁講 F1–F10**（自由巡邏 / 動態繞障 / D435 已融合 / auto-resume / 即時恢復 ...）。

---

## §3　操作員角色分工

> 人選由 Roy 拍板（needs_roy）。每角色列「手上工具 / 觸發時機 / 失速補位」。

| 角色 | 手上工具 | 觸發時機 | 失速補位 |
|---|---|---|---|
| **Driver（Roy）** | Go2 遙控器 / `emergency_stop.py` / Foxglove `/initialpose` | S1 帶位移動進場；S4 手勢 confirm 觸發；任何時刻 e-stop | 走偏立即 e-stop → 退影片 |
| **Trace Watcher** | Studio Evidence Center + `/state/brain` chip + **Studio 隱藏五幕鈕** | 盯 phase；串台時按隱藏鈕切回正確幕、必要時按 reset_context | chip 顯示 `?` 時改 `ros2 param get /brain_node demo_phase` 確認 |
| **S5 Trigger** | Studio **skill_request / 文字輸入** | S5 段送「翻跟斗/backflip」觸發 SafetyLayer reject（explicit input，phase-independent） | 文字輸入掛 → 改 `ros2 topic pub /brain/skill_request` |

- **never dead air 鐵律**：若操作員在某幕 `max_wait_s` 內**沒按鈕**，Trace-Watcher / S5-Trigger 須**立即用 Studio skill_request / 文字輸入觸發該幕 canned**，或退 `ros2 param set`——**不可乾等操作員**。
- **8GB stack 交接過場**：交接約 1 分鐘空檔，由 **Trace Watcher 口頭過場** + Studio 展示前段 trace 證據填補（決策依 plan1，§0 末）。

---

## §4　控制清單 + `ros2 param set` backup + 平台表

### Studio 隱藏鈕 ↔ `ros2 param set` 等價備援（rollback 階梯第三階）

| 動作 | Studio 隱藏鈕（FLOOR） | `ros2 param set` backup（SSH 上 Jetson） |
|---|---|---|
| 切幕 | 「S1/S2/S3/S4/S5」五幕鈕 | `ros2 param set /brain_node demo_phase <s1_nav\|s2_greet\|s3_pose_object\|s4_gesture\|s5_safety\|all\|quiet>`（**brain 收進表前用 §「重要契約備註」對照表的現行等效名**） |
| offline | 「離線」toggle | plan3 定義（param 或 topic）；**落地前退啟動前 env override**（§5） |
| 清場 | reset 按鈕 | `ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}` |
| 看 phase | phase chip（P1，可能顯 `?`） | `ros2 param get /brain_node demo_phase` |

### PLANNED CLI（**未上線，照同列 backup，不可照不存在的指令打**）

| PLANNED CLI | 狀態 | backup（現在就用這個） |
|---|---|---|
| `pawai demo phase <p>` | **PLANNED — Lane 3 / post-6/18** | `ros2 param set /brain_node demo_phase <p>`（SSH 上 Jetson） |
| `pawai demo mode offline` | **PLANNED — Lane 3 / post-6/18** | `ros2 param set /brain_node offline_mode true`（plan3 落地後）**或**啟動前 env override（§5，proven） |
| `pawai status` brain 區塊 | **PLANNED — Lane 3 / post-6/18** | `ros2 param get /brain_node demo_phase` |
| `pawai face delete` 刪 `.npz` | **PLANNED — Lane 3**（現只刪 `.pkl`） | HITL 手動 `ls /home/jetson/face_db/` → `rm -f .../model_sface.npz`（§2.3） |

> 既存可用 CLI（驗存在）：`pawai demo --help`、`pawai face --help`、`pawai status --help`、`pawai demo start/stop`、`pawai smoke`、`pawai evidence pull`。

### 平台支援表

| 工具 | Win PowerShell | WSL | macOS | Jetson |
|---|:--:|:--:|:--:|:--:|
| `pawai`（SSH wrapper） | 脆（CRLF / 引號 / rsync） | ✅ | ✅ | ✅ |
| `ros2 param set/get` / `ros2 action` / `ros2 topic pub` | ❌（無 ROS2 runtime） | ❌（無 ROS2 runtime） | ❌ | ✅ |
| Studio UI（瀏覽器） | ✅ | ✅ | ✅ | ✅ |

> **結論**：操作主控台用 **WSL 或 macOS**；所有 ROS2 runtime / Go2 / 感知一律 **SSH 上 Jetson**。

---

## §5　四階 rollback 階梯 + 誠實底線 + 8GB 交接

### 四階 rollback 階梯（Q6）+ 每階 timeout + 邊界 canned 補位（never dead air）

| 階 | 動作 | timeout（退下一階） | never-dead-air |
|---|---|---|---|
| ① auto-advance | plan-conductor 自動推進（per-phase flag） | 該幕 `max_wait_s`（S1 10–20 / S2 3–5 / S3 5–8 / S4 8–10 / S5 3–5s） | stall 超時 → **先自動播該幕 canned**（rule-based 0s）→ 退 ② |
| ② **Studio 隱藏五幕鈕**（本手冊 FLOOR） | 操作員手動切幕 | 按鈕後**無 200 OK > 3s**（Studio 不通）→ 退 ③ | **若 `max_wait_s` 內沒人按 → Trace-Watcher 立即 Studio skill_request / 文字觸發該幕 canned，不乾等** |
| ③ `ros2 param set /brain_node demo_phase <phase>` | SSH backup | param set **無 ack > 2s** → 退 ④ | 同時 `ros2 topic pub /brain/skill_request` 補 canned |
| ④ `demo_phase=all` + **影片** | 最終保底 | — | 影片永遠在手邊 |

> **6/18 永不押在 auto-advance。** 操作員角色卡（§3）標明誰計時、誰觸發 canned、誰按下一階。

### 全域 / 分項退路

- **全域退保守**：`ros2 param set /brain_node demo_phase all` + `ros2 param set /brain_node ism_enabled false`（byte-identical，plan2 保證）。
- **TTS 退**：`TTS_PROVIDER=piper` 重起 / offline mode / canned。
- **手勢退**：`ros2 param set /brain_node gesture_enabled false`。
- **stranger 退**：`ros2 param set /brain_node stranger_alert_enabled false`。
- **換幕殘留退**：`ros2 topic pub --once /brain/reset_context std_msgs/msg/Empty {}`。
- **nav 退**：`nav_capability/scripts/emergency_stop.py engage` → `pawai demo stop` → 影片。
- **face 退**：sim<0.7 → generic greet / 還原 backup。
- **Studio 掛**：`ros2 param get /brain_node demo_phase` + `pawai evidence pull` 看 trace。
- **offline 退（proven）**：啟動前 env override
  ```bash
  LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper \
    ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' \
    bash scripts/start_full_demo_tmux.sh
  ```
- **整 stack 退**：`pawai demo stop --force` + 逐一 `pkill -9 go2_driver; pkill -9 reactive_stop; ...`（§0 步驟 2）。

> 每個 rollback 都往**現行已驗行為**退，不引入新行為。

### 8GB stack 交接觀眾感知

S1（nav 段）與 S2–S5（brain 段）有 stack 交接約 1 分鐘空檔 → **操作員口頭過場 + Studio 展示前段 trace 證據**填補，不讓觀眾以為當機。交接決策依 **plan1 co-run profiling**（§0 末決策樹，TBD pending plan1）。

### 誠實底線（再強調）

- AFK 完成只說「merged + 單測綠（needs-HITL）」；**proven** 須 Roy 在場真機過。
- 對外 claim 全走 nav-618-claim-wording **S1–S8**；禁 **F1–F10** overclaim。
- **S1 標 FAILED / NOT_DEMO_READY**；本場 nav 退影片時明說是預錄片段。

---

## §6　P4-11 Dry-run review（發表日前 48h）

> 找一位**沒參與**的人照 §0–§5 唸一遍，標所有「照不下去 / 指令不存在 / 平台跑不了」的步驟，逐條修。

Dry-run checklist：
- [ ] §0 開場每步指令都能在指定平台跑（`emergency_stop.py` 路徑正確 = `nav_capability/scripts/`）。
- [ ] §1 五幕「切 phase」欄的 backup param 名與 §「重要契約備註」對照表一致（brain 現行只認 `all/s2_face/s3_object/s4_gesture/quiet`）。
- [ ] §4 PLANNED CLI 全部標 PLANNED 且同列有 backup（沒有人會照不存在的指令打）。
- [ ] §4 平台表「ros2 在 Win/WSL/mac 不可」這條被照唸的人理解。
- [ ] §5 四階階梯每階 timeout 數值清楚、never-dead-air 補位人明確。
- [ ] 全文無 F1–F10 禁講句；S1 標 FAILED。
- [ ] `.npz` 段要求**先 ls 再刪**，沒有未上機就斷言檔名。

**Dry-run 結果**（執行後填）：
- 執行日期：____　執行人（非參與者）：____
- 找到的 blocker：____（逐條 + 修法）
- 全部 blocker 已修：☐

---

## §7　P4-12 HITL 五幕全流程 + 控制面真機驗（Roy 在場，needs-HITL → proven 唯一閘）

> **先確認 Go2 停穩 + nav/brain 不同跑（8GB 互斥）後才開**（§0）。S1/S4 段 **Go2 會動，e-stop 就位**。

驗收項：
1. Studio 隱藏五幕鈕真機切 phase → `/state/brain` chip + trace suppress 集合符合 §1。
2. 每幕只觸發該幕功能、不串台。
3. 隱藏鈕「先 reset 再切」真機驗（換幕不污染）。
4. offline toggle 真機切（USB 喇叭非 Megaphone，風險低）— 無 silent fail。
5. S2 greet 進場觸發 + `greet_require_sitting=false` workaround。
6. S4 confirm 目標 vs peace 路徑（**Go2 會動，e-stop**）。
7. face re-enroll **sim ≥ 0.7**（含 `.npz` ls）。
8. S5 SafetyLayer reject 端到端（proven 復驗）。

驗收命令：
```bash
pawai smoke full              # 單測綠 = needs-HITL
pawai smoke nav --static      # 零 motion wiring
pawai face test               # sim ≥ 0.7
pawai evidence pull           # grep trace reason
```

**HITL 紀錄**（每幕填）：日期 / 是否串台 / sim 值 / 是否 silent fail / S1/S4 是否有 e-stop 介入 / 錄影（offline canned 出聲、S5 reject 端到端）。

任一幕失控 → `demo_phase=all` + 影片；Go2 走歪/撞 → `emergency_stop.py engage` + `pawai demo stop`。
