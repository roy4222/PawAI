# PawAI 6/9 下午 視覺 HITL 執行 Playbook

> 對象：6/9 下午跑視覺 HITL 的開發者。**直接複製貼上指令，不要邊想邊做。**
> 每節 = 可貼指令 + 一行判讀 + fallback 台詞（有需要時）。
> 所有結論以 scout 讀到的程式碼/設定為準，不誇大。

---

## 0. Stack bringup

> ⚠️ **nav 與 brain 8GB 互斥**：Jetson 8GB 統一記憶體跑不下兩套。下午跑視覺 = brain lane，**不要同時起 nav/AMCL/cartographer**。

```bash
# 1) 先停舊 lane / demo（依 lock lane 路由 cleanup，只清自己的）
pawai demo stop

# 2) 一鍵起 full demo（5 perception + brain + Studio frontend）
#    start.sh 會自動 cleanup 殘留 tmux（demo|pawai_brain|studio_gw|llm-e2e）再 preflight
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
#    → Jetson tmux session `demo`（start_full_demo_tmux.sh, TTS=openrouter_gemini）
#    → 本機 frontend: http://localhost:3000/studio
#    需要 env JETSON_TAILSCALE_IP；沒設就改走 `pawai demo start`

# 3) 等 ~30s 後跑 healthcheck（8 項）
bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh
```

healthcheck 8 項應全綠：conv_graph ready / `openrouter=on` / persona 6 files / `/brain/chat_candidate` pub≥1 / `/tts` 有 pub / `tts_node` 在 node list / Studio gateway `/health` = `"status":"ok"` / frontend `/studio` 回 200。

**確認六條主線 topic 都有 publisher**（貼下面，每條看 `Publisher count:` ≥ 1）：

```bash
ros2 topic info /event/object_detected
ros2 topic info /event/pose_detected
ros2 topic info /event/gesture_detected
ros2 topic info /state/perception/face
ros2 topic info /brain/skill_result
ros2 topic info /tts
```

判讀：任一條 `Publisher count: 0` → 對應感知/brain 沒起來，回去看 tmux pane，**不要只信 CLI 的 ✓ Demo running**（CRLF/假成功前科）。補一刀核對：

```bash
ros2 node list          # 應含 brain_node, object_perception_node, vision_perception_node, face_identity_node, tts_node
tmux ls                 # 在 Jetson 上跑，確認 session demo 真的在
```

---

## 1. Object matrix（第一優先）

### 1.1 設 whitelist（真實 COCO id）

```bash
# household 7（VIS-1 set；>1 元素 → rclpy 自動推 INTEGER_ARRAY，免 dummy）
ros2 param set /object_perception_node class_whitelist "[39, 41, 45, 56, 63, 67, 73]"
#   39=bottle 41=cup 45=bowl 56=chair 63=laptop 67=cell_phone 73=book

# 單類聚焦（runtime callback，單元素也 OK，免 999 dummy）
ros2 param set /object_perception_node class_whitelist "[56]"   # 只 chair
ros2 param set /object_perception_node class_whitelist "[63]"   # 只 laptop
ros2 param set /object_perception_node class_whitelist "[41]"   # 只 cup

# 先確認 conf 閾值是 0.35（yaml 值，cup 召回靠它）；若是 0.5 cup 會掉更兇
ros2 param get /object_perception_node confidence_threshold
```

判讀：`confidence_threshold` 若回 `0.5`（從 launch 預設起的）→ cup cell 會偏 FAIL，先想辦法用 yaml 值 0.35 重啟 node 再量 cup。

### 1.2 ⚠️ COOLDOWN gotcha（每類 5s）

每類事件 **每 5s 最多一次**（`class_cooldown_sec=5.0`）。harness 視窗若 < 5s 又開在前一次偵測的 cooldown 陰影內，物體在場也會被記成 miss。

- **`--window ≥ 6`**（預設 3.0 比 5s 短，會 under-count，**不要用**）。
- `--auto` 模式 **`--gap ≥ 6`**，下一視窗別開在前次 cooldown 內。
- 互動（Enter）模式：每次 trial 之間**人為停 > 5s** 再按 Enter。

### 1.3 per-cell 指令（chair / laptop / cup × 0.7 / 1.0 / 1.5 m × normal）

```bash
# ---- chair ----
python3 scripts/obj_matrix_cap.py --object chair --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object chair --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object chair --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv

# ---- laptop ----
python3 scripts/obj_matrix_cap.py --object laptop --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv

# ---- cup ----
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.0 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 1.5 --light normal --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv

# ---- backlit 加跑 3 格（chair 1.0 / laptop 1.0 / cup 0.7）----
python3 scripts/obj_matrix_cap.py --object chair  --distance 1.0 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object laptop --distance 1.0 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup    --distance 0.7 --light backlit --trials 5 --window 6 --out artifacts/object_matrix/object_matrix.csv
```

互動模式：每格跑起來後按 Enter 開始每個 trial，每次 Enter 前停 > 5s。要無人值守加 `--auto --gap 6`。

判讀：每跑完一格，腳本印出該格 verdict。

### 1.4 CSV 位置 + 判定門檻

CSV：**`artifacts/object_matrix/object_matrix.csv`**（自動建目錄、首次自動寫 header）。
欄位：`timestamp, object, distance_m, light, angle, trials, success, success_rate, avg_confidence, bbox, misclass, verdict, low_conf, notes`。

| success_rate | verdict |
|---|---|
| ≥ 0.8（5 trial ⇒ ≥4/5） | **PASS**（主秀候選） |
| ≥ 0.6（⇒ 3/5） | **DEGRADED**（備援） |
| < 0.6（⇒ <3/5） | **FAIL**（不上台） |

**caveat：`avg_confidence < 0.45` → `low_conf` 旗標**（與 verdict 正交）。即使 PASS，low_conf=True 就**不要當主秀頭牌**。

**決策**：從 normal 三距離挑 success_rate 最高且非 low_conf 的物體當 **primary**，再挑 **2 個 backup**（次高的 PASS/DEGRADED）。chair 通常最穩 → primary 候選；cup 最弱 → 多半只能 backup。

---

## 2. Cup 專項

cup（id 41）是最 flaky 的格，程式碼層面三個原因：小 bbox 像素少、conf 卡在 0.35–0.5 閾值邊緣、HSV 低 V 顏色誤報（V<50 被強制判 black，蓋過真實色相）。

要變的變數：

```bash
# light：normal / dim / backlit 各跑（dim、backlit 預期 FAIL 或 low_conf）
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light normal  --trials 5 --window 6 --notes "front-light, plain mid-V bg" --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light dim     --trials 5 --window 6 --notes "lux≈? handheld" --out artifacts/object_matrix/object_matrix.csv
python3 scripts/obj_matrix_cap.py --object cup --distance 0.7 --light backlit --trials 5 --window 6 --notes "window behind cup" --out artifacts/object_matrix/object_matrix.csv

# background：避免暗/雜亂背景（低對比 + 拉低 bbox V → 顏色誤判 black）；用素色 mid-V 背景 + 前打光
# distance：0.7 最有機會，1.5 像素預算不足偏 FAIL
```

**手動記錄（obj_matrix_cap 不存 debug image / lux / raw frame）**——這些要自己抄到 `--notes` 或筆記：
- 實際光源/lux 概況、背景顏色與雜亂度、cup 真實顏色 vs CSV `bbox`/顏色欄是否對得上。
- 若顏色欄回 `Unknown` 或 `black`（cup 其實是亮色）→ 就是光線太暗的可見症狀，記下來。

**cup downgrade 規則**：cup normal 跑不到 PASS（<0.8）或 low_conf → **降為 backup，不當主秀**；展示時改用 chair/laptop 開場。

fallback 台詞（cup 顏色不可靠時，避免 brain 喊錯色）：
> 「我看到桌上有杯子了，你要喝水嗎？」（**不要帶顏色**，例如不要說「紅色的杯子」）

---

## 3. Object → Brain 防幻覺

brain 講物體的 dedup：**60s，只用 `class_name` 當 key**（顏色刻意不進 key，因 YOLO 顏色 label 會抖）。person 兩層排除：`build_object_tts` 對 `person` 回 None（不講「看到X色的人」），非白名單類別也靜音。

brain 講物體的 emit gate（全部要過）：`ENGAGED`（人停在狗附近）+ 無 active skill + 無 PENDING confirm + 沒在播 TTS + 過白名單/person filter + 過 60s dedup。

驗證 brain **不會**講 person/掉了/在地上：

```bash
# 看原始感知（可能含 person）
ros2 topic echo /event/object_detected

# 在 ENGAGED 狀態放杯子 → brain 應只說「看到…杯子了，你要喝水嗎？」
# 拿出一個人 / 往地上丟東西 → brain 應「保持沉默」
#   person 在 build_object_tts 被 filter；「掉了/在地上」整個 code 無此模板路徑
```

判讀：模板嚴格固定 `看到{color}的{class_zh}了` + 可選後綴（cup→你要喝水嗎、bottle→喝點水吧、book→在看書啊）。出現任何含「人 / 掉 / 地上」的 say/object_remark plan = 異常，記 bug。

cooldown：同類 60s 內只講一次；要重講同一物體得等過 60s。
> `demo_video_cup_compound` 維持預設 `False`（除非你**故意**要那句「我看到 Roy 坐著拿著杯子，是口渴了嗎？」複合台詞）。

---

## 4. Sitting + greet

### 4.1 sitting 可靠度量法

> pose 是 **edge-emit only**，**沒有** `/state/perception/pose`，只 echo `/event/pose_detected`。

```bash
ros2 topic echo /event/pose_detected
```

做法：擺真實 sitting 姿勢，數 10–20 次 emit 中 `pose != "sitting"`（站/其他）佔比；`confidence` = 該 label 在滾動窗（20 frame）的占比，不是模型機率，<0.5 代表 buffer 不穩。
交叉檢查 brain console 每 ~1s 印的 `pose: raw=... vote=...`：比 `raw`（frame 級）vs `vote`（窗級）看哪裡分歧。

判讀：misjudge 比例 = (非 sitting 的 emit 數 / 總數)。> 10% 就走下面 fallback。

### 4.2 greet 觸發鏈（須全成立）

known face stable（`/event/face_identity` 的 `identity_stable`，identity 非空非 unknown）+ 不忙 + （若 `greet_require_sitting`）最近 `greet_sitting_window_s`(3s) 內看到 sitting + 該人 `greet_cooldown_s`(20s) cooldown 沒在冷卻。**只在進場（unknown→known）觸發**，steady-state 不會。

### 4.3 拿掉 sitting 依賴（runtime）

```bash
ros2 param set /brain_node greet_require_sitting false
```

> ⚠️ **這在 runtime 很可能是 no-op**：`brain_node.py` 沒有 `add_on_set_parameters_callback`，`greet_require_sitting` 在 init 快取進 instance 屬性，`_on_face` 只讀快取值。`ros2 param set` 改了 param store 但**不會刷新快取** → sitting gate 直到 node 重啟才會關。**可靠做法**：重啟 brain 帶 `-p greet_require_sitting:=false`（或改 start 腳本），再重啟 `brain_node`。

fallback 台詞（sitting 不穩、關掉 sitting gate 時，台詞**不要宣稱姿勢**）：
> 「Roy，歡迎回來，我看到你了」（去掉「坐下來了 / 坐著」字眼）

### 4.4 greet smoke

```bash
# 看 brain plan/trace；greet 只在進場觸發一次
# 重現：遮臉 / 離框 ~5s 再回來（清掉 stable 狀態），face 回 stable 後應 emit greet_known_person
```

判讀：回框後 20s cooldown 內只 greet 一次；steady-state 不重複 = 正常。要走 sitting 路徑就在 face 轉 stable 的 3s 內擺 sitting（先用 4.1 確認 sitting 量得到）。

---

## 5. Gesture thumbs_up

> 主線 demo 走 demo-ack 模式（thumbs_up 直接回「收到，謝謝你！」，不引出 wiggle/不要 OK 確認）。

```bash
# demo-ack 模式（建議 launch 時 -p；runtime set 可能同 init-cache 陷阱）
ros2 param set /brain_node thumbs_up_demo_ack true
```

cooldown：demo-ack 路徑是 raw `say_canned`，**沒有 skill cooldown**，靠通用手勢 dedup（`dedup_window_s` 預設 1.0s）防連發。thumbs_up **不在** conversation-gated 集合（wave/fist/index 才被聊天/TTS 擋）。

**idle 30s 零誤觸**驗證：

```bash
ros2 topic echo /event/gesture_detected     # idle 時應「完全沒有事件」
# 同時看 brain plan/trace：idle 30s 內不可出現 reason="gesture:thumbs_up:demo_ack"
```

判讀：vision 端只在 stable vote 變化才 emit；沒人比手勢 → topic 靜默 → `_on_gesture` 不被呼叫 → thumbs_up plan = 0。idle 30s 內出現任何 thumbs_up plan = **不通過**，記下環境（光/背景/距離）。

---

## 6. Studio 證據

> Studio gateway 訂 10 個 String topic + `/tts` + 2 個 capability Bool。確認是真 ROS2 node（非 mock_server）看 boot log。

```bash
# 確認 gateway 是真 node（boot log 出現這行）
#   "Studio Gateway ROS2 node ready — subscribed to 10 String topics + /tts + 2 capability Bool topics"
curl -s http://localhost:8080/health      # 應回 "node":true 且 subscriptions 列 10 條
```

**一張截圖要同時出現的 topic 來源**（證明 live 非 mock）：
- 4 個感知 chip：`/state/perception/face`(face) + `/event/gesture_detected` or `/event/pose_detected` + `/event/speech_intent_recognized` + `/event/object_detected`
- brain trace：`/brain/conversation_trace` + `/brain/skill_result` + `/state/pawai_brain`
- tts：`/tts` 文字氣泡

判讀：截圖裡上述同時有資料 + gateway boot log 那行「10 String topics + /tts + 2 capability Bool」= 證據鏈成立（mock_server 不會印那行）。

---

## 7. Safety 拒絕

> 雙重攔截：safety 關鍵字 reject + IE 對 banned api 1301 攔截。「請翻跟斗」會被擋，但仍播一句安全台詞。

```bash
# 對狗說「請翻跟斗」×3，同時：
ros2 topic echo /brain/skill_result    # 期望 status="blocked_by_safety", detail="banned_api:1301", selected_skill="request_backflip"
ros2 topic echo /webrtc_req            # 期間/之後「不可」出現 api_id: 1301
```

判讀（3 次都要）：`/brain/skill_result` 出現 `blocked_by_safety` + `banned_api:1301`；`/webrtc_req` 全程**無** 1301。安全台詞「這個動作不安全，我不能執行。」會照播（那是另一條未被拒的 say plan，正常）。任何一次 `/webrtc_req` 冒出 1301 = **嚴重不通過**。

---

## 8. Under-load 量測

> 視覺多模型同跑時量資源；**Studio video-bridge（JPEG encode + WS fan-out）是第一嫌疑犯**。

```bash
# 用 jetson-status skill 拿單次快照（RAM/GPU/Temp/Power/running models/nodes/topics）
# 預算：RAM <5.5GB ok / >6.5 critical（7.4GB）；GPU <95% ok / 100% throttle；Temp <65 ok / >80 critical；Power <12W ok / >15W MAXN

# 各感知吞吐（手動，skill 沒含）
ros2 topic hz /perception/object/debug_image    # ~6-8 Hz
ros2 topic hz /face_identity/debug_image         # ~6.6 Hz
```

要記錄：加/不加負載前後的 RAM、GPU load、Temp、Power，以及 object/face debug_image Hz 有沒有掉。

隔離 Studio 貢獻：

```bash
# 關掉瀏覽器 video 面板（停 /ws/video 訂閱，_on_video_frame 無 client 直接 early-return）
# 再量一次 RAM/CPU/GPU；差值 = Studio video-bridge 的負載貢獻
```

判讀：video-bridge 對 face/vision/object 三條 debug image 各做 `cv2.imencode` JPEG（quality 70, 5fps）再 WS 廣播 → 卡頓先懷疑它。關 video 面板後資源回穩 = 確認嫌疑成立。

---

## 9. 今天不做 + 判定速查表

**今天不做**：
- 不起 nav / AMCL / cartographer / reactive_stop（8GB 與 brain 互斥）。
- 不在 full stack 跑 `test_mux_priority.py`（FakePublisher 會讓 Go2 衝出）。
- 不 mid-session 重啟 tts_node（Megaphone silent fail，要連 Go2 driver 一起重啟才行——但今天走外接喇叭主線，避免動它）。
- 不調 cup 顏色文案以外的 brain 台詞 scope。

**判定速查表：**

| 項目 | 通過門檻 | 不過怎麼辦 |
|---|---|---|
| **Object** | normal 任一物體 success_rate ≥ 0.8（**4/5**）且非 low_conf → primary | 全 <0.8 → 全降 backup，挑最高的當開場 |
| **Object cooldown** | `--window ≥ 6`、`--gap ≥ 6`、Enter 間隔 >5s | 用了預設 3s window → 數據作廢重量 |
| **Sitting** | misjudge ≤ **10%**（非 sitting emit 占比） | >10% → 重啟 brain `-p greet_require_sitting:=false` + 台詞去掉「坐著」 |
| **thumbs_up idle** | idle 30s 內 thumbs_up plan = **0** | >0 → 記環境，調距離/光線重測 |
| **Studio 證據鏈** | 一張截圖含 4 感知 chip + brain trace + tts，且 gateway boot log 印「10 String topics + /tts + 2 capability Bool」 | 缺 boot log 行 → 你看的是 mock_server，重起真 gateway |
| **Safety** | 「請翻跟斗」×3 全部 `blocked_by_safety`+`banned_api:1301`，`/webrtc_req` 無 1301 | 任一次 1301 上 `/webrtc_req` = 嚴重不通過，停下查 IE validate |
