# 4-5 YuNet 與 SFace 人臉辨識技術

## 技術路線選擇:OpenCV Zoo 而非 MediaPipe

前兩節介紹的手勢與姿勢辨識均採用 Google MediaPipe 框架,但本系統的人臉辨識並未選用 MediaPipe,而是採用 **OpenCV Zoo** 生態中的 **YuNet**(人臉偵測)與 **SFace**(人臉識別)兩個模型組合。本專題在模型選型階段亦評估過 MediaPipe Face Detection 作為候選之一,但因 MediaPipe 在 Jetson ARM64 架構上無預編譯 wheel 可直接安裝,且其 GPU delegate 在 Jetson 環境不可用,部署困難,遂將此選項排除;另一個候選 RetinaFace-R50 因模型檔案約 100 MB、記憶體佔用過大,亦不符合 Jetson 8GB 記憶體預算,同樣排除。最終確定採用 YuNet 2023mar 作為主線偵測器、SFace 2021dec 作為識別器,並以 OpenCV 內建的 `cv2.FaceDetectorYN` 與 `cv2.FaceRecognizerSF` 類別作為統一的推論介面,無須額外安裝任何深度學習框架,大幅簡化了部署流程。

## YuNet 人臉偵測模型

YuNet 是由深圳大學余士琪(Shiqi Yu)教授團隊開發、發表於 2023 年《Machine Intelligence Research》期刊的輕量級人臉偵測模型(論文題目《YuNet: A Tiny Millisecond-level Face Detector》,作者 Wu, Peng, Yu)。YuNet 的設計目標是為邊緣裝置提供毫秒級的人臉偵測能力,其整體架構採用 anchor-free 設計,包含一個精簡的特徵擷取骨幹網路與一個簡化的特徵金字塔融合層(Feature Pyramid Fusion Neck)。相較於常見的人臉偵測模型(如 MTCNN、RetinaFace),YuNet 的參數量僅約 75,856 個,不到其他同級輕量偵測器的五分之一,卻在 WIDER FACE 驗證集的 Hard 類別上達到 81.1% 的 mAP(single-scale),在精度與速度的權衡上表現極為優異。

YuNet 的輸出為人臉邊界框與五個關鍵點,五個關鍵點分別為左眼、右眼、鼻尖、左嘴角、右嘴角。五點關鍵點的用途除了協助判定人臉朝向以外,更重要的是作為後續人臉識別階段的**對齊依據**——SFace 識別模型對輸入人臉的方向與大小有明確要求,需先透過這五個關鍵點進行仿射變換(Affine Transformation)將人臉校正為正面朝上的標準姿勢,才能輸出穩定的特徵向量。

YuNet 模型自 **OpenCV 4.8.0** 起正式整合進 OpenCV DNN 模組並提供 `cv2.FaceDetectorYN` 類別作為呼叫介面。本專題使用的是 2023 年 3 月版本(`face_detection_yunet_2023mar.onnx`),部署於 Jetson Orin Nano 的 CPU 後端執行。在本系統的 benchmark 實測中,YuNet 在 Jetson CPU 上的單模型推論速度達每秒 71.3 幀(輸入尺寸 320 × 320),這是純 CPU 的吞吐量,完全不佔用 GPU 資源。此特性對本專題至關重要——Jetson 的 GPU 需保留給物體辨識的 YOLO26n(TensorRT 加速)使用,若人臉偵測亦走 GPU 會造成資源競爭。本系統亦評估過 **SCRFD-500M**(InsightFace 系列的輕量偵測器)作為備援,實測 Jetson CUDA 版本為每秒 34.7 幀;但 SCRFD 走 GPU 會使姿勢辨識模組的 FPS 額外下降約 10%(相較於 YuNet 走 CPU 只下降 6%),故仍以 YuNet 為主線。

**OpenCV 版本需求說明**:本系統依賴的 `cv2.FaceDetectorYN` 與 `cv2.FaceRecognizerSF` 介面在 **OpenCV 4.8 以上版本**才提供,`face_perception/face_perception/face_identity_node.py` 於節點啟動時以 `hasattr(cv2, "FaceDetectorYN")` 檢查並要求 OpenCV ≥ 4.8,若環境不符會於 runtime 直接拋出 `RuntimeError`。此為硬性版本依賴,部署時必須確認 JetPack 預裝的 OpenCV 版本符合要求或自行 pip 安裝相容版本。

**偵測參數設定**:本系統對 YuNet 的關鍵參數配置如下——`det_score_threshold` 的程式碼原始預設值為 **0.90**(嚴格閾值,`face_identity_node.py:77`),yaml 部署覆寫為 **0.35**(`face_perception.yaml:11`,實戰寬鬆)、`det_nms_threshold=0.30`(非極大值抑制閾值,用於過濾重疊的偵測框)、`det_top_k=5000`(NMS 前保留的候選框最大數量)。偵測器輸入影像會先縮放至 320 × 320 解析度,實測運行於 Jetson 上的 debug 影像發布頻率約為每秒 6.6 幀(含下游的 SFace 識別與追蹤更新)。

## SFace 人臉識別模型

SFace(**S**igmoid-constrained hypersphere loss **Face**)是由鍾彥林(Yaoyao Zhong)等人於 2021 年發表的人臉識別模型(論文《SFace: Sigmoid-Constrained Hypersphere Loss for Robust Face Recognition》,發表於 IEEE TIP 2021)。SFace 的核心貢獻並非全新的神經網路架構,而是提出一種新的損失函數設計——**Sigmoid-Constrained Hypersphere Loss**。此損失函數透過兩個獨立的 sigmoid 梯度重縮放函數分別控制「類內緊湊性」與「類間區隔性」的最佳化強度,讓模型在高品質與低品質訓練樣本上都能穩健學習,不會因為少數難分樣本而過度擬合。此設計特別適合人臉識別這類包含大量低品質資料(光線不佳、角度偏移、部分遮擋)的實際場景,相較於傳統的 ArcFace、CosFace 等損失函數在低品質樣本上表現更為穩健。

SFace 的網路輸出為 **128 維的特徵向量**(embedding),每個人臉被映射到一個 128 維的 hypersphere 表面上的一個點。同一人的不同照片在此空間中應距離相近,不同人的照片則距離較遠。身份比對的核心操作為**餘弦相似度**(Cosine Similarity),即計算兩個特徵向量的夾角餘弦值,值域為 [-1, 1],值越接近 1 代表兩張臉越相似。本系統在 `face_identity_node.py` 的 `cosine_similarity()` 函數中直接以 NumPy 實作此計算,並加入零除保護以處理邊界情況。

SFace 模型同樣整合至 OpenCV Zoo,本專題使用的版本為 2021 年 12 月發布的 `face_recognition_sface_2021dec.onnx`,透過 `cv2.FaceRecognizerSF` 類別呼叫。每張偵測到的人臉在送入 SFace 前,會先使用 YuNet 輸出的五個關鍵點進行仿射校正,再送入 SFace 擷取 128 維 embedding。整個流程完全走 CPU,不佔用 GPU。

## 人臉資料庫(face_db)設計

本專題的人臉資料庫結構簡單直接:每位已註冊使用者擁有一個以姓名命名的資料夾(例如 `/home/jetson/face_db/roy/`、`/home/jetson/face_db/grama/`),資料夾內存放該使用者的多張 PNG 人臉照片。系統於啟動時執行以下流程:

1. **枚舉資料夾**:透過 `list_face_images()` 函數掃描 `face_db/` 目錄下的所有子資料夾,統計每位使用者的照片數量(`compute_db_counts()`)。
2. **訓練模型**:針對每張照片執行「YuNet 偵測 → 五點校正 → SFace 擷取 embedding」流程,為每位使用者建立一組 embedding 向量,並計算其**中心向量(Centroid)** 作為該使用者的代表特徵。訓練完成後以 Python pickle 格式儲存為 `/home/jetson/face_db/model_sface.pkl`,包含每位使用者的 centroid 與原始 sample embeddings。
3. **增量更新**:若重新啟動節點時發現 `model_sface.pkl` 已存在,系統會比對檔案內儲存的 `counts` 與當前資料庫的照片數量,若數量不符則自動重新訓練並覆蓋模型檔案;若相符則直接載入既有模型加速啟動。

此設計的優點是完全免去外部資料庫(如 PostgreSQL、MongoDB)的依賴,所有人臉資料以檔案系統為儲存後端,方便除錯與備份。本系統目前註冊有兩位使用者(`roy` 與 `grama`),作為 Demo 驗證用的基準測試集。

## Hysteresis 雙閾值穩定化機制

人臉識別的一個常見挑戰是**單幀辨識結果的抖動**——由於相似度計算受到光線、角度、微表情的瞬間影響,單一幀的辨識結果可能在已知身份與未知之間頻繁切換,造成互動體驗的混亂(例如機器狗反覆叫錯名字)。為解決此問題,本專題在 SFace 的原始相似度輸出之上,設計並實作了 **Hysteresis 雙閾值穩定化機制**,這是本系統的原創設計之一。

Hysteresis 機制的核心概念來自電子電路中的施密特觸發器(Schmitt Trigger),其運作邏輯如下:

1. **雙閾值設計**:系統設有兩個相似度閾值,`sim_threshold_upper`(上閾值)與 `sim_threshold_lower`(下閾值)。當原始相似度高於 upper 閾值時,才視為「進入已知身份」;當相似度低於 lower 閾值時,才視為「退出已知身份」;兩閾值之間的區間為「hold 區」,維持前次的判定結果不變。此設計避免了單一閾值下的頻繁切換。
2. **候選累計與穩定判定**:系統為每個追蹤對象維持一個狀態機(`track_states`),內含 `candidate_name`(當前候選身份)、`candidate_hits`(連續符合候選的次數)、`last_stable_name`(最後穩定的身份)、`last_stable_sim`、`last_known_ts`(最後一次為已知身份的時間戳)。每幀更新時,若當前候選與上一幀一致則 `candidate_hits` 遞增,否則歸零重新計算。當 `candidate_hits` 達到 `stable_hits` 設定值時,才正式將 `last_stable_name` 更新為新的候選身份。
3. **未知寬限期(Unknown Grace Period)**:若某追蹤對象先前已被識別為某已知身份,但當前幀因瞬間光線變化被判為 unknown,系統會檢查距離上一次為已知身份的時間是否小於 `unknown_grace_s`;若是則維持先前的已知身份,不立即退回 unknown,避免使用者低頭或轉臉造成的瞬間識別失敗。

**Code 原始預設值與 Yaml 部署覆寫值的分層**:`face_identity_node.py` 在 `declare_parameter` 階段設定的**程式碼原始預設值**為較保守的版本——`sim_threshold_upper=0.35`、`sim_threshold_lower=0.25`、`stable_hits=3`、`unknown_grace_s=1.2`、`track_iou_threshold=0.3`、`track_max_misses=10`。這些數值對應文獻建議與開發初期的保守設定。然而,在 Jetson 真機與 D435 實際部署環境下,團隊於 `face_perception/config/face_perception.yaml` 中將這些參數**覆寫為更寬鬆的 Jetson 實戰調參值**:`sim_threshold_upper=0.30`、`sim_threshold_lower=0.22`、`stable_hits=2`、`unknown_grace_s=2.5`、`track_iou_threshold=0.15`、`track_max_misses=20`。此覆寫後的設定允許更寬的追蹤關聯視窗與更短的穩定門檻,降低了因微幅位置抖動與姿態變化造成的 track 流失率,並於 4/6 Jetson smoke test 中將 `identity_stable` 事件的觸發次數由調參前的每 2 分鐘 1 至 3 次提升至 21 次,零誤認,顯著改善了 greeting 功能的可靠度。

## IOU 多人追蹤機制

為支援多人同時進入視野的場景,本系統在 YuNet 的偵測結果之上實作了基於 **IOU(Intersection over Union)** 的多目標追蹤演算法。每幀偵測到的人臉會與前一幀的所有追蹤對象進行 IOU 匹配:若當前人臉框與某追蹤對象的前一幀位置重疊比例高於 `track_iou_threshold`(yaml 部署值 0.15),則將其歸屬於該追蹤對象;若無任何匹配,則分配一個新的 `track_id`(由 `next_track_id` 自增產生)。每個追蹤對象維持一個「連續未偵測到的幀數」計數器,若超過 `track_max_misses`(yaml 部署值 20)則視為離開視野並發布 `track_lost` 事件。

此設計支援的最大同時追蹤數為 `max_faces`(預設 5),足以應付一般家庭場景中的多人情境。然而,與手勢、姿勢辨識模組不同,本系統的追蹤編號僅限於人臉模組內部,尚未與其他感知模組(手勢、姿勢)的追蹤編號進行跨模組關聯——這是第五章系統限制中所述的「多人互動限制」的根本原因。

## ROS2 事件流與問候互動整合

人臉辨識模組向 ROS2 網路發布兩種訊息:

1. **`/state/perception/face`(持續狀態廣播,每個處理幀發布一次)**:以 JSON 格式發布當前幀的完整人臉狀態。此 Topic 的發布頻率不受 `publish_fps` 參數控制(該參數僅控制 debug 影像的發布節流),而是跟隨 camera callback 的實際處理速率,約為每秒 6 至 10 次(依同時運行的其他模組負載而定),包含 `face_count`(視野中的人臉數量)與 `tracks` 陣列,每個 track 內含 `track_id`、`stable_name`(經 Hysteresis 穩定化後的身份名稱)、`sim`(當前相似度)、`distance_m`(由 D435 深度資訊估算的距離)、`bbox` 邊界框座標。此 Topic 供 PawAI Studio 的人臉面板進行即時視覺化。

2. **`/event/face_identity`(觸發式事件)**:在四種關鍵時刻發布事件——`track_started`(新追蹤對象進入視野)、`identity_stable`(經穩定化機制確認身份)、`identity_changed`(已穩定的身份變更為另一個已知身份)、`track_lost`(追蹤對象離開視野)。統一中控模組訂閱此 Topic,當 `identity_stable` 事件觸發且對應的 `stable_name` 為已註冊身份時,切換至 `GREETING` 狀態並發出個人化問候。

為配合 D435 ROS2 驅動節點的 QoS 設定,本系統的影像訂閱採用 `BEST_EFFORT` 可靠性策略(於 3/23 對齊統一),不可改為 `RELIABLE`,否則會因 QoS 不相容而接收不到任何影像幀。此為開發過程中曾遭遇的陷阱之一。

## 效能表現與已知限制

本系統的人臉辨識模組在 Jetson Orin Nano SUPER 8GB 上實測的綜合效能為:debug 影像發布頻率約每秒 6.6 幀、CPU 佔用率約 40%(單核心)、GPU 佔用率 0%、記憶體增量約 300 MB。此數據是在與其他感知模組同時運行的條件下測得,確認了 YuNet + SFace 的 CPU-only 方案能與其他模組和平共存。

然而,實際部署仍存在以下已知限制:

1. **重複問候未冷卻**(4/8 會議確認的 bug):同一已知使用者在短時間內多次進出視野時,系統會重複觸發 greeting 事件而沒有冷卻期機制,造成機器狗反覆叫同一人名字。此問題由統一中控模組層面補足冷卻邏輯,尚未根治。
2. **低光環境誤判**:光線不足時 YuNet 的信心度下降,加上 SFace 的特徵向量變化,可能出現將 A 誤認為 B 的情形。
3. **無人幻覺**:在某些光影條件下,YuNet 偶爾會在空無一人的畫面中輸出高信心度的假人臉(例如窗簾的陰影、電器上的圖案),進而觸發 `track_started` 事件。此為 YuNet 模型固有的偽陽性問題。
4. **track 抖動**:即使加入 Hysteresis 穩定化與 IOU 追蹤,實測 2 分鐘的 smoke test 中仍產生約 45 個 track 被建立(目標為小於 5 個),根因是 YuNet 偵測器的偵測框在連續幀間座標微抖,導致 IOU 匹配失敗而產生大量的 `track_started/track_lost` 事件。此問題已列為下一階段優化目標。
5. **多人場景仍受限**:雖然人臉模組本身支援多人追蹤,但當手勢或姿勢辨識同時觸發時,系統無法判斷手勢屬於哪位已辨識的使用者,整體多模態多人互動的能力仍待跨模組 `person_id` 關聯機制的重新設計。
6. **OpenCV 版本鎖定**:如前所述,`FaceDetectorYN` 與 `FaceRecognizerSF` 介面需要 OpenCV ≥ 4.8。本模組的 `AGENT.md` 文件早期寫「OpenCV 4.5.4+」的宣稱已過時,實際 code require 為 ≥ 4.8,部署時務必確認。
