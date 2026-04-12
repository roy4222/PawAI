# 4-1 機器人作業系統(Robot Operating System 2, ROS2)

## 什麼是 ROS2

機器人作業系統(Robot Operating System,簡稱 ROS)並非傳統意義上的作業系統,而是一個專為機器人軟體開發所設計的開源中介層框架(Middleware Framework)。ROS 最早於 2007 年由美國 Willow Garage 公司所發起,其核心理念是透過標準化的訊息傳遞協定與模組化架構,讓研究者與開發者能夠以「積木式組合」的方式快速搭建機器人應用,避免每個專案都必須從零開始重寫底層的硬體抽象、通訊機制與工具鏈。ROS 提供了一整套從硬體抽象(Hardware Abstraction Layer)、底層裝置驅動(Device Driver)、常用演算法函式庫(如路徑規劃、定位建圖)、訊息通訊(Message Passing)、到開發工具鏈(如 RViz 視覺化、rosbag 錄製回放、rqt 圖形介面)的完整生態系,使得原本高度整合且封閉的機器人研發流程得以以開放原始碼的方式進行協作。

然而,初代 ROS(即 ROS 1)在發展十餘年後逐漸顯露出架構上的限制:其中心化的 `roscore` 節點(Master Node)存在單點失效風險、缺乏即時性(Real-time)保證、無法滿足工業應用對確定性延遲的要求、跨平台支援不足(主要只在 Ubuntu 可穩定運行),並且在多機器人系統與嵌入式裝置上的表現不佳。為了解決這些問題,Open Robotics 於 2017 年正式發布了 ROS2,並以徹底重寫的方式推出全新架構。ROS2 與 ROS 1 在使用者層級的概念(Node、Topic、Service 等)保持類似,但底層實作則完全不同:ROS2 採用 Data Distribution Service(DDS)作為底層通訊協議,移除了中心化的 Master Node,轉為去中心化的點對點架構;新增即時性支援(Real-time Support)、Quality of Service(QoS)策略設定、Lifecycle Node 生命週期管理、跨平台支援(Linux、Windows、macOS、RTOS)、以及多機器人系統的原生支援。本專題採用的 ROS2 **Humble Hawksbill** 版本為 LTS(Long-Term Support)發行版,發布於 **2022 年 5 月 23 日**,官方支援至 **2027 年 5 月**,是目前學術與工業界最主流的 ROS2 版本之一。在本專案中,ROS2 扮演的角色是連接高階 AI 決策模型(雲端大型語言模型、多模態感知推理)與終端實體機器狗(Unitree Go2)底層馬達控制之間的關鍵橋樑:所有感知資料、決策結果與控制指令都透過 ROS2 的訊息機制在模組間流動,使得原本異質且分散的軟硬體元件能夠以統一的介面協同運作。

## 節點與分散式通訊架構

ROS2 採用分散式的節點(Node)架構,每個功能模組被封裝為一個獨立的行程(Process)或執行緒(Thread),節點之間完全解耦且可獨立啟動、停止、重啟,不會影響其他節點的運作。這種架構的優勢在於:首先,任一節點崩潰不會拖垮整個系統(錯誤隔離);其次,節點可分散部署於不同電腦或不同硬體平台(例如感知節點在 Jetson、大腦節點在雲端伺服器),透過網路即可組成完整系統;最後,開發團隊可以針對不同節點使用不同的程式語言(主要支援 C++ 與 Python,本專案大量使用 Python 的 `rclpy` 函式庫),並獨立迭代與測試。本系統的每一個感知與決策模組都被設計為獨立的 ROS2 套件(Package),例如 `speech_processor` 負責語音輸入輸出、`face_perception` 負責人臉辨識、`vision_perception` 負責手勢與姿勢辨識、`object_perception` 負責物體偵測、`interaction_executive` 負責狀態機與事件仲裁,各自可獨立 colcon build、獨立啟動、獨立除錯。

## Publisher–Subscriber 訊息傳遞模型

ROS2 最核心的通訊模型為發布者/訂閱者(Publisher–Subscriber)模型。節點可針對特定的 Topic(主題)建立發布者或訂閱者:發布者將訊息廣播至該 Topic,所有訂閱該 Topic 的節點都會自動收到訊息,發布者與訂閱者之間並不需要預先知道彼此的存在,完全由 ROS2 的 Discovery 機制自動處理連線。這種鬆耦合(Loose Coupling)的設計特別適合感知管線:例如人臉辨識節點只需將辨識結果發布至 `/event/face_identity` Topic,至於這個訊息最後會被 PawAI Studio 的 Gateway、Interaction Executive 狀態機、或是未來新增的記憶模組訂閱,人臉辨識節點完全不需要關心。Topic 上的訊息格式由 ROS2 的 IDL(Interface Definition Language,以 `.msg` 檔案定義)規範,本專案大量使用內建的 `std_msgs/String`(承載 JSON 序列化後的事件酬載)、`sensor_msgs/Image`(影像資料)、`geometry_msgs/Twist`(移動速度指令),以及自訂的 `go2_interfaces/WebRtcReq` 訊息類型(用於 Go2 機器狗的 WebRTC 控制請求)。

## Quality of Service(QoS)策略

ROS2 相較於 ROS 1 的重要進化之一是引入 Quality of Service(QoS)策略。QoS 讓開發者可針對每一組發布者與訂閱者設定訊息傳遞的可靠性、歷史記錄、存活期限等參數,以適應不同場景的需求。本專案主要使用兩種 QoS 設定:

- **Reliable QoS**:保證訊息必定送達,若網路暫時中斷會進行重傳,適用於狀態事件、控制指令等不可遺漏的訊息,例如 `/event/face_identity`、`/event/gesture_detected`、`/tts`、`/webrtc_req` 等 Topic。
- **Best Effort QoS**:不保證訊息送達,但具有較低的延遲與較少的網路負擔,適用於高頻率且可容忍遺失的感測器資料流,例如 D435 相機的 `/camera/camera/color/image_raw`、`/face_identity/debug_image` 等影像 Topic。

QoS 設定不相容會導致訂閱者無法接收訊息(Reliable 訂閱者無法接收 Best Effort 發布者的訊息),這是本專案開發過程中發現的常見陷阱之一,已在第四章「發展中遭遇問題」進一步說明。

## Service 與 Action 通訊模式

除了 Publisher–Subscriber 之外,ROS2 另外提供兩種通訊模式以補足非同步訊息流的不足:

- **Service(服務)**:採用請求/回應(Request–Response)模式,類似傳統的遠端程序呼叫(RPC),適用於一次性的查詢或指令,例如「請求讀取當前人臉資料庫」、「請求切換為守護模式」等。
- **Action(動作)**:擴充自 Service,額外支援進度回報(Feedback)與取消請求(Cancellation),適用於長時間執行且可能中途取消的任務,例如導航至目標點、執行多步驟自我介紹序列等。本專案的設計規格中規劃以 Action 作為 PawAI Brain Skill Queue 的底層實作,但截至本文件繳交時,此機制尚未落地實作——目前的動作仲裁由較輕量的 `interaction_executive` 狀態機(`state_machine.py`)以 Topic 訂閱與直接 publish 完成,並透過 `/executive/status` Topic(2 Hz)廣播狀態。

## 底層 DDS 中介層

ROS2 的通訊機制並不自行處理網路傳輸,而是抽象化為統一介面,底層則透過 Data Distribution Service(DDS)中介層實作。DDS 是由 Object Management Group(OMG)制訂的工業級機器對機器通訊標準,廣泛應用於航太、國防、金融、醫療等對即時性與可靠性要求高的領域。ROS2 預設支援多個 DDS 實作(如 Eclipse Cyclone DDS、eProsima Fast DDS、RTI Connext DDS),本專案使用的是預設的 Cyclone DDS,其特點是輕量、跨平台、社群活躍。ROS2 節點之間透過 DDS 的 Discovery 機制自動發現彼此,不需要類似 ROS 1 的中心化 Master Node,整個系統因此更加去中心化也更具韌性。

## colcon 建構工具與套件管理

ROS2 採用 `colcon` 作為統一的建構工具,取代 ROS 1 時代的 `catkin_make`。colcon 支援 CMake(C++ 套件)與 Python Setuptools(Python 套件)兩種建構系統,並能自動解析套件之間的依賴關係,按正確順序建構。本專案中每個套件都有獨立的 `package.xml`(描述元資料與依賴關係)與 `setup.py` 或 `CMakeLists.txt`,開發者可透過 `colcon build --packages-select <package_name>` 選擇性建構特定套件,加快迭代速度。建構完成後,ROS2 將產出檔案統一放置於 `install/` 目錄,開發者需執行 `source install/setup.zsh`(本專題使用 zsh)將環境變數載入當前 Shell,後續才能執行 `ros2 run`、`ros2 launch` 等指令。

## 本系統中的 ROS2 使用情境

在 PawAI 系統中,ROS2 貫穿所有的感知、決策與執行環節。感知層面,各感知節點以 Publisher 身份將觸發式事件(Event)與持續狀態(State)發布至各自的 Topic;決策層面,Interaction Executive 節點以 Subscriber 身份訂閱所有感知 Topic,根據事件優先序與狀態機狀態決定動作;執行層面,Executive 透過 `/tts` Topic 送出語音合成請求、透過 `/webrtc_req` Topic 送出 Go2 機器狗動作控制指令。整套系統形成一個完整的「感知 → 思考 → 行動」閉環,其中 ROS2 是這個閉環的神經網路,負責在各模組間傳遞訊息、仲裁衝突、協調時序。本系統的 ROS2 介面設計已凍結於 `docs/architecture/contracts/interaction_contract.md` v2.4 版本的介面契約文件,作為跨模組開發的統一參考。

---

# 4-2 Unitree Go2 四足機器人平台

## Unitree 公司與 Go2 系列簡介

宇樹科技(Unitree Robotics)是由中國開發者王興興於 2016 年創立的機器人公司,總部位於浙江杭州,專注於高性能四足機器人的消費級與研究級產品。Unitree 的技術路線以「自研全身關節馬達 + 自主開發運動控制演算法」為核心,相較於傳統機器人廠商動輒數萬美元的售價,Unitree 透過垂直整合與大規模製造將四足機器人的價格壓至消費級範圍,重新定義了四足機器人的市場門檻。其產品線自 2017 年的 Laikago 起,歷經 A1(2019)、Go1(2021)、B1(2022)等世代,於 2023 年推出第四代消費級產品 Unitree Go2,並於後續發展出 Go2-W(輪式混合版本)、Go2-X(特殊地形版本)與 Go2 EDU Plus(搭載 D1 機械手臂版本)等衍生型號。

Go2 的設計定位為「人人可負擔的機器狗」(The Intelligent Robotic Dog for Everyone),以消費級價格提供接近專業級的四足運動能力與 AI 互動體驗。相較於 Boston Dynamics 於 2019 年推出的商用四足機器人 Spot(單機售價約 75,000 美元,主要定位為工業巡檢與研究用途),Go2 以約 1,600 至 2,800 美元的消費級價格帶提供類似的基礎運動能力,大幅降低了四足機器人研究與開發的入門門檻。這也使得原本僅在頂尖實驗室與工業巨頭才能進行的四足機器人應用開發,得以進入大學研究團隊、個人創客,以及本專題所屬的大學部專題實作範疇。

## Go2 三個版本的產品差異

Unitree 為 Go2 系列規劃了三個差異化的版本——Go2 Air、Go2 Pro 與 Go2 EDU,以對應從一般消費者、進階愛好者到學術研究者的不同需求層級。三者使用相同的機身結構與基本運動能力,但在電池容量、運算資源、感測器配置、開發介面開放程度等層面有明顯差異。

**Go2 Air(約 1,600 美元級距)** 是入門消費款,搭載 8,000 mAh 電池,續航約 1 至 2 小時,最高速度約每秒 2.5 公尺,最大負重約 7 公斤。Air 版本不配備 LiDAR 感測器與 4G 通訊模組,使用者只能透過 Unitree 官方 App 以 Wi-Fi 連線進行基本遙控與動作觸發,無 SDK 或程式開發介面,定位為家庭娛樂與入門體驗用途。

**Go2 Pro(約 2,800 美元級距)** 為本專題所採用的版本。Pro 版本搭載 15,000 mAh 電池(續航約 2 至 4 小時,幾乎是 Air 的兩倍),最高速度提升至每秒 3.5 公尺,最大負重約 8 公斤,並配備 **Unitree 自研 4D LiDAR L2**(360° × 96° 半球型掃描、最小檢測距離約 0.05 公尺)與選配的 4G 通訊模組。Pro 版本主要面向進階消費者與入門開發者,定位介於純娛樂與完整研究用途之間。雖然原廠文件將 Pro 版本歸類為「僅支援圖形化 App 控制」,但實際上透過 WebRTC DataChannel 仍可進行底層的動作 API 呼叫與感測器資料接收,這正是本專題能夠在 Pro 版本上開發完整感知與控制系統的關鍵前提。

**Go2 EDU(依配置約 14,500 至 22,500 美元)** 為教育與研究專業版本,價格相較 Pro 有顯著的階梯式差距。在保留 Pro 所有硬體規格的基礎上,EDU 進一步整合了 NVIDIA Jetson Orin Nano(標準版)或 Jetson Orin NX(EDU Plus 版)運算模組(搭載於機身或專用擴充塢),提供 40 至 100 TOPS 的 AI 運算能力,最高速度可達每秒 5 公尺,最大負重可達 12 公斤,並開放完整的 Unitree SDK2(C++)與 `unitree_ros2`(ROS2 整合層)。EDU 版本支援擴充機械手臂(Unitree D1 Arm,EDU Plus 配置)、D435i 深度攝影機與額外感測器,並可透過 CycloneDDS 中介層進行低延遲的即時底層控制。上述售價依 Unitree 官方經銷商公開頁面為準,實際價格會因配置、地區、時間有所浮動。

## Pro 與 EDU 的關鍵差異

表面上看,Go2 Pro 與 Go2 EDU 的價差約為一萬多美元,但兩者在開發者能取得的控制權限與整合深度上存在本質差異。理解這些差異對於本專題的技術決策至關重要,因為它直接影響了本系統的架構選擇與可達成的功能範圍。

**控制權限與 SDK 存取**:Pro 版本的官方軟體支援定位為「圖形化 App 控制 + 預設動作腳本」,不提供 Unitree 官方的 C++ SDK(`unitree_sdk2`)與 ROS2 橋接(`unitree_ros2`)的完整存取權限;EDU 版本則完整開放這些開發者工具,研究人員可直接透過 C++ 或 Python 程式碼控制馬達、讀取感測器原始資料、實作自訂的運動控制演算法。這代表 EDU 版本具備**低階關節控制(Low-level Joint Control)** 的能力,而 Pro 版本僅能透過預先定義的 Sport Mode API 進行高階動作觸發。

**運算平台**:EDU 整合了 NVIDIA Jetson Orin Nano 或 Orin NX 作為機身內建的邊緣運算平台,讓 AI 推論與決策可直接在機身上完成;Pro 則沒有內建運算模組,所有高階 AI 運算必須仰賴外部裝置(例如本專題另外接上的 Jetson Orin Nano)。這使得 Pro 版本的完整系統必須由使用者自行整合外接運算模組、攝影機、電源系統與連線方案。

**通訊協議**:EDU 版本支援雙軌通訊,透過 CycloneDDS(搭配 Ethernet 有線連線)可進行微秒級延遲的底層控制,也支援 WebRTC(搭配 Wi-Fi)進行遠端互動;Pro 版本則主要透過 WebRTC DataChannel 通訊,延遲較高,不適合對即時性要求極高的運動控制,但足以滿足本專題的語音互動與事件觸發類應用。

**擴充能力**:EDU 版本提供更多的電源輸出接口(支援多組 I/O 供外接感測器)、支援 Unitree 原廠機械手臂(D1 Arm)與第三方擴充模組(如 Intel RealSense D435i 深度攝影機、3D 導航 LiDAR 等);Pro 版本的擴充點較少,使用者通常需要自行設計外接電源方案與機構固定件。本專題在 Go2 Pro 機身上外接 Jetson Orin Nano、Intel RealSense D435、USB 麥克風與 USB 喇叭,搭配 XL4015 降壓模組從 Go2 電池取電,即是在 Pro 版本上實作完整感知系統的典型工程挑戰。

## 本專題選用 Go2 Pro 的理由與權衡

本專題選用 Go2 Pro 而非 Go2 EDU 的決定,主要基於三個考量:其一,專題的運算需求由外接 Jetson Orin Nano(指導老師提供)承擔,EDU 內建的 Jetson 並無額外價值;其二,Pro 與 EDU 之間的價差達一萬多美元,遠超專題預算可承擔的範圍;其三,專題的互動式應用對即時控制的延遲要求相對寬鬆(語音對話延遲約數秒、動作觸發延遲低於 1 秒即可接受),不需要 EDU 提供的低階關節控制能力。然而,此選擇也帶來兩個主要的權衡成本:一是本專題無法使用 Unitree 官方 SDK 進行底層控制,必須透過社群開源的 `go2_ros2_sdk`(abizovnuralem/go2_ros2_sdk)以 WebRTC DataChannel 協議與 Go2 通訊,社群 SDK 的文件完整度與穩定性略遜於官方版本;二是 Pro 版本內建 LiDAR 透過 WebRTC 暴露的有效點覆蓋率僅約 18%(實測發布頻率靜止約 7 Hz、行走約 5 至 6 Hz,但每幀有效點數極低),不足以支援穩定的 SLAM 與自主導航,這也是本專題導航避障功能受限的根本原因之一(詳見第五章系統限制)。

## 機體硬體規格與運動能力

Go2 Pro 的機身採用鋁合金框架,整體重量約 15 公斤,尺寸約 70 × 31 × 40 公分(長 × 寬 × 高)。全身共 12 個自由度(12 Degrees of Freedom),每隻腳 3 個關節(髖關節橫向、髖關節縱向、膝關節),由 Unitree 自研的無刷直流伺服馬達驅動,**單關節最大扭矩約 45 N·m**(依 Unitree 官方公開規格),使 Go2 得以支援各種高難度運動動作。Go2 的內建運動控制系統已預訓練多種步態與特技動作,可透過 Sport Mode API 觸發,其中包含正常行走、慢跑、快跑、轉身、坐下、站立、握手、趴下、打招呼、轉圈、跳躍、前空翻、後空翻(部分動作為安全考量被列為禁用)、倒立、舞蹈動作等,總計約 42 個 API 指令。本專題在 Interaction Executive 狀態機中使用其中約 10 個常用動作作為互動反應的輸出。

## 感測器配置

Go2 Pro 的標配感測器包含:

- **Unitree 自研 4D LiDAR L2**:位於機身前方,提供 **360° × 96°** 的半球型掃描範圍,最小檢測距離約 **0.05 公尺**,主要用於原廠的避障與姿態感知功能(依 Unitree 官方公開頁面規格)。然而本專題實測顯示,透過 Go2 WebRTC DataChannel 對外暴露的 LiDAR 資料經過 voxel 編碼後,有效掃描點覆蓋率僅約 18%(每幀約 22 / 120 個有效點)。發布頻率方面,2026 年 2 至 3 月的初步實測曾觀測到低至 0.03 至 2 Hz 的極不穩定數值;2026 年 4 月 1 日重新測試(`docs/導航避障/research/2026-04-01-lidar-frequency-retest.md`)後修正為靜止約 7.3 Hz、16 節點全跑約 7.3 Hz、行走時約 5.0 至 6.1 Hz,推翻了先前的悲觀結論。儘管頻率修正後已不算極低,但有效覆蓋率 18% 仍遠不足以支援 ROS2 Nav2 導航堆疊所需的穩定掃描品質。此為 Go2 Pro 韌體層級將感測器資料向外暴露時的設計限制,而非 LiDAR 硬體本身的缺陷。因此本專題改由外接 Intel RealSense D435 深度攝影機進行近距離感知,並規劃外接 SLAMTEC RPLIDAR A2M12 雷達作為主要的 360° 感知輸入(詳見 4-8 節)。
- **前置 RGB 攝影機**:位於機身前方,用於原廠 App 的即時畫面串流與拍照功能,最高解析度約 1280 × 720、最高 30 FPS。本專題未使用此攝影機,而是外接 Intel RealSense D435 作為主要視覺輸入,因為 D435 同時提供 RGB 與深度資訊,並有較成熟的 ROS2 驅動支援。
- **Inertial Measurement Unit(IMU)**:提供加速度計、陀螺儀與磁力計資料,用於機身姿態估計與運動控制回饋。IMU 資料可透過 DataChannel 即時讀取。
- **關節編碼器**:每個關節配備絕對位置編碼器,提供即時的關節角度與角速度回饋,供運動控制系統使用。

## 通訊機制:WebRTC DataChannel

由於本專題採用 Go2 Pro 版本而非 EDU 版本,無法使用 CycloneDDS 進行底層的 ROS2 原生通訊,因此本系統與 Go2 之間的所有資料交換皆透過 **WebRTC DataChannel** 協議進行。WebRTC(Web Real-Time Communication)原本是為瀏覽器間即時音訊、視訊與資料通訊設計的開放標準,由 Google 主導制定並獲得 W3C 與 IETF 共同標準化。Unitree 將 WebRTC 應用於 Go2 Pro 與 Air 版本上作為主要控制通道,使得外部裝置(如 Jetson Orin Nano 或手機 App)可透過 Wi-Fi 與機器狗建立點對點連線,進行雙向的動作控制與感測器資料串流。

Go2 的 WebRTC DataChannel 通訊定義了一套自訂的 JSON 訊息格式,訊息類型分為 `req`(請求)、`msg`(一般訊息)與 `subscribe`(訂閱)等,每個訊息封包內含 `topic`、`api_id`、`parameter`、`current_block_size` 等欄位。開發者透過建立 Peer Connection 並開啟 DataChannel 後,即可以 JSON 格式發送控制指令(例如 `api_id: 1009` 代表坐下、`api_id: 1016` 代表打招呼)或訂閱感測器 Topic(例如 `rt/utlidar/voxel_map_compressed` 代表 LiDAR 體素圖、`rt/utlidar/robot_pose` 代表里程計)。本專題利用此機制實作了完整的動作控制通道(`/webrtc_req` ROS2 Topic)。音訊播放方面,本專題**主線採用外接 USB 喇叭本地播放**(Jieli CD002-AUDIO,保留原生取樣率,清晰度佳),Go2 機身喇叭的 Megaphone 協議(AudioHub API 4001-4003)則作為備援路徑(受限於 16 kHz 硬體降採樣,詳見 4-6 節)。

## 開發生態與社群資源

Unitree 官方為 Go2 EDU 提供了完整的開發工具鏈,包含 `unitree_sdk2`(C++ SDK,基於 CycloneDDS 實作)、`unitree_ros2`(ROS2 整合層,支援 Ubuntu 22.04 + ROS2 Humble),以及詳盡的 API 參考文件(https://support.unitree.com/home/en/developer)。然而,Go2 Pro 版本的開發者必須仰賴開源社群維護的非官方 SDK。本專題採用的是社群專案 `go2_ros2_sdk`(GitHub: abizovnuralem/go2_ros2_sdk),這是一套為 Go2 Air / Pro / EDU 三個版本提供統一 ROS2 支援的非官方開源框架,採用 WebRTC DataChannel 作為底層通訊協議,並將 Go2 的 Sport Mode API、感測器資料、音訊播放等功能封裝為標準的 ROS2 Topic、Service 與 Action 介面。本專題在此基礎上進一步擴充了語音互動、多模態感知融合、中控狀態機等高階功能,形成完整的 PawAI 系統架構。

---

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

---

# 4-4 MediaPipe Pose 姿勢辨識技術

## BlazePose 架構與全身 33 點骨架

MediaPipe Pose 是 MediaPipe 框架中負責全身姿勢估計的模組,其底層模型為 Google 研究團隊於 2020 年發表的 **BlazePose**(論文《BlazePose: On-device Real-time Body Pose Tracking》,CVPR 2020 Workshop)。BlazePose 是專為行動裝置與邊緣運算場景設計的輕量級人體姿勢估計模型,其架構設計與前節介紹的 MediaPipe Hands 同樣採用兩階段管線,但針對全身骨架的特性有重要差異。

**第一階段為 Pose Detector(姿勢偵測器)**:此模型的任務是從整張輸入影像中快速定位畫面中出現的人體,並輸出一個包裹住整個人的矩形邊界框(Bounding Box)與臉部中心座標。與 MediaPipe Hands 中的 BlazePalm 以手掌作為偵測目標不同,**BlazePose 的偵測器以人臉作為錨點**——因為人臉在各種姿勢變化下(站立、坐下、倒地)的外觀變化相對穩定,而整個人的形狀則會隨姿勢劇烈改變。以人臉為錨點後再推算出整個人的邊界框,偵測穩定性大幅提升。此設計也帶來一個實務限制:若畫面中人體的臉部完全被遮擋(例如背對攝影機、低頭、以帽子遮臉),BlazePose 的偵測穩定度會下降。

**第二階段為 Pose Landmark Model(姿勢關鍵點模型)**:在偵測器定位出人體區域後,該區域被裁切並送入關鍵點回歸模型,輸出全身 **33 個 3D 關鍵點**座標。這 33 點的定義涵蓋整個人體的解剖結構,包括:臉部 11 個關鍵點(鼻子、雙眼內眥、雙眼、雙眼外眥、雙耳、嘴巴左右)、上半身 12 個關鍵點(雙肩、雙肘、雙腕、雙手拇指、雙手食指、雙手小指)、軀幹與下半身 10 個關鍵點(雙髖、雙膝、雙踝、雙腳跟、雙腳趾)。每個關鍵點以 (x, y, z, visibility) 四維資料描述,其中 x、y 為畫面像素座標,z 為相對於髖部中心的估計深度,visibility 為該點是否被遮擋的信心度。

相較於學術界另一個廣為使用的 COCO 17 點骨架格式(僅定義身體主要關節但無臉部細節),MediaPipe Pose 的 33 點格式增加了臉部五官與手腳細節,使得單一模型即可支援從粗略的身體姿態判斷到細節的臉部朝向估計等多樣化需求。本專題為使姿勢分類器能同時支援 MediaPipe 與 RTMPose 兩種後端(兩者輸出格式不同),在 `mediapipe_pose.py` 中實作了一個**座標轉換 adapter(`_MP_TO_COCO`)**,將 MediaPipe 的 33 點骨架對應轉換為 COCO 17 點格式後,再統一餵入 `pose_classifier.py`。此設計讓分類器只需維護一份基於 COCO 17 點的幾何規則邏輯,無論前端使用哪個骨架偵測模型皆可通用。

## 模型複雜度設定(Lite / Full / Heavy)

MediaPipe Pose 提供三種不同複雜度的預訓練模型,允許開發者在速度與精度之間取得權衡:Pose Landmark Lite(約 3 MB,最小延遲、關鍵點偏差較大)、Pose Landmark Full(約 6 MB,精度與延遲兼顧)、Pose Landmark Heavy(約 26 MB,最高精度,但延遲較高且 CPU 負擔較重)。本專題選用 **Lite 版本**(`vision_perception.yaml` 中 `pose_complexity: 0`),理由是:居家場景中使用者距離攝影機通常為 2 至 5 公尺,此距離下 Lite 版本的關鍵點精度已足以支援姿勢判定,且延遲(實測 Jetson CPU 上每秒約 18.5 幀)足以滿足即時互動需求,同時保留最多 CPU 資源供其他感知模組(人臉、手勢、物體辨識)共存。Full 與 Heavy 版本精度更高但 CPU 佔用更大,在 Jetson 8 GB 統一記憶體的環境下不符合多模組共存的資源預算。

## 本系統的姿勢分類邏輯

MediaPipe Pose 僅負責輸出 33 個關鍵點座標,**並不直接輸出姿勢類別**(例如「站立」「坐下」「跌倒」等語意標籤),此部分需由開發者自行實作分類邏輯。本專題的 `pose_classifier.py` 接收經 adapter 統一為 **COCO 17 點格式的 `(17, 2)` 骨架陣列**(`pose_classifier.py:71` 硬性檢查輸入形狀),透過幾何規則判定姿勢類別。

系統從 COCO 17 點骨架中挑選出與姿勢判定最相關的關鍵點(依 COCO body keypoint 編號):雙肩(index 5, 6)、雙髖(index 11, 12)、雙膝(index 13, 14)、雙踝(index 15, 16)。接著計算三個核心角度特徵:

- **髖關節角度(Hip Angle)**:以髖部為頂點,由肩膀與膝蓋形成的夾角。站立時此角度接近 180 度(身體挺直),坐下時降至約 100 至 150 度,蹲下時進一步縮小。
- **膝關節角度(Knee Angle)**:以膝蓋為頂點,由髖部與腳踝形成的夾角。站立時接近 180 度,坐下時較小,蹲下時更小。
- **軀幹傾斜角度(Trunk Angle)**:軀幹中心線與垂直方向的夾角。正常站姿下此角度接近 0 度,跌倒時軀幹接近水平,角度接近 90 度。

結合上述三個角度特徵以及**邊界框長寬比(Bounding Box Aspect Ratio)**與**垂直比例(vertical_ratio)**等指標,系統將當前姿勢判定為以下**五類**之一(依 `pose_classifier.py` 實際程式碼):

| 類別 | 判定條件(本系統實作) | 應用情境 |
|---|---|---|
| `fallen`(跌倒) | `bbox_ratio > 1.0` **AND** `trunk_angle > 60°` **AND** `vertical_ratio < 0.4` | 緊急警示情境 |
| `standing`(站立) | `hip_angle > 155°` **AND** `knee_angle > 155°` | 使用者正常站立或走動 |
| `bending`(前彎) | `trunk_angle > 35°` **AND** `hip_angle < 140°` **AND** `knee_angle > 130°` | 使用者前彎拿東西、綁鞋帶的前期動作 |
| `crouching`(蹲姿) | `hip_angle < 145°` **AND** `knee_angle < 145°` **AND** `trunk_angle > 10°` | 使用者蹲下撿東西 |
| `sitting`(坐下) | `100° < hip_angle < 150°` **AND** `trunk_angle < 35°` | 使用者坐在椅子、沙發上 |

判定順序為 `fallen → standing → bending → crouching → sitting`,五類之間互斥——若都不符合則輸出 `unknown`。值得注意的是本系統的五類定義為 standing / sitting / crouching / fallen / **bending**,不包含一般開源框架常見的 `lying`(平躺)類別——因為實務上躺姿的偵測與 `fallen`(跌倒)在幾何特徵上高度重疊,強行區分兩者容易導致誤判,故將躺姿情境一律歸類為 `fallen`。

## Fallen 判定的關鍵改進:vertical_ratio 防護條件

跌倒偵測是本系統守護功能的核心,但也是最容易誤判的姿勢類別。本專題在開發初期曾遭遇嚴重的**正面站姿誤判為跌倒**問題——當使用者正面站立於攝影機前方時,由於肩膀展開導致邊界框寬度增大,單純依賴「邊界框長寬比 > 1.0」的判定條件會將正面站姿誤認為「橫躺」狀態,進而觸發錯誤的緊急警示。此問題的根源在於絕對尺度(像素寬度)受距離影響過大。

為解決此問題,本專題引入 **vertical_ratio(垂直比例)** 作為跌倒判定的核心防護條件。此指標定義為「肩膀到髖部的垂直距離」除以「軀幹的總長度」,是一個**相對尺度指標**,不受使用者距離攝影機遠近的影響。計算方式如下:

```
vertical_ratio = |shoulder.y - hip.y| / distance(shoulder, hip)
```

當使用者直立時(無論距離遠近),肩膀在髖部正上方,vertical_ratio 接近 1.0;當使用者倒地時,肩膀與髖部呈水平排列,vertical_ratio 接近 0.0。本專題設定閾值為 **0.4**,即 vertical_ratio 必須低於 0.4 才會被視為跌倒候選。此改進大幅降低了正面站姿被誤判為跌倒的情形,但在背景複雜(倒下的掃把、橫放的抱枕)或光線不佳的場景下仍可能出現 fallen 幻覺。**因此 Demo 場景透過 `enable_fallen:=false` 參數暫時關閉跌倒偵測**(`start_full_demo_tmux.sh:137`),以確保互動流程不被誤觸發;跌倒偵測作為守護功能在獨立展示時啟用。

## 多幀投票穩定機制

即使加入 `vertical_ratio` 防護條件,單幀的姿勢分類結果仍可能因為使用者瞬間的動作變化、手部揮動、或模型關鍵點抖動而產生噪訊。為進一步提升穩定性,本系統實作了**多幀投票機制**:姿勢分類器維持一個長度為 `pose_vote_frames`(部署值 20 幀,約對應 1 至 2 秒的真實時間)的滑動視窗,持續記錄每幀的分類結果,並以該視窗內的多數決作為最終輸出的姿勢標籤。多數決的門檻並非硬編碼為特定比例,而是由 buffer 內的類別分佈動態決定。

此機制帶來兩個實用好處:其一,有效過濾單幀誤判;其二,為跌倒判定提供「持續性」的條件——真實的跌倒事件通常持續數秒,人會維持倒地狀態;而誤判通常是瞬間的(例如使用者突然彎腰撿東西),不會連續數十幀都被判定為跌倒。透過 `vertical_ratio` 與多幀投票的雙重防護,本系統的跌倒偵測誤報率已降至可接受範圍。

## 本系統的姿勢事件流與中控整合

姿勢辨識模組持續以約每秒 18 幀的頻率更新姿勢狀態,並在姿勢類別發生變更時發布事件至 ROS2 Topic:

- **`/event/pose_detected`(觸發式事件)**:當多幀投票的結果從一個姿勢類別切換至另一個類別時,發布一次事件,訊息內含新的姿勢類別、信心度、時間戳記等欄位。此 Topic 為本系統姿勢模組對外的唯一輸出介面,其他模組(如 PawAI Studio 姿勢面板、Interaction Executive 中控)皆訂閱此 Topic 取得最新姿勢狀態。

統一中控模組(Interaction Executive)訂閱 `/event/pose_detected` Topic,並將 `POSE_FALLEN` 事件設定為最高優先級之一(與 stop 手勢並列)。當跌倒事件被觸發時,中控模組會立即切換至 `EMERGENCY` 狀態,執行以下動作序列:停止機器狗當前所有行為、透過 TTS 發出語音確認(「您還好嗎?」)、在 PawAI Studio 上以紅色邊框閃爍的方式醒目標示、等待使用者回應或進一步指示。為避免誤報影響 Demo 流程,本系統提供 `enable_fallen` 啟動參數,可在不需要守護功能的互動 Demo 場景中暫時關閉跌倒偵測。

## 效能表現與已知限制

本專題的姿勢辨識模組在 Jetson Orin Nano SUPER 8GB 平台上的實測效能如下:推論頻率約每秒 18.5 幀(MediaPipe Pose Landmark Lite 模型,`pose_complexity: 0`)、CPU 佔用率約 50%(單核心)、GPU 佔用率 0%、記憶體佔用約 250 MB。實際運行中與手勢辨識、人臉辨識模組共用同一支 D435 攝影機影像流,整體 CPU 總佔用率約 70%,仍有餘裕支援其他模組。

然而,姿勢辨識在本專題實際部署中仍存在以下已知限制:

1. **側面姿勢判定偏差**:BlazePose 模型的訓練資料以正面姿勢為主,當使用者側身面對攝影機時,部分關鍵點(特別是遠側的肩膀、膝蓋)容易被身體自身遮擋,導致髖關節與膝關節的角度計算出現偏差,坐下與站立的判定可能混淆。本系統的 Demo 場景建議使用者儘量正面面向攝影機。

2. **有效偵測距離約 2 至 5 公尺**:過近(小於 1.5 公尺)時人體超出攝影機視野,部分關鍵點(如腳部)無法被偵測;過遠(大於 5 公尺)時人體像素過小,關鍵點精度下降。

3. **多人場景僅支援單人**:MediaPipe Pose 預設僅處理畫面中最顯著的一位人員,即使 BlazePose 偵測器能同時偵測多人,關鍵點回歸模型每次只處理一個人體區域。多人同時出現時,姿勢辨識會鎖定其中一人並忽略其他人,此為本系統第五章中「多人同時互動」限制的一部分。

4. **跌倒誤判之殘存風險**:儘管已加入 `vertical_ratio` 與多幀投票機制,在背景複雜(倒下的掃把、橫放的抱枕、晾在椅背上的衣物)或光線不佳的場景下,BlazePose 仍可能將非人物體誤認為倒地的人體。本系統透過 `enable_fallen` 參數讓 Demo 場景可選擇性關閉此功能。

5. **快速動作辨識延遲**:多幀投票機制帶來約 1 至 2 秒的延遲,快速的姿勢變化(例如坐下後立即站起)可能來不及在視窗內累積足夠票數而被忽略。此為穩定性與即時性的取捨。

---

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

---

# 4-6 語音互動管線技術

## 兩條並存的語音輸入路徑

本系統的語音互動管線並非單一直線流程,而是由兩條並存的輸入路徑組成,以對應「Demo 主線」與「舊本地麥克風路徑」兩種不同的使用情境:

- **Demo 主線(目前實際使用)**:使用者於 PawAI Studio 網頁介面按住說話(push-to-talk),錄音音訊透過 WebSocket 經由 `/ws/speech` 端點上傳至 Gateway(`pawai-studio/gateway/studio_gateway.py`)。Gateway **在自身行程內完成 ASR 與意圖分類**——直接以 HTTP POST 將音訊送至雲端 SenseVoice server(`http://127.0.0.1:8001/v1/audio/transcriptions`,經 SSH tunnel),取得辨識結果後在 Gateway 端完成意圖分類,再將結果發布至 ROS2 的 `/event/speech_intent_recognized` Topic。**此路徑完全不經過 `stt_intent_node`**,也無前置 VAD——push-to-talk 的起訖時間由使用者按鈕動作明確界定。

- **舊本地麥克風路徑(已廢棄但保留)**:使用者直接對 Go2 機身上的 USB 麥克風說話,由 `stt_intent_node` 連續監聽音訊串流並透過 Energy VAD 自動切分語音段落,再送入 ASR。此路徑保留於 `stt_intent_node.py` 中以備未來使用者改用獨立指向性麥克風時可以快速復用,但目前 Demo 場景已全面改用 Studio push-to-talk。

之所以從機身麥克風路徑轉為 Studio push-to-talk,是因為 Go2 內建的散熱風扇在機器狗運作期間持續產生寬頻噪音,機身麥克風與風扇出風口距離過近,實測語音辨識正確率僅約 20%,低於可用門檻。團隊嘗試調高麥克風增益(mic_gain)、調整 VAD 閾值、擴充 Whisper 幻覺過濾黑名單等軟體手段,皆無法克服物理層級的 SNR 劣化,遂於 2026 年 4 月 8 日教授會議後定案改用 Studio push-to-talk。此方案雖然犧牲了「直接對機器狗說話」的直覺性,但換來穩定的辨識率與 Demo 可靠度。

## 管線七階段總覽

兩條路徑在 ASR 之後收斂為相同的後續流程。整條管線可分為七個階段:**音訊擷取 → (僅舊路徑) Energy VAD → ASR 語音辨識 → 意圖分類 → LLM 大型語言模型回覆生成 → TTS 語音合成 → 音訊播放**。其中 Demo 主線的前兩階段(音訊擷取 + ASR)在 Gateway 行程內完成,後續 LLM、TTS、播放仍由獨立 ROS2 節點處理。實測端到端延遲(從使用者停止說話到機器狗開始播放語音回覆)約為 2 秒級,於 2026 年 4 月 8 日的 Studio Chat 閉環實測中完成多句連續對話驗證,整體管線穩定性達到 Demo 可用水準。

## Energy VAD 語音活動偵測(舊路徑前處理)

在舊本地麥克風路徑下,系統需先判斷何時使用者真的在說話,避免將靜音或背景噪音送入辨識模組。本系統採用輕量的能量式語音活動偵測(Energy-based Voice Activity Detection, Energy VAD),其原理是計算連續音訊短時能量,若超過 `start_threshold` 即視為語音開始,低於 `stop_threshold` 並持續超過 `silence_duration_ms` 即視為語音結束。

**程式碼預設值與 Demo 啟動覆寫值的差異**:
- `stt_intent_node.py` 中 `declare_parameter` 的程式碼預設值為:`start_threshold=0.015`、`stop_threshold=0.010`、`silence_duration_ms=800`、`min_speech_ms=300`。
- 實際 Demo 啟動腳本 `scripts/start_full_demo_tmux.sh` 在啟動 `stt_intent_node` 時覆寫為:`start_threshold:=0.02`、`stop_threshold:=0.015`、`silence_duration_ms:=1000`、`min_speech_ms:=500`。

這組被稱為 Noisy Profile v1 的調校值是針對 Go2 伺服馬達運轉時的持續噪音環境做系統性 A/B 測試後的結果,提高 `start_threshold` 能有效避免 Go2 噪音誤觸發語音段開始。選擇 Energy VAD 而非更精準的深度學習 VAD(如 WebRTC VAD、Silero VAD)的主要理由是延遲與簡單性:Energy VAD 每幀僅需 O(1) 運算,無需載入模型,延遲極低。

需再次強調的是,**目前 Demo 主線採用 Studio push-to-talk,此路徑完全跳過 Energy VAD**;上述參數僅對舊本地麥克風路徑生效。

## ASR 三級 Fallback 機制

語音辨識是整條管線中最複雜的環節。本系統在 ASR 層存在**兩條獨立路徑**,需分開說明:

### Demo 主線:Gateway 內直打 SenseVoice Cloud

Demo 主線中,Studio Gateway(`studio_gateway.py`)的 `/ws/speech` WebSocket 端點接收到音訊後,**在 Gateway 行程內直接以 HTTP POST 呼叫 SenseVoice Cloud server**(`http://127.0.0.1:8001/v1/audio/transcriptions`,經 SSH tunnel 連線至遠端 RTX 8000),取得辨識文字後於 Gateway 端執行意圖分類,再將結果發布至 ROS2 的 `/event/speech_intent_recognized` Topic。此路徑是單條直打,**不經過 `stt_intent_node`**,也不存在多級 fallback——若雲端 server 不可用,Gateway 會直接回報錯誤。

### 舊本地麥克風路徑:stt_intent_node 三級 Fallback

舊本地麥克風路徑下,`stt_intent_node` 採用**三級自動降級(Graceful Degradation)** 策略,在網路狀況、伺服器可用性、運算資源變化時動態切換後端,確保服務不中斷。三個層級依 `stt_intent_node.py` 中 `provider_order` 參數的順序執行(注意:程式碼內部一級 provider key 仍為 legacy 名稱 `qwen_cloud`,實際後端已切換為 SenseVoice FunASR server):

**一級:SenseVoice Cloud(provider key: `qwen_cloud`)**。SenseVoice 是阿里巴巴達摩院於 2024 年開源的中文優化語音辨識模型家族,專為亞洲語言(中文、粵語、日文、韓文、英文)設計,相較於 Whisper 對中文短句與方言的辨識率更高,並額外輸出說話者的情緒與音訊事件標籤。本系統採用 SenseVoice Small 版本,透過 **FunASR 框架**(阿里巴巴達摩院維護的端到端語音工具包)部署於遠端 RTX 8000 伺服器上,以 FastAPI 封裝 HTTP 介面(`scripts/sensevoice_server.py`,port 8001)。Jetson 透過 SSH tunnel 與雲端伺服器建立連線,將錄音音訊以二進位格式 POST 至伺服器並接收 JSON 回應。實測延遲約 600 毫秒。

**二級(備援):SenseVoice Local**。當雲端伺服器不可用(SSH tunnel 斷線、伺服器未啟動、網路中斷)時,系統自動切換至 Jetson 本地執行的 SenseVoice 量化版本。此版本透過 **sherpa-onnx**(由 k2-fsa / 新一代 Kaldi 團隊維護的輕量化語音推理框架)執行 int8 量化後的 ONNX 模型(`sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17`,檔案大小約 228 MB,執行時佔用約 352 MB RAM)。此版本完全離線、僅使用 CPU,不佔用 Jetson 的 GPU 資源,實測延遲約 400 毫秒(因省去網路往返時間,甚至略快於雲端版本),辨識率維持與雲端相當的水準。

**三級(最終備援):Whisper Tiny(faster-whisper)**。若 SenseVoice Cloud 與 Local 皆不可用,系統退回至 OpenAI 於 2022 年發布的 Whisper 模型。Whisper 為多語言 Encoder-Decoder Transformer 架構,原生支援 99 種語言,在高品質錄音條件下表現優異。本專題透過 **faster-whisper** 框架(基於 CTranslate2 的 CUDA 加速實作,速度最高可達原生 Whisper 的約 4 倍)於 Jetson 上推理。

**關於 Whisper 實際部署配置的澄清**:`speech_processor/config/speech_processor.yaml` 中的**基礎預設值**為 `whisper_local.model_name: "tiny"`、`whisper_local.device: "cpu"`、`whisper_local.compute_type: "int8"`(CPU + tiny + int8 的極省資源配置,用於開發與低功耗場景)。然而 Demo 啟動腳本 `scripts/start_full_demo_tmux.sh` 在啟動 `stt_intent_node` 時**覆寫為 `whisper_local.device:=cuda`、`compute_type:=float16`**,即實際 Demo 跑的是 CUDA + float16 版本。此覆寫之必要性源於 Jetson 的 CUDA 核心不支援 int8 量化(強制指定 int8 會 silent fail 無錯誤訊息),因此 Demo 必須使用 float16 混合精度。實測 RTF(Real-Time Factor,推論時間除以音訊時長)約 0.13,即 3 秒音訊需約 390 毫秒處理,延遲約 3 秒(含模型首次載入)。**Whisper 僅為 `stt_intent_node` 三級 fallback 的最末層;Demo 主線走 Gateway 直打 SenseVoice Cloud,正常連線下 Whisper 不會被觸發**。

**三層 ASR A/B 測試結果**(25 筆,Go2 噪音環境):

| 指標 | SenseVoice Cloud | SenseVoice Local | Whisper Tiny |
|---|:---:|:---:|:---:|
| 正確 + 部分正確率 | 92% | 92% | 52% |
| Intent 正確率 | 96% | 92% | 56% |
| 幻覺 / 亂碼率 | 0% | 0% | 8% |
| 延遲 | ~600 ms | ~400 ms | ~3000 ms |
| 需要網路 | 是 | 否 | 否 |

**Whisper 幻覺問題與對策**:Whisper 模型存在一個已知的「幻覺」(Hallucination)問題——在靜音片段或低訊噪比片段會輸出假文字,最常見的是訓練資料中的字幕模板(例如「字幕 by 索兰娅」「請訂閱頻道」等)。本系統採取以下對策:啟用 `vad_filter=True` 使用 Silero VAD 預先過濾非語音段、設定 `no_speech_threshold=0.6` 拒絕低信心結果、設定 `log_prob_threshold=-1.0` 過濾低機率輸出、維持一份 **22 條幻覺黑名單字串**對輸出結果進行最終過濾、並過濾所有少於 2 字的結果。這些對策共同將 Whisper 的假陽性問題降至可接受範圍。

## 意圖分類與 Fast Path

ASR 輸出的文字接著進入意圖分類階段。本系統採用**規則式(Rule-based)分類器**而非機器學習分類器,原因是意圖類別有限(約 10 種)、規則明確、且可享受近乎零延遲的直接查表速度。分類器透過關鍵字匹配將 ASR 文字對應至以下意圖標籤:`greet`(打招呼)、`stop`(停止)、`sit`(坐下)、`stand`(站起)、`come_here`(過來)、`chat`(一般對話)等。

**Fast Path 設計**:對於高頻的動作類意圖(stop、sit、stand 等),系統繞過下游的大型語言模型處理,直接呼叫內建的 RuleBrain 規則引擎生成預設回覆,總延遲接近零。此設計讓 Demo 場景中的指令類互動能瞬間響應,優於「必須經過 LLM」的純雲端方案。僅當使用者說出一般對話(無法匹配任何已知意圖關鍵字)時才進入 LLM 流程。

## LLM 三級 Fallback 機制

大型語言模型負責處理意圖分類無法涵蓋的一般對話,生成符合情境的中文回覆。本系統同樣採用三級降級策略:

**主線:Cloud Qwen2.5-7B-Instruct**。採用阿里巴巴開源的 Qwen2.5 系列 7B 參數 Instruct 版本,透過 **vLLM** 推理框架部署於遠端 RTX 8000 伺服器。vLLM 是 UC Berkeley Sky Computing Lab 於 2023 年開源的高效能 LLM 推理引擎,核心技術為 **PagedAttention**(將 KV cache 管理對應至作業系統的虛擬記憶體分頁機制,大幅降低記憶體碎片化)與 **Prefix Caching**(重複 prompt 前綴的結果快取重用)。本系統的互動場景中,系統提示(system prompt)固定不變,Prefix Caching 帶來顯著的加速,實測 LLM 回覆延遲約 1.5 秒。模型參數 `llm_max_tokens=80`(由 `llm_bridge_node.py` declare_parameter 預設值),SYSTEM_PROMPT 內硬性要求 `reply_text` 不超過 **12 個中文字**,避免過長語音導致互動節奏拖沓。

**二級:Ollama 本地 Qwen2.5-1.5B**。當雲端不可用時(SSH tunnel 斷線、vLLM 伺服器異常、GPU OOM 等),系統自動切換至 Jetson 本地的 **Ollama**(Jetson ARM64 確認可用的輕量 LLM 推理框架)執行 Qwen2.5-1.5B-Instruct 模型(Q4_K_M GGUF 量化,檔案大小約 1.12 GB,執行時佔用約 1.2 至 1.5 GB RAM)。本地模型採用 CPU 推理模式(`CUDA_VISIBLE_DEVICES=""`)避免與其他 GPU 模組競爭資源,實測 P50 延遲約 1.0 秒、生成速度約 29 tokens/sec,25 字回覆的端到端延遲約 2 至 3 秒。值得注意的是,2026 年 4 月 8 日的教授會議上,團隊正式確認本地 LLM 的語言流暢度遠低於雲端主線,實務上只能作為「維持管線不中斷」的形式備援,無法承擔主要對話責任。先前評估的更小模型 Qwen2.5-0.5B 雖然速度更快(P50 延遲 0.8 秒、RAM 增量僅 139 MB),但中文對話品質明顯不足,已被排除。

**最終備援:RuleBrain 規則引擎**。當雲端與本地 LLM 皆不可用(或 LLM timeout 超過 2 秒)時,系統退回至完全 deterministic 的規則引擎。RuleBrain 內建一組固定的模板回覆(例如問候類回覆「你好,很高興見到你」、停止類回覆「好的,我停下」、無法理解時的通用回覆「抱歉,我聽不太懂,你可以再說一次嗎」等),根據輸入的意圖類別直接查表輸出,延遲接近零,並保證絕不輸出空字串或錯誤格式。此層級是整條管線的最後防線——即使網路完全斷線、本地模型損毀,RuleBrain 仍能讓機器狗維持基本的對話回應能力,不會完全啞掉。

## TTS 雙軌 Fallback 機制

語音合成階段採用雙軌策略:

**主線:edge-tts 微軟雲端 TTS**。edge-tts 是一個開源的 Python 客戶端,透過呼叫微軟 Edge 瀏覽器內部使用的 Neural Voice API 取得雲端合成的語音檔案。此服務不需註冊帳號或 API key,使用方式如同呼叫微軟的公開服務。本系統使用中文 Xiaoxiao 神經語音作為主線聲音,實測首句延遲約 0.3 至 0.8 秒(包含網路往返時間),音質等級評為 A 級(相較於本地備援的 Piper 音質更為自然、語調更有抑揚頓挫)。edge-tts 不佔用 Jetson 的 CPU / GPU / 記憶體資源(僅需約 50 MB 作為 HTTP 客戶端緩衝),是 Demo 場景中的理想選擇。主要限制為必須聯網,且此為微軟的非正式公開 API,若未來微軟變更介面可能失效。

**備援:Piper 本地 TTS**。Piper 是 Rhasspy 開源社群維護的離線 TTS 引擎,採用 **VITS(Variational Inference TTS)** 架構(VITS 為 2021 年論文《Conditional Variational Autoencoder with Adversarial Learning for End-to-End Text-to-Speech》提出的端到端語音合成模型),以 ONNX 格式於 CPU 上執行推理。本系統使用 `zh_CN-huayan-medium` 中文單聲道模型,模型檔案僅約 63 MB,執行時佔用約 200 MB RAM,完全不依賴網路。原生取樣率為 22050 Hz,透過 USB 外接喇叭播放時可保留此原始音質;若改走 Go2 Megaphone 路徑則會被硬體限制降採樣至 16 kHz。實測首句延遲約 2.4 秒,略慢於 edge-tts 但仍在可接受範圍。Piper 相較於其他開源 TTS 的主要優勢是其為 CPU-only 且記憶體佔用極低,不會與其他模組競爭 Jetson 的有限資源。

**已排除的 TTS 候選**:本專題曾評估過多個其他 TTS 方案並予以排除,包含:

- **MeloTTS**(音質接近 edge-tts 但速度不如 Piper,卡在尷尬定位,2026-03-26 會議決議棄用)
- **ElevenLabs**(商業服務成本高、API 整合複雜,已兩次棄用)
- **Spark-TTS-0.5B**(模型約 3.95 GB,Jetson 8 GB 記憶體不足以與其他模組共存)
- **XTTS v2**(模型約 1.8 GB、runtime 另需 2 至 3 GB,超出預算)
- **ChatTTS**(需 4 GB 以上 GPU VRAM,穩定性差)
- **Bark**(完整模型需約 12 GB VRAM,遠超 Jetson 硬體能力)

## 音訊播放:USB 外接喇叭與 Go2 Megaphone 雙路徑

合成完成的 WAV 音訊檔案接著送至播放階段。本系統支援兩條播放路徑:

**主線:USB 外接喇叭本地播放**。本專題於 2026 年 3 月採購外接 USB 音訊裝置(Jieli CD002-AUDIO,立體聲 48 kHz,對應 ALSA `plughw:3,0`)安裝於機器狗機身上,TTS 合成的音訊檔案直接透過 ALSA `aplay` 或 Python `sounddevice` 函式庫在本地播放。此路徑的優勢是:保留原生取樣率(22050 Hz 或 48 kHz)、延遲極低、穩定可靠、不依賴 Go2 韌體的 Megaphone API。

**備援:Go2 Megaphone DataChannel**。Unitree Go2 原廠提供 Megaphone API(api_id 4001 至 4003),允許外部裝置透過 WebRTC DataChannel 上傳音訊至機身內建喇叭播放。協議流程為 **ENTER(4001)→ UPLOAD(4003,分塊上傳,每塊 4096 base64 字元)× N → EXIT(4002)**,每塊間隔約 70 毫秒發送,訊息 type 必須為 `"req"`(非 `"msg"`)、payload 必須包含 `current_block_size` 欄位(文件未載明的隱性要求)。此路徑受限於 16 kHz 採樣率(Go2 硬體限制)與 mid-session 重啟後的 silent fail 問題,作為備援使用。本專題曾花費約兩週時間判定此 API「失效」,後透過逆向分析通訊封包找出正確格式,最終驗證連續播放成功。

## Echo Gate 自激防止

語音互動系統常見的一個問題是**自激回饋(Self-echo Feedback)**——機器狗播放語音時,同一組麥克風會接收到自己的聲音並誤判為新的語音輸入,造成無限迴圈。本系統透過 **Echo Gate** 機制解決此問題:當 `/state/tts_playing` flag 為 True 時(表示 TTS 正在播放),ASR 節點強制靜音不發布任何辨識結果;TTS 播放結束後,系統額外等待 `cooldown = 0.5` 秒(處理音訊管線殘留)+ `echo_cooldown = 1.0` 秒(處理喇叭延遲),共 **1.5 秒的總靜音期**,才重新開放 ASR 接收使用者語音。此機制經 Sprint 期間反覆驗證,是防止 Megaphone 播放回音造成管線失控的核心防護。

## Noisy Profile v1 噪音環境調校

為應對 Go2 伺服馬達運轉時的持續噪音,本專題於 2026 年 3 月 28 日建立 **Noisy Profile v1** 參數配置,針對 Go2 真機運作條件進行系統性的 VAD 與 ASR 調校。核心調整包括:

- **mic_gain**:`stt_intent_node` 中的 code default 為 1.0,Demo 啟動腳本覆寫為 **8.0**。A/B 實測甜蜜點——gain 10 測試後發現 Whisper 辨識率反而下降至 43%、gain 12 為 62%,證明噪音放大過度,8.0 為最佳平衡。
- **Energy VAD 閾值**:如前述「Energy VAD 語音活動偵測」段落所示,Demo 啟動腳本將 VAD 閾值覆寫為更高的值以避免 Go2 伺服噪音誤觸發。
- **Whisper 設定**:啟用 `vad_filter`、`no_speech_threshold=0.6`、幻覺黑名單從最初 6 條擴充至 22 條。

實測 Whisper Tiny(yaml 預設 `model_name: "tiny"`)在此 profile 下的 A/B 結果為 64% 正確率,確認為 Whisper 在中文短句 + 機器噪音場景下的瓶頸。此數據後來推動了從 Whisper 到 SenseVoice 的主線切換決策。

此外,Noisy Profile 亦引入 `ENABLE_ACTIONS` 環境變數作為動作執行的安全門——當設定為 `false` 時,`llm_bridge_node` 停止發布 `/webrtc_req`,Go2 即使收到錯誤的 ASR 結果或意圖分類錯誤也不會執行危險動作,用於開發與除錯階段。動作控制的仲裁主線目前由 `interaction_executive`(統一中控狀態機)負責,已取代早期的 `event_action_bridge`。

## Plan B 固定台詞備案

考量到 Demo 當天 GPU 雲端伺服器的穩定性風險(本專題 Sprint 期間實際發生過數次斷線事件),團隊於 2026 年 4 月 8 日教授會議上決定追加 **Plan B 固定台詞備案**。Plan B 的運作機制如下:ASR 辨識出意圖後直接匹配預先設計的固定回答,繞過 LLM 與 TTS 的動態生成流程(或使用 Piper 離線合成固定台詞的快取檔案),回應速度小於 1 秒。Plan B 需設計至少 15 組問答涵蓋 Demo 主要情境(自我介紹、功能說明、閒聊、指令回應),並於 PawAI Studio 顯示連線狀態燈號讓團隊能即時判斷是否切換模式。Plan B 的負責人為團隊成員陳如恩。此備案無法取代完整的 AI 對話體驗,但能在最壞情況下維持 Demo 現場的流暢度,必要時搭配預錄的 AI 對話影片作為佐證。

## ROS2 Topic 介面整合

語音模組透過以下 ROS2 Topic 與系統其他模組整合:

| Topic | 方向 | 說明 |
|---|:---:|---|
| `/event/speech_intent_recognized` | 輸出 | 意圖辨識事件(JSON 格式,含意圖類別、信心度、原始文字) |
| `/state/interaction/speech` | 輸出 | 語音管線狀態廣播(5 Hz,含目前階段:聆聽/辨識/思考/說話) |
| `/state/tts_playing` | 輸出 | TTS 播放中 flag(供 Echo Gate 使用) |
| `/tts` | 輸入 | 要合成的文字(供其他模組觸發語音輸出) |
| `/asr_result` | 輸出 | 原始 ASR 辨識文字 |

其他模組(如 Interaction Executive、PawAI Studio Gateway、物體辨識情境 TTS 觸發)透過這些 Topic 與語音模組互動,不需要知道管線內部的任何細節。

## 已知限制

本節對應第五章系統限制第 3 節,列出本模組實務上的邊界條件:

1. **機身麥克風不可用**(如前所述,已改用 Studio push-to-talk)。
2. **本地 LLM 品質不足**:Jetson 本地的 Qwen 系列小模型(1.5B)中文對話品質明顯低於雲端 7B 主線,4/8 會議確認僅能作為形式備援。
3. **LLM 回覆過短**:受限於 `llm_max_tokens=80` 與 SYSTEM_PROMPT 中的 **12 字硬截斷**要求,LLM 無法展開詳細對話或多輪推理,個性化表達空間有限。已列為下一步改進重點(prompt 放寬字數至 50+、加入 PawAI 個性設定)。
4. **無多輪對話記憶**:當前 LLM 呼叫為無狀態模式,每輪對話獨立,不記得先前的對話內容。多輪 memory 功能尚未整合,列為未來工作。
5. **Stop intent 辨識不穩**:SenseVoice 對「現在請停止動作」這類較長的句式辨識率約為 60%,簡短的「停」辨識率較高。建議使用者說簡短指令或搭配手勢 stop 作為更可靠的緊急停止機制。
6. **雲端 GPU 伺服器穩定性風險**:Sprint 期間實際發生過數次 RTX 8000 伺服器斷線事件,Plan B 固定台詞備案為 Demo 當天的必備保險。

---

# 4-7 YOLO26 物體辨識技術

## YOLO 系列演進與 YOLO26 定位

YOLO(**Y**ou **O**nly **L**ook **O**nce)是由 Joseph Redmon 等學者於 2016 年提出的即時物體偵測演算法,其核心理念是將物體偵測轉化為單一迴歸問題——影像只需進入神經網路一次,即可同時輸出所有物體的邊界框與類別,相較於前代基於區域提案的兩階段偵測器(如 R-CNN 系列)速度快數十倍。自首版 YOLO 發布以來,YOLO 系列歷經 v2、v3、v4、v5(Ultralytics 團隊接手維護)、v6、v7、v8、v9、v10、v11 等多個版本,逐代在精度與速度的權衡上取得突破。

本專題採用的 **YOLO26** 是 Ultralytics 於 **2026 年 1 月 14 日**正式發布並開放下載的最新一代 YOLO 架構,是專為邊緣裝置與低功耗平台設計的版本,核心改進包含 NMS-free 原生端到端設計、DFL 模組移除、MuSGD 最佳化器、ProgLoss 與 STAL 損失函數等多項技術創新。YOLO26 完整支援五種主要電腦視覺任務——物體偵測(Detection)、實例分割(Instance Segmentation)、影像分類(Classification)、姿勢估計(Pose Estimation)、旋轉框偵測(Oriented Bounding Box, OBB),每種任務皆提供 Nano(n)、Small(s)、Medium(m)、Large(l)、Extra-Large(x)五種模型大小,提供從邊緣運算到伺服器應用的完整頻譜。本專題採用最小的 **YOLO26n 偵測模型**,ONNX 格式檔案僅約 9.5 MB。YOLO26 採用 AGPL-3.0 授權,開放給學術與研究用途使用。

## YOLO26 的核心架構創新

YOLO26 相較於前一代 YOLO11 在架構層面導入了多項重要改進,使其在邊緣推理場景下表現顯著優於同級別的前代模型:

**NMS-free 原生端到端設計**。YOLO26 是原生的端到端物體偵測模型,推理階段直接輸出最終偵測結果,不再需要執行傳統 YOLO 系列中的非極大值抑制(Non-Maximum Suppression, NMS)後處理步驟。傳統 YOLO 的 NMS 有三個實務痛點:其一,NMS 的運算時間與場景中偵測框的數量成正比,擁擠場景下延遲會顯著增加,破壞即時性保證;其二,NMS 通常實作於 PyTorch 後處理階段,無法併入 TensorRT 的編譯流程,部署時需額外維護 Python 後處理邏輯;其三,NMS 的迴圈操作在邊緣裝置的 ARM CPU 上尤其耗時。YOLO26 透過 One-to-One Label Assignment 的訓練策略讓模型在訓練階段即學會對每個物體只輸出一個最佳候選框,推理時直接產生形狀為 `(N, 300, 6)` 的輸出張量(每張影像最多 300 個偵測框),每一列對應一個偵測結果 `[x1, y1, x2, y2, confidence, class_id]`,後處理只需執行信心度閾值過濾即可。此設計讓推理延遲恆定(不受場景複雜度影響)、模型可完全編譯為單一 TensorRT engine、並大幅簡化部署程式碼。

**雙頭架構(Dual-Head Design)**。YOLO26 實際上採用一套雙頭架構以兼顧訓練效率與部署便利性:

- **一對一頭部(One-to-One Head,預設)**:供推理階段使用的端到端無 NMS 路徑,輸出形狀為 `(N, 300, 6)`,最多 300 個偵測框。
- **一對多頭部(One-to-Many Head)**:供訓練階段使用的傳統 YOLO 輸出,形狀為 `(N, nc + 4, 8400)`,需搭配 NMS 後處理。

此設計讓模型於訓練時享受多頭監督帶來的收斂速度優勢,於部署時則使用簡潔的無 NMS 路徑,是端到端模型與多頭訓練效率的巧妙結合。

**DFL(Distribution Focal Loss)模組移除**。前代 YOLO 模型普遍使用 Distribution Focal Loss 來提升邊界框回歸的精度,但此模組會使模型匯出變得複雜並限制硬體相容性——特別是邊緣裝置與低功耗 NPU 上對 DFL 的數值運算支援不一致。YOLO26 完全移除了 DFL 模組,改用更簡潔的迴歸頭設計,此舉簡化了推理流程、擴大了可部署硬體的範圍,並顯著改善邊緣裝置上的匯出格式相容性(包含 TensorRT、ONNX、CoreML、TFLite、OpenVINO 等)。

**MuSGD 最佳化器**。YOLO26 引入了新的 **MuSGD** 最佳化器,為傳統 SGD 與 Muon 最佳化器的混合設計,其靈感來自 Moonshot AI 於 Kimi K2 大型語言模型訓練中所採用的最佳化器突破。MuSGD 提供更穩定的訓練行為與更快的收斂速度,是一個技術遷移的有趣案例——將原本用於 LLM 訓練的最佳化器概念引入電腦視覺模型訓練。

**ProgLoss 與 STAL 損失函數**。YOLO26 引入了兩項損失函數改進——**ProgLoss**(Progressive Loss,漸進式損失)與 **STAL**(Small-Target Assignment Learning,小目標指派學習)——這兩項改進共同提升了小物件的辨識精度。此改進對 IoT、居家機器人、無人機、航空影像等應用場景尤其重要,因為這些場景中的目標物體多為小型物件(居家環境中的水杯、手機、書本、瓶罐等)。這也是本專題選用 YOLO26 而非 YOLO11 的關鍵技術理由之一。

**CPU 推理加速**。YOLO26 相較於 YOLO11 在 CPU ONNX 推理上最多快 43%,這對於無法使用 GPU 的邊緣裝置或 CPU-only 備援路徑特別有意義。

## YOLO26 各尺寸的官方效能規格

下表為 Ultralytics 官方 benchmark 數據(COCO 2017 驗證集,輸入解析度 640 × 640,mAP 為 mAPval@0.5:0.95,TensorRT 延遲於 NVIDIA T4 GPU FP16 測得),呈現 YOLO26 五個尺寸變體的完整規格:

| 模型 | mAP (50-95) | CPU ONNX (ms) | T4 TensorRT (ms) | 參數量 (M) | FLOPs (B) |
|---|:---:|:---:|:---:|:---:|:---:|
| **YOLO26n**(本專題採用) | 40.9 | 38.9 ± 0.7 | 1.7 ± 0.0 | 2.4 | 5.4 |
| YOLO26s | 48.6 | 87.2 ± 0.9 | 2.5 ± 0.0 | 9.5 | 20.7 |
| YOLO26m | 53.1 | 220.0 ± 1.4 | 4.7 ± 0.1 | 20.4 | 68.2 |
| YOLO26l | 55.0 | 286.2 ± 2.0 | 6.2 ± 0.2 | 24.8 | 86.4 |
| YOLO26x | 57.5 | 525.8 ± 4.0 | 11.8 ± 0.2 | 55.7 | 193.9 |

本專題最終選用 **YOLO26n** 作為主線模型,理由是 COCO mAP 40.9% 雖然低於 YOLO26s(48.6%)或 YOLO26m(53.1%),但參數量僅 2.4 M(為 YOLO26s 的 25%、YOLO26m 的 12%)、FLOPs 僅 5.4 B(為 YOLO26s 的 26%、YOLO26m 的 8%),最符合 Jetson Orin Nano 的資源預算(8 GB 統一記憶體、需與五個感知模組共存)。考量 Jetson Orin Nano 的 GPU 算力約為 T4 的 25% 至 35%,T4 上 1.7 毫秒的 TensorRT 延遲於 Jetson 上預估約 5 至 7 毫秒;本專題實測於 Jetson 運行 YOLO26n TensorRT FP16 時,Python 端到端(含前處理、推理、後處理)穩定達到每秒 15 幀(tick period 約 0.067 秒),Debug 影像發布頻率約 6.3 至 6.8 Hz。

未來若需更高精度(特別是改善小物件辨識率),可考慮升級至 YOLO26s,mAP 提升 +7.7 個百分點,但參數量與 FLOPs 約為 YOLO26n 的 4 倍,需重新評估 Jetson 資源預算。此為本專題 4/13 繳交後的下一階段改進項目。

## 推理框架:ONNX Runtime + TensorRT Execution Provider

為在 Jetson 上執行 YOLO26n 的 TensorRT FP16 推理,本系統採用 **ONNX Runtime** 搭配 **TensorRT Execution Provider**(以下簡稱 TensorRT EP)的組合,而非直接呼叫 TensorRT C++ API 或原生 Ultralytics Python 介面。此決策考量如下:

- **ONNX Runtime 作為推理抽象層**:ONNX Runtime 是 Microsoft 主導的開源推理框架,支援多種硬體後端(CUDA、TensorRT、OpenVINO、DirectML、CoreML 等),透過統一的 Python API 呼叫。使用 ONNX Runtime 可讓相同的推理程式碼在不同硬體平台間移植(例如開發機 WSL 上走 CUDA EP、Jetson 上走 TensorRT EP),大幅降低跨平台開發複雜度。
- **TensorRT EP**:TensorRT 是 NVIDIA 為自家 GPU 設計的高效能推理引擎,透過 layer fusion、kernel auto-tuning、FP16 / INT8 量化等技術將 ONNX 模型編譯為高度最佳化的 engine。ONNX Runtime 的 TensorRT EP 允許開發者透過 ONNX Runtime 統一介面呼叫底層的 TensorRT,兼顧易用性與效能。
- **三層 Provider 備援**:本系統的 ONNX Runtime session 配置三個 Execution Provider,依優先序為 `TensorrtExecutionProvider`(主線)→ `CUDAExecutionProvider`(備援,若 TensorRT 編譯失敗時退回純 CUDA)→ `CPUExecutionProvider`(最終備援)。此設計確保即使 TensorRT 發生異常,系統仍能維持物體辨識能力,只是速度下降。

## Jetson 部署流程與「不裝 ultralytics」原則

本專題的 YOLO26n 部署流程分為兩階段:

**階段一:WSL 開發機上的模型匯出**。在 Windows WSL 開發環境(非 Jetson)中,團隊安裝 Ultralytics Python 套件,下載 YOLO26n 的 PyTorch 權重檔(`yolo26n.pt`),並以以下參數匯出為 ONNX 格式:`format='onnx'`、`imgsz=640`(輸入尺寸 640 × 640)、`simplify=True`(執行 ONNX 簡化器消除冗餘運算)、`opset=17`(指定 ONNX operator set 版本,與 Jetson 上的 ONNX Runtime 相容)。匯出完成後產生 `yolo26n.onnx`,大小約 9.5 MB。

**階段二:Jetson 上的部署與首次啟動**。透過 `scp` 將 `yolo26n.onnx` 檔案傳送至 Jetson 的 `/home/jetson/models/` 目錄,接著由 `object_perception_node` 透過 ONNX Runtime 載入模型並指定 `TensorrtExecutionProvider` 為主要後端。**首次啟動時 TensorRT 會進行引擎編譯**(包含 layer fusion、kernel 最佳化、FP16 量化校準等步驟),耗時約 3 至 10 分鐘,編譯結果會快取至 `/home/jetson/trt_cache/` 目錄。後續啟動時系統直接載入快取的引擎檔案,啟動時間降至秒級。

**不在 Jetson 上安裝 ultralytics 的硬規則**:Ultralytics 官方 Python 套件雖然提供便利的 YOLO 訓練與推論 API,但其套件依賴會強制安裝特定版本的 PyTorch 與 NumPy,與 Jetson 預裝的 ARM 架構最佳化 PyTorch wheel 完全不相容。本專題於 2026 年 4 月 4 日曾在 Jetson 上執行 `pip install ultralytics`,導致整個 Python 環境被破壞——原本可正常運作的 `face_perception`、`vision_perception` 等模組全部因 torch 版本衝突而無法啟動,環境救援耗時約半天。此後制定明確規則寫入 `docs/辨識物體/CLAUDE.md`:**Jetson 上嚴禁安裝 ultralytics 套件**,所有 YOLO 模型必須於開發機匯出為 ONNX 後再傳至 Jetson,由 `onnxruntime-gpu` 載入。

## TensorRT Provider 參數陷阱

ONNX Runtime 的 TensorRT EP 參數配置有一個容易踩坑的陷阱:布林類型的參數值**必須以字串形式** `"True"` / `"False"` 傳入,而非 Python 的 `True` / `False` 或 `"1"` / `"0"`。本專題實際使用的配置為:

```python
providers = [
    ("TensorrtExecutionProvider", {
        "trt_engine_cache_enable": "True",
        "trt_engine_cache_path": trt_cache_dir,
        "trt_fp16_enable": "True",
    }),
    "CUDAExecutionProvider",
    "CPUExecutionProvider",
]
```

若誤寫為 `"trt_fp16_enable": "1"`,ONNX Runtime 會回報錯誤訊息 `The value for the key 'trt_fp16_enable' should be 'True' or 'False'`,並 **silent 回退至 CPU provider**(不會拋出例外),導致物體辨識模組以 CPU 模式運行,FPS 從 15 驟降至 2 至 3,且不易從日誌中察覺。此陷阱已寫入模組 CLAUDE.md 的「踩過的坑」章節以防未來重複踩雷。

## Letterbox 前後處理

YOLO 系列模型為保持輸入影像的寬高比不變以避免物體變形,採用 **Letterbox(信箱式縮放)** 前處理策略。具體作法為:將原始影像(例如 D435 的 1280 × 720)等比例縮放使較長邊對齊 640 像素,短邊則以灰色(RGB 114, 114, 114)填補,最終得到 640 × 640 的方形輸入畫布。本系統的 `letterbox()` 方法實作此前處理並返回縮放比例(scale)、水平填補量(pad_left)與垂直填補量(pad_top)三個參數供後處理使用。

推理完成後,模型輸出的邊界框座標位於 640 × 640 的 letterboxed 空間中,必須經過**逆轉換**才能對應回原始影像的像素座標,否則在 PawAI Studio Live View 上視覺化時框線會出現嚴重偏移。本系統的 `rescale_bbox()` 方法實作此逆轉換:先減去填補量(`x - pad_left`、`y - pad_top`),再除以縮放比例還原至原始尺度(`/ scale`),最後裁切至原始影像邊界範圍內並轉為 Python `int` 類型(避免 `np.int32` 導致 JSON 序列化失敗——此為人臉模組曾踩過的坑)。

## COCO 80 類與白名單機制

YOLO26n 基於 **COCO 2017 資料集**訓練,支援 80 個常見物體類別,涵蓋人物(person)、交通工具(bicycle、car、bus、truck 等)、動物(bird、cat、dog、horse 等)、戶外設施(traffic_light、fire_hydrant、stop_sign 等)、配件(backpack、umbrella、handbag 等)、運動用品(frisbee、skis、snowboard 等)、廚房用品(bottle、wine_glass、cup、fork、knife、spoon 等)、食物(banana、apple、sandwich、pizza 等)、家具(chair、couch、bed、dining_table、toilet 等)、電子產品(tv、laptop、mouse、keyboard、cell_phone 等)、日用品(book、clock、vase、scissors、teddy_bear 等)共六大類。

**類別命名規則**:COCO 原始類別名稱中含空格者(共 15 個,例如 `dining table`、`cell phone`、`traffic light`、`teddy bear` 等)於本系統中統一將空格改為底線(`dining_table`、`cell_phone` 等),以確保 JSON 序列化一致性並避免下游程式碼處理空格時的錯誤。完整的類別 ID 對應表定義於 `object_perception/object_perception/coco_classes.py`,由 0 至 79 的連續 ID 對應至 80 個類別名稱(注意:YOLO 使用連續 ID,不同於原始 COCO paper 的 91 ID 稀疏編碼)。

**白名單機制(`class_whitelist` 參數)**:本系統提供 ROS2 參數 `class_whitelist` 允許動態篩選要關注的物體類別。此參數為整數陣列,空陣列 `[]` 代表偵測全部 80 類(預設值),非空陣列則僅保留指定類別的偵測結果並忽略其餘。例如 Demo 場景可設定為 `[0, 16, 39, 41, 56, 60]` 對應 person、dog、bottle、cup、chair、dining_table 六個與居家互動最相關的類別,避免無關物體(如街道上的車輛、戶外設施)造成誤觸發。

白名單機制的實作過程曾遭遇一個棘手的型別推斷陷阱:ROS2 的 `declare_parameter()` 無法從空陣列 `[]` 推斷參數型別(因為空陣列同時可能是整數、浮點數、字串陣列等),必須明確傳入 `ParameterDescriptor(type=ParameterType.PARAMETER_INTEGER_ARRAY)`,否則會在節點啟動時拋出 `ParameterUninitializedException` 例外。

## 事件發布、冷卻去重與中控整合

本系統的物體辨識模組透過兩個 ROS2 Topic 與下游模組互動:

1. **`/event/object_detected`(事件流)**:偵測到物體後以 JSON 格式發布事件,訊息 schema 如下:

```json
{
  "stamp": 1775371004.13,
  "event_type": "object_detected",
  "objects": [
    {"class_name": "chair", "confidence": 0.878, "bbox": [336, 240, 462, 474]}
  ]
}
```

每個 tick 內可能偵測到多個物件,統一以 `objects` 陣列承載,`bbox` 為經過 letterbox 逆轉換後的原始影像像素座標。此 schema 於 ROS2 介面契約 v2.4 中凍結,欄位名稱不可更動。

2. **`/perception/object/debug_image`(除錯影像)**:將偵測到的邊界框、類別名稱與信心度疊加於原始影像上發布,供 Foxglove 或 PawAI Studio Live View 視覺化使用,頻率由 `publish_fps` 參數控制(預設 8 Hz)。

**Per-class 冷卻去重機制**:為避免同一類別的物體(例如使用者手中的水杯)持續存在於視野中造成每幀都觸發相同事件進而打擾使用者,本系統實作了基於類別的冷卻去重邏輯:每個類別維持一個最後事件時間戳記,若距離上次發布同類別事件的時間小於 `class_cooldown_sec`(預設 5 秒),則該次偵測結果不發布事件。此機制允許不同類別的事件同時觸發,但避免了單一類別的重複洗版。

**統一中控整合**:`interaction_executive_node` 訂閱 `/event/object_detected` Topic,並根據內建的 `OBJECT_TTS_MAP` 映射表決定是否觸發語音互動話術。目前映射表內建三個高價值類別的話術:`cup` → 「你要喝水嗎?」、`bottle` → 「喝點水吧」、`book` → 「在看書啊」;其他 77 個 COCO 類別被靜默忽略以避免過度打擾。物體事件在中控的優先序為 5(低於人臉、語音、手勢、障礙物、跌倒偵測),且僅在 `IDLE` 狀態觸發,不會打斷正在進行的對話或其他互動。

## 實測效能數據

本專題的物體辨識模組於 2026 年 4 月 4 日與 4 月 5 日進行了兩階段壓力測試:

**Phase B(四核心全開壓測)**:YOLO26n ONNX + TensorRT FP16 在 Jetson Orin Nano SUPER 8GB 上單跑 70 秒的穩定性測試:

- **FPS**:15.0 穩定(零掉幀)
- **RAM 增量**:+1 GB(總記憶體由 2.6 GB 升至 3.7 GB,剩餘 3.9 GB)
- **GPU 佔用**:0%(TensorRT EP 統計顯示)
- **溫度**:56 °C
- **功耗**:8.9 W

**Phase C(ROS2 節點 5 分鐘穩定性測試)**:完整的 ROS2 node 單獨運行五分鐘:

- **Debug 影像頻率**:6.3 至 6.8 Hz(對應 `publish_fps=8.0` 的配置)
- **事件發布**:正確,per-class 冷卻去重機制生效
- **RAM 漂移**:2312 MB → 2319 MB(+7 MB,確認無記憶體洩漏)
- **溫度**:48 °C(持平略降,未見熱累積)
- **Node Process CPU**:38.5%
- **ONNX Providers 順序**:TensorRT + CUDA + CPU(確認 TensorRT EP 為主線)

## 實機驗證結果與已知限制

2026 年 4 月 6 日於 Jetson 真機上進行的實機驗收結果:

| 物品 | 結果 | 備註 |
|---|:---:|---|
| **cup 水杯** | ✅ 通過 | threshold 0.5,成功觸發 TTS「你要喝水嗎?」 |
| **cell_phone 手機** | ✅ 通過 | 適當光線條件下可辨識 |
| **book 書本** | ⚠️ 部分通過 | 平放時困難,翻開展示時可辨識(threshold 降至 0.3 時偶爾偵測) |
| **bottle 水瓶** | ❌ 未通過 | 未偵測到,Demo 場景中不展示 |

本模組實際部署中存在以下已知限制:

1. **光線敏感**:低光源環境下 YOLO26n 對小物件(水瓶、手機、書本)的偵測率顯著下降,Demo 場景必須確保場地照明充足。
2. **姿態依賴**:物體需在特定高度且正對攝影機的角度才能穩定偵測,平放的扁平物體(書本、手機)辨識困難,需翻開或立起後才能觸發。
3. **Nano 模型的固有精度限制**:YOLO26n(Nano 版本)的 COCO mAP 僅 40.9%,對小物件的偵測率本身就偏低。已規劃升級至 YOLO26s(mAP 48.6%,+7.7 百分點)作為下一階段改進項目,但需重新評估 Jetson 的 GPU 與 RAM 預算。
4. **Jetson 供電不穩**:Sprint 期間累計發生 8 次以上 Jetson 因 XL4015 降壓模組輸出不穩定而強制斷電,影響整體物體辨識模組的長時間運行穩定性(詳見第五章系統限制)。
5. **追蹤與 3D 能力缺失**:本系統目前僅做單幀偵測,未實作跨幀物體追蹤(Multi-Object Tracking, MOT)、3D 深度估計(雖然 D435 具備深度感測能力但未與物體模組整合)、目標選擇(target selection)等進階功能,列為未來工作。

---

# 4-8 自主導航避障技術(規劃中)

## 為什麼需要外接雷達

本專題原本規劃以 Intel RealSense D435 深度影像與 Go2 Pro 內建 LiDAR 作為導航避障的感測來源,但兩者於真機測試上皆遇到無法克服的硬體或韌體限制:

**D435 深度避障於 2026 年 4 月 3 日停用**。D435 因安裝於機身前方上緣,鏡頭角度略為偏上方,低矮障礙物(椅腳、門檻、散落於地面的小型物品)要到距離 0.4 公尺以內才會進入視野。加上從偵測到完全停止的延遲鏈過長(debounce 去抖動約 100 毫秒 + ROS2 rate limiter 約 200 毫秒 + WebRTC 通訊約 300 毫秒 + Go2 自身減速 500 至 1000 毫秒,總反應時間約 1 至 1.5 秒),三輪真機防撞測試全部失敗,機器狗在偵測到障礙後仍因慣性撞上目標物。此為鏡頭安裝角度的物理限制,軟體無法克服。

**Go2 內建 LiDAR 資料不可用**。Go2 Pro 內建的 **Unitree 自研 4D LiDAR L2**(360° × 96° 半球型掃描,依官方公開頁面規格)雖然在 LiDAR 硬體本身的技術規格上具備基礎導航能力,但 Go2 Pro 韌體層級將 LiDAR 資料透過 WebRTC DataChannel 對外暴露時,會先經過 voxel 體素編碼壓縮,再由 Jetson 端的 Python 驅動節點解碼還原為點雲。此解碼後的資料實測有效掃描點覆蓋率僅約 18%(每幀約 22 / 120 個有效點),發布頻率經 2026 年 4 月 1 日重新實測為靜止約 7.3 Hz、行走約 5.0 至 6.1 Hz(推翻先前 0.03 至 2 Hz 的舊結論),但有效覆蓋率仍遠低於 ROS2 Nav2 導航堆疊所需的品質門檻。此為 Go2 Pro 韌體對外資料介面的設計限制,屬於 Unitree 在 Pro 版本上對感測器資料的封裝選擇——Go2 EDU 版本才提供透過 CycloneDDS 取得完整 LiDAR 資料的介面。由於 Pro 版本暴露出的資料覆蓋率不足以支援穩定的 SLAM 建圖與路徑規劃,團隊於 2026 年 4 月 1 日正式宣告放棄基於 Go2 內建 LiDAR 的 Full SLAM 與 Nav2 全域導航方案。

團隊於 2026 年 4 月 8 日教授會議後決定採購外接雷達作為獨立的感測輸入,直接透過 USB 連接 Jetson Orin Nano,徹底繞開 Go2 WebRTC 解碼瓶頸。候選型號經過 RPLIDAR C1(採樣率 5,000 次/秒,點數太稀疏)、RPLIDAR A2M12(16,000 次/秒,為 ROS 社群最多實機案例的標準配置)、RPLIDAR S2(32,000 次/秒,室內應用過剩)三款的比較後,最終選定 **SLAMTEC RPLIDAR A2M12**。

## RPLIDAR A2M12 規格

SLAMTEC RPLIDAR A2M12 為上海思嵐科技推出的 2D 360 度雷射測距儀,採用三角測距(Triangulation)技術,專為室內機器人導航、SLAM 建圖與障礙物迴避場景設計。其關鍵規格如下(依 Slamtec 官方 datasheet):

| 規格項目 | 數值 |
|---|---|
| 掃描角度 | 360 度全向 |
| 最大測距 | **12 公尺**(白色物體)/ 10 公尺(黑色物體) |
| 最小測距 | 0.2 公尺 |
| 採樣頻率 | **每秒 16,000 次**(16 kHz) |
| 掃描頻率 | 10 Hz 典型值(可於 5 至 15 Hz 範圍內調整) |
| 角度解析度 | 0.225 度 |
| 每圈點數 | 約 1,600 點(16,000 次/秒 ÷ 10 Hz) |
| 介面 | USB 序列埠(Jetson 可直接供電與資料傳輸) |
| 功耗 | 約 3 至 5 瓦 |
| 測距原理 | 光磁融合(OPTMAG,無滑環設計,壽命長) |

## 為何選 A2M12

相較於 Go2 Pro WebRTC 暴露出的每幀僅約 22 個有效點與不穩定的頻率,RPLIDAR A2M12 每圈提供約 1,600 個掃描點、每秒穩定 16,000 次採樣,解析度與資料量皆為前者的兩個數量級以上,足以支援基礎的反應式避障與入門級的 SLAM 建圖。USB 直連的設計讓雷達資料完全繞過 Go2 WebRTC 解碼瓶頸,由 `rplidar_ros2` 輕量 C++ 驅動節點直接發布標準的 `/scan` LaserScan topic 至 ROS2 網路,CPU 開銷極低。此外,A2M12 是 ROS 社群中擁有最多實機部署案例與教學資源的型號,例如 Waveshare UGV Beast 專案便以「Jetson Orin Nano + RPLIDAR A2M12 + ROS2 Humble」的相同組合完整實現 SLAM 建圖與 Nav2 自主導航,為本專題的整合提供了可靠的參考路線。

## 當前進度

本專題於 2026 年 4 月 8 日完成外接雷達可行性研究(`docs/導航避障/research/2026-04-08-external-lidar-feasibility.md`),確認 RAM 預算安全(增量約 0.85 至 1.15 GB)、CPU 用量需管理(導航進行時需關閉部分次要感知模組)、主要風險為雷達馬達對 Jetson 外接供電的額外負擔。採購流程透過指導老師的國科會計畫變更進行,預計 4 月 14 日前完成最終決策。雷達到貨後的整合時程規劃為 5 天(驅動驗證、`slam_toolbox` 建圖、Nav2 整合、實機防撞測試),目標於 5 月 16 日 Demo 前完成基礎反應式避障與短距直線移動能力的實機驗收。

由於本功能於本文件繳交時尚未正式整合實作,第三章系統範圍中的「自主導航避障」對應條目已明確標註為**條件式啟用功能**(依賴 RPLIDAR 到貨與 Go2 四足里程計漂移驗證通過),並於第五章系統限制中詳細說明不確定性。本章背景知識層面介紹的重點是技術選型的邏輯與 RPLIDAR A2M12 的硬體規格,實際整合結果將於 Demo 前後補充。

---

# 4-9 NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB

## 平台定位

NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB 是本專題所有本地感知與即時推理運算的核心邊緣運算平台,負責運行人臉辨識、語音辨識、手勢辨識、姿勢辨識、物體偵測、語音合成與 ROS2 節點等全部本地端軟體堆疊,同時透過 WebRTC DataChannel 與 Unitree Go2 Pro 機器狗進行雙向通訊、透過 USB 介面連接 Intel RealSense D435 深度攝影機與外接音訊裝置。Jetson 是 NVIDIA 專為 AI 邊緣推理設計的嵌入式運算模組產品線,從早期的 Jetson TK1(2014)、TX1、TX2、Xavier NX,至 2023 年發布的 Orin 系列(Orin Nano / Orin NX / AGX Orin),逐代提升算力與能效。其中 Orin Nano 系列是最小、最便宜、最適合入門開發者與學術研究的型號。

## Super 升級的背景

本專題所使用的是 2024 年 12 月 17 日 NVIDIA 發布的 **Jetson Orin Nano SUPER Developer Kit**,這是前代 Jetson Orin Nano Developer Kit 的軟體升級版本——透過 JetPack 6.1 新增的 MAXN 極致效能模式,將原本 40 TOPS 的 AI 推理能力提升至 **67 INT8 TOPS**(提升幅度 1.7 倍),記憶體頻寬從 68 GB/s 提升至 **102 GB/s**(提升 50%)。值得注意的是,「Super」升級並非硬體更動——所有現有的 Jetson Orin Nano Developer Kit 使用者都可以透過 NVIDIA SDK Manager 或直接燒錄新版 SD Card Image 取得此性能升級,無需更換任何實體元件。同時 NVIDIA 也將新版套件的建議售價從原本的 499 美元大幅調降至 **249 美元**,明確瞄準機器人、生成式 AI、Transformer 類模型等邊緣 AI 應用,定位為「人人可負擔的 Gen AI 超級電腦」。此升級對本專題是關鍵利多,讓原本預算有限的學術專題得以取得能執行 LLM、Vision Transformer 等較重推理任務的運算能力。

## 硬體規格

| 規格項目 | 數值 |
|---|---|
| **AI 運算能力** | 67 TOPS(INT8 稀疏),Super MAXN 模式 |
| **GPU 架構** | NVIDIA Ampere |
| **CUDA 核心數** | 1024 顆 |
| **Tensor 核心數** | 32 顆(第三代) |
| **CPU** | 6 核心 Arm Cortex-A78AE v8.2 64 位元 |
| **CPU 時脈** | 最高 1.7 GHz |
| **CPU 快取** | 1.5 MB L2 + 4 MB L3 |
| **記憶體** | 8 GB 128-bit LPDDR5 統一記憶體 |
| **記憶體頻寬** | 102 GB/s |
| **儲存** | 支援 microSD 卡與外接 NVMe SSD |
| **功耗模式** | 7 W / 15 W / 25 W(MAXN 模式,本專題使用) |
| **影片編解碼** | 1× 4K60 / 3× 4K30 / 多路 1080p H.264 / H.265 編解碼硬體加速 |
| **I/O 介面** | 4× USB 3.2 Gen2、1× USB-C(刷機用)、Gigabit Ethernet、DisplayPort、40-pin GPIO header、M.2 Key M(NVMe)、M.2 Key E(Wi-Fi) |
| **載板尺寸** | 100 × 79 公釐 |
| **建議售價** | $249 美元 |

## Ampere GPU 架構與統一記憶體

Jetson Orin Nano SUPER 的 GPU 採用 NVIDIA **Ampere 架構**,與桌上型 RTX 30 系列顯示卡相同世代(CUDA 計算能力 8.7),支援 FP32、FP16、BF16、INT8 等多種精度的張量運算。第三代 Tensor 核心特別針對深度學習推理最佳化,支援結構化稀疏(Structured Sparsity)加速——即模型權重若滿足 2:4 稀疏模式(每 4 個權重中有 2 個為 0),推理速度可額外加倍。這也是 NVIDIA 標榜 67 TOPS 的數據依據(INT8 稀疏模式),密集模式下約為 33 TOPS。

**統一記憶體架構(Unified Memory Architecture)** 是 Jetson 系列相較於桌上型 GPU 系統最重要的架構特色。桌上型 GPU 透過 PCIe 介面與主記憶體(RAM)分離,資料需在 CPU RAM 與 GPU VRAM 之間透過 PCIe 匯流排複製,此複製成本是高頻寬應用的主要瓶頸。Jetson 則將 8 GB LPDDR5 記憶體設計為 CPU 與 GPU 共享,任何資料只需存在實體記憶體一次,CPU 與 GPU 可直接存取同一份資料而無需複製,大幅降低延遲並簡化記憶體管理。對本專題這類多模組並行(人臉、手勢、姿勢、物體、ASR/LLM 皆需讀取相同的相機影像或中間張量)的場景特別有利。此設計同時也是資源競爭的來源——CPU 的記憶體使用與 GPU 的推理工作互相擠壓同一個 8 GB 空間,本專題的 RAM 預算管理因此需要極度謹慎(詳見下文資源分配段)。

## 軟體堆疊:JetPack 6

本專題使用 NVIDIA **JetPack 6.1+** 作為 Jetson 的作業系統與 SDK 套件。JetPack 是 NVIDIA 為 Jetson 系列提供的完整嵌入式 Linux 開發套件,基於 **Ubuntu 22.04 LTS** 客製化,預裝 NVIDIA 的全部 AI 推理軟體堆疊,包含:

- **Linux for Tegra(L4T)核心**:針對 Jetson 硬體最佳化的 Ubuntu Linux 發行版。
- **CUDA Toolkit 12.6**:NVIDIA 的並行運算平台,提供在 GPU 上執行通用運算的 API。
- **cuDNN 9.x**:深度神經網路基礎運算函式庫,為 CNN 等常見層提供最佳化核心。
- **TensorRT 10.x**:NVIDIA 的高效能推理引擎,透過 layer fusion、kernel auto-tuning、FP16 / INT8 量化等技術將 ONNX 或 PyTorch 模型編譯為高度最佳化的推理 engine,本專題的 YOLO26n 物體辨識即透過 TensorRT 加速。
- **VPI(Vision Programming Interface)**:電腦視覺運算函式庫,提供加速的影像前處理運算(如 resize、warp、濾波)。
- **Multimedia API**:支援硬體加速的 H.264 / H.265 影片編解碼。
- **DeepStream SDK**:高階視訊分析管線框架(本專題未使用)。
- **Jetson Platform Services**:系統監控與效能管理服務。

JetPack 6.1 的重要新增功能為 **MAXN 極致效能模式**——這是驅動 Orin Nano 升級為 Super 的核心軟體改動,透過放寬動態電壓頻率調整(DVFS)策略讓 GPU 與 CPU 能持續運行於更高的時脈,進而解鎖硬體原本就具備但先前韌體未釋放的 67 TOPS 能力。本專題透過 `sudo nvpmodel -m 0 && sudo jetson_clocks` 兩道指令啟用 MAXN 模式並鎖定最高時脈,確保推理效能穩定可重現。

## 為何選擇此平台

本專題評估邊緣運算平台時曾考量多個候選方案,包含 Jetson Orin Nano 8GB、Jetson Orin NX 16GB、x86 mini PC(Intel NUC 或同級)、Raspberry Pi 5 等。最終選擇 Jetson Orin Nano SUPER 8GB 的理由綜合如下:

- **AI 推理原生加速**:相較於 x86 mini PC 需額外採購 USB 加速棒或 PCIe 加速卡才能取得硬體 AI 推理能力,Jetson 直接內建 1024 CUDA + 32 Tensor 核心,且 CUDA / cuDNN / TensorRT 軟體堆疊完整整合,無需額外驅動程式或套件安裝問題。
- **ROS2 生態成熟度**:Jetson 在 ROS2 機器人社群中有最多實機部署案例與教學資源,相容性與除錯便利度遠勝其他平台。
- **記憶體與算力平衡**:8 GB 統一記憶體足以同時運行六個感知模組,67 TOPS 算力足以即時處理多路視覺推理。
- **體積與功耗**:載板尺寸僅 100 × 79 公釐、重量輕、功耗 25 瓦以下,可直接安裝於 Go2 Pro 機身上作為外掛運算模組,由 Go2 電池經 XL4015 降壓模組供電。
- **採購成本**:$249 美元的 Jetson Orin Nano SUPER 是目前市場上最具性價比的嵌入式 AI 運算平台,指導老師提供的 Jetson 讓本專題無需額外採購即可開始開發。
- **社群參考案例豐富**:NVIDIA 官方 Jetson AI Lab、Ultralytics、Unitree 社群(如 abizovnuralem/go2_ros2_sdk)均提供針對 Jetson Orin Nano 的部署教學與踩坑紀錄,降低本專題遭遇未知技術問題的機率。

## 本專題的 Jetson 資源分配

本專題於 Jetson Orin Nano SUPER 8GB 上運行的軟體堆疊包含下列模組,其實測資源佔用(於人臉、手勢、姿勢、物體、語音五大感知模組同時運行時)如下。**以下數據取自 Demo 部署主線(`start_full_demo_tmux.sh`)的覆寫配置**,即 gesture_backend=recognizer、pose_backend=mediapipe(Lite)、TTS=edge-tts、ASR=SenseVoice Cloud;程式碼原始預設配置會走 RTMPose pose/gesture backend 與舊本地麥克風路徑,資源分布會有所不同:

| 模組 | RAM | CPU | GPU | 備註 |
|---|:---:|:---:|:---:|---|
| ROS2 runtime + Go2 driver | 1.5–2.0 GB | ~20% | 0% | 基礎通訊層 |
| D435 camera driver | 0.6–1.0 GB | ~10% | 0% | RGB + Depth 串流 |
| 人臉辨識(YuNet + SFace) | ~0.3 GB | ~40% | 0% | CPU-only |
| 手勢辨識(MediaPipe Hands) | ~0.2 GB | ~45% | 0% | CPU-only |
| 姿勢辨識(MediaPipe Pose) | ~0.25 GB | ~50% | 0% | CPU-only |
| 物體辨識(YOLO26n TensorRT) | ~1.0 GB | ~40% | 使用中 | TensorRT FP16 |
| 語音(edge-tts / Cloud ASR) | ~0.1 GB | ~10% | 0% | 雲端主線 |
| **總計** | **~4.0–5.5 GB** | **~215%(六核共 600%)** | 部分佔用 | 餘 2.5–4 GB 安全邊界 |

此資源分配策略的核心原則為:**GPU 獨佔給 YOLO26n 的 TensorRT 推理,所有其他感知模組走 CPU 以避免資源競爭**。這也是本專題選擇 MediaPipe 而非 RTMPose(後者會佔滿 GPU 91 至 99%)、選擇 YuNet 而非 SCRFD(後者需 GPU)、選擇 CPU 模式的 Qwen2.5-1.5B 本地 LLM 備援的根本理由。整體架構在資源邊界內達成穩定運行,但餘量有限,任何新增模組都需謹慎評估資源衝擊。

## 已知限制

- **統一記憶體為雙面刃**:CPU 與 GPU 共享同一 8 GB 空間,任何一方的記憶體洩漏都會影響另一方,記憶體壓力需嚴密監控。
- **散熱管理**:MAXN 模式下 Jetson 核心溫度通常維持於 50 至 65 °C,配備主動風扇時可長時間穩定運行;若無風扇或進風口被遮擋,可能觸發 thermal throttling 自動降頻。本專題於 Go2 機身上安裝 Jetson 時已確保進風口暢通。
- **供電穩定性**:如第五章所述,Jetson 透過外接 XL4015 降壓模組從 Go2 電池取電,高負載時段電壓不穩定為 Demo 期間的已知風險。
- **ARM 生態碎片化**:部分 Python 套件(如 ultralytics、PyTorch 某些版本)的 ARM wheel 與 JetPack 6 CUDA 版本不相容,需避免直接 `pip install` 破壞預裝環境。

---

# 4-10 Intel RealSense D435 深度攝影機

## 平台定位

Intel RealSense D435 是本專題所使用的唯一視覺感測裝置,同時承擔五個感知模組(人臉辨識、手勢辨識、姿勢辨識、物體辨識、與未來可能擴充的深度避障)的視覺輸入來源。此單一感測器多工使用的架構設計原則是「一機多用、統一資料來源」——透過 ROS2 的 Publisher / Subscriber 模型讓一支攝影機發布的影像串流同時被多個下游感知節點訂閱並各自獨立推論,避免多支相機帶來的同步、校正、功耗、USB 頻寬負擔等實務問題。本專題選用 D435 而非更便宜的 USB 網路攝影機或其他深度相機,主要考量是 D435 同時提供高品質 RGB 與即時深度資料、原生支援 ROS2 驅動、與 Jetson Orin Nano 的 Ubuntu + USB 3.0 環境完全相容、且在機器人研究社群中擁有豐富的教學資源與踩坑紀錄。

## Active IR Stereo 深度技術

Intel RealSense D435 採用 **Active IR Stereo(主動紅外線立體視覺)** 技術作為深度感測原理,這與另外兩種常見的深度感測技術——結構光(Structured Light,如 Apple Face ID)與飛時測距(Time-of-Flight, ToF,如 Microsoft Kinect v2、Intel L515)——在物理機制上有明顯差異。

**被動立體視覺原理**:立體視覺的基本原理類似人類雙眼的視差——兩個相機從略微不同的角度拍攝同一場景,透過比對兩張影像中相同特徵點的水平位置差(disparity)配合已知的兩相機基線距離(baseline),即可透過三角測量幾何推算出每個像素點的深度。純被動立體視覺在紋理豐富、光線充足的場景下表現良好,但在**缺乏紋理**的平面(如白牆、光滑桌面)上難以找到對應特徵點,深度圖會出現大量破洞。

**主動紅外線立體視覺(D435 採用)**:D435 在兩個紅外線感測器中間設置一個紅外線投射器(IR Projector),主動向場景投射隨機的紅外線斑點圖案,人工為原本紋理不足的表面加上「紋理」,讓立體視覺演算法能穩定找到對應點。此設計結合了被動立體視覺的「在有紋理時無需額外輔助」優勢與結構光的「在無紋理時主動補齊」優勢,使得 D435 在各種室內環境都能產生穩定的深度圖。值得注意的是,D435 的紅外線投射器並非必要——即使關閉投射器,D435 仍能在紋理豐富的場景下運作(純被動模式),這是相較於純結構光相機的重要彈性。D435 的深度感測本質是**三角測量立體視覺**而非結構光或 ToF,這點在技術文件中需特別澄清,避免誤解為「紅外線結構光」。

此技術選擇對本專題有兩個實務影響:其一,室內環境下深度感測穩定,即使面對白牆或光滑地板也能產生完整深度圖;其二,在直射陽光下,環境中的紅外線會淹沒 D435 投射的圖案,導致戶外深度感測精度下降——這也是本專題定位為「居家互動機器狗」而非戶外應用的考量之一。

## 硬體規格

| 規格項目 | 數值 |
|---|---|
| **深度感測技術** | Active IR Stereo(主動紅外線立體視覺) |
| **深度視野(FOV)** | 87° × 58° × 95°(H × V × D,±3°) |
| **深度解析度** | 最高 1280 × 720 @ 90 FPS |
| **RGB 感測器** | OmniVision OV2740(200 萬畫素) |
| **RGB 視野(FOV)** | 69° × 42° × 77°(H × V × D,±3°) |
| **RGB 解析度** | 最高 1920 × 1080 @ 30 FPS |
| **深度感測器快門** | Global Shutter(全域快門) |
| **RGB 感測器快門** | Rolling Shutter(捲簾式快門) |
| **最小測距(MinZ)** | 0.2 公尺典型值(最低可調至 0.1 公尺,需降低解析度) |
| **理想工作範圍** | 0.3 至 3 公尺 |
| **最大有效距離** | 約 10 公尺(精度於 3 公尺後顯著下降) |
| **基線距離(Baseline)** | 50 公釐(兩個深度感測器之間的距離) |
| **連線介面** | USB 3.0 Type-C(USB 供電) |
| **尺寸** | 90 × 25 × 25 公釐 |
| **紅外線投射器** | 可程式化開關,功率約 300 毫瓦 |
| **IMU** | **不配備**(若需 IMU 應選 D435i 變體) |

## D435 vs D435i 的關鍵差異

本專題採用**標準版 D435(不含 IMU)**,而非同系列的 D435i(含 Bosch BMI055 6 軸慣性測量單元)。兩者的視覺感測器與深度感測原理完全相同,唯一差異是 D435i 額外整合了 IMU 晶片,可用於影像穩定、視覺慣性里程計(Visual-Inertial Odometry, VIO)、或輔助 SLAM 建圖時的姿態估計。本專題未選用 D435i 的理由是:其一,Jetson 已透過 Go2 Pro 取得機器狗自身的 IMU 資料(Go2 內建 IMU 可透過 WebRTC DataChannel 讀取),無需另一組冗餘資料來源;其二,本專題的視覺感知任務(人臉、手勢、姿勢、物體)皆為單幀推論,不依賴跨幀的 IMU 補償;其三,原始 D435 的採購成本低於 D435i,且為指導老師既有的硬體資源,不需要額外採購。

## Global Shutter 與 Rolling Shutter 的影響

D435 的深度感測器採用 **Global Shutter(全域快門)**——所有像素於同一瞬間曝光、同一瞬間讀取,此特性對快速移動物體的深度感測至關重要,避免因為上下排像素曝光時間差而產生的深度扭曲。這是 D435 相較於普通 USB 網路攝影機的重要優勢之一,使其能穩定感知移動中的人體姿勢(例如使用者揮手、走動)。

然而,D435 的 **RGB 感測器採用 Rolling Shutter(捲簾式快門)**——像素按行順序曝光與讀取,當相機或場景快速移動時,會產生「果凍效應」(jello effect)使物體出現傾斜變形。對本專題而言,此特性於靜態使用者互動(站立、坐下、面對機器狗對話)場景下影響輕微,但若機器狗行走中錄製 RGB 影像則可能出現畫面傾斜。由於本專題的互動場景以靜態使用者為主,Rolling Shutter 尚未對感知精度造成實務問題。

## 本專題的使用情境與 ROS2 整合

本專題於 Jetson Orin Nano 上透過 Intel 官方的 **librealsense2 SDK** 與 ROS2 wrapper 套件 `realsense2_camera` 存取 D435。啟動相機後,系統會在 ROS2 網路中發布以下關鍵 Topic(注意:本專題採用 `realsense2_camera` ROS2 wrapper 的 **double namespace** 命名慣例 `/camera/camera/…`):

| Topic | 說明 | 訂閱者 |
|---|---|---|
| `/camera/camera/color/image_raw` | RGB 影像串流 | 人臉、手勢、姿勢、物體辨識模組 |
| `/camera/camera/aligned_depth_to_color/image_raw` | 與 RGB 對齊的深度影像(以 RGB 像素座標為參考) | 人臉辨識(距離估算) |
| `/camera/camera/depth/image_rect_raw` | 原始深度影像(深度感測器原始座標) | 預留未來避障使用 |
| `/camera/camera/depth/camera_info` | 深度相機內部參數(焦距、主點、畸變係數) | 座標轉換 |

值得特別說明的是 `aligned_depth_to_color` 的處理——D435 的 RGB 感測器與深度感測器有不同的物理位置、內部參數與視野,原始的深度影像需經過座標對齊處理才能讓深度與 RGB 像素一對一對應。此對齊功能由 Demo 啟動腳本在啟動 `realsense2_camera` 時啟用;本系統的人臉辨識模組並不自行啟動相機節點,而是直接訂閱已對齊的 `/camera/camera/aligned_depth_to_color/image_raw` Topic,以人臉邊界框的中心點座標查詢對應深度值,估算使用者與機器狗的距離(輸出於 `distance_m` 欄位供 PawAI Studio 顯示)。此設計免去了開發者自行處理兩組內部參數與外部校正矩陣的複雜度。

## D435 深度資料的實務限制

本專題在 D435 使用過程中遭遇以下幾項實務限制:

1. **直射陽光干擾**:D435 的紅外線投射圖案在直射陽光下會被背景紅外線淹沒,深度感測率顯著下降。此為本專題將展示場景限定於室內的技術理由之一。

2. **高反光表面**:玻璃、鏡面、拋光金屬等高反光表面會反射紅外線,產生錯誤的深度讀數或空洞。

3. **深色吸光物體**:深黑色或黑色絨面材質會吸收紅外線,導致深度圖出現破洞。此為本專題物體辨識遭遇 `bottle`(深色水瓶)偵測失敗的可能原因之一。

4. **最小距離限制**:0.2 公尺的最小工作距離意味著使用者不能過於接近 D435,否則深度資料會變為無效讀數。本專題的人臉辨識與手勢互動建議距離範圍為 1 至 3 公尺。

5. **USB 3.0 頻寬需求**:同時啟用 RGB(1920 × 1080 @ 30 FPS)與深度(1280 × 720 @ 30 FPS)兩路串流時,USB 頻寬佔用接近 USB 3.0 Type-C 介面的理論上限,若搭配劣質 USB 線材或主機 USB 控制器能力不足會造成掉幀。本專題使用官方 USB 3.0 線材直接連接 Jetson 的 USB 3.2 Gen2 port,確保頻寬穩定。

6. **librealsense2 與 JetPack 6 的相容性**:Jetson 上的 librealsense2 需使用 NVIDIA 針對 ARM 架構編譯的版本,透過 ROS2 套件管理員安裝 `ros-humble-librealsense2*`,若直接從 Intel 官方下載 x86 版本會無法運作。此為 Jetson 部署的常見陷阱。

## 安裝位置與光線條件

本專題將 D435 安裝於 Go2 Pro 機身前方的固定支架上,鏡頭朝向機器狗正前方。如第五章系統限制所述,安裝角度略為偏上方,使得低矮障礙物(地面雜物、椅腳、門檻)於近距離才進入視野,這是原本 D435 深度避障方案於 2026 年 4 月 3 日停用的根本原因。視覺感知類模組(人臉、手勢、姿勢、物體)則不受此安裝角度影響,因為它們的目標物(人體上半身、手部、桌上物體)多位於鏡頭的正常視野內。光線方面,本專題 Demo 場景統一採用充足照明以確保所有視覺模組穩定運作;低光源或側光場景會導致人臉偵測信心度下降、物體偵測率降低、手部關鍵點抖動等問題。
