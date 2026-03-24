# 專案狀態

**最後更新**：2026-03-24（edge-tts + fast path，已知 intent E2E ~3.4s）
**硬底線**：2026/4/13 文件繳交，五月展示

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **edge-tts + fast path** | 3/24 | 已知 intent ~3.4s，LLM path ~6s，edge-tts 主線 |
| 人臉 (face_perception) | Jetson smoke 通過 | 3/18 | QoS 3/23 已修（RELIABLE→BEST_EFFORT），待上機驗證 |
| 手勢 (vision_perception) | Phase 1 完成 | 3/23 | Gesture Recognizer 模式穩定，23 unit tests |
| 姿勢 (vision_perception) | Phase 1 完成 | 3/23 | MediaPipe Pose CPU 18.5 FPS |
| LLM (llm_bridge_node) | 本地+雲端+fast path | 3/24 | fast path 跳 LLM，Ollama 1.5B 本地，Cloud 7B 備用 |
| Studio (pawai-studio) | 前端開發中 | 3/16 | Next.js，前端截止 3/26 |
| CI | 14 test files, 198 cases | 3/23 | fast-gate + flake8 report-only |
| interaction_executive | 空殼 | — | 系統無統一中控，事件雙重消費風險 |

## 最近完成（3/24）

- **外接 USB 麥克風+喇叭驗證通過**（E2E: mic → ASR → intent → TTS → speaker）
- tts_node 新增 `local_output_device` 參數，`_play_locally()` 改用 aplay 指定 ALSA device
- start_llm_e2e_tmux.sh 預設改為 USB 外接設備（可用環境變數切回 HyperX/Megaphone）
- stt_intent_node 新增 `mic_gain` 參數：VAD 用原始 RMS、錄音送 ASR 前再放大（gain x4 → ASR 2/8→4/5）
- **qwen2.5:1.5b 本地 LLM 驗證通過**：JSON parse 6/6，中文穩定，建議為本地 fallback 主力
- Echo 自激 5/5 無觸發，cooldown 1000ms 足夠
- 本地 E2E 延遲基線：P50 8.1s / P95 13.6s
- **edge-tts 整合**：合成 P50 0.72s（vs Piper 2.0s），Piper 自動 fallback
- **intent fast path**：greet/stop/sit/stand + conf >= 0.8 跳過 LLM → E2E ~3.4s
- **reply_text 硬截斷 12 字**：小模型不遵守 prompt 限制，code 層面強制
- **max_tokens 120→80**：JSON envelope 50 tok + 短 reply 足夠

### 3/23

- 4-agent 全面審查（81 項發現）→ `docs/audit/2026-03-23-full-audit.md`
- CI 1→14 測試擴充 + pytest-cov coverage
- greet 去重 cooldown（5s）+ wave→hello 退讓
- face QoS 修正 + Go2 api_id 常數化
- bare except 修復 + Dependabot 啟用
- intent_classifier / llm_contract 從 node 抽出為純 Python 模組

## 待辦（按優先序）

### 必須上機驗證（下次 Jetson）
1. face QoS 改動 → debug_image 仍有影像
2. speech 模組抽取 → stt_intent_node 啟動正常
3. greet dedup → 說「你好」+ 有人走進 → 只 1 次 hello
4. stop 不受 cooldown → 說「停」+ 做停手勢 → stop 正常

### 系統風險（4/13 前）
5. 事件雙重消費完整版 → interaction_executive
6. Required status checks → GitHub 保護規則
7. Flake8 425 違規清理

### 設備到貨後（已完成 3/24）
8. ~~外接喇叭+麥克風驗證~~ ✅ 3/24 E2E 通過
9. VAD 斷句優化 → 目標 < 2s
10. 三模型同跑測試 → face + gesture + pose GPU 預算

## 里程碑

| 日期 | 事項 |
|------|------|
| 3/26 | 前端網站截止 |
| 3/26 – 4/2 | 四功能整合測試 |
| 4/6 | P0 穩定化（Demo A/C ≥ 90%） |
| **4/13** | **文件繳交** |
| **五月** | **展示／驗收** |
