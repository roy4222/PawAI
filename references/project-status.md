# 專案狀態

**最後更新**：2026-03-25（深度審計 + blocker 修復 + repo 瘦身 + CI 強化 + 研究文件）
**硬底線**：2026/4/13 文件繳交，五月展示

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **Demo ready** | 3/24 | edge-tts + fast path + Cloud→Ollama→RuleBrain，silent exceptions 已補 log |
| 人臉 (face_perception) | Jetson smoke 通過 | 3/18 | QoS 已修，YuNet default 改 2023mar，待上機驗證 |
| 手勢 (vision_perception) | Phase 4 完成 | 3/23 | Gesture Recognizer 主線，23 + 15 tests（含 bridge 行為測試） |
| 姿勢 (vision_perception) | Phase 4 完成 | 3/23 | MediaPipe Pose CPU 18.5 FPS，L3 壓測通過 |
| LLM (llm_bridge_node) | 本地+雲端+fast path | 3/24 | Cloud 7B → Ollama 1.5B → RuleBrain 三級 fallback |
| Studio (pawai-studio) | 前端開發中 | 3/16 | Next.js，前端截止 3/26，WebSocket bridge 不存在 |
| CI | **16 test files, 214+ cases** | 3/25 | fast-gate + **blocking contract check** + git pre-commit hook |
| interaction_executive | 空殼 | — | 系統無統一中控，py_trees explore 排定 |
| 物體辨識 | **研究完成** | 3/25 | YOLO26n 可行性報告產出，CONDITIONAL GO，~3 天實作 |
| 導航避障 | **研究完成** | 3/25 | D435 ROI depth 主線，LiDAR No-Go，~10-12hr 實作 |

## 最近完成（3/25）

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

### 3/26 整合日（明天）
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
11. 物體辨識 Phase 0-3（YOLO26n，~3 天）
12. D435 反應式避障 Phase 0（~10-12hr）
13. 文件繳交準備

### 系統風險
14. interaction_executive 空殼 → py_trees explore
15. Demo C scope 收斂（Studio WebSocket bridge）
16. Jetson 硬編碼路徑（52 files）

## 里程碑

| 日期 | 事項 |
|------|------|
| **3/26** | **四模組整合日** |
| 3/26 | 前端網站截止 |
| 3/27-4/2 | 整合測試 + Demo A/B 驗收 |
| 4/2 | 物體辨識研究啟動 |
| 4/6 | P0 穩定化（Demo A ≥ 90%） |
| **4/13** | **文件繳交** |
| **五月** | **展示／驗收** |
