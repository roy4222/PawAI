# 4-3 MediaPipe 框架與手勢辨識技術

## MediaPipe 框架簡介

MediaPipe 是由 Google Research 於 2019 年開源的即時多模態感知機器學習框架,全稱為 *MediaPipe: A Framework for Building Perception Pipelines*。與一般將機器學習視為「單一模型的輸入與輸出」的思考方式不同,MediaPipe 將機器學習應用視為一條由多個階段組成的**管線(Pipeline)**,每個階段可以是神經網路推論、前處理(如影像裁切、色彩轉換)、後處理(如座標轉換、濾波平滑)、或是跨幀的時序處理。MediaPipe 透過 Graph-based Computation Model(圖運算模型)將這些階段抽象為計算節點(Calculator),各節點之間以資料流(Stream)相連,整體形成一個有向無環圖(DAG, Directed Acyclic Graph)。此架構讓開發者能以組合既有 Calculator 的方式快速搭建複雜的感知管線,並針對行動裝置與邊緣運算場景進行高度最佳化。

MediaPipe 的設計哲學以「CPU 友善」為核心,強調在不依賴龐大 GPU 算力的情況下,於一般行動裝置處理器(如手機 ARM CPU)或邊緣運算設備(如 NVIDIA Jetson、Raspberry Pi)上實現即時推論。為達到此目標,Google 團隊專門為 MediaPipe 訓練了一系列輕量化模型,採用知識蒸餾(Knowledge Distillation)、模型剪枝(Pruning)與量化(Quantization)等技術將模型大小壓縮至數 MB 等級,同時保持足以實用的精度。這個設計特性完美契合本專題將感知模組部署於機器狗本地 Jetson Orin Nano 的需求,使得多個感知模組(人臉、手勢、姿勢)可同時在 CPU 上運行而不佔用寶貴的 GPU 資源(GPU 主要留給物體辨識的 TensorRT 加速推論使用)。

MediaPipe 目前提供多種預訓練的感知解決方案(Solutions),涵蓋人臉偵測與追蹤、手部追蹤、姿勢估計、人像分割、物件偵測、文字分類、音訊分類等任務。本專題主要使用其中的三個模組:MediaPipe Pose(33 點全身骨架,用於姿勢辨識,詳見 4-4 節)、MediaPipe Hands(21 點手部關鍵點,用於手勢辨識的底層特徵擷取)、MediaPipe Gesture Recognizer(基於 Hands 之上的高階手勢分類器,辨識預定義的手勢類別)。Google 於 2023 年將 MediaPipe 重新整理為 MediaPipe Solutions API(內部稱 Tasks API),取代早期的 Legacy API,新 API 以 Task(任務)為單位提供統一的 Python / C++ / Android / iOS / Web 介面,本專題採用的即是此新版 Tasks API。

## MediaPipe Hands 與 21 個手部關鍵點

MediaPipe Hands 是 MediaPipe 框架中專門處理手部偵測與關鍵點估計的子模組,於 2019 年由 Google 研究團隊首次發布(相關論文《MediaPipe Hands: On-device Real-time Hand Tracking》發表於 CVPR 2020 Workshop)。MediaPipe Hands 採用兩階段的神經網路管線設計,以兼顧偵測速度與關鍵點精度:

**第一階段——BlazePalm 手掌偵測模型**:BlazePalm 是一個專為手掌偵測設計的輕量級單階段物件偵測器(Single-Shot Detector),其設計理念延續自 Google 同年發表的 BlazeFace 人臉偵測模型,採用 Anchor-Free 的卷積神經網路架構與高效的解碼邏輯,能在行動裝置 CPU 上達到每秒數百幀的推論速度。BlazePalm 在此管線中負責的工作是從整張輸入影像中快速定位所有可能的手掌區域並輸出矩形邊界框,作為下一階段關鍵點偵測的輸入。手掌(而非整隻手)作為偵測目標的選擇是刻意的設計決策——手掌相較於整隻手在形狀與紋理上較為固定,不會因手指姿態變化而大幅改變外觀,這讓偵測模型可以更簡單且更準確地完成任務。

**第二階段——Hand Landmark Model 手部關鍵點模型**:在 BlazePalm 定位出手掌區域後,MediaPipe 將該區域裁切並送入 Hand Landmark Model,此模型是一個專門針對手部幾何結構訓練的回歸型神經網路,輸出手部的 **21 個 3D 關鍵點**座標。這 21 個關鍵點分別對應手部的解剖結構:手腕根部(Wrist)1 個、拇指從掌根到指尖 4 個、其餘四指(食指、中指、無名指、小指)各 4 個,共 1 + 4 + 4 × 4 = 21 個關鍵點。每個關鍵點包含 (x, y, z) 三個座標值,其中 x、y 為畫面上的像素座標,z 為相對於手腕根部的相對深度(正值代表離攝影機較近、負值代表較遠)。此外,模型還輸出每隻手的左右手判定(Handedness)與整體信心度分數。MediaPipe Hands 可同時追蹤畫面中的雙手,在辨識到單手後啟用持續追蹤模式以避免每幀都重新跑 BlazePalm 偵測器,大幅降低運算負擔。

21 點手部骨架的完整性使得 MediaPipe Hands 能支援各種下游應用,不僅限於靜態手勢分類,亦可用於手寫辨識、虛擬樂器演奏、手語翻譯、AR 介面操控等。對本專題而言,21 點骨架是手勢分類邏輯的原始輸入,分類器透過計算關鍵點之間的相對角度、距離、比例等幾何特徵來判斷手勢類別。

## MediaPipe Gesture Recognizer 與預定義手勢

MediaPipe Gesture Recognizer 是建立在 MediaPipe Hands 之上的高階手勢分類模組,於 2023 年隨 MediaPipe Tasks API 一同發布。其設計目標是讓開發者不需要自行撰寫手勢分類邏輯,只要傳入影像,模組即可直接輸出預定義的手勢類別標籤。Gesture Recognizer 的內部架構採用**兩階段分類管線(Two-Step Classification Pipeline)**:

**第一步——手勢嵌入模型(Gesture Embedding Model)**:此模型接收 MediaPipe Hands 輸出的 21 點手部關鍵點座標(經過正規化處理),並將其編碼為一個固定維度的特徵向量(Embedding Vector)。此特徵向量捕捉了手部的整體姿態資訊,但與具體的手勢類別無關,可視為手部姿態的「語意表徵」。此嵌入模型透過大規模手勢資料集訓練而成,能對不同使用者、不同角度、不同光線條件下的相同手勢產生相似的特徵向量。

**第二步——手勢分類模型(Gesture Classification Model)**:此為一個輕量級的全連接神經網路分類器,以前一步的特徵向量作為輸入,輸出手勢類別的機率分佈。預設模型可辨識以下八個類別(含「無法識別」類):

0. **None(Unknown)**:無法辨識的手勢或未偵測到手部
1. **Closed_Fist(握拳)**:五指彎曲收攏成拳頭
2. **Open_Palm(張開手掌)**:五指完全伸直張開
3. **Pointing_Up(食指向上)**:食指伸直其餘四指彎曲
4. **Thumb_Down(拇指向下)**:拇指向下其餘四指彎曲
5. **Thumb_Up(拇指向上,比讚)**:拇指向上其餘四指彎曲
6. **Victory(勝利手勢)**:食指與中指伸直成 V 字型
7. **ILoveYou(我愛你手勢)**:拇指、食指、小指伸直,中指與無名指彎曲

Gesture Recognizer 的兩階段設計具有重要的擴充性優勢:開發者可以保留第一步的嵌入模型不變(因其已透過大規模資料訓練達到良好的泛化能力),僅針對自己的應用場景重新訓練第二步的分類器,即可辨識自訂的手勢類別。Google 提供了官方的 Model Maker 工具支援此客製化流程,使用者只需提供每個自訂手勢約 100 張樣本影像即可完成訓練。本專題目前採用預設的八類分類器,未來若需支援專題特定的手勢(如「召喚」「跟隨」等自訂指令)可考慮此客製化路徑。

## 本系統的手勢辨識實作

本專題的手勢辨識模組(`vision_perception` ROS2 套件)支援兩種後端:MediaPipe Gesture Recognizer(`gesture_recognizer_backend.py`)與 RTMPose 手部關鍵點分類(`gesture_classifier.py`)。程式碼與 config 的預設值為 `gesture_backend: "rtmpose"`(`vision_perception.yaml:13`、`vision_perception.launch.py:21`),但 **Demo 部署主線**由啟動腳本覆寫為 `gesture_backend:=recognizer`(`start_full_demo_tmux.sh:129`),採用 MediaPipe Gesture Recognizer 作為實際運行後端。以下以 Demo 主線(Gesture Recognizer)為例說明處理流程:

1. **影像擷取**:從 Intel RealSense D435 的 RGB 輸出取得即時影像幀(透過 `/camera/camera/color/image_raw` ROS2 Topic),透過 cv_bridge 轉換為 OpenCV 格式的 NumPy 陣列。

2. **MediaPipe 推論**:將影像傳入 Gesture Recognizer Task,模型回傳當前幀中所有偵測到的手部,每隻手包含:手勢類別與信心度、21 個手部關鍵點座標、左右手判定(Left 或 Right)。

3. **標籤映射**:Gesture Recognizer 直接輸出手勢類別標籤(如 `Open_Palm`、`Thumb_Up`、`Closed_Fist` 等),由 `gesture_recognizer_backend.py` 的 `_GESTURE_MAP` 映射為系統內部名稱(`stop`、`thumbs_up`、`fist` 等)。此路徑為端到端分類,**不經過 `gesture_classifier.py` 的幾何特徵計算**——幾何特徵分類邏輯(手指伸展比例、彎曲角度等)僅在 RTMPose / MediaPipe Hands 後端路徑下使用,供開發期替換與比較。

4. **時序平滑與投票**:為避免單幀誤判造成手勢結果抖動,系統維持一個滑動視窗並透過多幀多數決得出穩定的手勢標籤。此視窗長度由 `gesture_vote_frames` 參數控制,**程式碼預設值為 5 幀,實際部署於 `vision_perception.yaml` 中覆寫為 3 幀**(依真機測試調整),在實機測試中顯著降低了快速切換手勢時的誤判率。

5. **白名單過濾與去重**:Gesture Recognizer 輸出的 8 類標籤經 `_GESTURE_MAP` 映射為內部名稱(`Open_Palm→stop`、`Thumb_Up→thumbs_up`、`Closed_Fist→fist` 等),再經 `GESTURE_COMPAT_MAP`(`fist→ok`)轉換後,由 `interaction_rules.py` 的 `GESTURE_WHITELIST = {"stop", "thumbs_up", "ok"}` 進行白名單過濾——只有 stop / thumbs_up / ok 三類能進入中控,其餘手勢(Victory、Pointing_Up、Thumb_Down、ILoveYou)在此層即被過濾,不會到達 Executive。系統層級的去重由 `interaction_executive` 中控模組統一處理,定義了 `DEDUP_WINDOW = 5.0` 秒的全域去重視窗。依 ROS2 介面契約(`interaction_contract.md:507`)的設計意圖,**stop 手勢作為安全優先事件不受 cooldown 限制**。

6. **ROS2 事件發布**:辨識結果以 JSON 格式透過 `/event/gesture_detected` ROS2 Topic 發布,訊息內含手勢類別、信心度、左右手判定、時間戳記等欄位。統一中控模組(Interaction Executive)訂閱此 Topic 並根據手勢類型觸發對應的 Go2 機器狗動作與語音回應。

## 為何選擇 MediaPipe 而非其他手勢辨識方案

本專題在選擇手勢辨識模型時,曾評估過多個候選方案,包括 MediaPipe Hands / Gesture Recognizer、RTMPose-WholeBody(含手部關鍵點)、DWPose(基於 DETR 架構的全身與手部關鍵點)、OpenPose 等,最終選擇 MediaPipe 作為主線方案,決策依據如下:

- **CPU 即時推論能力**:MediaPipe Gesture Recognizer 在 Jetson Orin Nano 的 CPU 上實測可達每秒約 7 幀,完全不佔用 GPU 資源。相較之下,RTMPose-WholeBody 與 DWPose 在 Jetson 上運行需要 GPU 加速(TensorRT FP16),實測前者 GPU 佔用率達 91 至 99%,無法與其他 GPU 模組(如 YOLO26 物體辨識)共存;DWPose 的 Transformer 架構在 FP16 量化後關鍵點出現明顯偏移,且 MMPose 在 JetPack 6 環境的社群支援極度有限,部署困難。

- **部署成熟度**:MediaPipe 提供 Python pip 套件(`mediapipe`),安裝便利,模型檔案可直接從 Google 官方下載,無需自行轉換 ONNX 或 TensorRT 引擎。相較之下,其他方案皆需要複雜的模型轉換流程,且 Jetson 生態的碎片化使得不同 JetPack 版本的相容性問題層出不窮。

- **功能完整性**:MediaPipe 同時提供 Hands 與 Gesture Recognizer 兩個層級的 API,可滿足從低階關鍵點到高階手勢分類的不同需求;且其預設支援 21 點手部骨架,關鍵點的 3D 座標輸出可直接用於後續的自訂幾何特徵計算。

- **開源且穩定**:MediaPipe 為 Google 官方維護的開源專案,社群活躍度高、文件完整、更新穩定,相較於一些研究型專案更適合實際部署。

## 本系統支援的手勢與動作映射

本專題根據 Demo 場景的實際互動需求,從 MediaPipe 預設的 8 類手勢中挑選出以下幾個作為主要互動手勢,並在 Interaction Executive 狀態機中設計了對應的 Go2 機器狗動作與語音回應:

| 手勢(MediaPipe 原名) | 中文名稱 | Go2 動作 | 語音回應 | 優先序 |
|---|---|---|---|:-:|
| `Open_Palm` → `stop` | 張開手掌(停止) | `ACTION_STOP`(立即停止移動) | — | 最高 |
| `Thumb_Up` → `thumbs_up` | 拇指向上(比讚) | `ACTION_CONTENT`(開心動作) | 「謝謝!」 | 中 |
| `Closed_Fist` → `fist` → `ok` | 握拳(確認) | `ACTION_CONTENT`(開心動作) | — | 中 |

上述三類手勢由 `interaction_rules.py` 的 `GESTURE_WHITELIST` 放行後進入 Executive 狀態機;其餘 MediaPipe 可辨識的手勢(Pointing_Up、Victory、Thumb_Down、ILoveYou)在 vision_perception 端即被白名單過濾,不會到達 Executive。這是刻意的保守設計——在專題時程內先確保少數核心手勢穩定可靠,後續有需要再擴充白名單與映射表。

`Open_Palm`(停止手勢)為中控層級的安全優先事件,Executive 無論當前處於哪個狀態(對話中、執行動作中、自我介紹中)都會切換至 `IDLE` 並停下機器狗。依介面契約設計,stop 手勢作為安全機制不受一般 cooldown 限制。

## 效能表現與已知限制

本專題的手勢辨識模組在 Jetson Orin Nano SUPER 8GB 平台上的實測效能如下:推論頻率約每秒 7 幀、CPU 佔用率約 45%(單核心)、GPU 佔用率 0%、記憶體佔用約 200 MB。此效能數據是在人臉辨識、姿勢辨識、物體辨識等其他模組同時運行的場景下測得,確認了 MediaPipe Gesture Recognizer 能與其他感知模組和平共存,不會因為資源競爭而導致整體系統崩潰。

然而,實際部署於本專題時仍存在以下限制:

1. **有效距離約 2 公尺**:MediaPipe Hands 的 BlazePalm 偵測器對手掌的最小像素尺寸有要求,當使用者距離 D435 攝影機超過約 2 公尺時,手部像素過小,關鍵點偵測失敗率顯著上升。

2. **光線敏感**:低光源環境下手部偵測率顯著下降,特別是側光或背光場景。

3. **多人場景跨人關聯缺失**:MediaPipe Hands 預設支援最多雙手同時追蹤,但多人場景下無法將不同人的手進行關聯,無法識別「是誰做了這個手勢」。本系統目前僅對「最靠近」的使用者的手勢做出反應。

4. **複雜背景干擾**:若背景中有類似手掌的物體(如膚色系的家具、其他手型的物品),BlazePalm 偵測器可能產生假陽性。

5. **動態手勢支援有限**:MediaPipe Gesture Recognizer 預設只支援靜態手勢分類,不包含揮手、劃圈等動態手勢。若需支援動態手勢,需自行累積多幀關鍵點並訓練時序分類器(如 LSTM),此為未來工作。
