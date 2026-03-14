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
| `/event/speech_activity` | `String` (JSON) | `speech_start` / `speech_end` + `session_id` |
| `/asr_result` | `String` (JSON) | `text`, `provider`, `latency_ms`, `session_id` |
| `/event/speech_intent_recognized` | `String` (JSON) | `intent`, `confidence`, `text`, `session_id`, `latency_ms` |
| `/tts` | `String` | TTS 輸入文字（純文字，無 session_id） |
| `/webrtc_req` | `go2_interfaces/WebRtcReq` | `api_id` 判斷播放狀態 |

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
  speech_start_ts: float         # /event/speech_activity
  speech_end_ts: float           # /event/speech_activity
  asr_ts: float                  # /asr_result 收到時的 wall clock
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
  e2e_latency_ms: float          # speech_start → webrtc_play_start
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

**一次性消費規則**：
- Service 寫入 `pending_round_meta`
- 下一個新 `session_id` 到來時綁定，**立即清空**
- 連續呼叫 → 後一次覆蓋前一次
- 超過 `round_meta_timeout_s`（預設 `30.0`）未收到新 session → 清空 + WARN log

#### 報告生成（ROS2 Service）

```
Service: /speech_test_observer/generate_report
  Request:  {}
  Response: { csv_path: str, summary_path: str, ok: bool }
```

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
    utterance: "坐下"
    expected_intent: "sit"
  - round_id: 12
    utterance: "坐好"
    expected_intent: "sit"
  - round_id: 13
    utterance: "站起來"
    expected_intent: "stand"
  - round_id: 14
    utterance: "起來"
    expected_intent: "stand"
  - round_id: 15
    utterance: "今天天氣怎麼樣"
    expected_intent: "chat"

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
- 每個核心 intent 各 2 輪 + `chat` 1 輪 = 15 輪
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
source "$(dirname "$0")/clean_speech_env.sh"
```

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

#### Grade 判定邏輯

| Grade | 條件 |
|-------|------|
| `PASS` | 所有 pass_criteria 都通過 |
| `MARGINAL` | 恰好一項未通過，且實際值在門檻的 90% 以內 |
| `FAIL` | 兩項以上未通過，或單項嚴重未達 |

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
