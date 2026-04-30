# PawAI 手勢辨識互動系統 (Gesture Recognition)

本模組為 PawAI 專案的手勢辨識組件，利用 Mediapipe 實作本機端的即時手勢偵測。支援 6 種靜態手勢與 3 種動態手勢，並可與 PawAI Studio 前端即時連動，將骨架畫面串流至網頁。

---

## 1. 環境設定與安裝

本專案建議在 macOS (M 系列晶片) 搭配 Python 3.12 執行。

### 建立虛擬環境 (建議)
```bash
# 在專案目錄下
source pawai-studio/backend/venv/bin/activate
```

### 安裝必要套件
請務必安裝特定版本的 `mediapipe` 以解決 Mac M 系列晶片的相容性問題。

```bash
# 核心辨識套件 (特別指定 0.10.14 版本以避免 solutions 模組缺失)
pip install mediapipe==0.10.14

# 影像處理與網路通訊
pip install opencv-python websockets
```

---

## 2. 啟動與使用

要讓手勢辨識與網頁前端連動，請按照以下順序啟動：

1. **啟動後端 Mock Server** (用於接收手勢事件與影像串流):
   ```bash
   cd pawai-studio/backend
   python -m uvicorn mock_server:app --port 8080
   ```

2. **啟動前端 Studio** (查看儀表板):
   ```bash
   cd pawai-studio/frontend
   npm run dev
   ```

3. **啟動手勢辨識程式**:
   ```bash
   # 確保已進入虛擬環境
   python gesture-wu/gesture_recognition.py
   ```

---

## 3. 支援手勢清單

### 靜態手勢 (Static Gestures)
穩定維持手勢 0.5 秒以上觸發動作。

| 手勢 | 標籤 | 陪伴模式 | Go2 動作 | 功能說明 |
| :--- | :--- | :--- | :--- | :--- |
| 🖐️ Palm | `Palm` | `Pause` | 1003 (Stop) | 全面暫停動作 |
| 👊 Fist | `Fist` | `Mute` | 1009 (Sit) | 純關閉語音模式 |
| ☝️ Index | `Index` | `Listen` | 1004 (Stand) | 開啟語音模式 |
| 👌 OK | `OK` | `Confirm` | 1020 (Content) | 確認指令 （所有手勢都要經過這個確認 才動作） |
---
### 互動功能

| 👍 Thumb | `Thumb` | `Happy` | 1033 (Wiggle) | 搖屁股 |    
| ✌️ Peace | `Peace` | `Relax` | 1017 (Stretch) | 伸懶腰 |

### 動態手勢 (Dynamic Gestures)
需要一定軌跡的動作才會觸發。

| 手勢 | 標籤 | 模式 | Go2 動作 | 判定方式 |
| :--- | :--- | :--- | :--- | :--- |
| 👋 Wave | `Wave` | `Greeting` | 1016 (Hello) | 你好 |
| 🫴 ComeHere| `ComeHere`| `Follow` | 1018 (Follow) | 手掌張開，上下連續擺動 (招手) | 走過來 (高難度）
| 🔄 Circle | `Circle` | `Explore` | 1029 (Dance) | 跳舞 

---

## 4. 技術細節
- **影像串流**：本程式會將處理過後的骨架影像壓縮為 JPEG，透過 WebSocket (`ws://localhost:8080/ws/video_upload/vision`) 傳送給後端。
- **事件發送**：偵測到穩定手勢後，會透過 HTTP POST 發送事件至 `/mock/trigger` 以更新前端 UI。
- **Mac 優化**：已排除 `AVCaptureDeviceTypeExternal` 警告，並針對 Metal 加速進行初步優化。
