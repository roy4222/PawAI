# 語音主路徑 30 輪驗收 — 設計文件

> 日期：2026-03-14
> 目標：將 Phase 1-4 已通過的本地保底鏈驗成可交付狀態
> 主線：`no-VAD → ASR → Intent/Template Reply → TTS → Go2 播放`
> 硬底線：2026/4/13 Demo，3/16 交付清單需通過此驗收

---

## 1. 問題定義

Phase 1-4 各自已通過，但缺乏端到端的可重複驗證：

- 沒有 30 輪統計數據（命中率、延遲、播放成功率）
- 啟動環境不乾淨，重複節點互相干擾，測試結果不可信
- `Consent to send expired` 連線穩定化尚未處理

**本設計解決前兩項**：30 輪統計 + clean-start 固化。連線穩定化列為獨立後續任務。

---

## 2. 設計決策摘要

| 決策 | 選擇 | 理由 |
|------|------|------|
| 測試觸發方式 | 人工逐輪講 + energy VAD 自動分段 | 貼近真實使用，不是全自動固定窗口 |
| 測試句安排 | 混合制：15 輪固定 + 15 輪自由 | 固定句做 baseline，自由句測變體覆蓋 |
| 數據收集方式 | Observer node（方案 B） | 可重複用、不靠 log scraping、職責乾淨 |
| 測試定義 | 獨立 YAML 檔 | 可版控、改句不改 code |
| 環境清理 | 獨立 `clean_speech_env.sh` | 清理與啟動分離，可被多個腳本重用 |

---

## 3. 元件設計

### 3.1 `speech_test_observer` node

**職責**：純觀測 + 記錄。不控制流程、不 kill process、不觸發 TTS。

**套件歸屬**：`speech_processor`（與其他語音 node 同套件）

#### 訂閱 Topic

| Topic | 訊息型別 | 抓什麼 |
|-------|---------|--------|
| `/asr_result` | `String` (JSON) | `text`, `provider`, `latency_ms`, `session_id` |
| `/event/speech_intent_recognized` | `String` (JSON) | `intent`, `confidence`, `text`, `session_id`, `latency_ms` |
| `/state/interaction/speech` | `String` (JSON) | `state` 欄位變化（`LISTENING`→`ASR`→`IDLE`），推算 speech_start/end |
| `/tts` | `String` | TTS 輸入文字（純文字，無 session_id） |
| `/webrtc_req` | `go2_interfaces/WebRtcReq` | `api_id` 判斷播放狀態 |

> **設計注意**：no-VAD 主線下 `stt_intent_node` 的 energy VAD 是內部邏輯，不發布 `/event/speech_activity`。
> Observer 以 `/asr_result`（帶 `session_id` 的第一個事件）作為 session 起始信號，
> 並用 `/state/interaction/speech` 的 `state` 變化推算 `speech_start_ts`（state 從 `IDLE` 變為 `LISTENING`）
> 和 `speech_end_ts`（state 從 `LISTENING` 變為 `ASR`）。
> `e2e_latency_ms` 定義為 `asr_ts`（收到 `/asr_result` 的 wall clock）到 `webrtc_play_start_ts`。

#### WebRTC api_id 映射（已核實）

來源：`go2_robot_sdk/domain/constants/webrtc_topics.py:69-72`

| api_id | 常數名 | Observer 用途 |
|--------|--------|--------------|
| 4001 | `START_AUDIO` | 記錄 `webrtc_play_start_ts` |
| 4002 | `STOP_AUDIO` | 記錄 `webrtc_play_end_ts` |
| 4003 | `SEND_AUDIO_BLOCK` | 累計 `audio_chunks_count` + 記錄 `last_audio_chunk_ts` |
| 4004 | `SET_VOLUME` | 忽略 |

#### Session 聚合：RoundRecord

以 `session_id` 為 key，每個 session 建一個 `RoundRecord`：

```
RoundRecord:
  session_id: str
  round_id: int                  # 自動遞增
  mode: "fixed" | "free"         # 來自 set_round_meta
  expected_intent: str | ""      # 來自 set_round_meta
  utterance_text: str | ""       # 來自 set_round_meta
  speech_start_ts: float         # /state/interaction/speech IDLE→LISTENING
  speech_end_ts: float           # /state/interaction/speech LISTENING→ASR
  asr_ts: float                  # /asr_result 收到時的 wall clock（session 起始信號）
  asr_text: str                  # /asr_result.text
  asr_latency_ms: float          # /asr_result.latency_ms（node 自報）
  intent_ts: float               # /event/speech_intent_recognized 收到時的 wall clock
  intent: str                    # predicted intent
  intent_confidence: float
  intent_latency_ms: float       # node 自報
  tts_ts: float                  # /tts 收到時的 wall clock
  tts_text: str
  webrtc_play_start_ts: float    # api_id 4001
  webrtc_play_end_ts: float      # api_id 4002
  last_audio_chunk_ts: float     # api_id 4003 最後一塊
  audio_chunks_count: int        # api_id 4003 計數
  e2e_latency_ms: float          # asr_ts → webrtc_play_start（見下方定義）
  match: "hit" | "miss" | "n/a" # expected vs predicted
  status: "complete" | "partial" | "timeout" | "orphan"
  correlated_by_time: bool       # TTS/webrtc 是否靠時序推定
  notes: str
```

#### TTS / webrtc_req 時序關聯

`/tts` 和 `/webrtc_req` 沒有 `session_id`，用時序關聯：

- 參數：`tts_correlation_window_s`（預設 `3.0`，可配置）
- Intent 收到後，窗口內的第一個 `/tts` 和 `/webrtc_req` 4001 歸入同一輪
- 超時未收到標記對應欄位為空 + `status=partial`
- 每筆記錄 `correlated_by_time=true` 標記

> 長期改善方向：讓 reply/TTS 鏈也帶 `session_id`，消除時序推定。

#### Round metadata 注入（ROS2 Service）

```
Service: /speech_test_observer/set_round_meta
  Request:  { round_id: int, mode: str, expected_intent: str, utterance_text: str }
  Response: { ok: bool }
```

**實作方式**：使用 `rcl_interfaces/srv/SetParameters` 或 topic-based request/response 模式
（用 `/speech_test_observer/round_meta_req` publish JSON + `/speech_test_observer/round_meta_ack` subscribe），
避免自訂 `.srv` 檔案以減少 interface package 修改。若後續需要正式化再升級為自訂 `.srv`。

**一次性消費規則**：
- Service 寫入 `pending_round_meta`
- 下一個新 `session_id` 到來時綁定，**立即清空**
- 連續呼叫 → 後一次覆蓋前一次
- 超過 `round_meta_timeout_s`（預設 `30.0`）未收到新 session → 清空 + WARN log

**round_id 優先順序**：`set_round_meta` 注入的 `round_id` 優先。Observer 內部自動遞增的計數僅作為 fallback（metadata 未注入時使用）。

#### 報告生成（ROS2 Service）

```
Service: /speech_test_observer/generate_report
  Request:  {}
  Response: { csv_path: str, summary_path: str, ok: bool }
```

**實作方式**：同上，使用 topic-based request/response 或直接由 shell 腳本發送 `ros2 topic pub` 觸發。

#### 參數一覽

| 參數 | 預設 | 說明 |
|------|------|------|
| `output_dir` | `test_results/` | CSV + summary 輸出目錄 |
| `tts_correlation_window_s` | `3.0` | TTS/webrtc 時序關聯窗口 |
| `round_meta_timeout_s` | `30.0` | pending metadata 超時清空 |
| `round_complete_timeout_s` | `10.0` | 一輪從 speech_start 到 play_end 的最大等待 |

---

### 3.2 YAML 測試定義

**檔案位置**：`test_scripts/speech_30round.yaml`

```yaml
test_name: "語音主路徑 30 輪驗收"
version: 1
description: "no-VAD 主線端到端：講話 → ASR → Intent → TTS → Go2 播放"

fixed_rounds:
  - round_id: 1
    utterance: "你好"
    expected_intent: "greet"
  - round_id: 2
    utterance: "嘿你好嗎"
    expected_intent: "greet"
  - round_id: 3
    utterance: "過來"
    expected_intent: "come_here"
  - round_id: 4
    utterance: "到我這邊來"
    expected_intent: "come_here"
  - round_id: 5
    utterance: "停"
    expected_intent: "stop"
  - round_id: 6
    utterance: "不要動"
    expected_intent: "stop"
  - round_id: 7
    utterance: "拍照"
    expected_intent: "take_photo"
  - round_id: 8
    utterance: "幫我拍一張"
    expected_intent: "take_photo"
  - round_id: 9
    utterance: "狀態"
    expected_intent: "status"
  - round_id: 10
    utterance: "你現在怎麼樣"
    expected_intent: "status"
  - round_id: 11
    utterance: "哈囉"
    expected_intent: "greet"
  - round_id: 12
    utterance: "你來一下"
    expected_intent: "come_here"
  - round_id: 13
    utterance: "停住"
    expected_intent: "stop"
  - round_id: 14
    utterance: "照相"
    expected_intent: "take_photo"
  - round_id: 15
    utterance: "你還好嗎"
    expected_intent: "status"

free_rounds:
  - round_id: 16
    notes: "同義句變體"
  - round_id: 17
    notes: "同義句變體"
  - round_id: 18
    notes: "同義句變體"
  - round_id: 19
    notes: "口語化 / 帶停頓"
  - round_id: 20
    notes: "口語化 / 帶停頓"
  - round_id: 21
    notes: "口語化 / 帶停頓"
  - round_id: 22
    notes: "應判為 unknown 的句子"
  - round_id: 23
    notes: "應判為 unknown 的句子"
  - round_id: 24
    notes: "較長聊天句"
  - round_id: 25
    notes: "較長聊天句"
  - round_id: 26
    notes: "自由測試"
  - round_id: 27
    notes: "自由測試"
  - round_id: 28
    notes: "自由測試"
  - round_id: 29
    notes: "自由測試"
  - round_id: 30
    notes: "自由測試"
```

**設計決策**：
- `fixed_rounds` / `free_rounds` 明確分開，不靠空欄位判斷
- 每個 `SUPPORTED_INTENTS` 各 3 輪 = 15 輪（`greet`, `come_here`, `stop`, `take_photo`, `status`）
- 注意：`sit`/`stand`/`chat` 不在 `stt_intent_node.py` 的 `SUPPORTED_INTENTS` 中，不可用於 fixed rounds
- `free_rounds` 有 `notes` 提示測試方向，不強制特定句子
- `round_id` 全域唯一遞增

---

### 3.3 `scripts/clean_speech_env.sh`

**職責**：清理語音測試環境，確保下一次啟動是乾淨狀態。

**清理順序**：

| 步驟 | 動作 | 說明 |
|------|------|------|
| 1 | Kill speech tmux sessions | `asr-tts-no-vad`, `speech-e2e`, `speech-test` |
| 2 | pkill speech nodes | `stt_intent_node`, `intent_tts_bridge_node`, `tts_node`, `speech_test_observer` |
| 3 | 等待退出 | 輪詢最多 5 秒，確認 process 真正消失 |
| 4 | 檢查殘留 | `ros2 node list` 過濾 speech 相關，若有殘留則 WARN |
| 5 | 輸出狀態 | 列出清理結果（killed N processes, M sessions） |

**可選旗標**：
- `--with-go2-driver`：同時清理 `go2_driver_node`（僅診斷用，預設不啟用）

**不做的事**：
- 預設不碰 `go2_driver_node`
- 不做 `colcon build`
- 不刪 log 或測試結果檔案

**退出碼**：
- `0`：環境已乾淨
- `1`：有殘留 process 無法清除（WARN + 列出 PID）

**整合方式**：現有 `start_asr_tts_no_vad_tmux.sh` 開頭的手動 kill 邏輯替換為：

```bash
bash "$(dirname "$0")/clean_speech_env.sh" || { echo "[ERROR] clean_speech_env failed"; exit 1; }
```

> 用子 shell 執行（`bash`）而非 `source`，避免 `clean_speech_env.sh` 的 `exit 1` 直接結束呼叫者的 shell。

---

### 3.4 `scripts/run_speech_test.sh`

**用途**：一鍵執行 30 輪測試的 orchestration 腳本。

**參數**：

```
run_speech_test.sh [--yaml path] [--skip-build] [--skip-driver]
```

- `--yaml`：測試定義檔路徑（預設 `test_scripts/speech_30round.yaml`）
- `--skip-build`：跳過 `colcon build`
- `--skip-driver`：假設 `go2_driver_node` 已在跑，不另起

**流程**：

```
1. source clean_speech_env.sh
2. colcon build（除非 --skip-build）
3. 啟動主線 nodes + health check
4. 啟動 speech_test_observer
5. 讀 YAML → 測試迴圈
6. 呼叫 generate_report service
7. 輸出摘要到 terminal + 寫檔
```

**Health check 分層**：

| Node | 等待 topic | Timeout |
|------|-----------|---------|
| `go2_driver_node` | `/webrtc_req` 有 subscriber | 15s |
| `intent_tts_bridge_node` | `/tts` 有 publisher | 15s |
| `tts_node` | `/webrtc_req` 有 publisher | 15s |
| `speech_test_observer` | service 可呼叫 | 15s |
| `stt_intent_node` | `/event/speech_intent_recognized` 有 publisher | **45s** |

超時未就緒 → 報錯退出，不開始測試。

> **注意**：這是最低限度 health check（topic 已註冊）。`stt_intent_node` 在 Whisper 模型載入完成前就會註冊 publisher，
> 但此時尚無法處理音訊。建議 orchestration 腳本在第一輪前加一個 warmup 提示（「請說任意一句話做暖機，此輪不計分」）。

**操作者互動**：

- Fixed round：
  ```
  [Round 1/30] [FIXED] 請說：「你好」
  expected_intent: greet
  （準備好後按 Enter）
  ```
- Free round：
  ```
  [Round 16/30] [FREE] 自由講
  提示：同義句變體
  expected_intent?（可留空，直接 Enter 跳過）：
  （準備好後按 Enter）
  ```
- 每輪結束即時顯示：`[Round 1] intent=greet match=✓ e2e=1823ms status=complete`
- 輸入 `q` 可提前結束（已完成輪次仍輸出報告）

---

### 3.5 輸出格式

#### Raw CSV

檔案：`test_results/speech_test_YYYYMMDD_HHMMSS.csv`

欄位（逐輪一行）：

```
round_id, mode, utterance, expected_intent, session_id,
speech_start_ts, speech_end_ts,
asr_ts, asr_text, asr_latency_ms,
intent_ts, intent, intent_confidence, intent_latency_ms,
tts_ts, tts_text,
webrtc_play_start_ts, webrtc_play_end_ts, last_audio_chunk_ts, audio_chunks_count,
e2e_latency_ms, match, status, correlated_by_time, notes
```

#### Summary JSON

檔案：`test_results/speech_test_YYYYMMDD_HHMMSS_summary.json`

```json
{
  "test_name": "語音主路徑 30 輪驗收",
  "yaml_file": "test_scripts/speech_30round.yaml",
  "date": "2026-03-14T15:30:00",
  "total_rounds": 30,
  "completed": 28,
  "status_breakdown": {
    "complete": 26,
    "partial": 2,
    "timeout": 0,
    "orphan": 0
  },
  "fixed_rounds": {
    "total": 15,
    "hit": 13,
    "miss": 1,
    "empty": 1,
    "accuracy": 0.867
  },
  "free_rounds": {
    "total": 15,
    "with_expected": 8,
    "hit": 6,
    "miss": 1,
    "unknown": 1,
    "no_expected": 7
  },
  "latency": {
    "e2e_median_ms": 2100,
    "e2e_p90_ms": 3200,
    "e2e_max_ms": 4500,
    "asr_median_ms": 600,
    "asr_max_ms": 1200,
    "tts_ok_rate": 0.93,
    "play_ok_rate": 0.89
  },
  "pass_criteria": {
    "fixed_accuracy_ge_80pct": { "threshold": 0.80, "actual": 0.867, "pass": true },
    "e2e_median_le_3500ms": { "threshold": 3500, "actual": 2100, "pass": true },
    "e2e_max_le_6000ms": { "threshold": 6000, "actual": 4500, "pass": true },
    "play_ok_rate_ge_80pct": { "threshold": 0.80, "actual": 0.89, "pass": true }
  },
  "grade": "PASS"
}
```

#### Summary 欄位定義

| 欄位 | 定義 |
|------|------|
| `hit` | `predicted_intent == expected_intent` |
| `miss` | `predicted_intent != expected_intent`，且 ASR 有輸出文字 |
| `empty` | ASR 沒有回傳文字（空字串），intent 無法判定 |
| `unknown` | `predicted_intent == "unknown"`（intent 規則未命中） |
| `accuracy` | `hit / total`（包含 empty 和 miss，不排除任何輪次） |
| `tts_ok_rate` | 有收到 `/tts` 的輪次佔 `completed` 的比例 |
| `play_ok_rate` | 有收到 `api_id=4001` 的輪次佔 `completed` 的比例 |
| `no_expected` | free_rounds 中操作者未填 `expected_intent` 的輪次，不參與命中率計算 |

#### Grade 判定邏輯

| Grade | 條件 |
|-------|------|
| `PASS` | 所有 pass_criteria 都通過 |
| `MARGINAL` | 恰好一項未通過，且偏離門檻 ≤ 10%（見下方公式） |
| `FAIL` | 兩項以上未通過，或單項偏離門檻 > 10% |

**MARGINAL 偏離計算公式**：
- 越高越好的指標（accuracy, play_ok_rate）：`deviation = (threshold - actual) / threshold`，例如 accuracy 門檻 0.80、實際 0.75 → deviation = 6.25% → MARGINAL
- 越低越好的指標（e2e_median, e2e_max）：`deviation = (actual - threshold) / threshold`，例如 e2e_median 門檻 3500ms、實際 3800ms → deviation = 8.6% → MARGINAL

門檻值來源：`docs/語音功能/jetson-MVP測試.md` §14.1，不放寬。

---

## 4. 檔案變更清單

| 動作 | 檔案 | 說明 |
|------|------|------|
| 新增 | `speech_processor/speech_processor/speech_test_observer.py` | Observer node |
| 新增 | `test_scripts/speech_30round.yaml` | 30 輪測試定義 |
| 新增 | `scripts/clean_speech_env.sh` | 環境清理腳本 |
| 新增 | `scripts/run_speech_test.sh` | 測試 orchestration 腳本 |
| 修改 | `speech_processor/setup.py` | 新增 `speech_test_observer` entry_point |
| 修改 | `scripts/start_asr_tts_no_vad_tmux.sh` | 開頭改用 `source clean_speech_env.sh` |

---

## 5. 不做的事

- 不做 LLM 整合（Phase 5）— 先驗本地保底鏈
- 不做 `Consent to send expired` 連線修復 — 獨立後續任務
- 不做英文 Piper 模型切換
- Observer 不做流程控制、不 kill process
- `clean_speech_env.sh` 預設不碰 `go2_driver_node`
