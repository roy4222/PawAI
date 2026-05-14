# PawAI Studio Live View — Design Spec

**日期**：2026-04-07
**作者**：Roy + Claude
**狀態**：Draft
**頁面路由**：`/studio/live`

---

## 1. 定位

Foxglove 替代展示牆。給 Demo 觀眾一眼看懂「狗正在看什麼、辨識到什麼」。

- 三路即時影像串流（人臉 / 手勢+姿勢 / 物體）
- 每路只有精簡 overlay 標籤，不放完整 panel 卡片
- 影像流和事件流完全分離，互不干擾

**不做**：錄影、回放、frame history、完整 panel 展開。

---

## 2. 架構

```
Jetson ROS2 Topics                    Gateway (port 8080)              Browser
─────────────────                    ──────────────────              ─────────
/face_identity/debug_image      ──→  WS /ws/video/face    (binary)  ──→  左欄
/vision_perception/debug_image  ──→  WS /ws/video/vision  (binary)  ──→  中欄
/perception/object/debug_image  ──→  WS /ws/video/object  (binary)  ──→  右欄

/state/perception/face          ┐
/event/gesture_detected         │
/event/pose_detected            ├──→  WS /ws/events        (JSON)   ──→  overlay + ticker
/event/speech_intent_recognized │
/event/object_detected          ┘
```

**核心邊界**：影像走獨立 WebSocket binary 連線，事件走現有 `/ws/events` JSON 連線。一路影像掛掉不影響其他路，也不影響事件流。

---

## 3. Gateway — 影像串流 Endpoints

### 3.1 新增 Endpoints

```
WS /ws/video/face      JPEG binary frames — 人臉辨識 debug image
WS /ws/video/vision    JPEG binary frames — 手勢+姿勢 debug image
WS /ws/video/object    JPEG binary frames — 物體辨識 debug image
```

### 3.2 ROS2 Topic 對照

| Endpoint | ROS2 Topic | msg type | 預期 FPS |
|----------|-----------|----------|:--------:|
| `/ws/video/face` | `/face_identity/debug_image` | `sensor_msgs/Image` | ~6.6 |
| `/ws/video/vision` | `/vision_perception/debug_image` | `sensor_msgs/Image` | ~3.8 |
| `/ws/video/object` | `/perception/object/debug_image` | `sensor_msgs/Image` | ~6-8 |

> Topic 名稱以實作為準。上表為目前已確認的名稱。

### 3.3 處理流程

```
ROS2 Image callback:
  1. cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
     - 如果轉換失敗 → drop frame + log warning，不 crash
  2. cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
  3. 節流：距上次 send < 200ms (5 FPS) → drop
  4. asyncio.run_coroutine_threadsafe → ws.send_bytes(jpeg_bytes)
     - 如果 send 失敗（client 斷線）→ 移除 client，不 crash
```

### 3.4 硬限制

| 項目 | 值 | 原因 |
|------|---|------|
| JPEG quality | 70 | 頻寬 vs 畫質平衡 |
| 節流 FPS | 5 | Gateway 端限制，避免 Jetson 網路壓力 |
| 影像不走 `/ws/events` | — | 事件流和影像流分離 |
| 不做錄影/回放 | — | scope 限制 |

### 3.5 依賴

- `cv_bridge`（ROS2 套件，Jetson 已有）
- `cv2`（OpenCV，Jetson 已有）
- `sensor_msgs`（ROS2 標準訊息）

---

## 4. 前端 — `/studio/live` 頁面

### 4.1 版面

```
┌──────────────────────────────────────────────────────────────────┐
│ PawAI Live View            Gateway ●  FPS: 5/5/3   Jetson 56°C  │
├───────────────────┬─────────────────────┬────────────────────────┤
│ FACE IDENTITY     │ GESTURE + POSE      │ OBJECT PERCEPTION      │
│ ┌───────────────┐ │ ┌─────────────────┐ │ ┌──────────────────┐   │
│ │               │ │ │                 │ │ │                  │   │
│ │  JPEG stream  │ │ │  JPEG stream    │ │ │  JPEG stream     │   │
│ │               │ │ │                 │ │ │                  │   │
│ └───────────────┘ │ └─────────────────┘ │ └──────────────────┘   │
│ Roy 92% 1.4m      │ Pose: standing 91%  │ cup 83%                │
│ 2 faces · stable  │ Gesture: thumbs_up  │ book 48%               │
│         5.2 fps   │            3.8 fps  │              6.1 fps   │
├───────────────────┴─────────────────────┴────────────────────────┤
│ ▸ 14:32:05 face.identity_stable Roy → 14:32:07 gesture.stop → … │
└──────────────────────────────────────────────────────────────────┘
```

- **三欄等寬**，影像 `aspect-ratio: 4/3`（D435 原生比例），`object-fit: contain`
- **響應式**：視窗過窄時垂直堆疊（breakpoint ~1024px）

### 4.2 各欄 Overlay

| 欄位 | Overlay 內容 | 資料來源 |
|------|-------------|---------|
| Face（左） | 名字 + similarity% + distance + face_count + stable/hold | state store `faceState` |
| Vision（中） | current_pose + current_gesture + confidence + hand | state store `gestureState` / `poseState` |
| Object（右） | top 3 物品 class_name + confidence% | state store `objectState` |
| 共通 | 左上角 topic 名稱小字、右下角 FPS、NO SIGNAL 狀態 | `useVideoStream` hook |

### 4.3 Status Bar（頂部）

```
PawAI Live View            Gateway ●  FPS: 5/5/3   Jetson 56°C
```

- Gateway 連線狀態 dot（綠/灰）
- 三路 FPS 即時顯示（face/vision/object）
- Jetson 溫度（從 `/ws/events` system health 取）

### 4.4 Event Ticker（底部）

- 單行橫向滾動，控制台 log 風格
- 格式：`▸ HH:MM:SS source.event_type detail`
- 接現有 event store，最近 20 筆
- 自動捲動，新事件從右邊推入

### 4.5 NO SIGNAL 狀態

- 10 秒無新 frame → 影像區域顯示 `NO SIGNAL`（半透明遮罩 + 大字）
- WebSocket 斷線 → 顯示 `DISCONNECTED`，自動重連（復用 3s 重連邏輯）

---

## 5. 前端 — `useVideoStream` Hook

### 5.1 介面

```typescript
interface UseVideoStreamOptions {
  source: "face" | "vision" | "object";
  enabled?: boolean;  // default true
}

interface UseVideoStreamResult {
  imageUrl: string | null;    // objectURL for <img src>
  fps: number;                // 即時 FPS（滑動平均）
  isConnected: boolean;
  lastFrameAt: number | null; // timestamp
  status: "connected" | "no_signal" | "disconnected";
}
```

### 5.2 實作要點

```
1. WebSocket 連線：ws(s)://{hostname}:8080/ws/video/{source}
   - 自動選 ws/wss（同現有 useWebSocket）
   - 斷線 3s 自動重連

2. 收到 binary message：
   a. blob = new Blob([data], { type: "image/jpeg" })
   b. newUrl = URL.createObjectURL(blob)
   c. 如果 prevUrl 存在 → URL.revokeObjectURL(prevUrl)  // 防 memory leak
   d. setImageUrl(newUrl)

3. FPS 計算：
   - 維護最近 10 個 frame timestamp（ms）
   - fps = (n - 1) * 1000 / (latestMs - oldestMs)，n = buffer 內 frame 數

4. NO SIGNAL：
   - 10s 無 frame → status = "no_signal"

5. Cleanup（unmount）：
   - ws.close()
   - URL.revokeObjectURL(currentUrl)  // 必須 revoke
```

---

## 6. 視覺風格

延續 Mission Control 深色控制室風格。

| 元素 | 值 |
|------|---|
| 背景 | `#0a0f1a`（深藍黑） |
| 強調色（正常） | `#00ffc8`（青綠） |
| 強調色（警告） | `#ffb800`（琥珀） |
| 強調色（危險） | `#ff3b3b`（紅，fallen/error） |
| 影像框 | 1px `#1a2a3a` border，圓角 8px |
| Overlay 標籤 | 半透明黑底 `rgba(0,0,0,0.7)` 白字，貼影像下方 |
| Topic 名稱 | 左上角小字 `text-xs opacity-60` |
| FPS | 右下角小字 `text-xs`，正常綠 / <2 琥珀 / 0 紅 |
| Event ticker | 底部固定高度 40px，`font-mono text-xs`，青綠色文字 |
| NO SIGNAL | 影像區域半透明黑遮罩 + `text-2xl` 白字居中 |

---

## 7. 實作順序

| Step | 內容 | 預計產出 |
|:----:|------|---------|
| 1 | Gateway 增加 3 路 `/ws/video/{source}`（訂閱 ROS2 Image → cv_bridge → JPEG → binary send） | `studio_gateway.py` 修改 |
| 2 | 新增 `/studio/live` 頁面 + 三欄佈局 + status bar | `app/(studio)/studio/live/page.tsx` |
| 3 | `useVideoStream` hook（WebSocket binary → createObjectURL → img） | `hooks/use-video-stream.ts` |
| 4 | 各欄 Overlay 接現有 state store 數值 | 三個 `LiveFeedCard` 元件 |
| 5 | Event ticker 接現有 event store | `components/live/event-ticker.tsx` |
| 6 | Gateway 測試 + 前端測試 | `test_gateway.py` 補測 + component 測試 |

---

## 8. 風險與 Fallback

| 風險 | 影響 | Fallback |
|------|------|---------|
| Jetson 上 cv_bridge 不可用 | Gateway 無法轉換 Image | 該 video endpoint disabled，回傳 NO SIGNAL；不做手寫 Image decode |
| Object debug image topic 不存在 | 右欄無畫面 | 顯示 NO SIGNAL，overlay 仍從事件流取數值 |
| 三路同跑頻寬不足 | 丟幀嚴重 | 降 JPEG quality 到 50 或降 FPS 到 3 |
| 長時間 demo memory leak | 瀏覽器變慢 | `URL.revokeObjectURL` 每次換 frame 必做 |
| ROS2 Image encoding 不是 bgr8 | cv_bridge 轉換失敗 | `desired_encoding="bgr8"` 自動轉換，失敗則 drop + warning |
