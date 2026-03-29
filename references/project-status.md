# 專案狀態

**最後更新**：2026-03-29（Sprint Day 2 完成 — SenseVoice ASR 三級 fallback）
**硬底線**：2026/4/13 文件繳交，5/16 省夜 Demo，5/18 正式展示，6 月口頭報告

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **Demo ready** | 3/29 | SenseVoice cloud+local 三級 ASR fallback（92% correct+partial），edge-tts + Cloud→Ollama→RuleBrain |
| 人臉 (face_perception) | **整合測試通過** | 3/25 | YuNet 2023mar + SFace，偵測+識別+WELCOME 觸發+LLM 問候 全通 |
| 手勢 (vision_perception) | **整合測試通過** | 3/25 | Gesture Recognizer：stop/thumbs_up 正確觸發 Go2 動作 |
| 姿勢 (vision_perception) | **整合測試通過** | 3/25 | MediaPipe Pose CPU，四模組同跑正常 |
| LLM (llm_bridge_node) | 本地+雲端+fast path | 3/24 | Cloud 7B → Ollama 1.5B → RuleBrain 三級 fallback |
| Studio (pawai-studio) | 前端開發中 | 3/16 | Next.js，前端截止 3/26（已截止），後端 4/9 後啟動，WebSocket bridge 不存在 |
| CI | **16 test files, 214+ cases** | 3/25 | fast-gate + **blocking contract check** + git pre-commit hook |
| interaction_executive | 空殼 | — | 系統無統一中控，py_trees explore 排定 |
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
| **2** | **3/29** | **ASR 替換：可順暢溝通** | **正確+部分 >= 80%，高風險誤判 = 0** |
| 3-4 | 3/30-31 | 硬體上機：可跑+可用 | Jetson + D435 固定 + 3x 重開機 + 行走穩定 |
| 5 | 4/1 | Executive v0：State Machine | 19 tests pass + ROS2 node 啟動 |
| 6 | 4/2 | Executive v0：整合 | 5 邊界測試 + bridge 遷移 + 腳本同步 |
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
