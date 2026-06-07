# 6/18 一鏡到底 Demo 可行性 Audit（實機證據版）

> 2026-06-06。read-only 審計 PawAI 真實完成度，以「一鏡到底連續 demo」為主目標。所有結論附 file:line / evidence path。
> 來源：6/04 baseline（SHA 78fbf36）+ start_full_demo_tmux.sh + 各 node + 5-agent ultracode audit。
> 四態分類：①已有實機證據 ②wired 未 HITL ③只在文件 ④目前做不到。

---

## 🎯 VERDICT：`ONE_TAKE_POSSIBLE_BUT_NEEDS_P0_FIXES`

**必須區分兩個範疇：**

- **(A) 含 S1「真實移動 + Foxglove map」的全流程一鏡 = NOT_REALISTIC。** 三重物理互斥（Jetson 8GB / demo lock lane / cmd_vel ownership），brain NAV step 是 no-op（#129），nav.* 全 insufficient_data。真實移動只能切 nav stack 獨立 session，**不可能與 S2-S7 同一鏡**。
- **(B) S2-S7 互動鏈一鏡 = 同一 brain demo stack 單一 lock 可連續跑**，但**今晚補完 P0 才穩**（#127 安全拒絕 HITL + depth_clear 假成功防呆 + 啟動驗證）。

> **結論**：demo 結構 = **「S2-S7 互動鏈一鏡到底」+「S1 移動另段純顯示（不同 stack/不同鏡，口白誠實標 insufficient_data）」**。移動段一律走純顯示或 Go2 sport action 盲走，**不碰 Nav2/自走/繞障**。

---

## §0 會打臉的錯誤假設（8 個，全被實機證據打臉）

| # | 錯誤假設 | 實機真相 | 證據 |
|:-:|---|---|---|
| 1 | 一鏡可含「Go2 走進客廳 + Foxglove map」與互動鏈同鏡 | 物理不可能，三重互斥；要 map 必切 stack=斷鏡 | `start_full_demo_tmux.sh:135-136`(enable_lidar/nav2/slam=false) + CLAUDE.md 8GB 互斥 + `main.py:745-769` |
| 2 | 不用 Nav2 也能讓 brain 下「前進 N 公尺」自走 | brain NAV step 是 **no-op**，下了也不動 | `interaction_executive_node.py:220-221`(NAV not implemented) + `skill_contract.py:451` + #129 |
| 3 | Studio 紅 BLOCKED badge 可當安全拒絕證據 | badge 被 say_canned completed 蓋掉只閃一瞬，**主證據用 terminal** | `state-store.ts:94`(newest-first) + `chat-panel.tsx:83,539-543` |
| 4 | camera 揮手可觸發打招呼（互動主軸） | gesture.wave **recall=0.0**（6/6 全 none），baseline 後零變更，#131 wontfix | `baseline_snapshot.json` wave grade=fail + `README.md:15,27`(wave_pub=False) |
| 5 | S3 坐姿 sit_along 有實機證據可演 | pose.* **完全無 HITL**（n=0，無 observer），今晚屬 unknown | `baseline_snapshot.json` pose insufficient + `README.md:17` |
| 6 | safety unit test 全綠 = 真機端到端已驗證 | 只在 code+test 層，scoreboard brain.skill_gate=**insufficient_data**，真機 BLOCKED 待 #127 | `baseline_snapshot.json` skill_gate n=0 + `safety_layer.py:52-98` |
| 7 | `✓ Demo running` 代表 stack 起齊 | .env CRLF 致靜默 abort，CLI 仍假成功，**必數 process** | CLAUDE.md .env 陷阱 + `start_full_demo_tmux.sh:17` |
| 8 | voice.command 0.875 = 語音 e2e（ASR no-VAD）已驗證 | 只是**意圖分類成功率**，latency 全 null，VAD-era，no-VAD 主線無新 run | `baseline_result.jsonl`(latency=null, git=c56cd8f≠snapshot) + `README.md:13,29` |

---

## §1 Part A：`pawai demo start` 實際啟動什麼

鏈路：`pawai demo start` → `main.py:640-649` → `start.sh demo`（=full + STUDIO=1）→ Jetson `start_full_demo_tmux.sh`（13-window）+ 本機 next dev。

**brain demo stack 完全沒有 LiDAR / Nav2 / SLAM / Foxglove map**（`start_full_demo_tmux.sh:135-136` 硬寫 false）。Foxglove bridge 有起但 scan/pointcloud 來源不存在 → 無 map。

| 模組 | demo start 啟動 | 一鏡到底影響 |
|---|:-:|---|
| Go2 Driver(WebRTC) | ✅ | 全程在；唯一 `/webrtc_req` 訂閱者；**一鏡內不可重啟** |
| D435 / face / vision(gesture+pose) / object / ASR / TTS / conversation(langgraph) / IE+brain / depth_safety / Studio gateway | ✅ | 全在同 brain stack，S2-S7 可一鏡 |
| Studio frontend | 條件式(default 含，`--no-studio`/`--brain-only` 不含) | 本機跑不佔 Jetson |
| **LiDAR / Nav2 / AMCL / SLAM / map / nav executor** | ❌ | **全在 nav lane、8GB 互斥；真實移動+map 不可能與互動鏈同鏡** |

**資源 gate**：D435 被 face+gesture+pose+object+depth_safety 同吃（8GB/GPU 主壓力）；`depth_clear=false` 靜默擋所有 MOTION；TTS/driver 一鏡內不可重啟；換 LLM 模型要重啟整 stack=斷鏡（須事前決定）。

---

## §2 Part B：逐段 audit

| 段 | 四態 | 今晚預期 | 一句話 + 證據 | 能否接下一段 |
|---|---|:-:|---|---|
| **S1 移動** | wired 未 HITL → 真自走=做不到 | **fail** | nav.* insufficient、dry-run amcl_lost actual_distance=0、NAV no-op。`README.md` nav + `nav_action_server_node.py:341-399` | ❌ 切 stack 斷鏡 |
| **S2 認人** | ✅ 已有實機證據(僅 Roy) | **flaky** | 6/04 n=9 recall=1.0，但量到距離 **1.79-2.42m 全 >1.6m ENGAGED 門檻** → 展示須走到 ~1m。`attention_machine.py:33,36` + `face_identity_node.py:482` | ✅ 接 S3 但留 QUIET 8s |
| **S3 坐姿** | wired 未 HITL | **unknown** | pose **n=0 從沒上機量**；sit_along auto-fire(`brain_node.py:1110`) 會與 cup/gesture 互搶 | ✅ 自動互擾高 |
| **S4 水杯** | ✅ 已有實機證據(~1m) | **pass** | 6/04 cup 5/5 @1m conf 0.83-0.88；但 manual_declared 非 depth、2m 無樣本。先暖 TRT | ✅ 同 stack；隔 >5s cooldown |
| **S5 hello** | wired 未 HITL | **flaky** | camera wave fail(recall=0)→走 **Studio 按鈕(確定性)** 或語音(LLM 非確定)；gesture 有 30s conversation gate | ✅ 同 stack；注意 gesture gate |
| **S6 安全拒絕** | wired 未 HITL(**唯一全綠最硬**) | **pass** | 100% rule-based 不經 LLM(`safety_layer.py:52-98`)，23 test 綠；**真機端到端待今晚 #127** | ✅ 同 stack；ALERT 會 preempt |
| **S7 Studio trace** | wired 未 HITL | **flaky** | gateway→WS→前端全接；badge 覆蓋 bug；主證據用 terminal | ✅ 同 stack 並行 |

---

## §3 Part D：claim 表（可講 / 不可講 / 缺）

| 能力 | ✅ 可講（窄版） | ❌ 不可講 | 還缺什麼 |
|---|---|---|---|
| **face** | 認出**已註冊 Roy**(n=9 recall=1.0 false-accept=0) | 拒絕陌生人/不會認錯/2m/通用/把新主角當已驗證 | 新主角 recall(0樣本)、≥2註冊者、真陌生人、conf 邊界 |
| **object.cup** | **~1m 桌上單色杯**(5/5 conf 0.83-0.88) | 2m 也穩/即時/通用80類/觸發移動/絆倒守護 | 1.5/2m 樣本、D435 量真距、p90 4.9s 降到「即時」 |
| **gesture.wave** | 誠實揭露 **fail**(recall=0.0) | 揮手可觸發/手勢觸發 motion/混為語音 wave_hello | 調參重測 或 改 static palm |
| **pose** | 有鏈路但**本輪未量、不做** | 跌倒可靠/防跌/坐下已 pass/醫療判斷 | pose observer 工具 + HITL ground-truth |
| **voice.command** | 固定指令**意圖分類** 0.875 | 延遲/急停/自由對話/LLM 直控/no-VAD 已驗 | 真人 ASR e2e ≥20、量 latency、no-VAD run |
| **safety refusal** | **機制** deterministic 不經 LLM + 單測綠 | 已實機端到端驗證/skill_gate pass/不會幻覺 | 真機 BLOCKED HITL(#127)、N≥10 攔截 |
| **nav/obstacle** | 純顯示感知 + action chain fail-closed | 遇障停車/遙控自走/自主繞行/停了不暴衝 | F7 root cause、定位、供電穩、no_auto_resume 驗 |

---

## §4 Part C：今晚一鏡能力 audit checklist（測極限，非拍漂亮）

### 啟動前
```bash
# 0. .env CRLF（最大假成功殺手）
ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local && cp .env.local .env"
# 1. 起 demo（不混 nav stack）
ssh jetson-nano 'cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh'
# 2. 不信 CLI，數 process（缺任一停止往下）
ssh jetson-nano 'zsh -lic "ros2 node list"'   # brain_node/interaction_executive_node/studio_gateway/depth_safety_node
tmux ls                                        # demo 13-window
# 3. P0 GATE：depth_clear（false 則所有 MOTION 靜默被擋、gateway 仍 ok:true）
ros2 topic echo /capability/depth_clear --once # 要 true；false 則修 D435/清鏡頭前 / latch: ros2 topic pub -1 ... '{data:true}'
# 4. WebRtcReq 非 dry-run
ros2 topic info /webrtc_req -v                 # subscriber 含 go2_driver_node
# 5. config override（非裸 launch 讀 yaml）
ros2 param get /vision_perception_node gesture_backend   # recognizer
ros2 param get /interaction_executive_node enable_fallen # false
# 6. 沒誤啟 nav obstacle gate
ros2 topic echo /state/reactive_stop/status --once       # 無 publisher 或 obstacle_active=false
```

### 監看視窗（錄前先跑著）
- **W1 主證據** `ros2 topic echo /brain/skill_result`（S6 看 banned_api:1301；append-only 帶 timestamp）
- **W2 Go2 下令** `ros2 topic echo /webrtc_req`（1016=hello / 1005=sit；翻跟斗時無新訊息=零下令）
- **W3 depth gate** `ros2 topic echo /capability/depth_clear`（連續監看）
- **W4 face** `/state/perception/face` + Foxglove `/face_identity/debug_image`

### 測試順序（PRE-0 正控 → S6 壓軸先 → 其餘）
1. **PRE-0 正控**（先證鏈路活）：`ros2 topic pub -1 /brain/skill_request std_msgs/String '{data: "{\"skill\": \"wave_hello\", \"args\": {}, \"request_id\": \"pc1\", \"source\": \"studio_button\"}"}'` → **PASS=`/webrtc_req` 出 1016 + Go2 揮手出聲**。過了才證後面「翻跟斗被擋」是真擋。
2. **S6 安全拒絕**（語音，no-VAD）：連喊「PawAI 請翻跟斗」**3 次隔 ≥3 秒** → **PASS=3/3 Go2 不動 + TTS「不安全」+ skill_result `banned_api:1301` + webrtc_req 無新訊息**。ASR 不穩則 Studio 文字輸入繞過。
3. **S6b sit_along**：發 `sit_along` skill_request → **PASS=TTS「陪你坐一下」+ `/webrtc_req` 1005 + Go2 趴低**（口白「趴下來陪你」）。
4. **S2 認人**：Roy 走到 **~1m 站 2s** → 名字穩定吐 + greet。
5. **S4 cup**：暖 TRT ≥30s → 桌上 ~1m 杯 → object_detected cup conf≥0.8。
6. **S3 pose smoke**：站→坐 ×5，**≥4/5 觸發 + 0 誤報才解鎖「看到坐下」口白**；否則 `demo_video_silent_sit_along:=true` 砍 auto-fire。
7. **S5 手勢**：靜態 palm/語音 wave_hello（camera wave 不演）。

### 要存的證據
- `ros2 topic echo /brain/skill_result | tee ~/elder_and_dog/runtime/hitl_$(date +%Y%m%d_%H%M)/skill_result.log`（S6 最硬留痕）
- 分割畫面影片（每段第三人稱 + terminal echo + debug_image 同框）
- 截圖：face/object debug_image、Studio 12-stage trace、`ros2 node list`/`topic info`（證真 gateway 非 mock）
- 量測：ASR unsafe keyword 5 組辨識率、pose smoke 5 次、各段 request→api_id 延遲
- **收工**：`pawai demo stop` / `clean_full_demo.sh`，殘留才手動 pkill

---

## §5 Part E：開發 backlog（按「阻止一鏡到底」嚴重度排序）

### P0（不做就跑不了一鏡 / 假成功）
1. **.env CRLF 清理** — `sed -i 's/\r$//' .env .env.local` + 數 process 不信 CLI。
2. **depth_clear=true 確認** — 否則所有 MOTION 靜默被擋但 gateway 回 ok:true。
3. **PRE-0 正控 + S6 安全拒絕真機 HITL（#127）** — 全 demo 唯一全綠最硬一段，今晚補。
4. **WebRtcReq 非 dry-run + 真 gateway 非 mock** — `topic info -v` 確認，否則 skill_result COMPLETED 但 Go2 沒收命令。

### P1（不做會很不穩）
5. **S2 face 距離/dwell** — 展示走 ~1m（6/04 量到全 >1.6m 門檻）。
6. **S4 cup TRT 暖機 + 鎖 ≤1.2m**。
7. **config override 驗證**（gesture_backend=recognizer / enable_fallen=false）。
8. **S3 pose smoke gate**（≥4/5 才講「看到坐下」）。

### P2（polish）
9. Studio blocked badge 不被覆蓋（前端改，主證據已用 terminal 故非阻擋）。
10. ASR unsafe keyword 辨識率實測（不穩改 Studio 文字）。

### 不做（6/18 前不值得）
- **S1 真實 nav 移動 + Foxglove map 進一鏡**（三重互斥 + nav 全 insufficient + 撞機/斷電風險）→ 移動退純顯示或盲走 cmd_vel。
- **camera wave 除錯**（#131 wontfix）→ 走 Studio 按鈕/語音。
- **換任何感知模型**（6/05 KEEP_CURRENT）。

---

## §6 Roy 必須拍板（只列會改變開發方向的）

1. **S1 移動定位**：另排獨立 nav session 純顯示（不同鏡、口白標 insufficient）vs 開場退 Go2 sport action 盲走/站立招呼 vs 完全不碰 nav？（三者都不能與 S2-S7 同鏡）
2. **S6 觸發主路徑**：語音（最有說服力但卡 ASR 字面辨識）vs Studio 文字（100% 穩但少戲劇性）？今晚 #127 3/3 結果決定 production-plan 口白能否改「已完成真機端到端 HITL」。
3. **S2 認人對象**：學校是否先用 #128 face CLI enroll 新主角並當場補量 recall？不補則只能講「辨識已註冊 Roy」、新主角不能宣稱已驗證。
4. **互動鏈節拍授權**：是否接受「每段間留 ≥8s 間隔、必要時 `demo_video_silent_sit_along:=true` 關 auto-fire 改純語音帶」作為一鏡腳本硬約束（防 perception 自動 fire 互相干擾）？
