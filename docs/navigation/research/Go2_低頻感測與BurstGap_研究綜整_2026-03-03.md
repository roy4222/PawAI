# Go2 低頻感測與 Burst+Gap 研究綜整

更新日期：2026-03-03  
適用範圍：Go2 Pro + Jetson Orin Nano 8GB + ROS2 Humble + Nav2  
目的：將多份外部研究報告轉為可執行、可驗證、可回滾的部署決策

---

## 1. 結論先行

- 目前狀態屬於「定位可用，連續避障不可用」：`/amcl_pose` 可出，但 `/scan`、`/point_cloud2` 常態低於 2Hz，且存在長 gap。
- 在此條件下，連續導航避障為 **No-Go**；必須先修復感測資料新鮮度（freshness）與間隔上界（max gap）。
- Nav2 參數可做暫時降級（保命），但不能當根治。根治點在上游資料路徑（傳輸/排程/解碼/負載）。
- 安全策略必須獨立於 Nav2 主流程：感測逾時即停車（stale-data stop gate）。

---

## 2. 報告整合評估（本輪 4 份）

### R1（早期報告）
- 優點：方向正確，指出「問題在資料鏈而非單純控制器」。
- 缺點：可追溯數據不足，偏策略導向。
- 採納：中等（方向採納，數值不直接採納）。

### R2（數字較多但證據混雜）
- 優點：涵蓋面廣，提供大量假設與實作建議。
- 缺點：部分比例與數值過度確定，來源層級混雜。
- 採納：中低（當假設清單，不當定稿依據）。

### R3（目前最強）
- 優點：清楚區分「硬證據 vs 推定」，具體提出 `P95/max gap/message age` 與 gate 思路。
- 缺點：仍需本場域數據封口（尤其 WebRTC vs CycloneDDS 對照）。
- 採納：高（本文件主框架來源）。

### R4（模板完整但保守看待）
- 優點：架構完整、可讀性高。
- 缺點：多處泛化敘述，針對性不如 R3。
- 採納：中等（作為補充目錄與清單）。

---

## 3. 證據分級（只用可驗證內容決策）

### A 級（可直接決策）
- 專案內實測紀錄（本機命令輸出、bag、影片、參數版本）。
- 官方文件對應參數語義（Nav2/ROS2/Unitree/NVIDIA）。

### B 級（可形成假設）
- GitHub issue、論壇案例、社群實作文章。

### C 級（僅作靈感）
- 無完整測試條件的二手整理、行銷型內容、未附可重現步驟的結論。

決策規則：**A 級可決策，B 級需本地驗證，C 級不可直接進主線。**

---

## 4. 決策型 Go/No-Go Gate（硬條件）

## 4.1 感測新鮮度 Gate
- 必填指標：`gap95`、`gap99`、`gap_max`、`age95`、`age99`。
- No-Go 任一成立：
  - `gap_max > 1.0s`
  - `gap99 > 0.5s`（連續避障模式）
  - `age99 > 0.2s`（moving localization）

## 4.2 安全停車 Gate（獨立安全層）
- 必須啟用 stale-data stop：感測逾時即 `cmd_vel=0`。
- 建議起始：`T_stale <= 0.6s`（後續依實測收斂）。
- 測試必過：強制 3 秒感測黑屏時，不可繼續前進。

## 4.3 AMCL 可用性 Gate
- 「移動中定位可用」條件：
  - `gap99 <= 1.0s`
  - `gap_max <= 2.0s`
  - `age99 <= 0.2s`
- 否則僅允許「停車定位」（Stop-to-localize）。

## 4.4 系統負載 Gate
- 監控：CPU、RAM、swap、溫度、節流事件。
- 發生 swap churn 或持續節流時，導航測試自動降級/停止。

---

## 5. 當前技術判斷（對本專案）

- 目前不是 planner/controller 先天失敗；主阻塞是資料路徑不穩（低頻 + 長 gap）。
- 先修「資料可用性」，再追「控制體感」。順序不可反。
- 在 `<2Hz` 與長 gap 狀態下，任何「能到點」都不能視為安全避障成功。

---

## 6. 可複製實驗矩陣（下一輪 deep research 執行模板）

固定條件：同地點、同路徑、同障礙配置、同測試時長（>=30 分鐘）。

### Matrix A：傳輸路徑
- A1: WebRTC
- A2: CycloneDDS/Ethernet

### Matrix B：解碼/資料管線
- B1: decoder 路徑 1
- B2: decoder 路徑 2

### Matrix C：負載條件
- C1: headless（無 RViz/錄包）
- C2: RViz + 錄包（壓力）

每一格都輸出：
- `gap95/gap99/gap_max`
- `age95/age99`
- controller miss rate
- 近失誤數（near-miss）與最小安全距離
- 是否觸發 stale stop（次數/原因）

---

## 7. 反假進展（Anti-False-Progress）

- 只報平均 Hz 視為無效結果。
- 關閉逾時檢查後的成功率，不計入通過。
- 僅空場地成功，不計入避障通過。
- 未綁定 `config hash + commit + bag + video` 的結果，不計入比較。

---

## 8. 下一步（直接執行）

1. 建立統一量測腳本：自動輸出 gap/age 分位數與 max gap。  
2. 導入獨立 safety stop（感測逾時即停車）並做故障注入測試。  
3. 跑 Matrix A/B/C，先拿到本場域證據，再決定是否調 Nav2 主參數。  
4. 僅在 Gate 穩定通過後，才進入 DWB/MPPI 體感優化。

---

## 9. 文件定位

本文件是研究決策索引，不取代：
- `docs/navigation/README.MD`（總覽）
- `docs/navigation/weekly_plan.md`（週執行）
- `docs/navigation/落地計畫_v2.md`（落地路線）

若本文件與上述文件衝突，以「安全 gate 較嚴格者」為準。

---

## 10. 最新外部深研採納（2026-03-03，Minimax 版）

本輪新增一份高品質外部研究（評估：9/10），其價值在於把「低頻與 burst+gap」轉成可操作量測與故障樹。以下內容採納為本專案下一輪實驗標準。

### 10.1 新增採納要點

- A/B 測試需採公平鎖定條件：
  - 同版 `go2_ros2_sdk`、同 launch 組合、同測試場景
  - 鎖定網卡/介面（CycloneDDS 指定 interface + peers）
  - 固定 Jetson power/clocks 與 swap 策略
  - 固定 D435 輸出配置（避免因相機負載污染通訊比較）
- 指標以分位數為主，不再以平均 Hz 作為主結論：
  - 必報 `gap95/gap99/gap_max`、`age95/age99`
  - topic 最小集合：`/point_cloud2`、`/scan`、`/odom`、`/tf`、`/cmd_vel`
- 根因優先順序採「故障樹」：
  1. TF / MessageFilter
  2. costmap update timeout
  3. controller miss rate / scheduling starvation
  4. 通訊路徑與介面選擇
  5. Nav2 細參數

### 10.2 新增硬性驗證項目

- 端到端分段延遲拆解（至少近似版）：
  - sensor stamp -> RX
  - RX -> costmap update
  - costmap update -> cmd_vel publish
- 安全故障注入測試（必做）：
  - 人工注入 3 秒感測黑屏，系統必須停車且不可自行前進
  - 人工增加 200ms 延遲，檢查是否觸發降級或停車 gate

### 10.3 立即執行的實驗矩陣（覆蓋 Matrix A/B/C）

- Matrix A（通訊）：WebRTC vs CycloneDDS/Ethernet
- Matrix B（管線）：decoder 路徑 1 vs 2
- Matrix C（負載）：headless vs RViz+錄包

每格最少 10 分鐘，採 ABBA 順序（減少熱飄與時間漂移偏差）。

### 10.4 決策更新（何時停止微調 Nav2）

若以下條件成立，停止「只調 Nav2」，改做架構變更：

- 在固定低負載與 TF 修復後，仍持續 `gap99 > 0.5s` 或 `gap_max > 1.0s`
- 為避免 miss rate 只能把 controller 頻率壓到過低，且安全速度上限無法滿足任務需求

架構變更方向：

1. 優先切換/固定通訊路徑（CycloneDDS/Ethernet）
2. 簡化或重構重負載資料轉換節點
3. 強化獨立 safety layer（stale-data stop + collision monitor）

---

## 11. KIMI 深度研究採納（2026-03-03）

本節整合 KIMI 報告的高價值內容，並明確區分「直接採納 / 條件採納 / 暫不採納」。

### 11.1 可信度結論（本專案視角）

- 策略價值：高（結構完整、主題覆蓋面廣）
- 可直接採信度：中（部分數值需本場域驗證封口）
- 決策定位：可作為研究輸入，不可取代本地量測結果

### 11.2 直接採納（Now）

1. 主線架構維持 `LiDAR -> /scan -> Nav2`，D435 先做近場補強，不直接取代 LiDAR 主安全來源。  
2. 導航安全判準以資料新鮮度為核心（`gap/age`），不是只看平均 Hz。  
3. 低頻抖動診斷順序採分層排查：TF/時間戳 -> costmap 更新 -> controller miss -> 通訊路徑。  
4. 安全層必須獨立於 Nav2 主控制：感測逾時停車（stale stop）與 collision monitor。  

### 11.3 條件採納（Need Local Evidence）

以下主張僅作為假設，需完成本地 A/B 後才能升級為決策：

1. WebRTC 與 CycloneDDS 的延遲差距幅度（包含是否達到特定倍數改善）。  
2. D435 在 Orin Nano 的最佳 profile（解析度/FPS/filter）與 CPU 成本。  
3. DWB/RPP/MPPI 在本場域低頻感測下的穩定排序。  
4. 各 topic 健康頻率門檻的固定數值（必須由本地分位數報表定義）。  

### 11.4 暫不採納（Reject for Now）

1. 未附同條件基準（同 firmware、同場景、同負載）的精確數值結論。  
2. 僅靠平均 Hz 或單次 demo 成功率宣稱「可安全避障」。  
3. 在未通過 freshness/stale-stop gate 前，直接進入高複雜控制器或 3D 重管線升級。  

### 11.5 KIMI 對應實驗收斂清單

為避免「報告好看但不可落地」，KIMI 內容統一收斂到以下實驗：

- E1：WebRTC vs CycloneDDS ABBA 對照（必報 `gap95/gap99/gap_max`、`age95/age99`）  
- E2：D435 三組 profile 對照（headless 與 RViz+錄包雙負載）  
- E3：故障注入（3 秒感測黑屏、+200ms 延遲）下的停車行為  
- E4：controller 比較（DWB/RPP）僅在 E1-E3 通過後執行  

### 11.6 與現有 Gate 的關係

KIMI 報告不會覆蓋本文件第 4 節硬門檻；若 KIMI 建議與 gate 衝突，
一律以本文件硬門檻（安全較嚴格者）為準。
