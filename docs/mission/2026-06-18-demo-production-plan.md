# 6/18 Demo 製作計畫：資料收集 + 開發 + 拍攝（誠實可呈現版）

> 狀態：2026-06-06 收斂版。把會議原稿的 demo 流程，校準成「真的拍得出來、每句有證據、零 overclaim」的可執行計畫。
> 來源：6/04 baseline（SHA 78fbf36）+ demo-flow-plan + capability-claim-matrix + 本日 4 workflow 稽核 + 3 輪 grill。
> 配套 issue：#127(安全拒絕 HITL)、#128(face CLI)、#129(前進N公尺·有 NAV blocker)、#130(depth panel)、#131(gesture wontfix)。

---

## §0 三條總原則（決定每段怎麼做）

1. **雙軌錄製**
   - **家裡備片 = 交付主體**：Roy 當主角、網路穩、**可無限重拍**。8 段全在這裡錄到乾淨。
   - **學校 live = 求穩**：她當主角（6/15 現場 enroll）。**只演不可重拍風險低的段**；涉及真 Go2 locomotion / 需 depth_clear 放行 / ASR 一次性的段，一律退家裡備片或純顯示。
2. **每段都要有「即時非預錄」鉤子**：第三人稱鏡頭旁**同框** Studio trace / debug_image / terminal `ros2 topic echo`。這是回應老師「怎麼證明不是預設回話」的唯一硬證據。
3. **每功能只演最強一次**；做得到的秀、沒驗證的**誠實標在 scoreboard**。避免一次開五個手勢造成亂跳。

---

## §1 原稿紅旗修正表（開發/收集前必先改掉）

| 會議原句 | 問題（已對碼驗證） | 改成 |
|---|---|---|
| 「叫牠**撿起來**」水杯 | Go2 無手臂/夾爪；skill_contract 只有 SAY/MOTION/NAV、零 pick/grasp | 「**桌上**有杯子，它沒有手臂，是**看到並說出來**」 |
| 「杯子**兩公尺外**可辨識」 | 9cm 杯 @2m≈21px 踩 YOLO26n nano 下限；input 硬鎖 640；6/05 已裁鎖≤1.5m | **刪「兩公尺」**→「近距 ~1m、cup-only、非通用」 |
| 「**動態繞開**障礙物 / 往右繞開」 | 5/3 Block E 實測 **L3 FAIL**，DWB 本質 stop-only | **全禁**：禁演/禁字幕/禁口白 |
| 「移動到現場進行**巡檢** / 從門口走向 Roy / slam+nav2 自走」 | nav.short_move insufficient、F7 未定位、dry-run amcl_lost、Go2 零移動 | 退 **Foxglove 純感知顯示**（家裡可加遙控短移動 A2）；字幕「**守望互動小閉環**」 |
| 「我看到你**坐下來了**」 | pose n=0 insufficient + persona 自編姿勢幻覺 | pose **只 Studio panel 顯示**；條件式（smoke≥4/5 才講，見 S3） |
| 「我看到**地上**有水杯，請記得**拿起來**」 | 絆倒守護語言（禁說）+ 撿不起來 | 「我看到桌上有杯子」 |
| 手勢 take A 走 **camera 揮手** | gesture.wave recall=0.0（已 wontfix #131） | 靜態 palm/舉手 或語音 wave_hello(1016) |
| 「坐下」 | sit_along=StandDown(1005)=趴低，非盤腿坐 | 「**趴下來陪你**」 |

---

## §2 逐段製作（開發前置 + 資料收集 + 拍攝）

> 格式：每段＝① 開發/前置（錄前要就緒的 code/config）② 資料收集（echo 哪些 topic、錄哪些畫面、什麼算 usable take）③ 拍攝（家裡/學校、camera、口白、dontSay）。

### S1 移動到現場（純感知顯示，家裡可加遙控短移動）

- **① 開發/前置**：
  - 純顯示：nav stack（`start_nav2_amcl_demo_tmux.sh` 或建圖 stack）+ RPLIDAR + D435 + Foxglove。**與 brain demo stack 互斥（8GB），要單獨一個 session/天**。
  - 遙控短移動 A2（家裡選配）：**只起最小 driver**（`robot.launch.py nav2:=false slam:=false`），不需 nav stack、不互斥 brain。**不要碰 #129 前進N公尺**（NAV executor 還是 no-op）。
- **② 資料收集**：
  - Foxglove 螢幕錄製：`/scan_rplidar` 光達點雲（掃出客廳輪廓）+ `/camera/.../aligned_depth_to_color` depth + `home_living_room` map。
  - A2 短移動：手動發**短促前進指令** → `ros2 topic echo /webrtc_req` 看指令送出 + driver log 看 **StopMove** 收尾（**停車證據**；實際 api_id 今晚 echo/driver log 核對後再寫死，先別寫滿）。
  - ⚠️ **A2 安全不靠 depth_clear**：手動 WebRTC/driver 直發可能**繞過 IE SafetyLayer**，`/capability/depth_clear` 不保證會擋。A2 真正安全靠：**空場 ≥3m + 短促 + StopMove + e-stop 在手 + 供電穩**；depth_clear 只是環境檢查、非安全保證。
  - usable take：純顯示=三畫面同框清楚；A2=Go2 抬腳走一小步 + 立刻 StopMove 停住站 2-3s。
- **③ 拍攝**：
  - 家裡：第三人稱斜 45° 同框「人+Go2+空地+terminal」；A2 用搖桿（有 deadman）+ e-stop 在 Roy 手；場地清 ≥3m、正前方無人、地貼 0.3-0.5m 膠帶當參考尺。
  - 學校：**直接純顯示、不碰 motion**。
  - **口白**：「系統在**看**，不是它會自己走；動態繞障我們實測做不到、誠實標 future work；前方有障礙安全層讓它**即時停下、不是繞開**——而且停下後障礙移開會自動恢復前進，這個保證還沒驗證通過。」
  - **dontSay**：自主導航 / 巡檢 / 走向 Roy / 繞開 / 精準走 N 公尺 / 停了不暴衝。
  - owner：鄔。

### S2 認人問候（face，窄版 pass）

- **① 開發/前置**：face stack（`start_face_identity_tmux.sh` 或含在 full demo）。家裡 face_db 有 Roy（已 n=9）；學校 6/15 用 **#128 face CLI** enroll 她。
- **② 資料收集**：
  - `/face_identity/debug_image`（bbox+名字+距離）+ `/state/perception/face`（10Hz JSON，看名字穩定吐）。
  - **live-proof**：第三人稱鏡頭**同框** debug_image。
  - usable take：主角走近 ~1.5-1.7m（ENGAGED 門檻 ≤1.6m）正對停 1-2s，名字穩定（不閃 unknown）。
- **③ 拍攝**：
  - 家裡=Roy；學校=她。
  - **口白**：「歡迎回來，Roy。」旁白：「認出**已註冊的** Roy（窄版 pass n=9, recall=1.0, false-accept=0），僅此人、idle 空景，**不宣稱拒絕陌生人、不宣稱不會認錯**。」動詞用「辨識」。
  - **dontSay**：認得任何人 / 2m / 不會認錯 / 陌生人警報。
  - owner：楊（帶窄版 caveat）+ Roy 接深水 Q&A。

### S3 看姿態（pose，條件式）

- **① 開發/前置**：pose 在 full demo（`pose_backend:=mediapipe`、`enable_fallen:=false`）。**條件式 gate**：demo 前 smoke——坐椅子正對 2m，站→坐 **≥4/5 觸發、彎腰/蹲 0 誤報** 才解鎖「看到坐下」口白。
- **② 資料收集**：`/event/pose_detected` + Studio pose panel 顯示 sitting event。usable take：smoke 過 → 家裡備片可講；沒過 → 只 Studio 顯示。
- **③ 拍攝**：
  - 家裡（**smoke≥4/5 才解鎖**）：可講「**我看到你坐下來了**」+ 輕量回應；旁白補 caveat：「pose **本輪未完整量測**、僅 demo 前 smoke 驗證、非醫療、**不做跌倒判斷**」。
  - 學校 live / smoke 未過：**只 Studio pose panel 顯示 sitting，不出聲**。
  - 兩軌共通：**絕不提跌倒**、鏡頭帶到 fallen 紅標一律靜音。
  - owner：楊。

### S4 看物品（object cup，窄版 pass 鎖 ~1m）

- **① 開發/前置**：object_perception（YOLO26n，**不換模型**）。**錄製前先暖 TRT cache**（首啟 inference 3-10 分鐘；先空跑 object node 到 `debug_image` 穩定 ≥30s 才開錄，全程不關該 node）。
- **② 資料收集**：`/perception/object/debug_image`（中文「杯子」+conf）+ `/event/object_detected`。usable take：**桌上 ~1m**（≤1.5m）單色杯置中停穩，conf ≥0.8。
- **③ 拍攝**：
  - **口白**：「我看到**桌上**有杯子。」旁白：「刻意**只開杯子一類**、**僅近距 ~1m** 可靠、**非通用物體辨識**、2m 未驗；它沒有手臂，是看到並說出來、**不是去撿**。」
  - **dontSay**：地上 / 兩公尺 / 拿起來 / 認得 80 種 / 通用辨識。
  - fallback：顏色亂跳→只講「杯子」；miss→播 debug_image 截圖。
  - owner：楊。

### S5 手勢 / 語音互動（gesture FAIL → fallback）

- **① 開發/前置**：vision（`gesture_backend:=recognizer` override，**不是裸 launch 讀 yaml 預設 rtmpose**）。camera 動態 wave **不修**（#131 wontfix）。
- **② 資料收集**：
  - take A：靜態 palm/舉手（`/event/gesture_detected`）**或**語音 wave_hello → `/webrtc_req` api 1016 + Go2 hello。
  - take B：語音「PawAI 陪我坐一下」→ sit_along → `/webrtc_req` 1005 + Go2 趴低。
  - usable take：靜態手勢 1.5-2.5m 手抬胸口以上、一次一個放下給 3-4s。
- **③ 拍攝**：
  - **口白**：「動態揮手 6/04 量到 **fail**(recall=0.0)，我們**不演 camera 揮手**、改靜態手勢/語音，並在 Studio 誠實標 fail。」take B 是 **sit_along=趴低**，不講「盤腿坐下」；語音 wave_hello 是另一條路徑、**不混為 camera wave 已 pass**。
  - fallback：靜態也不穩→只 gesture panel 顯示 event + 標 wave=fail。
  - owner：鄔（觸發）+ 楊（解說 fail）。

### S6 安全拒絕（壓軸，唯一全綠，先錄）

- **① 開發/前置**：brain+studio stack（nav 必關）。`brain_node`/`interaction_executive_node` 都在。**已對碼驗證**：`safety_layer.unsafe_request` 純關鍵字字串比對（翻跟斗/後空翻/倒立/backflip…）→ say_canned 拒絕 + request_backflip → `banned_api:1301`，**100% rule-based 不經 LLM**。
- **② 資料收集（這是全 demo 證據最硬的一段）**：
  - **主證據 = terminal** `ros2 topic echo /brain/skill_result`（append-only、帶 timestamp、`detail=banned_api:1301`）。**不要靠 Studio 紅 badge 當主證據**——它是 `brainResults[0]` 會被 say_canned 的 completed 蓋掉、只閃一瞬（chat-panel.tsx:83）。badge 只當人話版輔證。
  - 同步 echo `/webrtc_req`：喊翻跟斗時這裡**無新訊息** = Go2 零下令。
  - **positive control**（證明 echo 沒壞）：先 `/capability/depth_clear --once`=true → 發 wave_hello 確認 `/webrtc_req` 出 1016 → 再喊翻跟斗看 blocked + 無 1301。
  - **觸發語音版**（no-VAD）：連喊「翻跟斗」**3 次、隔 ≥3 秒**，3/3 都出 `banned_api:1301` 才算過。
  - usable take：Go2 不動 + TTS「這個動作不安全，我不能執行」+ terminal `banned_api:1301` + Studio 紅 badge（輔證）四者同框。
- **③ 拍攝**：
  - camera：**分割畫面**（第三人稱 Go2 + Studio chat + terminal echo 滾動）。
  - 家裡=Roy 語音；**學校=Roy 代喊（穩）+ 家裡預錄保底**；學校一次性風險高，手邊留打字版/預錄。
  - **口白**：「危險動作拒絕是 100% rule-based 關鍵字比對、**完全不經 LLM**；backflip(1301) 是我們**刻意造的一個被禁 api** 來示範安全層怎麼攔——Go2 sport mode 本來就沒有翻跟斗，不是本來想做被擋。pure-Python unit test 全綠（safety 36/IE 221）、執行層再攔一次（雙層 fail-closed）；**真機端到端 BLOCKED 屬後續 HITL**，今天講的是邏輯+test+Studio 即時顯示。」**不講「假動作」**，講「**受控測試指令 / 危險動作測試案例**」。
  - **⏳ 待今晚 #127 同步**：若今晚翻跟斗 3/3 通過，口白「真機端到端屬後續 HITL」改為「**已完成真機端到端 HITL：語音觸發 → SafetyLayer block → Go2 不動 → skill_result 留證**」。
  - fallback：badge/TTS 不出→播預錄三連拍 + 終端跑 `pytest -k 'safety or banned'` 證邏輯。
  - owner：**Roy 主持**（技術深度最高）+ 鄔操作。

### S7 收尾（Studio evidence + 守望小閉環）

- **① 開發/前置**：Studio（真 `studio_gateway` 非 mock）。
- **② 資料收集**：ChatPanel + BrainStatusPill → `?dev=1` 12-stage trace 色票流 → `/studio/live` 三欄影像牆。開場/收尾主畫面用 **git-tracked** `baseline-evidence/*.json`（readiness=not_ready）+ dev trace GateChip。**不承諾螢幕有 scoreboard pass/fail LED**（前端無 fetch /api/scoreboard 的 UI 元件）。
- **③ 拍攝**：
  - **口白**：「每一步——認人、看姿態、看物品、互動、安全拒絕——都能在 Studio 看到證據，這是跟一般 chatbot 的差別：可解釋、可追溯。做到的秀給你看，沒驗證可靠的**誠實標在 scoreboard**，量測證據全程留痕在 repo。」
  - readiness 標準答案（雙層）：「**能力上還沒全 ready，這是誠實量測的結果；但 demo 可演、有證據、有 backup。**」
  - owner：盧（架構收尾）+ 陳（英文總結）。

---

## §3 開發排程（這週，對應 issue）

| 優先 | 任務 | issue | 何時 | 性質 |
|:-:|---|:-:|---|---|
| **今晚** | 安全拒絕鏈真機驗（語音翻跟斗 3/3 + Studio button wave/sit） | #127 | 今晚上機 | HITL（Roy） |
| 這週 | `pawai face` CLI（list/enroll/delete，6/15 用） | #128 | Codex 寫 + Roy review | ready-for-agent |
| 這週 | pose.sitting smoke（≥4/5 解鎖 S3 口白） | — | 上機 smoke | HITL |
| 加分 | Studio depth panel | #130 | Codex（排第四，不搶時間） | ready-for-agent |
| **不碰** | 前進N公尺（NAV executor 是 no-op，要改後端） | #129 | demo 後 | blocker |
| **不碰** | camera wave（recall=0.0，已 wontfix） | #131 | — | wontfix |
| **不換** | 任何感知模型（cup 鎖≤1.5m，6/05 KEEP_CURRENT） | — | demo 後 | — |

---

## §4 拍攝時間表（最小骨架）

| 日期 | 地點 | 做什麼 | 產出 |
|---|---|---|---|
| **6/15** | 學校 | 她 face enroll（#128）+ **mini recall smoke**（1.5m 正樣本 + 隊友負樣本）+ pose/gesture smoke + 第一段純顯示素材（Foxglove/depth）| 她的 recall 數字、學校素材 |
| **6/16-17** | 家裡 | 錄 8 段（Roy 主角，無限重拍）；**先錄 S6 安全拒絕**（最穩）→ S2/S4 強段 → S3/S5 條件段 → S1 移動 | 全段 take |
| **6/17 晚** | — | 鄔剪輯（4:30-5:30 成片，含 caveat 旁白）；Roy 6/17 晚前交全部 take | 完整備片 |
| **6/18** | 學校 | 簡報 + 學校 live（求穩段）+ 備片三情境保底 | demo |

> 三情境保底：①正常現場 ②部分離線（face/手勢即時，語音用 piper/edge_tts 本地或影片補）③完全斷網（播完整備片）。

---

## §5 拍前 checklist + footguns（每次錄製前逐項）

```bash
# 0. .env CRLF（假成功陷阱）
ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local && cp .env.local .env"
# 1. 起 demo 後不信 CLI「✓ running」，數 process
ssh jetson-nano 'zsh -lic "ros2 node list"'   # brain_node/interaction_executive_node/studio_gateway/depth_safety 全在
tmux ls
# 2. depth gate（不放行則所有 MOTION 靜默被擋、SAY 出聲假成功）
ros2 topic echo /capability/depth_clear --once   # 要 true
# 3. config override 生效（非裸 launch 讀 yaml 預設）
ros2 param get /vision_perception_node gesture_backend   # 要 recognizer
ros2 param get /interaction_executive_node enable_fallen # 要 false
# 4. 真 gateway 非 mock（safety badge 要這個）
ros2 topic info /brain/skill_result -v
# 5. nav 段單獨 session（與 brain 8GB 互斥）
# 6. 供電：Go2 行走中 XL4015 反覆斷電 8+ → 充飽 + 備電 + 單拍短 + Ethernet 直連避 OTA
# 7. 收工清乾淨：優先 pawai demo stop / clean_full_demo.sh，殘留才手動 kill
pawai demo stop                      # 或 bash scripts/clean_full_demo.sh
# 必要時（多 driver instance 殘留）才手動：
# pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 joy_node; pkill -9 teleop; pkill -9 twist_mux
```

**Q&A live-proof（回應「怎麼證明不是預錄」）**：請老師**當場指定一句輸入/一個杯子顏色** → 現場輸入 → 同畫面 `ros2 topic echo /brain/skill_result`（帶 timestamp 滾動）+ `ros2 node list` 證真 gateway（鄔執行）。

**5 人禁說把關**：per-speaker dont_say 卡（楊講功能表最易把窄版說成通用）；深水 7 題（scoreboard 無 UI / face 窄版 / voice.stop auto-resume / F7 / mock vs live …）handoff 暗號「**可靠度數據我請負責量測的同學補充**」交給 Roy。
