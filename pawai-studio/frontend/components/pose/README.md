# Pose 模組上手文件

本文件整理 pose 模組目前實作狀態，包含：
- 如何啟動（Python API + 前端）
- 每個檔案用途
- 姿勢種類與辨識規則
- 前端顯示功能
- 前後端資料流
- 常見問題與排查

---

## 1. 模組目標

此模組提供「姿勢辨識面板」：
- 讀取筆電相機
- 將影像送到 Python 推論服務（OpenCV + MediaPipe + 規則分類）
- 回傳姿勢結果、信心度、骨架疊圖
- 在前端顯示目前姿勢、信心度、歷史紀錄與跌倒警示

---

## 2. 檔案結構與責任

### 前端（React / TypeScript）

- `pose-panel.tsx`
  - Pose 面板 UI
  - 相機顯示、骨架疊圖、目前姿勢、信心度、歷史清單、歷史彈窗

- `use-pose-stream.ts`
  - 相機啟停與 frame 擷取
  - 呼叫後端 API
  - 管理錯誤、最新結果、歷史資料
  - 將「動作判斷更新頻率」與「影像擷取頻率」分開控制

- `pose-client.ts`
  - HTTP 呼叫封裝（POST `/pose/infer`）
  - 回傳資料容錯與格式轉換

- `pose-types.ts`
  - Pose 模組型別
  - 預設設定（endpoint、擷取頻率、判斷頻率、影像品質）

- `pose-mapper.ts`
  - 姿勢字串正規化
  - 姿勢對應中文、emoji、顏色樣式

### 後端（Python）

- `pose_infer_server.py`
  - FastAPI 伺服器
  - 提供 `GET /health`、`POST /pose/infer`
  - CORS 設定（允許 frontend:3000）
  - 接收 base64 影像、呼叫規則分類、回傳 canonical pose 格式與骨架疊圖

- `test_pose.py`
  - 姿勢分類規則核心（MediaPipe landmarks + 幾何規則）
  - `classify_pose(...)`：主要判斷邏輯
  - `infer_pose_from_bgr(...)`：給 API 使用的單張推論介面
  - `run_demo_loop()`：本地視窗 demo（可直接跑）

---

## 3. 支援姿勢（Canonical 格式）

後端目前固定回傳以下其中一種：

- `standing`
- `sitting`
- `crouching`
- `bending`
- `hands_on_hips`
- `kneeling_one_knee`
- `fallen`
- `unknown`

前端以此 canonical 格式顯示中文與圖示，不依賴上游多種別名。

---

## 4. 姿勢辨識方法（規則式）

主要在 `test_pose.py` 進行 landmark 幾何判斷：
- 關鍵點：肩、髖、膝、踝、肘、腕
- 特徵：
  - 髖角（hip angle）
  - 膝角（knee angle）
  - 軀幹與垂直夾角（trunk angle）
  - 手肘彎曲角
  - 膝高差、踝可見度、腕與髖距離

### 判斷優先序

1. `fallen`
2. `kneeling_one_knee`
3. `hands_on_hips`
4. `standing`
5. `sitting`
6. `crouching`
7. `bending`
8. `unknown`

### 目前額外強化

`kneeling_one_knee` 已新增一個分支條件：
- 一膝著地 + 另一腳呈坐姿型幾何（髖膝近同高、小腿向下、膝角彎曲）
- 用於提升單膝跪地命中率

---

## 5. 前端功能總覽

`pose-panel.tsx` 目前包含：
- 相機啟用/停用
- 即時畫面顯示
- 骨架疊圖顯示（API 回傳標註影像）
- 目前姿勢（中文 + emoji）
- 信心度條與百分比
- 跌倒警示 UI
- 最近 10 筆歷史
- 完整歷史彈窗

---

## 6. 資料流

1. 前端啟用相機（`usePoseStream`）
2. 每 `captureIntervalMs` 擷取 frame（canvas -> JPEG base64）
3. POST 到 `POST /pose/infer`
4. Python 端：
   - base64 decode
   - MediaPipe 推 landmarks
   - 規則分類
   - 回傳 canonical pose + confidence + debug + 骨架標註圖
5. 前端接收後：
   - 骨架圖高頻更新（流暢）
   - 姿勢判斷結果依 `decisionIntervalMs` 更新（降噪）

---

## 7. 頻率與效能設定

在 `pose-types.ts` 的 `DEFAULT_POSE_INFERENCE_CONFIG`：

- `captureIntervalMs: 150`
  - 影像送後端頻率（影響骨架畫面流暢度）

- `decisionIntervalMs: 1000`
  - 姿勢結果更新頻率（每秒更新一次）

- `jpegQuality: 0.95`
- `maxImageWidth: 1280`

注意：
- 畫面卡頓通常先調低 `maxImageWidth`（例如 960）
- 想更穩定可再提高 `decisionIntervalMs`

---

## 8. 啟動方式（Windows / PowerShell）

### A. 啟動 Python API

```powershell
conda activate test
cd C:\Programming\project\PawAI\pawai-studio\frontend\components\pose
python -m uvicorn pose_infer_server:app --host 127.0.0.1 --port 8765 --reload
```

### B. 啟動前端

```powershell
cd C:\Programming\project\PawAI\pawai-studio\frontend
npm run dev
```

開發頁面：
- `http://localhost:3000/studio/pose`

健康檢查：
- `http://127.0.0.1:8765/health`

---

## 9. 常見問題

### Q1: `Could not import module "pose_infer_server"`

原因：啟動目錄錯誤。

解法：
- 先 `cd ...\frontend\components\pose` 再啟動
- 或使用 `--app-dir` 指定目錄

### Q2: API log 一直出現 `OPTIONS /pose/infer 405`

原因：CORS 預檢被擋。

解法：
- 已在 `pose_infer_server.py` 加 `CORSMiddleware`
- 確認前端網址是 `localhost:3000` 或 `127.0.0.1:3000`

### Q3: 編輯器顯示 `cv2` / `mediapipe` 無法解析

若終端可執行 import，通常是 VS Code Interpreter 指錯環境。

檢查：
```powershell
python -c "import sys; print(sys.executable)"
python -c "import cv2, mediapipe, numpy; print('ok')"
```

### Q4: 為什麼有 `__pycache__`

Python 編譯快取，正常現象，可忽略。

---

## 10. 調整建議（給後續維護）

1. 若 `hands_on_hips` 仍難命中：
- 放寬手肘彎曲角與腕髖距離門檻

2. 若 `sitting` / `crouching` 常混淆：
- 增加下肢幾何次判斷（髖膝踝相對位置）

3. 若 `kneeling_one_knee` 命中不足：
- 放寬膝高差門檻與支撐腳彎曲區間

4. 若畫面卡：
- 先降 `maxImageWidth`
- 其次調高 `captureIntervalMs`

---

## 11. 版本備註（目前整合重點）

- 已完成前後端 canonical pose 契約
- 已完成骨架疊圖回傳與前端疊圖顯示
- 已完成判斷頻率與擷取頻率分離
- 已完成單膝跪地條件強化分支
