# PawAI 全面深度審查報告

**日期**：2026-03-23
**範圍**：架構 / ROS2 規範 / 程式碼品質 / CI-CD
**方法**：4 個專家 agent 並行審查，交叉驗證

---

## Executive Summary

| 面向 | Critical | High | Medium | Low |
|------|:--------:|:----:|:------:|:---:|
| 架構設計 | 2 | 6 | 8 | 5 |
| ROS2 規範 | 4 | 0 | 8 | 7 |
| 程式碼品質 | 3 | 7 | 6 | 4 |
| CI/CD | 2 | 6 | 8 | 5 |
| **合計** | **11** | **19** | **30** | **21** |

**最緊急的 5 件事**（4/13 前必須處理）：

1. **CI 沒有 required status checks** — 即使 CI 紅燈也能 merge PR
2. **`ros-tooling/action-ros-ci@master`** — 追蹤 master 隨時可能壞
3. **face_identity_node 相機 QoS 可能不匹配** — RELIABLE sub vs BEST_EFFORT pub = silent fail
4. **face_identity 事件雙重消費無仲裁** — 同一人可能觸發兩次 Hello
5. **3 處 bare `except: pass`** — 吞掉 SystemExit/KeyboardInterrupt

---

## 1. 架構設計

### Critical

**A-01: `interaction_executive` 空殼，系統無統一中控**
- 位置：`interaction_executive/`（4 個空目錄，無任何程式碼）
- 影響：語音流（`llm_bridge_node`）和視覺流（`interaction_router`）完全獨立運作，無仲裁
- 症狀：同一人出現 → `llm_bridge_node` 呼叫 LLM 生成問候 + `interaction_router` 發 welcome event → Go2 可能執行兩次 Hello

**A-02: `go2_driver_node` 是唯一硬體閘道，無備援**
- 位置：`go2_robot_sdk/go2_robot_sdk/go2_driver_node.py`
- 影響：此節點掛掉 = 整個系統失去對 Go2 的控制（TTS 無法播放、動作無法執行）
- 無 retry / watchdog / fallback 機制

### High

**A-03: Go2 動作定義散落三處，違反 DRY**
- `go2_robot_sdk/domain/constants/robot_commands.py` — ROBOT_CMD dict
- `speech_processor/speech_processor/llm_contract.py:16-22` — SKILL_TO_CMD（重複 api_id）
- `vision_perception/vision_perception/event_action_bridge.py:18-27` — GESTURE_ACTION_MAP（又重複）
- 三處不同步就出 bug

**A-04: `speech_processor` 越權包含 LLM 大腦**
- `llm_bridge_node` 同時處理 speech intent + face identity + LLM + Go2 動作
- 應屬於 `interaction_executive`，不是語音處理器

**A-05: `vision_perception` 混合感知與決策**
- `event_action_bridge`（Layer 3 bridge）和 `interaction_router`（Layer 3 融合）塞在 Layer 2 package

**A-06: GESTURE_WHITELIST 和 GESTURE_ACTION_MAP 不一致**
- `interaction_rules.py` WHITELIST: `{"stop", "point", "thumbs_up"}`
- `event_action_bridge.py` ACTION_MAP: `{"wave", "stop", "ok", "thumbs_up"}`
- `wave` 和 `ok` 在 bridge 有、whitelist 沒有；`point` 在 whitelist 有、bridge 沒有

**A-07: TTS 播放阻塞 ROS2 callback**
- `tts_node.py:762-836` — `time.sleep()` 在 subscription callback 中等待播放完成
- 播放 3 秒音訊 = 節點 3 秒無法處理其他 callback

**A-08: 伺服器 IP 硬編碼在 declare_parameter**
- `llm_bridge_node.py:149` — `"http://140.136.155.5:8000/v1/chat/completions"` 作為預設值
- `ros-mcp-server/server.py:3025` — `"http://140.136.155.5:8001"`

### Medium

- **A-09**: `event_action_bridge` 和 `llm_bridge_node` 都發布到 `/webrtc_req`，可能重複動作
- **A-10**: `interaction_router` 輸出的 `/event/interaction/*` 目前無訂閱者消費（懸空）
- **A-11**: LLM daemon thread 卡住 → `_llm_lock` 永不釋放 → 後續事件全跳過
- **A-12**: 無統一事件匯流排，新感知模組需改 2-3 個下游節點
- **A-13**: `intent_tts_bridge_node` 遺留程式碼仍在 setup.py 中，可能被誤啟動
- **A-14**: Topic 名稱字串散佈多個檔案，無共用常量
- **A-15**: `speech_processor.yaml` channels:1 vs 程式碼預設 channels:2 衝突
- **A-16**: `tts_node` 重複定義 `RTC_TOPIC` 常數（跨 package 邊界問題）

---

## 2. ROS2 規範

### Critical

**R-01: 過度使用 `std_msgs/String` 傳 JSON**
- 9 個核心 topic 全用 String + JSON，無型別安全
- 所有 subscriber 都有 `try: json.loads() except JSONDecodeError` boilerplate
- `ros2 topic echo` 只看到 JSON 字串，Foxglove 無法自動生成 panel
- 唯一的 custom msg `WebRtcReq` 反而是做對的例子

**R-02: face_identity_node 相機 QoS 不匹配風險**
- `face_identity_node.py:203` — 用預設 QoS (RELIABLE) 訂閱 D435
- `vision_perception_node.py:204-206` — 正確用 BEST_EFFORT
- D435 ROS2 driver 預設 BEST_EFFORT 發布 → RELIABLE sub 理論上收不到
- 但 CLAUDE.md 記錄「全通」→ 可能 Jetson 上 D435 driver 設為 RELIABLE，需確認

**R-03: 沒有任何 Lifecycle Node**
- 29 個 Node 全繼承 `rclpy.node.Node`
- `face_identity_node`（模型載入+D435）、`go2_driver_node`（WebRTC 連線）最需要 lifecycle 管理
- 目前靠 tmux script 控制啟動順序 + `pkill -9` 關閉

**R-04: `coco_detector` package.xml 依賴全缺**
- 完全沒有任何 `<depend>`，但程式碼用了 rclpy/sensor_msgs/vision_msgs/cv_bridge
- `setup.py` entry_point 缺 `:main`（`ros2 run` 無法啟動）

### Medium

- **R-05**: 版本號不一致（0.0.0 / 0.1.0 / 1.0.0 混用）
- **R-06**: 4 個套件缺 `<buildtool_depend>ament_python</buildtool_depend>`
- **R-07**: `go2_robot_sdk` setup.py `install_requires` 只有 `setuptools`
- **R-08**: `robot.launch.py` 和 `robot_cpp.launch.py` 80% 程式碼重複
- **R-09**: `Go2LaunchConfig.__init__` 在 module level 執行 side-effect
- **R-10**: 硬編碼 Jetson 路徑在 launch file default values
- **R-11**: 硬體斷線（D435/Go2）無重連機制、無 watchdog timer
- **R-12**: `webrtc_web.launch.py` 引用不存在的 `tts_node` executable

---

## 3. 程式碼品質

### Critical

**Q-01: 3 處 bare `except: pass`**
- `go2_connection.py:534` — 吞掉所有異常包含 SystemExit/KeyboardInterrupt
- `go2_omniverse/ros2.py:143-144`
- `benchmarks/scripts/bench_llm_local.py:163-164`

**Q-02: `pickle.load()` 無來源驗證**
- `face_identity_node.py:165` — pickle 可執行任意程式碼
- 應改用 JSON/safetensors 或至少驗證檔案 hash

**Q-03: 7 處 `except Exception: return None` 無 log**
- `tts_node.py:168,183,205,306,379,412,427` — AudioCache/TTSProvider 靜默吞掉異常

### High

**Q-04: God Methods**
- `face_identity_node.tick()` — 165 行，偵測+追蹤+識別+繪圖+發布全塞一起
- `VisionPerceptionNode._tick()` — 183 行，推理+分類+手勢+姿勢+debug
- `stt_intent_node.__init__()` — 75 行過長初始化

**Q-05: 超大檔案**
- `ros-mcp-server/server.py` — 3481 行（單一檔案包含所有 MCP 邏輯）
- `stt_intent_node.py` — 1009 行（ASR provider+VAD+錄音+intent 全混）
- `tts_node.py` — 888 行（5 個類別）

**Q-06: Dead Code**
- `tts_node.py:618-620` — 註解掉的 service 建立
- `go2_driver_node.py:454-467` — 3 個 CycloneDDS callback 只有 `pass`
- `stt_intent_node.py:9` — `import re` 已搬到 `intent_classifier.py` 但未移除
- `tts_node.py:86-88` — GOOGLE/AMAZON/OPENAI TTS enum 定義但無實作

**Q-07: Debug WAV 持續寫入 /tmp**
- `tts_node.py:783-789` — 每次 TTS 都寫 `/tmp/megaphone_debug_*.wav`

**Q-08: 核心節點零測試**
- `go2_driver_node.py`（501 行）— 零行為測試
- `tts_node.py`（888 行）— 零測試
- `stt_intent_node.py`（1009 行）— 只有抽出的 intent_classifier 被測
- `face_identity_node.py`（674 行）— 只有 utility 被測

**Q-09: face_identity_node.py 幾乎零型別標註**（~10% 覆蓋率）

**Q-10: `datetime.utcnow()` 棄用**（8 處，Python 3.12+ 會警告）

### Medium

- **Q-11**: `Dict[str, Any]` 大雜燴（`go2_driver_node`, `robot_data_service`）— 應用 TypedDict
- **Q-12**: 前端 `speech-panel.tsx`（342 行）和 `chat-panel.tsx`（308 行）過大
- **Q-13**: 前端 `USE_MOCK_DATA = true` 硬編碼，真實資料永不顯示
- **Q-14**: 前端 `as unknown as` 繞過型別（6 處 in `use-event-stream.ts`）
- **Q-15**: MD5 用於 TTS cache key（`tts_node.py:142`）— 應用 SHA-256
- **Q-16**: ROS2 參數宣告 boilerplate 重複（每節點 40-80 行）

---

## 4. CI/CD

### Critical

**C-01: 沒有 required status checks**
- Branch protection 有設 required review，但**沒有設 required checks**
- CI 紅燈也能 merge PR

**C-02: `ros-tooling/action-ros-ci@master`**
- 追蹤 master 分支，上游任何 breaking change 立即影響 CI
- 應改 `@v0.3` 或鎖定 commit SHA

### High

**C-03: Flake8 `--exit-zero`** — lint 形同虛設
**C-04: Dependabot 停用** — 公開 repo 無依賴漏洞掃描
**C-05: pip-audit / npm audit 缺失** — 13+12 個依賴未掃描漏洞
**C-06: ROS2 CI 無 path filter** — 修改 docs 也觸發 2.5 分鐘 build
**C-07: 前端零測試 + 後端只驗 import**
**C-08: Dismiss stale reviews 未啟用** — review 後可偷改程式碼

### Medium

- **C-09**: pip cache 未設定（fast-gate 每次重裝，浪費 ~10s）
- **C-10**: colcon test 形同虛設（setup.cfg 無 pytest 入口）
- **C-11**: Python syntax check 在 Tier 1 和 Tier 2 重複
- **C-12**: Tier 2 pip install 用 `|| true` 吞錯
- **C-13**: 無 pre-commit hooks（所有品質檢查只在 CI 跑）
- **C-14**: 無自動部署到 Jetson 的 CI（手動 rsync）
- **C-15**: Coverage 只上傳 artifact，無最低覆蓋率門檻
- **C-16**: 無 CODEOWNERS 檔案

---

## 交叉驗證：多個 agent 獨立發現的共同問題

以下問題被 2+ 個 agent 獨立指出，可信度最高：

| 問題 | 架構 | ROS2 | 品質 | CI |
|------|:----:|:----:|:----:|:--:|
| String+JSON 取代 custom msg | A | R-01 | | |
| Go2 動作定義散落三處 | A-03 | | | |
| face_identity QoS 不匹配 | | R-02 | | |
| 硬編碼 IP 140.136.155.5 | A-08 | | Q | |
| 無 Lifecycle Node | | R-03 | | |
| bare except: pass | | | Q-01 | |
| 核心節點零測試 | | | Q-08 | C-07 |
| Flake8 不 blocking | | | | C-03 |
| No required checks | | | | C-01 |

---

## 建議行動計畫

### 本週（4/13 前必做）

| # | 行動 | 風險 | 工時 |
|---|------|:----:|:----:|
| 1 | GitHub 設定 required status checks | 零 | 5 min |
| 2 | `action-ros-ci@master` → `@v0.3` | 零 | 1 min |
| 3 | 確認 face_identity_node 的 D435 QoS 實際行為 | 低 | 30 min |
| 4 | 修 3 處 bare `except: pass` | 低 | 15 min |
| 5 | ROS2 CI 加 path filter（避免 docs 觸發 build） | 零 | 10 min |
| 6 | 啟用 Dependabot | 零 | 5 min |

### 下一輪（展示前）

| # | 行動 | 風險 | 工時 |
|---|------|:----:|:----:|
| 7 | Flake8 blocking（先清違規） | 中 | 2-4 hr |
| 8 | 解決 face_identity 事件雙重消費 | 中 | 2 hr |
| 9 | Go2 動作定義統一到一處 | 低 | 1 hr |
| 10 | face_identity_node/vision_perception_node 加 watchdog | 低 | 1 hr |
| 11 | 移除 debug WAV 寫入 | 零 | 5 min |
| 12 | pickle.load 改 JSON 或加驗證 | 低 | 30 min |

### 長期（展示後）

| # | 行動 |
|---|------|
| 13 | 實作 `interaction_executive` 中控 |
| 14 | 核心 topic 改 custom msg |
| 15 | 核心節點遷移 LifecycleNode |
| 16 | 拆分 God Methods（tick, _tick） |
| 17 | 前端測試框架（Vitest + testing-library） |
| 18 | 自動部署 pipeline |
