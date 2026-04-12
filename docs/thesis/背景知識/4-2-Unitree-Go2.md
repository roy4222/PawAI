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
