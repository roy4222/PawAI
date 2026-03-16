# Audio Pipeline Observability Design

**版本**：v1.1
**日期**：2026-03-16
**狀態**：approved（review round 2）
**解決的問題**：Go2 音訊播放黑箱 — 封包送出但無法確認播放狀態

---

## 背景

ASR → LLM → TTS → ROS2 → WebRTC → Go2 六層鏈路中，前五層都有 log 顯示成功，但 Go2 喇叭經常靜音。根因是**可觀測性不足**：

- `go2_connection.py` 的 `on_data_channel_message` 只處理 `validation` 和二進位資料，**靜默丟棄** response/heartbeat/errors/err
- `rt/audiohub/player/state` 已在 constants 定義（`AUDIO_HUB_PLAY_STATE`）但**從未被 subscribe**
- DataChannel 送包後不檢查 `bufferedAmount`，不知道有沒有 buffer 爆掉
- `tts_node` 報 "Robot playback completed" 只代表等待時間到了，不代表 Go2 真的播了

---

## 範圍

**B-lite（今天）**：項目 1-5
**B-full（本週）**：項目 6

不在範圍內：`diagnostic_msgs` 整合、TTS provider fallback、模型候補清單（留給後續設計）

---

## 項目 1：Go2 訊息全量接收與分類 log

**檔案**：`go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/go2_connection.py`
**方法**：`on_data_channel_message()`

### 改動邏輯

```
收到 message
  ├─ isinstance(bytes) → 既有邏輯不動
  └─ isinstance(str) →
       try json.loads（失敗 → warning + return）
       ├─ 分類 log（msg_type: response/heartbeat/errors/err/msg/unknown）
       │    response: log api_id + code + topic
       │    heartbeat: log timestamp
       │    errors/err: log 完整 data
       │    其他: debug log
       ├─ 獨立判斷 topic（不放在 elif 裡，避免被 msg_type 分支吃掉）
       │    topic == AUDIO_HUB_PLAY_STATE → info log 播放狀態
       └─ try 轉發 on_message callback（失敗 → warning，不能殺收包 loop）
```

### 設計決策

1. **topic 判斷獨立於 msg_type** — audiohub state 可能包在 `type="response"` 裡，用 `elif` 會被前面吃掉
2. **JSON 解析加 try/except** — 壞包 warning 不崩 callback
3. **code 路徑不寫死** — 先抓 `data.data.code`，fallback `data.code`
4. **on_message callback 包 try/except** — 上層處理失敗不能反殺底層收包
5. **heartbeat 用 debug 級別** — heartbeat 頻率高，用 info 會淹沒音訊 debug；errors/err 用 warning/error
6. **同時更新 ConnectionHealth** — 分類 log 的同時更新 `self._health` dataclass（見項目 5），避免在 adapter 層重複分類

---

## 項目 2：Subscribe `rt/audiohub/player/state`

**檔案**：`go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py`
**方法**：`_on_validated()`

### 改動

在 `subscription_topics` 列表加入：

```python
subscription_topics.append(RTC_TOPIC["AUDIO_HUB_PLAY_STATE"])
```

### 效果

Go2 開始回報 audiohub 播放器狀態變化。訊息在項目 1 的 `on_data_channel_message` 裡被 log。

### 注意事項

- 訂閱在 `_on_validated` 時一次性完成，不支援動態開關
- 如果 audiohub state 訂閱後始終無資料，不代表實作錯誤 — Go2 可能只在有播放事件時才推送
- 未來可用 `4005`（GET_AUDIO_STATUS）做主動 probe，但不在本次範圍

---

## 項目 3：分層診斷腳本 `diagnose_audio.sh`

**檔案**：`scripts/diagnose_audio.sh`

### 四層診斷

| 層級 | 測試內容 | 預設行為 | 回傳狀態 |
|------|---------|---------|---------|
| L1 | Go2 喇叭硬體 | MANUAL（提示用 Go2 App 播放測試，SSH 檢測為加分項） | PASS/FAIL/SKIP/MANUAL |
| L2 | WebRTC 直連 beep（繞過 ROS2） | SKIP（需 `--include-l2`，會中斷 driver） | PASS/FAIL/SKIP |
| L3 | ROS2 鏈路（pub /tts → 檢查 /webrtc_req） | 預設執行 | PASS/FAIL |
| L4 | 完整 E2E（麥克風 → Go2 播放） | MANUAL（提示使用者說話） | PASS/FAIL/MANUAL |

### 每層輸出格式

```
[L3] ROS2 Pipeline ........ PASS
     → 4004→4001→4003x3→4002 sequence confirmed
     → Next: If Go2 still silent, run with --include-l2
```

### 設計決策

- 預設只跑 L3/L4（不中斷現有 session）
- L1 以 Go2 App 播放為主，SSH 為可選加分項
- 每層固定回傳狀態碼 + 下一步建議
- L2 需要殺 driver，用 `--include-l2` flag 明確 opt-in
- L3 timeout：5 秒內沒收到 `/webrtc_req` 即 FAIL

---

## 項目 4：DataChannel bufferedAmount 監控

**檔案**：`go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py`
**方法**：`_async_send_command()`

### 改動邏輯

```python
buffered_before = getattr(dc, 'bufferedAmount', None)
dc.send(command)
buffered_after = getattr(dc, 'bufferedAmount', None)

# 音訊命令詳細 log
if _api in AUDIO_HUB_COMMANDS.values():  # 使用常量，不用 magic number
    logger.info(
        f"[AUDIO DEBUG] dc_state={state} api_id={_api} "
        f"payload_len={len(command) if isinstance(command, (bytes, str)) else '?'} "
        f"buffered={buffered_before}→{buffered_after}"
    )

# buffer 告警
if buffered_after is not None:
    if buffered_after > 512_000:
        logger.error(f"[DC BUFFER] bufferedAmount={buffered_after} — CRITICAL backlog")
    elif buffered_after > 64_000:
        logger.warning(f"[DC BUFFER] bufferedAmount={buffered_after} — backlogged")
```

### 設計決策

- 記錄 send 前/後的 bufferedAmount，比較有診斷價值
- 64KB warning，512KB error（兩級告警）
- `len(command)` 前先確認型別
- `bufferedAmount` 是 local SCTP buffer 指標（非對端確認），主要用於偵測本地 buffer 堆積到無法 drain 的極端場景
- 使用 `AUDIO_HUB_COMMANDS` 常量取代 magic number；需在 `domain/constants/__init__.py` 補 export

---

## 項目 5：`/state/connection/go2` topic

**發布者**：`go2_driver_node`
**頻率**：每 2 秒
**格式**：`std_msgs/String` JSON（4/13 前不換 msg 型別）

### Schema

```json
{
  "stamp": 1773653710.0,
  "seq": 42,
  "dc_state": "open",
  "connection_state": "connected",
  "validated": true,
  "last_response_ts": 1773653709.5,
  "last_heartbeat_ts": 1773653708.2,
  "last_msg_type": "response",
  "last_audio_state": "playing",
  "last_audio_state_ts": 1773653709.8,
  "error_count": 0,
  "last_error": "",
  "uptime_s": 3600.0
}
```

### 資料來源

### 架構

**`ConnectionHealth` dataclass** 定義在 `go2_connection.py` 頂層（與 `Go2Connection` 同檔）：

```python
@dataclass
class ConnectionHealth:
    dc_state: str = "closed"
    connection_state: str = "new"
    validated: bool = False
    last_response_ts: float = 0.0
    last_heartbeat_ts: float = 0.0
    last_msg_type: str = ""
    last_audio_state: str = "unknown"
    last_audio_state_ts: float = 0.0
    error_count: int = 0           # 累計（自 connected 以來），reconnect 時重置
    last_error: str = ""
    connected_at: float = 0.0      # 在 on_data_channel_open 時設為 time.time()
```

**更新位置**：`go2_connection.on_data_channel_message()` — 項目 1 的分類 log 同時更新 `self._health` 欄位，避免在 adapter 層重複分類。

**Accessor API**：`Go2Connection` 新增 property：

```python
@property
def health(self) -> ConnectionHealth:
    return self._health
```

`WebRTCAdapter` 新增 public method：

```python
def get_connection_health(self, robot_id: str = "0") -> Optional[ConnectionHealth]:
    conn = self.connections.get(robot_id)
    return conn.health if conn else None
```

**`go2_driver_node` timer 與 publisher**：在 node `__init__` 中建立（只建一次，避免重連時重複建立）：

```python
# __init__ 中
self._health_pub = self.create_publisher(String, '/state/connection/go2', 10)
self._health_timer = self.create_timer(2.0, self._publish_connection_health)
```

`_publish_connection_health` callback 呼叫 `self.adapter.get_connection_health("0")` 並序列化為 JSON 發布。validated 之前發布的是預設值（`validated: false`），不會造成誤判。

### 執行緒安全

`ConnectionHealth` 被 asyncio 執行緒（on_data_channel_message）寫入，被 ROS2 timer 執行緒讀取。`health` property 回傳 shallow copy（`dataclasses.replace(self._health)`）避免讀到部分更新值。寫入側用 `threading.Lock` 保護。

### 設計決策

- `seq` 用於 debug 訊息順序
- `last_msg_type` 記錄最近收到的 Go2 訊息類型
- `last_audio_state` 旁邊放 `last_audio_state_ts`，避免看到舊值誤判

---

## 項目 6：播放確認（B-full）

**檔案**：`go2_robot_sdk/.../webrtc/webrtc_adapter.py`（不在 tts_node）

### 概念

播放確認在 `go2_driver_node` / `webrtc_adapter` 側做，不在 tts_node。理由：driver 有 asyncio event loop 能即時收到 audiohub state，不受 single-thread executor 限制。

### 改動邏輯

```
webrtc_adapter 送出 4001 (start)
  → 記錄 last_audio_send_ts = time.time()

on_data_channel_message 收到 audiohub state == "playing"
  → 且 ts > last_audio_send_ts
  → INFO "✅ Go2 confirmed playback"

定期檢查（health timer 觸發時）：
  → 如果 last_audio_send_ts > 0 且距今 > 3 秒 且沒收到 playing
  → WARNING "⚠️ Audio sent but Go2 did not report playback"
  → 重置 last_audio_send_ts
```

### 設計決策

- **確認在 driver 側**，避免 tts_node single-thread executor 問題
- **用 timestamp 比對**，避免吃到前一輪的 playing
- **只告警不阻塞**，不重試
- tts_node 不做任何改動（項目 6 不涉及 speech_processor）

### 已知限制：single-thread executor

`tts_node` 的 `_play_on_robot` 方法用 `time.sleep` 阻塞，在 rclpy 的 single-threaded executor 下，subscription callback 在播放期間不會被觸發。

**解法**：播放確認移到 `go2_driver_node` 側做（方案 B）。

`go2_driver_node` 已有 asyncio event loop 在跑，收到 audiohub state 時直接比對最近一次 4001 送出時間，確認播放。不依賴 tts_node subscription，避免 single-thread executor 問題。

tts_node 不做播放確認，只負責送出。確認邏輯全在 driver 側。

---

## 契約相容性

`/state/connection/go2` 為新增 topic，不修改 `interaction_contract.md` v2.0 既有凍結介面。待驗證穩定後再追加到下一版契約。

---

## 檔案變更清單

| 檔案 | 改動類型 | 項目 |
|------|---------|------|
| `go2_robot_sdk/.../webrtc/go2_connection.py` | 修改 on_data_channel_message | 1 |
| `go2_robot_sdk/.../webrtc/webrtc_adapter.py` | 加 subscribe + bufferedAmount | 2, 4 |
| `scripts/diagnose_audio.sh` | 新建 | 3 |
| `go2_robot_sdk/.../domain/constants/__init__.py` | export AUDIO_HUB_COMMANDS | 4 |
| `go2_robot_sdk/.../presentation/go2_driver_node.py` | 加 /state/connection/go2 publisher + timer | 5 |
| `go2_robot_sdk/.../webrtc/webrtc_adapter.py` | 加播放確認邏輯 | 6 |

---

## 驗收標準

1. 送 TTS 後，driver log 能看到 Go2 的 response（api_id + code）
2. audiohub player state 有在 log 中出現
3. `diagnose_audio.sh` L3 能正確判斷 PASS/FAIL
4. `/state/connection/go2` topic 每 2 秒發布一次
5. 如果 Go2 不播放，driver log 出現 WARNING（而非只有 tts_node 假的 "completed successfully"）
