# Day 3 四核心驗證設計

**日期**：2026-03-30
**目的**：上機前桌測，確認四核心模組功能正常且共存穩定
**策略**：B（結構化 checklist）+ A（Foxglove 即時觀察）輕量版

---

## 交付物

1. **Foxglove Layout JSON** — `foxglove/day3-verification.json`
2. **Verification Observer Node** — `scripts/verification_observer.py`
3. **Verification Checklist** — 本文件 §3

---

## 1. Foxglove Layout

### Panel 配置

```
┌─────────────────────────┬──────────────────────────┐
│  /face_identity/        │  /vision_perception/     │
│    debug_image          │    status_image          │
│  (Image panel)          │  (Image panel)           │
├─────────────────────────┼──────────────────────────┤
│  Event Log              │  State Monitor           │
│  (RawMessages panel)    │  (RawMessages panel)     │
│  Topics:                │  Topics:                 │
│  - /event/face_identity │  - /state/perception/    │
│  - /event/interaction/  │      face               │
│      welcome            │  - /state/tts_playing    │
│  - /event/speech_       │                          │
│      intent_recognized  │                          │
│  - /event/gesture_      │                          │
│      detected           │                          │
│  - /event/pose_detected │                          │
└─────────────────────────┴──────────────────────────┘
```

- 上排：視覺化（D435 人臉 debug + vision 儀表板）
- 下左：四模組 event 流（即時觀察觸發）
- 下右：face state + TTS playing（判斷系統活性）
- 連線：`ws://<jetson-ip>:8765`

### 不含

- Go2 navigation topics（今天不測導航）
- `/state/interaction/speech`（資訊與 event 重複，先不塞）

---

## 2. Verification Observer

### 定位

單一 Python 腳本（非 ROS2 package），訂閱 event topics，每筆 append JSONL。
復用 `speech_test_observer` 的 JSONL 模式，但大幅簡化。

### 訂閱 Topics

| Topic | Message Type | 來源 |
|-------|-------------|------|
| `/event/face_identity` | `std_msgs/String` (JSON) | `face_identity_node` |
| `/event/interaction/welcome` | `std_msgs/String` (JSON) | `interaction_router` |
| `/event/speech_intent_recognized` | `std_msgs/String` (JSON) | `stt_intent_node` |
| `/event/gesture_detected` | `std_msgs/String` (JSON) | `vision_perception_node` |
| `/event/pose_detected` | `std_msgs/String` (JSON) | `vision_perception_node` |

### JSONL 欄位

```json
{
  "ts": 1711785600.123,
  "topic": "/event/gesture_detected",
  "source": "vision_perception_node",
  "event_type": "stop",
  "payload": { "...原始 JSON payload..." }
}
```

- `ts`：收到時的 `time.time()`（wall clock）
- `topic`：ROS2 topic 名稱
- `source`：從 payload 中提取（若有 `source` 欄位）或根據 topic 推斷
- `event_type`：從 payload 中提取（各 topic 的 `event_type` / `intent` / `gesture` / `pose` 欄位）
- `payload`：原始 JSON，原封保留

### 輸出

- 檔案：`logs/day3-verification-{YYYYMMDD-HHMMSS}.jsonl`
- 啟動時印：訂閱的 topic 列表
- Ctrl+C 結束時印：每個 topic 的 event count summary

### 執行方式

```bash
# 前提：已 source install/setup.zsh
python3 scripts/verification_observer.py
# 或指定輸出路徑
python3 scripts/verification_observer.py --output logs/my-test.jsonl
```

### 不做

- 不做 pass/fail 自動判定（事後 jq 查）
- 不建 ROS2 package（純 script）
- 不記 state topics（只記 event）
- 不做 UI

---

## 3. Verification Checklist

### 驗收流程

1. 啟動 `start_full_demo_tmux.sh`（ENABLE_ACTIONS=false）
2. 啟動 `verification_observer.py`
3. 開 Foxglove 連上 `ws://jetson-ip:8765`，載入 layout
4. 逐一執行 10 個 test case
5. 全過 → `ENABLE_ACTIONS=true` 重啟 → 補跑 case 6-7 確認 Go2 動作觸發
6. 結束後用 JSONL 比對 pass 條件

### 10 個 Test Case

| # | 模組 | Test Case | 操作 | Pass 條件 | 驗證 Topic |
|:-:|------|-----------|------|-----------|-----------|
| 1 | 人臉 | 人臉出現 | 站到 D435 前 1-2m | 3 秒內 `/event/face_identity` 出現 tracking 事件 | `/event/face_identity` |
| 2 | 人臉 | 已知人臉辨識 | 已註冊的人站到鏡頭前 | `event_type=identity_stable`，`stable_name` = 正確名字 | `/event/face_identity` |
| 3 | 人臉 | WELCOME 觸發 | 同 case 2（首次穩定辨識） | `/event/interaction/welcome` 發布，`name` 正確 | `/event/interaction/welcome` |
| 4 | 語音 | 真人對話 5 輪 | 對麥克風說 5 句自然語句 | 每輪 transcript 可讀、非幻覺文字 | `/event/speech_intent_recognized` |
| 5 | 語音 | Intent 正確 | 說「你好」→ greet、「坐下」→ action | intent 與語句語意一致，無明顯亂跳 | `/event/speech_intent_recognized` |
| 6 | 手勢 | stop 手勢 | 對鏡頭做 stop（張開手掌） | `gesture=stop` 事件發布 | `/event/gesture_detected` |
| 7 | 手勢 | thumbs_up | 對鏡頭比讚 | `gesture=thumbs_up` 事件發布 | `/event/gesture_detected` |
| 8 | 姿勢 | standing | 站立面對鏡頭 | `pose=standing` 事件發布 | `/event/pose_detected` |
| 9 | 姿勢 | sitting | 坐下 | `pose=sitting` 事件發布 | `/event/pose_detected` |
| 10 | 穩定性 | 四模組共存 3 分鐘 | 保持節點運行，低頻人工觸發確認系統活著 | Foxglove 不斷線、節點不 crash、state/debug image 持續更新、人工再觸發時 event 正常出現 | 全部 |

### Pass/Fail 判定

- **Case 1-9**：JSONL 中有對應 event 且內容符合 → pass
- **Case 10**：3 分鐘內各 topic 持續有 event，Foxglove 無斷線 → pass
- **全過**：10/10 pass → 開 `ENABLE_ACTIONS=true`，補驗 case 6-7 Go2 動作

### 事後驗證指令（參考）

```bash
# 各 topic event 數量
jq -r '.topic' logs/day3-verification-*.jsonl | sort | uniq -c

# 檢查 welcome 事件
jq 'select(.topic == "/event/interaction/welcome")' logs/day3-verification-*.jsonl

# 檢查 gesture stop
jq 'select(.topic == "/event/gesture_detected" and .event_type == "stop")' logs/day3-verification-*.jsonl

# 檢查語音 transcript
jq 'select(.topic == "/event/speech_intent_recognized") | {ts, event_type, text: .payload.text}' logs/day3-verification-*.jsonl
```

---

## 4. 執行順序

```
Phase 1: 功能驗證（ENABLE_ACTIONS=false）
  1. start_full_demo_tmux.sh（ENABLE_ACTIONS=false）
  2. verification_observer.py
  3. Foxglove 連線 + 載入 layout
  4. Case 1-9 逐一執行
  5. Case 10 靜置 3 分鐘

Phase 2: 動作驗證（全過後）
  6. 重啟 ENABLE_ACTIONS=true
  7. 補跑 case 6-7 確認 Go2 stop_move / thumbs_up 動作

Phase 3: 硬體上機（Phase 1+2 全過後）
  8. Jetson + D435 + USB 音訊固定到 Go2
  9. Bring-up 測試（重跑 Phase 1 確認上機後正常）
```

---

## 不做

- 自動化測試腳本（今天人工觸發）
- Observer 內建 pass/fail 判定
- 新 ROS2 package
- 修改 `start_full_demo_tmux.sh`
- 導航/物體辨識相關測試
