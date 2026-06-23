# 6/9 下午 視覺 MVP（cup-focused）HITL 執行計畫 Implementation Plan

> **For agentic workers:** 硬體 HITL（Roy 在 Jetson + 相機 + Go2 前手動跑）。照表 top-to-bottom，勾 checkbox。完整可貼指令 + 深度陷阱見姊妹 playbook：`docs/archive/pawai-brain-legacy/research/2026-06-09-afternoon-vision-playbook.md`。
> **⚠️ 2026-06-09 砍版**：本版**只主測 cup**。中午寫的完整 chair/laptop/cup 矩陣**已廢棄**（太大、浪費注意力）。chair/laptop 只在 cup 失敗時做保底 sanity。

**Goal:** 用最少時間量出「**cup 能多遠辨識得到 + 什麼光線/背景穩**」，定出 demo cup 距離與 fallback；其餘 face/sitting/gesture/safety 只 smoke 確認，不重測。

**Architecture:** 清 nav → 起 brain/demo+Studio → **先確認 RGB/object pipeline 活著** → cup-only `[41]` 距離掃 0.7/1.0/1.5/2.0m + 光線 → 定 cup demo 距離 → cup 不穩才用「好杯子+好光+好背景」救（**不換模型**）→ chair/laptop 保底 sanity（只在 cup 失敗時）→ face/sitting/gesture/safety smoke → Studio evidence。

**Tech Stack:** ROS2 Humble / object_perception (YOLO26n TRT, input_size=640) / `scripts/obj_matrix_cap.py` / interaction_executive brain_node / vision_perception / face_perception / pawai-studio。

**真相來源：** playbook `docs/archive/pawai-brain-legacy/research/2026-06-09-afternoon-vision-playbook.md`；YOLO/像素物理 `docs/archive/pawai-brain-legacy/research/2026-06-09-nav-vision-execution-research.md` §5/§9 + `2026-06-04-pinto-model-zoo-full-analysis.md`。

---

## ⚠️ 開跑前硬規則

- **nav 與 brain 8GB 互斥** → 先 `pawai demo stop` 清 nav 再起 brain。
- **object event 每類 5s cooldown** → `obj_matrix_cap.py` 必用 `--window 6`、每 trial 間隔 **>5s**（預設 3 會把真偵測記成 miss、數據作廢）。
- **今天不換 YOLO**：先用 26n + 好杯子/光/背景。只有 `cup 0.7m & 1.0m normal 都不穩`才開 YOLO26s spike。**不做 segmentation / YOLO-pose / SAHI**。
- **不回導航**（Studio 死頁面等 vision MVP 過了才碰）。

---

## Task 0: 清 nav + 起 brain/demo + **確認 RGB/object pipeline 活著**

- [ ] **Step 1: 清 nav stack**

Run: `pawai demo stop`
Expected: nav lane cleanup；Jetson `tmux ls` 無 `nav-cap-demo`。順手用遙控器把 Go2 移離牆（剛剛卡 0.21m）。

- [ ] **Step 2: 起 brain/demo + Studio**

Run: `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`
等 ~30s → `bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh`（8 項全綠）。frontend `http://localhost:3000/studio`。

- [ ] **Step 3: 確認 RGB/object pipeline 真的活（先做，免得白測）**

Run:
```bash
ros2 topic hz /perception/object/debug_image      # 應 ~6-8 Hz（有畫面）
ros2 topic echo /event/object_detected --once     # 放個物體在鏡頭前，應有 JSON
ros2 param get /object_perception_node confidence_threshold
```
Expected: debug_image ~6-8 Hz、event 有資料、`confidence_threshold` = **0.35**。
> ⚠️ **`confidence_threshold` 不是 runtime param**：`_on_param_changed`（line 247-258）**只處理 `class_whitelist`**，detect 迴圈讀 init 時快取的 `self.conf_thresh`（line 178）。`ros2 param set confidence_threshold 0.35` 會**回 success 但實際無效 → 數據作廢**。→ 若 `confidence_threshold` 回 `0.5`：**必須重啟 object_perception_node 讓 yaml/launch 的 0.35 生效**（**不要** param set）。`class_whitelist "[41]"` runtime set **可以**用（callback 有處理）。

**Acceptance（0）：** object debug_image 有畫面、`/event/object_detected` 有事件、conf=0.35。

---

## Task 1: 🥇 Cup 主測「能多遠辨識得到」

- [ ] **Step 1: 切 cup-only**

Run: `ros2 param set /object_perception_node class_whitelist "[41]"`
Expected: set 成功（41=cup，單元素 runtime callback OK）。

- [ ] **Step 2: cup × 距離 × 光線（每格 5 trial，window 6，間隔>5s）**

Run（normal 4 距離 + backlit/dim 各近 2 格）:
```bash
# normal: 0.7 / 1.0 / 1.5 / 2.0m
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light normal  --trials 5 --window 6 --notes "size?/color?/bg?" --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light normal  --trials 5 --window 6 --notes "..." --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.5 --light normal  --trials 5 --window 6 --notes "..." --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 2.0 --light normal  --trials 5 --window 6 --notes "..." --out artifacts/object_matrix/cup_matrix.csv
# backlit: 0.7 / 1.0
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/cup_matrix.csv
# dim: 0.7 / 1.0
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light dim     --trials 5 --window 6 --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light dim     --trials 5 --window 6 --out artifacts/object_matrix/cup_matrix.csv
```
> 互動模式每 trial 按 Enter 前停 >5s；無人值守加 `--auto --gap 6`。

- [ ] **Step 3: 3.0m 只做一次快速 sanity（不完整測）**

Run: `python3 scripts/obj_matrix_cap.py --object cup --distance 3.0 --light normal --trials 3 --window 6 --notes "sanity only" --out artifacts/object_matrix/cup_matrix.csv`
> 預期 FAIL（9cm 杯 @3m ≈ 14px，像素物理）。確認「3m 看不到」就好，不糾結。

- [ ] **Step 4: 手動記錄（CSV 不存的）**

每格抄：**杯子大小/顏色、背景顏色與雜亂度、光線、是否反光、實測距離**（CSV 已自動存 success_rate/avg_conf/bbox/misclass）。顏色欄回 `Unknown`/`black`（杯子其實亮色）= 光太暗症狀。

- [ ] **Step 5: 定 cup demo 距離**

判定（CSV `cup_matrix.csv`）：`success_rate ≥0.8`(4/5)=**可用** / `≥0.6`(3/5)=**備援** / `<0.6`=**不主秀**；`avg_conf <0.45` 即使 pass 也不當頭牌。
Record: **demo cup 鎖在哪個距離**（預期 ≤1.0-1.2m 最穩）。fallback 台詞（顏色不可靠）：「我看到桌上有杯子了，你要喝水嗎？」（**不帶顏色**）。

**Acceptance（1）：** `cup_matrix.csv` 有 cup × 0.7/1.0/1.5/2.0(+3.0 sanity) × normal/backlit/dim；**demo cup 距離已定**。

---

## Task 2: Cup 救法（先 post-processing，不換模型）+ YOLO26s spike 條件

- [ ] **Step 1: cup 不穩先試這些（比換模型快又可靠）**

- 換**大、非透明、高對比**杯子（不要小/透明/亮面）。
- 放**桌上**不放地上。
- 背景用**深淺對比明顯**的布/紙（避免低對比、暗背景 → HSV V<50 顏色誤判 black）。
- 光從**側前方**打，不要強逆光。
- demo 距離鎖 **≤1.2m**。

- [ ] **Step 2: YOLO26s spike — 只在這個條件才開**

**觸發條件**：`cup 0.7m & 1.0m normal` 用好杯子/好光/好背景**都還 <0.8**。
否則**不換**。原因（研究結論）：遠距小杯是**像素物理**（9cm@2m≈21-28px 逼近偵測下限），26s 在固定像素幫助有限；唯一物理槓桿是 **input 640→1280**（要 TRT 重匯出 ~3-10min，不是 param flip）。**今天不做 seg/pose/SAHI**。

**Acceptance（2）：** cup 用 post-processing 救過一輪；spike 條件未達 → 不換模型，記 backlog。

---

## Task 3: chair/laptop 保底 sanity（**只在 cup 不穩時**）

- [ ] **Step 1: cup 失敗才跑，各 1.0m × 3 次**

Run（只在 cup demo 距離都 <0.8 時）:
```bash
ros2 param set /object_perception_node class_whitelist "[56, 63]"   # chair+laptop
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.0 --light normal --trials 3 --window 6 --out artifacts/object_matrix/cup_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light normal --trials 3 --window 6 --out artifacts/object_matrix/cup_matrix.csv
```
> 目的只有一個：**確保 demo 有一個能用的物體**，不是研究所有物體。

**Acceptance（3）：** cup 可用 → **跳過本 task**；cup 不可用 → chair 或 laptop 至少一個 ≥2/3 當 demo 物體。

---

## Task 4: face / sitting / gesture / safety — 只 smoke（不重測）

- [ ] **Step 1: face 1 smoke**

做法：遮臉/離框 ~5s 再回框 → 應 emit `greet_known_person` + TTS「roy，歡迎回來…」。sim 明顯掉才 `pawai face enroll/rebuild`。

- [ ] **Step 2: sitting 5 次（不做 10-20）**

Run: `ros2 topic echo /event/pose_detected`（pose 是 edge-emit，無 state topic）。坐 5 次數 `pose=="sitting"` 命中。
判定：**≥4/5 → 台詞保留「我看到你坐下來了」**；<4/5 → 重啟 brain `-p greet_require_sitting:=false`（runtime set 是 no-op）+ 台詞改「Roy，歡迎回來，我看到你了」。

- [ ] **Step 3: gesture 只 thumbs_up（OK 可選）**

Run: `ros2 topic echo /event/gesture_detected`（idle 應靜默）。比 thumbs_up → brain 回「收到，謝謝你！」。idle 30s false-trigger **必須=0**。OK 可當輔助確認，**不穩就丟**。wave/wiggle/多手勢今天不上台。

- [ ] **Step 4: safety 快速 1 次（已驗過，當有了）**

Run（背景 `ros2 topic echo /brain/skill_result`）：對狗說「請翻跟斗」1 次 → 應 `blocked_by_safety`/`banned_api:1301`、`/webrtc_req` 無 1301、Go2 不動。確認一次即可。

**Acceptance（4）：** face 講出問候；sitting 台詞鎖定（坐/不坐版）；thumbs_up 可動 + idle 0 誤觸；safety 1 次 blocked。

---

## Task 5: Studio evidence 截圖

- [ ] **Step 1: 截一張同框圖**

跑一輪互動，截圖含：object(cup) + face + pose + gesture chip + brain trace(`/brain/skill_result`,`/state/pawai_brain`) + tts 氣泡。確認 gateway boot log「subscribed to 10 String topics + /tts + 2 capability Bool」（mock 不印 = 真 live）。

**Acceptance（5）：** 一張截圖同框證據鏈。

---

## 今天不做 + 下一階段

**今天不做**：完整 chair/laptop/cup 矩陣 / 全 COCO / 換 YOLO26s（除非 cup 近距 normal 都不穩）/ segmentation / YOLO-pose / SAHI / D435 fusion / auto-resume / 回導航 / sitting 10-20 大測 / face 重測。

**下一階段（vision MVP 收完才做）**：① 回 nav：**修 Studio 死掉的導航頁面**（改成至少有地圖/移動畫面，讓人看得出 Go2 在移動）② 繼續 nav 避障（物體辨識 + 導航避障是兩個最難項，先收 vision 再回頭）。

**收尾**：cup demo 距離 + fallback 台詞 + sitting 台詞版本 → 寫回 `references/project-status.md`，`/update-docs` commit。

---

## Self-Review

- ✅ 主線只 cup `[41]`（Task 1）；chair/laptop 只保底 sanity（Task 3，cup 失敗才跑）。
- ✅ 距離 0.7/1.0/1.5/2.0m + 3.0 sanity（非 1/2/3 直跳）。
- ✅ 先確認 RGB/object pipeline + conf 0.35（Task 0 Step 3）。
- ✅ cooldown 防誤判：window 6 + 間隔>5s（硬規則 + Task 1）。
- ✅ 不換 YOLO，spike 條件明確（Task 2）；seg/pose/SAHI 排除。
- ✅ face/sitting/gesture/safety 只 smoke（Task 4，sitting 5 次非 10-20）。
- ✅ Studio nav 死頁面 → 下一階段（不在今天）。
