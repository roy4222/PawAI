# 6/9 下午 視覺 Phase 2 HITL 執行計畫 Implementation Plan

> **For agentic workers:** 多數 task 是**硬體 HITL（Roy 在 Jetson + Go2 + 相機前手動執行）**，不是 subagent 可代跑的 code。照表 top-to-bottom 跑，每個 Task 勾 checkbox。完整可貼指令 + 深度陷阱解釋見**姊妹 playbook**：`docs/pawai-brain/research/2026-06-09-afternoon-vision-playbook.md`。

**Goal:** 用實機 HITL 把視覺各能力（object / cup / 防幻覺 / sitting / greet / gesture / Studio 證據 / safety / under-load）量化，**當天定出 demo 主秀物體 + 2 備援 + 每項台詞與降級方案**。

**Architecture:** 清 nav stack → 起 brain/demo + Studio（8GB 與 nav 互斥）→ 第一優先 object 矩陣（最大缺口）→ cup 專項 → 防幻覺 → sitting/greet → gesture → Studio 證據 → safety → under-load。每測一項就填 CSV / scoreboard，沒過就降級、鎖 fallback 台詞。

**Tech Stack:** ROS2 Humble / object_perception (YOLO26n TRT) / interaction_executive brain_node / vision_perception (pose+gesture) / face_perception / pawai-studio gateway+frontend / `scripts/obj_matrix_cap.py` + `benchmarks/core/object_matrix.py`。

**真相來源：** playbook（精確指令）`docs/pawai-brain/research/2026-06-09-afternoon-vision-playbook.md`；策略研究 `docs/pawai-brain/research/2026-06-09-nav-vision-execution-research.md` §3-§6；今日 HITL Log `docs/superpowers/plans/2026-06-09-nav-vision-hitl-execution.md`。

**誠實底線：** object/sitting 目前都是窄版/未量化。本計畫目的是**量出真實數字 + 鎖誠實台詞**，不是預設它們會過。

---

## ⚠️ 開跑前硬規則

- **nav 與 brain 8GB 互斥** → 先 `pawai demo stop` 清 nav，再起 brain。不要兩套同跑。
- **object event 每類 5s cooldown** → `obj_matrix_cap.py` 必用 `--window 6`（預設 3 會漏數、把真偵測誤記 miss）。
- **`greet_require_sitting` runtime `param set` 是 no-op**（init-cached）→ 要關 sitting gate 必須**重啟 brain 帶 `-p`**。
- pose 是 **edge-emit only**：echo `/event/pose_detected`，**沒有** `/state/perception/pose`。
- 不在 full stack 跑 `test_mux_priority.py`（會讓 Go2 衝出）；不 mid-session 重啟 `tts_node`（Megaphone silent fail）。

---

## Task 0: 清 nav stack + 起 brain/demo + Studio

- [ ] **Step 1: 清 nav stack**

Run: `pawai demo stop`
Expected: nav lane cleanup（依 lock lane 路由）；`tmux ls`（Jetson）無 `nav-cap-demo`。

- [ ] **Step 2: 一鍵起 full demo（5 perception + brain + Studio）**

Run: `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`
Expected: Jetson tmux `demo` 起；本機 frontend `http://localhost:3000/studio`。需 env `JETSON_TAILSCALE_IP`；沒設改 `pawai demo start`。

- [ ] **Step 3: healthcheck（等 ~30s）**

Run: `bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh`
Expected: 8 項全綠（conv_graph ready / openrouter on / persona 6 files / `/brain/chat_candidate` pub≥1 / `/tts` pub / `tts_node` 在 / gateway `/health` ok / frontend 200）。

- [ ] **Step 4: 確認 6 條主線 topic 都有 publisher**

Run:
```bash
ros2 topic info /event/object_detected
ros2 topic info /event/pose_detected
ros2 topic info /event/gesture_detected
ros2 topic info /state/perception/face
ros2 topic info /brain/skill_result
ros2 topic info /tts
```
Expected: 每條 `Publisher count: ≥ 1`。任一 0 → 看 tmux pane，**不要只信 `✓ Demo running`**（CRLF 假成功前科）。補核：`ros2 node list`（含 brain_node/object_perception_node/vision_perception_node/face_identity_node/tts_node）。

**Acceptance（0）：** 6 topic 全有 publisher、healthcheck 8 綠、frontend 開得起。

---

## Task 1: Object 矩陣（第一優先 — 今天最大缺口）

**Files:** `scripts/obj_matrix_cap.py`（量測）→ `artifacts/object_matrix/object_matrix.csv`（輸出）

- [ ] **Step 1: 設 household 白名單 + 確認 conf 閾值**

Run:
```bash
ros2 param set /object_perception_node class_whitelist "[39, 41, 45, 56, 63, 67, 73]"
ros2 param get /object_perception_node confidence_threshold
```
Expected: whitelist set 成功（39=bottle 41=cup 45=bowl 56=chair 63=laptop 67=phone 73=book；>1 元素 → 自動 INTEGER_ARRAY）。`confidence_threshold` 應是 **0.35**（yaml）；若回 `0.5`（launch 預設）→ cup 會偏 FAIL，先設法用 0.35 重啟 node 再量 cup。

- [ ] **Step 2: 跑 chair → laptop → cup × 0.7/1.0/1.5m × normal（每格 5 trial，window 6）**

Run（每格一條；互動模式每 trial 按 Enter 前**停 >5s**；無人值守加 `--auto --gap 6`）:
```bash
python3 scripts/obj_matrix_cap.py --object chair  --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup    --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup    --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup    --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
```
Expected: 每格印 `CELL: PASS|DEGRADED|FAIL success=x/5 rate=... avg_conf=...`，append `artifacts/object_matrix/object_matrix.csv`。
> ⚠️ false positive 太多 → 切單類對照：`ros2 param set /object_perception_node class_whitelist "[56]"`（chair）/ `"[63]"`（laptop）/ `"[41]"`（cup）。

- [ ] **Step 3: backlit 加 3 格（chair 1.0 / laptop 1.0 / cup 0.7）**

Run:
```bash
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.0 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup    --distance 0.7 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
```

- [ ] **Step 4: 定主秀物體 + 2 備援**

判定（CSV `verdict`/`low_conf` 欄）：`success_rate ≥0.8`(4/5)=**PASS** 主秀候選 / `≥0.6`(3/5)=**DEGRADED** 備援 / `<0.6`=**FAIL** 不上台。**`avg_confidence <0.45` → low_conf 旗標，即使 PASS 也不當頭牌**。
Record: primary（normal 三距離 success_rate 最高且非 low_conf）+ 2 backup。預期 chair primary、cup 多半只 backup。

**Acceptance（1）：** object_matrix.csv 有 chair/laptop/cup × 0.7/1.0/1.5 × normal + 3 backlit；**主秀物體 + 2 備援已定**。

---

## Task 2: Cup 專項（有時間才做；決定 cup 能否當備援）

- [ ] **Step 1: cup × light 三變數（0.7m）**

Run:
```bash
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light normal  --trials 5 --window 6 --notes "front-light plain mid-V bg" --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light dim     --trials 5 --window 6 --notes "dim handheld" --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light backlit --trials 5 --window 6 --notes "window behind" --out artifacts/object_matrix/object_matrix.csv
```

- [ ] **Step 2: 手動補記（obj_matrix_cap 不存 debug image/lux/raw）**

Record（抄進 `--notes` 或筆記）：實際光源/lux、背景顏色與雜亂度、cup 真實顏色 vs CSV 顏色欄。若顏色欄回 `Unknown`/`black`（cup 其實亮色）= 光太暗的可見症狀（HSV V<50 強判 black）。

**Acceptance（2）：** cup 降級決策有數據。cup normal <0.8 或 low_conf → **降 backup**，台詞限「近距桌上水杯」、**不講** 2m/地上/掉落/絆倒。fallback 台詞（顏色不可靠）：「我看到桌上有杯子了，你要喝水嗎？」（**不帶顏色**）。

---

## Task 3: Object → Brain 防幻覺

- [ ] **Step 1: ENGAGED 狀態放物體 + 放人/丟地上**

Run（背景開著）: `ros2 topic echo /event/object_detected`
動作：人停在狗附近（ENGAGED）放杯子 → brain 應只說「看到…杯子了，你要喝水嗎？」；拿出一個人 / 往地上丟東西 → brain 應**保持沉默**。
Record: brain plan/trace。

**Acceptance（3）：** brain **不出現**任何含「人 / 掉了 / 在地上」的 object_remark；同類 60s 內只講一次（dedup 60s，key=class_name，person 在 build_object_tts 被 filter）。出現異常 = 記 bug。

---

## Task 4: Sitting 可靠度 + greet

- [ ] **Step 1: sitting 可靠度（站/坐/站 10-20 組）**

Run: `ros2 topic echo /event/pose_detected`（pose 是 edge-emit，沒有 state topic）
做法：擺真實 sitting，數 10-20 次 emit 中 `pose != "sitting"` 佔比；`confidence` = label 在 20-frame 窗占比（非模型機率），<0.5 = buffer 不穩。交叉看 brain console 每 ~1s 印的 `pose: raw=... vote=...`。
Record: misjudge 比例。

- [ ] **Step 2: misjudge >10% → 關 sitting gate（須重啟 brain）**

Run（runtime `param set` 是 no-op，必須重啟帶參數）:
```bash
# 重啟 brain_node 帶 -p greet_require_sitting:=false（改 start 腳本或單獨重啟 brain pane）
ros2 run interaction_executive brain_node --ros-args -p greet_require_sitting:=false   # 視實際 launch 方式調整
```
fallback 台詞（不宣稱姿勢）：「Roy，歡迎回來，我看到你了」（去掉「坐下來了/坐著」）。

- [ ] **Step 3: greet smoke**

做法：遮臉/離框 ~5s 清掉 stable → 回框 → face 轉 stable 後應 emit `greet_known_person` + TTS。
Expected: 進場觸發一次，20s cooldown 內不重複（steady-state 不觸發 = 正常）。

**Acceptance（4）：** sitting misjudge 數字出來；greet 台詞鎖定（穩→可講坐；不穩→重啟關 gate + 去掉坐姿台詞）；greet smoke 實機講出「roy，歡迎回來…」。

---

## Task 5: Gesture thumbs_up（只測這個）

- [ ] **Step 1: idle 30s 零誤觸 + 正觸**

Run: `ros2 topic echo /event/gesture_detected`（idle 應完全靜默）
做法：idle 30s 數誤觸（必須=0）；比 thumbs_up → brain 應回「收到，謝謝你！」（demo-ack，不引 wiggle / 不要 OK 確認）。
> demo-ack 模式：`ros2 param set /brain_node thumbs_up_demo_ack true`（runtime 可能同 init-cache 陷阱，建議 launch `-p`）。dedup `dedup_window_s=1.0` 防連發。

**Acceptance（5）：** idle 30s thumbs_up plan = **0**；thumbs_up 可動、只簡單回應。台詞只講「靜態手勢」，**不可洗白失敗的 wave**（recall=0）。

---

## Task 6: Studio 證據截圖

- [ ] **Step 1: 確認 gateway 是真 node（非 mock）**

Run: `curl -s http://localhost:8080/health`
Expected: `"node":true`、subscriptions 列 10 條；gateway boot log 印「subscribed to 10 String topics + /tts + 2 capability Bool topics」（mock_server 不印這行）。

- [ ] **Step 2: 一張截圖同框 4 感知 chip + brain trace + tts**

跑一輪互動，截圖含：face(`/state/perception/face`) + gesture/pose(`/event/gesture_detected`或`/event/pose_detected`) + speech(`/event/speech_intent_recognized`) + object(`/event/object_detected`) + brain trace(`/brain/conversation_trace`+`/brain/skill_result`+`/state/pawai_brain`) + tts(`/tts` 氣泡)。
> object chip 空 → 放近 chair/laptop/cup 並確認 whitelist。**不可宣稱** LED pass/fail chip wall（前端無 `/api/scoreboard`）。

**Acceptance（6）：** 一張截圖同框完整證據鏈 + boot log 那行 = live 非 mock。

---

## Task 7: Safety refusal（6/18 強亮點，不可被矩陣擠掉）

- [ ] **Step 1: 「請翻跟斗」×3**

Run（背景兩個 echo）:
```bash
ros2 topic echo /brain/skill_result    # 期望 status="blocked_by_safety" detail="banned_api:1301" selected_skill="request_backflip"
ros2 topic echo /webrtc_req            # 全程「不可」出現 api_id: 1301
```
對狗說「請翻跟斗」連 3 次。
Record: 3 次是否全 blocked、`/webrtc_req` 有無 1301、trace 截圖。安全台詞「這個動作不安全，我不能執行。」會照播（正常）。

**Acceptance（7）：** 3/3 `blocked_by_safety`+`banned_api:1301`、`/webrtc_req` 全程**無** 1301、Go2 零移動。任一次 1301 上 `/webrtc_req` = **嚴重不通過，停下查 IE validate**。

---

## Task 8: Under-load 效能

- [ ] **Step 1: face+object+pose/gesture+Studio video 同跑量資源**

Run: `jetson-status` skill 拿快照（RAM/GPU/Temp/Power/models/nodes）+ 手動吞吐：
```bash
ros2 topic hz /perception/object/debug_image    # ~6-8 Hz
ros2 topic hz /face_identity/debug_image         # ~6.6 Hz
```
預算：RAM <5.5GB ok / >6.5 critical；GPU <95% ok；Temp <65 ok / >80 critical；Power <12W ok。

- [ ] **Step 2: 隔離 Studio video-bridge 貢獻**

做法：關掉瀏覽器 video 面板（停 `/ws/video` 訂閱）→ 再量一次 → 差值 = video-bridge 負載（對 3 條 debug image 各 `cv2.imencode` JPEG q70 5fps + WS 廣播）。
Record: 加/不加負載前後 RAM/GPU/Temp/Power + debug_image Hz。

**Acceptance（8）：** 一組 under-load 數字；卡頓**先懷疑 Studio video-bridge**，不要馬上換 YOLO。

---

## 今天不做 + 判定速查表

**今天不做**：換 YOLO / 全測 COCO 80 類 / D435 fusion / Reactive Patrol / DimOS live / 回頭刷短距 goto / auto-resume demo / segmentation / YOLO-pose。

| 項目 | 通過門檻 | 不過怎麼辦 |
|---|---|---|
| **Object** | normal 任一物體 success_rate ≥0.8（4/5）且非 low_conf → primary | 全 <0.8 → 全降 backup，挑最高當開場 |
| **Object cooldown** | `--window ≥6`、`--gap ≥6`、Enter 間隔 >5s | 用了預設 3s → 數據作廢重量 |
| **Sitting** | misjudge ≤10% | >10% → **重啟** brain `-p greet_require_sitting:=false` + 台詞去掉「坐著」 |
| **thumbs_up idle** | idle 30s thumbs_up plan = 0 | >0 → 記環境，調距離/光線重測 |
| **Studio 證據鏈** | 一張截圖含 4 感知 chip + brain trace + tts + boot log「10 String + /tts + 2 Bool」 | 缺 boot log 行 → 看的是 mock_server，重起真 gateway |
| **Safety** | 「請翻跟斗」×3 全 `blocked_by_safety`+`banned_api:1301`、`/webrtc_req` 無 1301 | 任一次 1301 上 `/webrtc_req` = 嚴重不通過，停下查 IE validate |

**收尾（Phase 2 跑完）**：把 object 主秀/備援、sitting/greet 台詞、cup 降級、safety 結果寫回 `references/project-status.md` + demo flow 台詞鎖定，再 `/update-docs` commit。

---

## Self-Review（對照下午需求）

- ✅ stack bringup（0）、object 矩陣（1，含 cooldown gotcha + conf 0.35 check + 主秀決策）、cup 專項（2）、防幻覺（3）、sitting+greet（4，含 runtime no-op → 重啟）、gesture（5）、Studio 證據（6）、safety（7）、under-load（8）— 涵蓋使用者鎖定的下午全序。
- ✅ 每 Task 有 exact 指令 + acceptance gate + fallback 台詞。
- ✅ 關鍵陷阱內嵌：object 5s cooldown(window 6)、conf 0.35 vs 0.5、greet_require_sitting init-cached(重啟)、pose edge-emit-only、Studio boot-log、safety 1301。
- 註：全為硬體 HITL（Roy 執行），無 subagent code task。完整可貼指令見姊妹 playbook。
