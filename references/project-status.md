# 專案狀態

**最後更新**：2026-03-26（3/26 會議決策 + 時程更新 + 物體辨識策略調整 + 審計修復 4 項）
**硬底線**：2026/4/13 文件繳交，5/16 省夜 Demo，5/18 正式展示，6 月口頭報告

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **Demo ready** | 3/25 | edge-tts + fast path + Cloud→Ollama→RuleBrain，Whisper CUDA float16 OK，USB mic 收音弱需調 gain |
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

## 待辦（按優先序）

### 3/26 整合日（已完成）
1. Deploy to Jetson（rsync + colcon build）
2. `bash scripts/start_full_demo_tmux.sh` — 10 window cold start
3. 四模組同跑不 OOM（RAM < 6.5GB）
4. face QoS 改動上機正常（debug_image 有影像）
5. 語音與視覺不互相卡住（Whisper CUDA + MediaPipe CPU）
6. 基本事件進出（你好→回應、stop→停、人臉→問候）

### 整合後（3/27-4/6）
7. Demo A 30 輪驗收 ≥ 90%
8. Demo B E2E（手勢→Go2 真機 5 輪）
9. tts_node silent exceptions 上機驗證
10. Flake8 改 blocking（確認違規量後）

### 4/13 前
11. 物體辨識 Phase 0-3（YOLO26n，預設目標，~3 天）
12. D435 反應式避障 Phase 0（~10-12hr，尚未測試 D435+Go2 導航）
13. 文件繳交（Ch1-5，分工見上方）
14. 介紹網站基本架構（硬體介紹、模型介紹、Demo 截圖/影片）

### 系統風險
14. interaction_executive 空殼 → py_trees explore
15. Demo C scope 收斂（Studio WebSocket bridge）
16. Jetson 硬編碼路徑（52 files）

## 里程碑

| 日期 | 事項 |
|------|------|
| **3/26** | **四模組整合日 + 教授會議** ✅ |
| 3/26 | 前端網站截止 |
| 3/27-4/2 | 整合測試 + Demo A/B 驗收 + 文件撰寫 |
| 4/2 | 物體辨識開發啟動（預設目標策略） |
| 4/6 | P0 穩定化（Demo A ≥ 90%） |
| **4/9** | **教授會議（檢視文件+進度）** |
| **4/13** | **文件繳交（硬底線）** |
| **4/16** | **卓斯科技線上會議（暫定）** |
| **5/16** | **省夜 Demo（暖身展示）** |
| **5/18** | **正式展示／驗收** |
| **6 月** | **口頭報告** |
