# 專案狀態

**最後更新**：2026-04-01（Sprint Day 6 — Gate A/B PASS, Gate C FAIL 噪音阻塞）
**硬底線**：2026/4/13 文件繳交，5/16 省夜 Demo，5/18 正式展示，6 月口頭報告

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **聊天可用 / 命令未達標** | 4/1 | 安靜 4/5 PASS；Go2 噪音下聊天互動可用，stop 等命令不可靠→改靠手勢 |
| 人臉 (face_perception) | **Executive 整合通過** | 4/1 | Gate B face welcome → TTS 問候 PASS |
| 手勢 (vision_perception) | **Executive 整合通過** | 4/1 | Gate B stop gesture → StopMove + dedup PASS |
| 姿勢 (vision_perception) | **桌測通過** | 3/30 | MediaPipe Pose CPU，standing 10 / sitting 8 / fallen 1，四模組同跑穩定 |
| LLM (llm_bridge_node) | **E2E 通過** | 4/1 | Cloud 7B → RuleBrain，greet cooldown dedup 正確 |
| Studio (pawai-studio) | 前端開發中 | 3/16 | Next.js，前端截止 3/26（已截止），後端 4/9 後啟動，WebSocket bridge 不存在 |
| CI | **16 test files, 214+ cases** | 3/25 | fast-gate + **blocking contract check** + git pre-commit hook |
| interaction_executive | **v0 整合通過** | 4/1 | Gate B 6/6 PASS（face/speech/gesture/dedup/priority/crash 7s recovery） |
| 物體辨識 | **研究完成** | 3/25 | YOLO26n，**預設目標（非自由搜尋）**，~3 天實作 |
| 導航避障 | **研究完成** | 3/25 | **LiDAR 正式放棄**，D435 depth camera 下一步（未測），~10-12hr |

## 3/26 會議決策

### 關鍵決定
- **物體辨識策略調整**：改為**預設目標**辨識（指定日常物品如水杯、藥罐），非自由搜尋。參考 AI Expo 業界做法，降低複雜度、聚焦可展示性
- **LiDAR 正式放棄**：Go2 LiDAR <2Hz 不可行，下一步改用 D435 depth camera 做基礎反應式避障（尚未測試）
- **整體完成度**：約 50%（含功能開發，不含文件與網站）
- **MeloTTS 正式棄用**：卡在尷尬定位 — 音質不如 Edge TTS，速度又比 Piper 慢
- **Qwen 3/3.5 棄用**：太聰明導致回答不受控，Qwen 2.5 最符合需求
- **Go2 韌體自動更新風險**：Demo 當天禁止連外網，避免被更新

### 文件章節分工（4/13 前繳交 Ch1-5）
| 章節 | 內容 | 負責人 |
|------|------|--------|
| Ch1 | 專題介紹、背景說明 | 共同 |
| Ch2 | User Story、需求分析 | 魏宇同、黃旭 |
| Ch3 | 系統架構、技術細節 | 按功能：人臉+導航+語音（Roy）、物體+姿勢（魏宇同/黃旭）、手勢（陳若恩） |
| Ch4 | 問題與缺點、未來展望 | 簡單撰寫 |
| Ch5 | 分工貢獻表、個人心得 | 各自撰寫 |

### 外部交流
- **4/16（暫定）**：卓斯科技創辦人線上會議 — 陪伴機器人產品觀點
- **NVIDIA 交流**：老師在 GBUA 認識 NVIDIA 亞太區行銷經理，後續邀請工程師來校

### 審計修復（3/26 commit）
- #1 TTS echo gate 洩漏 → 修復（early return 補 `_publish_tts_playing(False)`）
- #6 跨執行緒 DC.send() → 修復（移除不安全 fallback）
- #7 執行緒無限增長 → 修復（ThreadPoolExecutor 取代 per-event Thread）
- #18 模型版本不一致 → 修復（script yunet_legacy → 2023mar）

---

## Sprint Day 6 完成（4/1）

### Gate A — 安靜環境 ASR E2E：PASS (4/5)
- **Cloud ASR 恢復**：sensevoice_server.py async fix 生效，不再全 timeout
- **ASR timeout**：3s → 5s（tunnel latency 餘裕）
- **sensevoice_server.py**：加 `disable_update=True`（離線模型載入，避免重啟時 modelscope API 失敗）
- **E2E 流程通**：ASR → LLM → TTS → 喇叭播放，完整鏈路驗證
- **已知缺口**：單字「停」被 VAD 吞掉（min_speech_ms 斷句不穩定），Demo 改用「停下來」
- **SSH tunnel 永久化**：Jetson systemd user service，開機自動起、斷線重連
- **USB speaker 穩定化**：改用 `plughw:CD002AUDIO,0`（by ALSA name，不受 device drift 影響）

### Gate B — Executive 邊界測試：PASS (6/6)
- **Face welcome → TTS**：executive 收到 identity_stable → TTS「roy 你好」 ✅
- **Speech chat → LLM**：intent → LLM 回覆 → TTS 播放 ✅
- **Stop gesture → StopMove**：executive api_id=1003 priority=1 ✅
- **Face + Speech 同時**：llm_bridge greet cooldown dedup 正確 ✅
- **Gesture stop + Speech 同時**：stop 優先序正確 ✅
- **Crash recovery**：殺 executive → 重啟 → 7 秒恢復 ✅

### Gate C — Go2 上機語音驗收：拆分判定

#### Gate C-command（語音命令控制）：FAIL
- **stop 語音指令不可靠** — 被 VAD 截斷或 ASR 辨識錯誤，安全關鍵指令不能依賴語音
- **transcript 準確率 ~25%** — Go2 風扇噪音壓過語音（mic_gain 8.0/12.0 均無效）
- **Demo 對策**：stop 改靠手勢 stop（Gate B 已驗證 100%），不用語音

#### Gate C-conversation（聊天陪伴互動）：PASS with caveat
- **使用者體驗**：講話後機器人幾乎都有合理回應
- **come_here / take_photo**：完全正確辨識 + 正確回覆
- **greet**：ASR 文字糊但 LLM chat fallback 回覆自然（「你好呀」「哈囉，我在這裡」）
- **status**：未被正確辨識為 status intent，但 LLM 回覆仍合理（「好的，有需要再叫我」）
- **結論**：聊天可用，命令控制未達標。Demo 詞庫應偏向容錯高的句子

#### 噪音調查結論
- **主噪音源**：Go2 內建散熱風扇（非 LiDAR），無法軟體關閉
- **adaptive VAD**（noise floor EMA + 動態 threshold）已實作並部署，改善觸發穩定性但不改善 ASR 準確率
- **根因**：硬體 SNR — 全向麥克風收到的語音被風扇噪音蓋住
- **Day 7+ 方向**：軟體降噪（noisereduce）或物理隔離麥克風

### 基礎設施改善
- **interaction_contract.md v2.2**：新增 `/executive/status`(v0)、`/event/obstacle_detected`(planned)、deprecate router+bridge
- **Jetson GPU tunnel systemd**：`gpu-tunnel.service`（SSH key + auto-reconnect）
- **USB speaker by name**：`plughw:CD002AUDIO,0` 取代 `plughw:N,0`

---

## Sprint Day 4+5 完成（3/31）

### Day 4：硬體穩定性驗證 — GATE C 通過
- **3x 冷開機** bring-up 全部成功，USB index 穩定（mic=0, spk=plughw:1,0）
- **Go2 行走 2 分鐘**：硬體不鬆脫（熱熔膠固定 USB 接頭後）
- **30 分鐘連續運行**：peak 56.2°C < 75°C，16 node 全程無掉，喇叭全程在線
- **XL4015 電壓調整**：18.8V → 19.2V（原值偏低導致 Go2 行走時 Jetson 斷電）
- **USB 喇叭反覆斷連**：根因是振動 + 接觸不良，熱熔膠固定後解決
- **啟動腳本同步**：Jetson 舊版只有 whisper_local，已推新版含 SenseVoice 三級 fallback

### Day 5：Executive v0 State Machine
- **Package scaffold**：interaction_executive ROS2 package（setup.py/cfg/package.xml）
- **TDD**：27 tests GREEN（19 state machine + 6 api_id alignment + 2 obstacle edge cases）
- **State machine**：純 Python，6 狀態（IDLE/GREETING/CONVERSING/EXECUTING/EMERGENCY/OBSTACLE_STOP）
- **ROS2 node**：訂閱 5 event topics → /tts + /webrtc_req + /executive/status(2Hz)
- **api_id 修正**：計畫裡 Damp/Sit/Stand 寫錯，已對齊 robot_commands.py 權威來源
- **Jetson 部署驗證**：`/executive/status` → `{"state": "idle"}` 確認

### Bug Fixes（審查報告 3 個 critical）
- **llm_bridge_node lock race**：acquire(False) fail 時 finally release 未持有的 lock → crash
- **sensevoice_server model null check**：model 未載入時直接 crash → 503
- **sensevoice_server blocking generate()**：async handler 裡跑 blocking call → run_in_executor

---

## Sprint Day 3 完成（3/30）

### 四核心桌測 + Go2 動作補驗
- **Phase 1 桌測**：10/10 PASS（face + speech + gesture + pose）
- **Phase 2 動作**：stop→stop_move 3x、thumbs_up→content 3x、PASS
- **驗證工具**：Foxglove layout（4-panel）+ verification_observer.py（5 topic → JSONL 882 筆）
- **模型策略收斂**：
  - ASR：SenseVoice cloud → SenseVoice local → Whisper local（三級 fallback）
  - LLM：Cloud Qwen2.5-7B → RuleBrain（**砍掉 Ollama 1.5B**，展示期要可預測不要半智能）
  - TTS：edge-tts + USB 喇叭 plughw:3,0
- **排查修復**：USB 喇叭未插、麥克風 device drift 24→0、LLM endpoint 直連→localhost tunnel、observer QoS import

### 硬體上機（3/30 晚完成）
- **供電**：Go2 BAT (XT30, 28.8V) → XL4015 DC-DC 降壓 → 19V → Jetson DC jack
- **固定**：Jetson + D435 + USB 麥克風 + USB 喇叭全部上 Go2
- **Bring-up**：full demo 10 window 啟動成功，ASR/LLM/TTS 鏈路通
- **已知問題**：
  - 喇叭 USB 間歇斷開（已束帶固定，待觀察）
  - 麥克風 device drift（啟動腳本 device=24 但實際=0，每次需確認）
  - LLM SSH tunnel 需手動開

### 結論
- Day 3 超進度：桌測 + 硬體上機一天完成（原定兩天）
- 明天 Day 4 只剩穩定性驗證（3x 重開機 + 行走 + 熱測試）

---

## Sprint Day 2 完成（3/29）

### ASR 替換：SenseVoice 三級 Fallback
- **SenseVoice cloud**（FunASR on RTX 8000）：92% correct+partial，0 幻覺，~600ms
- **SenseVoice local**（sherpa-onnx int8 on Jetson CPU）：92% correct+partial，0 幻覺，~400ms，352MB RAM
- **Whisper local**（最後防線）：52% correct+partial，8% 幻覺
- **Qwen3-ASR-1.7B** 也測了（96%），但延遲 2x、模型 8.5x，SenseVoice 更適合
- Fallback 鏈驗證通過：cloud 斷 → local SenseVoice → Whisper 全自動
- `sensevoice_server.py` 部署在 RTX 8000 GPU 1（1.1GB VRAM）
- 審計 #5 #6 #7 #9 安全修復

### 驗收標準
- [x] 固定音檔正確+部分 >= 80%（實測 92%）
- [x] 高風險 intent 誤判 = 0
- [x] Cloud → Local fallback 自動切換
- [ ] `ENABLE_ACTIONS` 尚未改回 true（等等量 A/B 補測再開）

---

## Sprint Day 1 完成（3/28）

### Baseline Contract
- **3/3 cold start PASS** + **1/1 crash recovery PASS**（1m26s < 3min）
- Topic graph 快照：51 topics, 16 nodes
- QoS runtime 驗證：全部符合靜態推導，`/state/tts_playing` TRANSIENT_LOCAL 確認
- Device mapping：mic card 24→0（device drift 確認），speaker plughw:3,0
- 新增 `scripts/clean_full_demo.sh`（全環境清理）
- 新增 `scripts/device_detect.sh`（USB 音訊裝置自動偵測，source 介面）
- 新增 `docs/operations/baseline-contract.md`（啟動順序 + QoS + SOP + 驗收記錄）

### 語音 Noisy Profile v1
- **問題：** Go2 伺服噪音下 Whisper 產生幻覺，垃圾 intent 觸發 Go2 危險動作
- **安全門：** `ENABLE_ACTIONS=false` 封鎖 llm_bridge + event_action_bridge 的 `/webrtc_req`
- **ASR 調校：** 3 組 A/B 測試（gain 8/10/12），固定音檔 controlled test
- **結果：** gain=8.0 + VAD start=0.02 是甜蜜點（64% 正確+部分），gain 更高反而噪音放大
- **Whisper 改善：** vad_filter=True + no_speech_threshold=0.6 + 擴充幻覺黑名單（6→22）
- **結論：** Whisper Small 在中文短句+噪音場景的上限已到，**明天優先研究替代 ASR（SenseVoice）**

---

## 最近完成（3/25）

### Jetson 四模組整合測試（3/25 晚）
- **四模組同跑**：face + speech + gesture + pose，不 OOM、不互卡 ✅
- **人臉→LLM 問候**：偵測 roy → WELCOME → TTS「roy 你好」✅
- **手勢→Go2 動作**：stop/thumbs_up 正確觸發 ✅
- **語音 TTS**：edge-tts + USB 喇叭播放正常 ✅
- **語音 ASR**：Whisper CUDA float16 warmup 5.9s OK，但 USB mic 收音弱，需靠近或加 gain ⚠️
- **已修問題**：Whisper compute_type int8→float16、LD_LIBRARY_PATH 帶入 ROS_SETUP、silent exception 加 log
- **已知問題**：USB device index 重開機後會飄（mic 24→0, speaker hw:3,0→hw:1,0）、debug_image 需 resize 降頻寬

### 深度審計
- 7 軸並行掃描 + 4 類 web research = 99 findings
- Decision Packet（Keep/Fix/Explore 路線圖）
- Pre-flight Checklist（3/26 整合日逐項驗證）
- Demo Gap Analysis（A ~70% / B ~75% / C ~25%）

### Code 修復（4 commits）
- **event_action_bridge rewiring**：改訂閱 interaction_router 輸出，消除雙重消費
- **TTS guard**：stop/fall_alert 永遠通過，其他 gesture TTS 播放中 skip
- **vision_perception setup.cfg**：修正 executable 安裝路徑
- **Full demo 啟動腳本全面對齊**：USB mic/speaker、edge-tts、router required、Ollama fallback、sleep 15s（Whisper warmup）
- **tts_node**：11 個 silent exception 補 log + destroy_node()
- **YuNet default**：legacy → 2023mar

### Repo 瘦身
- 206 files 刪除，~24K lines，~144MB
- go2_omniverse、ros-mcp-server、camera、coco_detector、docker、src 等
- 過時腳本清理（18 個 speech/nav2/一次性腳本）
- .gitignore 完善

### 文件更新
- interaction_contract.md v2.1（3 新 topic、gesture enum、發布者名稱、LLM 型號）
- 4 份模組 README 全部對齊實作（語音/人臉/手勢/姿勢）
- mission/README.md 選型對齊
- CLAUDE.md 日期 + hook install + 腳本引用

### CI 強化
- test_event_action_bridge.py 加入 fast-gate（15 tests）
- Topic contract check 改 blocking（FAIL → exit 1）
- Git pre-commit hook（py_compile + contract + smart-scope tests）
- 三層品質閘門：Claude hooks → git pre-commit → GitHub Actions

### 依賴管理
- 3 個 setup.py install_requires 補齊
- requirements-jetson.txt 新建

### 研究文件
- `docs/research/2026-03-25-object-detection-feasibility.md`（YOLO26n，32KB）
- `docs/research/2026-03-25-reactive-obstacle-avoidance.md`（D435 避障，34KB）
- `docs/research/2026-03-25-go2-sdk-capability-and-architecture.md`（SDK 能力 + Clean Architecture 藍圖，41KB）

## Sprint B-prime（3/28-4/7，一人衝刺）

> 完整每日任務見 [`docs/mission/sprint-b-prime.md`](../docs/mission/sprint-b-prime.md)

| Day | 日期 | 主題 | 驗收標準 |
|:---:|------|------|---------|
| 1 | 3/28 | Baseline Contract | 3x cold start + 1x crash recovery ✅ |
| 2 | 3/29 | ASR 替換：可順暢溝通 | 正確+部分 >= 80%，高風險誤判 = 0 ✅ |
| **3** | **3/30** | **四核心桌測 + 動作補驗** | **10/10 PASS + Go2 動作 PASS ✅** |
| **4** | **3/31** | **硬體穩定性 GATE C** | **3x 重開機 + 行走 + 30min 56°C + USB 穩定 ✅** |
| **5** | **3/31** | **Executive v0 State Machine** | **27 tests + ROS2 node + Jetson 部署 ✅** |
| **6** | **4/1** | **ASR 修復 + Executive 整合 + 上機驗收** | **Gate A 4/5 ✅ Gate B 6/6 ✅ Gate C FAIL（噪音）** |
| 7 | 4/3 | 導航避障：D435 Depth | 7 tests + ROS2 node + 10x 防撞 |
| 8 | 4/4 | 導航避障：Hardening | 30x 防撞 + Pass/Warning/Fail 判定 |
| 9 | 4/5 | 物體辨識 Hard Gate | Go/No-Go → Phase 0（4-6h timebox）|
| 10 | 4/6 | Freeze + Hardening | Demo A 30 輪 + Demo B 5 輪 + crash drill |
| 11 | 4/7 | Handoff Day | docs 重組 + Starlight scaffold + 分工文件 |

### 砍刀順序（時程爆炸時）
1. 物體辨識 → 2. 硬體擴張 → 3. Executive 完整版 → 4. 導航避障

## 待辦（Sprint 後 / 4/9 團隊接手）

- Demo A 30 輪持續監控
- Studio 後端開發（FastAPI + WebSocket bridge）
- Starlight 文件站 + 展示站
- 文件繳交 Ch1-5（4/13 硬底線）
- Flake8 改 blocking
- Jetson 硬編碼路徑清理

## 里程碑

| 日期 | 事項 |
|------|------|
| **3/26** | **四模組整合日 + 教授會議** ✅ |
| **3/27** | **Sprint B-prime 規劃完成** ✅ |
| **3/28** | **Sprint Day 1 — Baseline Contract PASS** ✅ |
| 3/29-30 | 硬體上機（可跑→可用） |
| 3/31-4/1 | Executive v0 開發 + 整合 |
| 4/2-3 | 導航避障開發 + 30 次防撞 |
| 4/4 | 物體辨識 Hard Gate |
| 4/5-6 | Freeze + Hardening |
| **4/7** | **Handoff Day** |
| **4/9** | **教授會議 + 團隊分工啟動** |
| **4/13** | **文件繳交（硬底線）** |
| **4/16** | **卓斯科技線上會議（暫定）** |
| **5/16** | **省夜 Demo（暖身展示）** |
| **5/18** | **正式展示／驗收** |
| **6 月** | **口頭報告** |
