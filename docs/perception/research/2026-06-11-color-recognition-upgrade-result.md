# 顏色辨識升級研究結果 — HSV 12 色之後的方案

> **日期**：2026-06-11
> **對應 goal**：`docs/perception/research/goals/2026-06-11-color-recognition-upgrade-goal.md`
> **Verdict**：**GO_LAB_NEAREST_NAME**（方案 A 為主軸 + 方案 C 中央 50% 取樣為配套 + 事件級時序平滑；光照前處理裁定為「demo 場次 AWB lock 選配、不疊 gray-world」）
> **紀律**：read-only 研究，無 code 變更、無 commit、無安裝。微基準只在 WSL 既有環境執行（numpy/cv2 已存在），腳本以 stdin 餵 `python3` 不落地檔案；完整腳本與原始輸出內嵌於附錄 A（read-only 紀律下本檔是唯一寫入物，腳本入 repo 留待 §7 next step 的 `color_naming_spike.py`）。

---

## TL;DR

1. **「不準」的根因排序 = ③ 12 色粒度（確定）≥ ① bbox 背景污染（高）> ② 光照飄移（中，黃光/暗處放大）**。三者現役代碼各有具體弱點（見 §1，行號齊）。
2. **方案 A（Lab + CIEDE2000 最近色名 + 預建 LUT）成本實測級便宜**：全管線（resize 300→64 + LUT 查表 + bincount）每 bbox **0.190ms**（WSL x86 實測，腳本+輸出見附錄 A；Jetson ×2-3 外推 ~0.4-0.6ms），其中查表本體僅 0.026ms、resize 佔大宗——與現役 HSV 同管線（0.186ms）幾乎同價。輸出是「逐像素投票 → peak 比例」——`color_confidence` 語意直接保留、模組級純函數測試形態直接沿用。
3. **方案 B（k-means）成本同級（全管線 0.346ms 實測，附錄 A）但有 init 隨機性 → 連續幀色名翻動風險**，而且 dominant cluster 在污染 bbox 裡照樣可能是桌面——它解的問題 C（中央取樣）用零成本就解掉了。
4. **方案 D（seg mask 取色）被 goal 1 裁決封死**：seg 變體已因 box mAP 反而 -1.3、GFLOPs +65% 被踢出上機矩陣（scaleup result :15）——D 只能當未來 seg 若因其他理由上線後的順手升級，不能當主軸。
5. **gray-world 不要疊在 D435 AWB 上**，crop 級 gray-world 對單色物件是毀滅性的（會把紅杯校成灰杯）；demo 場次可改用「鎖定 AWB」拿可重複性（MartyG：設任何手動 WB 值會自動關 AWB）。
6. **色名表選自訂生活色名表：19 名 +1 保留位（合計 20 槽，含米/木/深淺變體）**，不選 CSS140/xkcd949/ISCC-NBS267——中文 TTS 輸出鏈（`OBJECT_COLOR_ZH` → 「看到紅色的杯子了」）是硬需求，外部表沒有可念的 zh 對應。
7. 下游同步點明確：contract v2.5 的 12 色 enum（`interaction_contract.md:677`）要 bump、`pawai_contracts/zh_tables.py` 單一真相 + parity test、Studio `object-config.ts:205` 副本、以及一條會被新設計弄壞的 regex 測試（`test_object_perception.py:336-348`）。

---

## §1 診斷先行：「不準」三根因排序（附現役代碼弱點行號）

### 排序結論

| 排名 | 根因 | 信心 | 直接證據 |
|---|---|---|---|
| 1 | **③ 12 色粒度不足** | 確定 | 使用者 6/11 原話「12 種也不夠」（goal :8）；米色/木色/深淺藍在現役邊界全擠進錯桶（F5、F9、Q1 推導） |
| 2 | **① bbox 背景污染** | 高 | `analyze_bbox_color` 取整個 bbox crop 無任何空間先驗（`object_perception_node.py:91`）；幾何估算桌面可佔 cup bbox 30-50%（Q2）；brain 端已因 color-jitter 把 color 從 dedup key 拔掉（`brain_node.py:55-58`，F15）——jitter 的主要來源就是逐幀 bbox 內容物比例變動 |
| 3 | **② 光照 HSV 飄移** | 中 | 白色 gate `S < 40`（`object_perception_node.py:101`）對任何 >~15% 色偏立即破功；暗處 `V<50→black`、暖色相 `V<130→brown`（:100, :106）讓暗景彩色塌縮（Q1 完整推導）；但 D435 AWB 預設開著會吸收掉一部分 |

排序依據：③ 是使用者直接陳述的需求缺口，不需實拍佐證；① 有代碼結構性弱點 + brain 端 jitter 歷史證據雙重支撐；② 的影響被 AWB 部分緩解（AWB 預設開，F17），且 demo S3 紅杯近距是實錄成功過的——「demo S3 實測 0.7m 才穩」（scaleup goal，`docs/perception/research/goals/2026-06-11-yolo26-scaleup-highres-seg-goal.md:8`）、6/10 S3 cup 段狀態 Recorded（`docs/pawai-demo/2026-06-10-demo-snapshot.md:38`，註明 near-range and controlled）——表示至少在當日受控場地的光照下紅色判定成立。但該紀錄**未記載現場色溫**，且 snapshot 的 Forbidden Claims 明文禁止宣稱「under arbitrary lighting」可靠（`2026-06-10-demo-snapshot.md:93`）⟹ 光照魯棒性視為**未驗證**，② 評「中」而非「低」。（勘誤：本報告初稿此句曾寫「現場黃光下紅杯 0.7m 成功」並引 `demo_script.md:52,168`——查證後該檔全文無 0.7m 也無黃光字眼（:28 寫的是擺位目標 ~1.5m、:52 是 preflight checklist、:168 是台詞稿），0.7m 真正出處是 scaleup goal :8；「黃光下」限定詞無任何引用支撐，已刪除。）排除 `NEEDS_TEST_COLOR_SAMPLE_SET` 的承重論據是 ③（使用者原話，方向已定）與 ①（代碼結構性弱點，不需實拍即可指認），**不依賴 ② 的精確權重**；②的權重不確定性交給 §7 驗收 protocol 在上機日同場收齊三光照數據作 falsification。

### 各根因對應的代碼弱點（cite）

- **①**：`object_perception_node.py:91` `crop = image_bgr[y1c:y2c, x1c:x2c]` — 整個 bbox 無中央加權；`:133-135` peak 取 max count——桌面像素若佔 40%、杯身佔 30%，**桌色以 ratio 0.4 過 0.25 門檻勝出**，回報的還是「高信心錯誤答案」。0.25 fragmentation 門檻（`:135`）只防碎裂、不防「背景剛好是最大單色塊」。
- **②**：`:100` `V<50→black`、`:101` `S<40 ∧ V≥200→white`、`:106` `H∈[5,25] ∧ V<130→brown`。三個 gate 全是絕對閾值，光照變了就整片平移（Q1 量化）。
- **③**：`:115-121` 七個彩色 hue 帶 + 5 個特例桶 = 12 名。米色（高 V、S≈40-90、H≈15-30）落在 chromatic ∧ V≥130 → **「orange/yellow」**；木桌（H≈10-20、V 中）→ brown/orange；深藍淺藍同進 `blue (100,130]`；無 beige/tan/navy 可用。

---

## §2 Findings（F1–F40，逐條附引用）

### A. 現役實作（本地代碼）

- **F1** 顏色分析對象 = **整個 bbox crop、原解析度、無 downsample**：`crop = image_bgr[y1c:y2c, x1c:x2c]`（`object_perception/object_perception/object_perception_node.py:91`）。300×300 bbox = 9 萬像素全跑 12 個 boolean mask；沒有中央加權、沒有形狀先驗。
- **F2** 12 色 mask 是**互斥且完備**的分割：achromatic gate（black/white/gray，`:100-103`）→ brown 特例（`:106`）→ pink 特例（`:110-112`）→ 7 個 hue 帶（`:115-121`）。H∈[0,180] 全覆蓋，total = crop 全像素（`:129-131`），所以 `color_confidence` 分母固定是 bbox 面積。
- **F3** `color_confidence` 的真實語意 = **peak 純度（peak_pixels/total_pixels），不是「答對的機率」**（`object_perception_node.py:78-79,133-137`；contract 描述同：`docs/contracts/interaction_contract.md:679-680`）。被污染的 bbox 回報「桌色 0.45」時是高純度的錯誤答案。升級方案 A 的 peak-vote 比例可無縫接同一語意。
- **F4** 白色 gate `S < 40`（`:101`）= 容忍色偏上限約 **40/255 ≈ 16% 飽和度**。黃光下白物 S 輕易衝到 80-125（Q1 計算）→ 白永遠不會被判白。
- **F5** brown 特例 `chromatic ∧ H∈[5,25] ∧ V<130`（`:106`）有雙面刃：暗處的橘/紅/暖灰全進 brown；亮處的真棕色（V≥130 的淺木色）反而漏出去變 orange。
- **F6** pink 規則 `(H≥160 ∨ H≤5) ∧ S<150 ∧ V≥180`（`:110`）會把**亮面紅杯的高光區**（V 高、S 因鏡面反射下降）判成 pink → 同一顆紅杯隨打光角度在 red↔pink 翻動。
- **F7** magenta 帶 `150<H<165` 判 pink **無任何 S/V gate**（`:111`）——深紫紅也回 pink。
- **F8** `V<50→black`（`:100`）：暗角的任何彩色物直接塌縮成黑（3000K 下藍物反射能量低，V 掉 2-3 倍，極易跌破 50；外推假設見 Q1）。
- **F9** cyan 帶只有 `(85,100]` 15 個 hue 單位（`:119`），居家常見 teal/湖水綠類物品會在 green/cyan/blue 三桶間抖。
- **F10** **`analyze_bbox_color` 沒有任何餵真實像素的單元測試**：`object_perception/test/test_object_perception.py` 全檔只有 zh 覆蓋的 regex 測試（`:336-348`）與事件 gating 測試（`:354-387`），沒有一條「給定合成色塊 → 斷言色名」的 pixel-level 測試——「不準」目前完全沒有回歸網。
- **F11** 模組級函數設計（「Module-level (vs class staticmethod) so unit tests can import without pulling in rclpy」，`object_perception_node.py:80-82`；wrapper `:345-347`）是升級必須保留的測試形態（goal :71）。
- **F12** Contract v2.5 把 color 寫成**封閉 enum 恰好 12 值**：`"enum": ["red","orange",...,"gray"]`（`docs/contracts/interaction_contract.md:668,677`）。擴成 N 色 = contract bump + `pawai contract check` 鏈同步。
- **F13** zh 色名表 6/10 Plan C3 後**單一真相在 `pawai_contracts/pawai_contracts/zh_tables.py:27`**（`OBJECT_COLOR_ZH`），brain 由此 import（`brain_node.py:44-52`），producer canon 是 `coco_classes.py` 的 `COLOR_ZH`（`coco_classes.py:129-142`），Studio TS 副本在 `pawai-studio/frontend/components/object/object-config.ts:204-206` 且有 parity test 看守（`pawai_contracts/test/test_zh_parity.py:1`）。**擴色名 = 四處同步 + parity test 改**。
- **F14** brain TTS 對未知色名是 graceful degrade：`if color and color != "Unknown" and color in OBJECT_COLOR_ZH`（`brain_node.py:101-104`）——新色名沒進 zh 表時只會少念顏色、不會 crash。部署順序上「先擴 producer 後補 zh」是安全的。
- **F15** **色名翻動已是被記錄的實戰問題**：brain 的 per-class dedup「D-4: key = class_name only, **color dropped to prevent color-jitter bypass**」（`brain_node.py:56-58`）——同物件連續事件色名跳動到需要在消費端防禦的程度。任何升級方案都該附時序平滑（Q5）。
- **F16** Demo S3 的消費鏈：紅色杯子放 ~1.5m（`docs/runbook/demo_script.md:28`）、台詞「我看到一個紅色的杯子」（`:168`）、技術台詞「用 YOLO 認出杯子，再用 OpenCV 看主要顏色」（`:178`）、預檢命令（`:52`）、失敗預案（`:184`）。**S3 只消費 "red" 一個色名**——擴表不會破壞 S3，反而讓「紅」的邊界（vs pink/brown）更穩。
- **F17** D435 相機啟動參數只設了 `rgb_camera.color_profile:=640x480x15`，**沒碰 white balance**（`scripts/start_full_demo_tmux.sh:143-147`）→ librealsense 預設 AWB 開啟，現場色溫由 ISP 動態決定，逐幀可變。
- **F18** 事件層只在 `color != "Unknown"` 時帶 color 欄位（`object_perception_node.py:448-450`；測試 `test_object_perception.py:354-366`）——Unknown 多了不會污染 brain，只會讓 S3 念不出顏色。
- **F19** 顏色是**單幀快照**：每 class 5s cooldown（`object_perception_node.py:441-452`）下，事件帶的 color 來自 cooldown 過期那一幀，**沒有跨幀聚合**——單幀剛好打到高光/陰影就直接定生死，是 F15 jitter 的結構性來源。
- **F20** goal 1（scaleup）已裁定：「**seg 變體對 cup recall 是純虧損**……本矩陣剔除 seg，輪廓/顏色需求留給 goal 3 另案」（`docs/perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md:15`）；同文 :100 明說 mask 內取色比 bbox 乾淨但「那是顏色線的 ROI 問題，不是 cup recall 問題」。**方案 D 的前置依賴在可見未來不存在**。
- **F21** supervision 研究已確認時序穩定化哲學與限制：ByteTrack `minimum_consecutive_frames`「連續 N 幀才建 track」防單幀假陽性（`docs/perception/research/2026-06-11-supervision-pawai-fit-report.md:64`）；但 `DetectionsSmoother` 平滑的是 xyxy+confidence、**不平滑 class label**（`:160`）——色名平滑得自己做（多數決），不能指望 supervision 現成件。

### B. 色彩科學與色名表（web）

- **F22** OpenCV 8-bit Lab 轉換：先轉 float 並 scale 到 [0,1] 計算，輸出 `L←L*255/100, a←a+128, b←b+128` 壓進 [0,255]，白點 **D65**（[OpenCV imgproc color conversions — RGB ↔ CIE L\*a\*b\*](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html)）。8-bit Lab 的量化粒度（L 每階 100/255≈0.39）遠小於色名邊界尺度（相鄰生活色名 ΔE 通常 >15），**uint8 路徑對「命名」夠用**，不需 float32 全精度。
- **F23** OpenCV 8-bit HSV 的 H 是 `H/2` 壓到 [0,180]（同上 OpenCV docs）——現役代碼註解 `:60` 一致，hue 帶寬解讀無誤；這也意味 hue 解析度只有 2°/階，窄帶（如 cyan 15 階）天生抖。
- **F24** CIEDE2000 自 2013 起是 ISO 與 IDEAlliance 的色差工業標準（[Datacolor/Techkon — CIE ΔE\* equations](https://techkon.datacolor.com/cie-de-color-difference-equations/)）；CIELAB 是其感知均勻基底（[Wikipedia — Color difference](https://en.wikipedia.org/wiki/Color_difference)）。
- **F25** 2026 的色名系統研究：**19,555 個 RGB-色名對（20 來源）→ CIELAB + CIEDE2000 距離 k-means → 280 個最優聚類**，並指出「人類實際只區分有限數量的色彩類別」而既有表充滿「感知上不可分的重疊色」（[arXiv 2604.03235 — Toward a Universal Color Naming System](https://arxiv.org/abs/2604.03235)）。⟹ 佐證「自訂小表（~20）+ 感知距離」優於照搬大表。
- **F26** xkcd 色名調查：22.25 萬 sessions、500 萬+ 答案 → **954 個 RGB 色名**；結論包含「RGB is not an absolute color space」與拼字混亂（"Nobody can spell 'fuchsia'"）（[xkcd color survey results](https://blog.xkcd.com/2010/05/03/color-survey-results/)）。949/954 名全是英文俚語式命名（無 zh 對應），當查表用會把輸出炸成 TTS 念不出的長尾。
- **F27** ISCC-NBS 含 **267 個標準色名，基於 12 個基本色詞 + 修飾詞**（[W3Schools — ISCC-NBS colors](https://www.w3schools.com/colors/colors_nbs.asp)；[MIT CSAIL — Color-Name Dictionaries](https://people.csail.mit.edu/jaffer/Color/Dictionaries)）——學術完備但 267 名對語音輸出同樣過細。
- **F28** Berlin & Kay 跨語言研究的 **11 個基本色詞**：black/white/gray/purple/pink/red/green/blue/yellow/orange/brown（[peteroupc — Color Topics for Programmers](https://peteroupc.github.io/colorgen.html)）。現役 12 色 = 11 基本詞 + cyan，**粒度天花板就是基本詞層級**；使用者要的米/木/深淺變體屬於「基本詞 + 修飾」層，自訂表是唯一能對齊 zh 的路。
- **F29** 最近色名法的標準做法：在列表中找 ΔE 最小者；ΔE76 = Lab 歐氏距離，**CIEDE2000 是更準的首選**（含 CIE 230:2019 的後續改良）（[peteroupc — Color Topics for Programmers](https://peteroupc.github.io/colorgen.html) §Nearest Colors / §Color Difference）。
- **F30** k-means 取主色的文獻慣例：**用 CIELAB 而非 RGB**（感知均勻）、配 CIEDE2000；對背景/陰影的對策是「把含黑/背景的 cluster 排除在主色判定外」（[IEEE 9869653 — Color Feature Based Dominant Color Extraction](https://ieeexplore.ieee.org/document/9869653/)；[Doug Fenstermacher — X-means + CIE2000 dominant color](https://dougfenstermacher.com/project/xmeans-cie2000-dominant-color-extraction-visualization-tutorial)；[TDS — From RGB to Lab](https://towardsdatascience.com/from-rgb-to-lab-addressing-color-artifacts-in-ai-image-compositing/)）。⟹ 「排除背景 cluster」最終還是要一個背景先驗——繞回中央取樣。
- **F31** `cv2.kmeans` 介面：data 必須 float32、`attempts` 控制重跑次數、`KMEANS_PP_CENTERS`（kmeans++）/`KMEANS_RANDOM_CENTERS` 是**隨機初始化**、回傳 compactness（[OpenCV core cluster docs](https://docs.opencv.org/4.x/d5/d38/group__core__cluster.html)）。隨機 init = 連續幀聚類結果可變（Q5 翻動風險的來源）。

### C. 光照恆常性與 D435 AWB（web）

- **F32** MartyG（Intel RealSense 官方支援）：「**Applying any manual white balance value causes AWB to disable if it is currently enabled**」；WB 手動下限 **2800**（"WB reduced as low as it would go (2800)"）（[realsense-ros issue #1354 comments](https://github.com/IntelRealSense/realsense-ros/issues/1354)，MartyG-RealSense 2020-08）。⟹ 鎖定 AWB 的操作就是「設一個手動 WB 值」。
- **F33** AWB 開啟時**讀不到當前 WB 值**（無法「先 AWB 收斂再凍結讀值」）（[librealsense issue #10143 — Save and load auto white balance settings](https://github.com/IntelRealSense/librealsense/issues/10143)）。鎖定值只能現場掃描挑選，不能抄 AWB 的答案。
- **F34** ROS wrapper 關 AWB 的官方做法（doronhi，realsense-ros maintainer）：launch 層設 `rgb_camera/enable_auto_exposure: false`、`rgb_camera/enable_white_balance: false` 等 rosparam，參數名照 rqt_reconfigure 層級拼（[realsense-ros issue #1354 comments](https://github.com/IntelRealSense/realsense-ros/issues/1354)）。ROS2 wrapper 對應 `rgb_camera.enable_auto_white_balance` + `rgb_camera.white_balance`。
- **F35** D435 手動 WB 的行為基準（逐字釘自官方支援人員留言）：「As a general rule, decreasing the white balance setting below its **default value of '4600'** shifts the color tinting of the RGB image towards the blue range, whilst increasing it above the default brightens the image and makes the colors more intense (for example, a pale red becoming an intense red like a rosy apple)」，留言並附 low WB（blue tinted）/ high WB（warm colors）對照圖（MartyG-RealSense 2022-02-11，[librealsense issue #10143 comment](https://github.com/IntelRealSense/librealsense/issues/10143#issuecomment-1036056796)，本研究以 GitHub API 取回留言全文逐字驗證）。Intel Help Center 兩討論串（[Blueish tone in rgb image d435](https://support.intelrealsense.com/hc/en-us/community/posts/360049132913-Blueish-tone-in-rgb-image-d435)、[Auto vs manual white balance](https://support.intelrealsense.com/hc/en-us/community/posts/7338435151507-Auto-white-balance-vs-manual-white-balance)）方向一致，但該站 fetch 被拒、未取得原文逐字，僅列**未逐字驗證的輔證**，不作承重引用。
- **F36** gray-world 的已知失效模式：**場景被單一顏色主導時整個假設崩潰**（[ResearchGate — An example illustrating the failure of Grayworld color constancy](https://www.researchgate.net/figure/An-example-illustrating-the-failure-of-Grayworld-color-constancy-solution-Sample-image_fig2_262426470)；原理見 [Nick Pai — Gray-World Assumption in Computer Vision](https://medium.com/@weichenpai/gray-world-assumption-in-computer-vision-0a6612c1420a)）。**crop 級 gray-world 是這個失效模式的極端版**：單色物件的 crop 平均就是物件色，校正會把物件色直接抹向灰（紅杯→灰杯）。
- **F37** 鎢絲/暖光（~3000K）的畫面特徵是整體黃橙色偏（[The Refracted Light — Gray World & Retinex](http://therefractedlight.blogspot.com/2011/09/white-balance-part-2-gray-world.html)；通則亦見 [UnitX — White Balance Machine Vision Essentials](https://es.unitxlabs.com/resources/white-balance-machine-vision-system-essentials-2025/)）——Q1 的飄移方向依據。
- **F38** 即使「AWB 關 + 手動 WB + 手動曝光全鎖」，D435 仍有使用者回報批間色調漂移（ISP 其他環節），Intel 方建議再關 AE Priority 鎖幀率（[realsense-ros issue #1354](https://github.com/IntelRealSense/realsense-ros/issues/1354) 開題與 MartyG 回覆）。⟹ 鎖 AWB 能除掉最大變因但不是萬靈丹，演算法端（Lab 感知距離 + 平滑）仍要自己扛殘餘漂移。

### D. 反面路線：tiny color classifier（web）

- **F39** 車色辨識文獻：CNN 路線 94.92% vs **HSV 2D histogram + SVM 同樣 94.92%**（5 色、500 張室外車圖）（[arXiv 1510.07391 — Vehicle Color Recognition using CNN](https://arxiv.org/pdf/1510.07391)）；輕量 CNN 至多 95.41%、僅 +0.7%（[ScienceDirect S016516841830029X](https://www.sciencedirect.com/science/article/abs/pii/S016516841830029X)）。**在固定類別、可控 ROI 的設定下，CNN 對統計式方法沒有決定性優勢**。
- **F40** 不利條件下深度法確實領先（HSV clustering 71.87% vs deep classifiers，[arXiv 2408.11589 — Vehicle Color Recognition in Adverse Conditions](https://arxiv.org/html/2408.11589v2)），但代價是訓練資料集 + 模型維護；PawAI 的「不利條件」（黃光/暗）可用 AWB 管理 + Lab 距離 + 平滑壓掉大半，且 **CPU 已被 face/pose/gesture 吃滿、零新模型優先是硬約束**（goal :18）⟹ tiny classifier 出局（Q8）。

### E. 成本實測錨點（本研究，WSL x86，外推需 ×2-3）

- **F41** 微基準（本研究 2026-06-11 於 WSL x86 單核重跑，**完整腳本 + 原始輸出 + 環境版本見附錄 A**，可逐字重跑；**Jetson Orin Nano Cortex-A78AE 外推假設 ×2-3 慢**，未上機實測）。每 bbox「全管線」= resize 300×300→64×64（INTER_AREA）+ 該方案核心運算：
  - **方案 A 全管線**（resize + 32³ LUT 查表 + bincount）：**0.190 ms/bbox**；查表+bincount 本體僅 **0.026 ms**（resize 佔大宗）
  - **方案 B 全管線**（resize + BGR→Lab + `cv2.kmeans` k=3、4096 px float32、10 iter、1 attempt PP_CENTERS）：**0.346 ms/bbox**
  - 現役 HSV 對照（resize + cvt + 12 mask 中代表性 3 條）：全管線 **0.186 ms**、mask 本體 0.019 ms
  - LUT 建表（32³ × 20 槽，Lab 歐氏距離代理；runtime 與建表度量無關）：**17 ms 一次性啟動成本**
  ⟹ A 全管線與現役 HSV 同管線**幾乎同價**（0.190 vs 0.186 ms，差異被 resize 淹沒）；兩方案在 Jetson 都估 **≤1 ms/bbox**（保守上限 1.5ms），「毫秒級 CPU 成本」紅線（goal :18）全過。
  **勘誤**：本報告初稿引用的 0.45 / 0.31 / 0.012 ms 是**未存檔的一次性量測**（無腳本、無原始輸出可查），不符 goal :33「claims without citations are rejected」，已由附錄 A 的存檔重跑取代；量級結論（毫秒級紅線全過）不變。

---

## §3 Q1–Q9 逐題回答

### Q1：黃光（~3000K）下現役 12 色最先壞掉的是哪幾色？

**最先壞：白 → 橘/黃；其次：灰 → 棕/橘；再來：暗處彩色 → 黑/棕。**

推導（假設：AWB 關閉或欠校正，鎢絲光對白面的典型成像 RGB≈(255,205,140)，依 F37 黃橙色偏方向；數字為外推示意）：
- 白物 RGB(255,205,140) → S = 255×(1−140/255) ≈ **115 ≫ 40**（白 gate `S<40` 破，`object_perception_node.py:101`）；H = 60°×(205−140)/(255−140) ≈ 33.9° → OpenCV H≈17 → 落 **orange 帶 (8,22]**（`:116`）。較淡色偏落 H 19-25 → yellow。**白永遠出不來**。
- 中亮度灰（V 130-199）帶同樣色偏 → S>40 進 chromatic、H≈17-20：V≥130 → orange；**V<130 → brown**（`:106`）。
- 暗角彩色物：3000K 藍光能量僅日光的約 1/3（黑體輻射外推，假設標注），藍物反射訊號掉 2-3 倍 → V 跌破 50 → **black**（`:100`）；暖色物 V 落 50-129 → **brown**。
- 紅 (H≤8) 本身最抗黃光（暖光抬 R 通道、hue 幾乎不動），但**亮面高光區因 S 下降會踩進 pink 規則**（`:110`，F6）——demo 紅杯的 red↔pink 翻動主要是這條，不是色溫。

AWB 開啟（現役預設，F17）時上述被部分吸收，但 AWB 本身逐幀變（F33/F38）→ 邊界色（白/灰/米）在 gate 邊緣抖動，與 F15 的 jitter 紀錄一致。

### Q2：bbox vs 中央 50% vs seg mask 的污染率估算法？

可引用的估算法 = **物件 mask 面積 / bbox 面積（fill ratio）幾何推導 + 離線實測**：
- **整 bbox**：cup 是近圓柱 + 把手，緊 bbox 下杯身 fill ratio 幾何上 ~0.6-0.75（把手區基本全是背景；假設標注：理想正視圓柱投影近滿框，把手/透視扣 25-40%）→ **背景污染 25-40%**，桌沿入框時更高。0.25 門檻擋不住「桌面是最大單色塊」（F1, `object_perception_node.py:133-135`）。
- **中央 50%（線性）= 中央 25% 面積**：對居中凸物件，中央區幾乎全在物件上 → 污染估 **<5%**（幾何假設：YOLO bbox 中心偏差小於 bbox 1/4 邊長）。文獻側證：k-means 主色流程靠「剔除背景 cluster」達成同效（F30），而中央取樣是無聚類版的同一先驗。
- **seg mask**：污染只剩 mask 邊界誤差（~數 %），是根治版——但 proto 解析度 = 輸入的 1/4（160×160@640，scaleup result F12，`2026-06-11-yolo26-scaleup-highres-seg-result.md:39`），小杯子的 mask 邊界本身就糊，且 seg 已被裁出局（F20）。
- **實測法（上機日免費拿）**：對驗收 bag 的 cup 幀離線跑任一 seg 模型（WSL，一次性），量真實 fill ratio 分佈，回填本表的假設值。

### Q3：CIEDE2000 最近色名的每 bbox CPU 成本（64×64 前提）？

兩種實作形態，**裁定走 LUT**：
- **naive 逐幀**：4096 px × 20 槽（19 名 +1 保留位）= 81,920 次 ΔE00。CIEDE2000 每對含 atan2/sqrt/三角函數共數十 flops（[Wikipedia — Color difference](https://en.wikipedia.org/wiki/Color_difference)；skimage `deltaE_ciede2000` 為向量化實作，[scikit-image delta_e 文件](https://pydocs.github.io/p/skimage/0.17.2/api/skimage.color.delta_e.deltaE_ciede2000.html)）→ x86 估 2-5ms、Jetson 估 5-15ms/bbox（外推假設 ×2-3）。15Hz 多 bbox 下偏貴。
- **啟動時預建 32³ RGB→名 LUT**：32,768 bins × 20 槽 ≈ 65.5 萬次 ΔE00，向量化一次性 <1s（量級估算；附錄 A 用 Lab 歐氏距離代理建表實測 17ms，CIEDE2000 版多三角函數仍遠在 1s 內）；**runtime = `LUT[B>>3,G>>3,R>>3]` + `np.bincount` = 全管線（含 resize）實測 0.190 ms/bbox、查表本體 0.026 ms（WSL x86，F41/附錄 A）→ Jetson 估 ~0.4-0.6 ms**。5-bit 量化誤差 ≤4/255/通道，遠小於色名邊界 ΔE（>15）。
- 結論：**LUT 版把 CIEDE2000 的全部成本搬到啟動期，runtime 與現役 HSV 同管線幾乎同價（0.190 vs 0.186 ms，附錄 A）**，毫秒級紅線（goal :18）過。

### Q4：色名表選哪張？

**自訂生活色名表 19 名 +1 保留位（v0 見 §5），不選現成三張**：
- **CSS 140**：sRGB 命名是英文 web 慣用（[peteroupc colorgen](https://peteroupc.github.io/colorgen.html)），`papayawhip`/`gainsboro` 類名無 zh 對應，TTS 鏈（F13/F14）直接斷。
- **xkcd 949/954**：眾包俚語名（F26），同樣無 zh、且粒度過細到感知不可分（F25 的批評正中此類表）。
- **ISCC-NBS 267**：學術嚴謹（F27）但 267 名對「機器狗念一句話」過細；其「12 基本詞 + 修飾」的**構詞法值得抄**——v0 表就是「Berlin & Kay 11 基本詞（F28）+ 米/木/深淺修飾變體」的 zh-native 版。
- 決定性論據：輸出端是 `OBJECT_COLOR_ZH[color]` 進中文 TTS（`brain_node.py:101-102`），**表的每一名都必須有自然的中文念法**——只有自訂表能保證；arXiv 2604.03235（F25）亦支持「少量感知可分類別」優於大表。

### Q5：k-means k=3 in Lab 的成本與穩定性？需不需要時序平滑？

- **成本**：全管線實測 0.346 ms/bbox（resize + Lab 轉換 + 4096 px、10 iter、1 attempt，F41/附錄 A）→ Jetson 估 ~0.7-1.0 ms。成本不是 B 的問題。
- **穩定性**：`cv2.kmeans` 的 init 是隨機的（`KMEANS_PP_CENTERS`/`KMEANS_RANDOM_CENTERS`，F31）→ 同一畫面連續兩幀可收斂到不同分割；雙色物（白杯紅蓋）的 dominant cluster 在近平手時逐幀翻 → **色名翻動風險 > 方案 A**（A 是逐像素確定性查表 + 計數，零隨機）。且 dominant cluster 在污染 bbox 中照樣可能是桌面，文獻對策「剔除背景 cluster」（F30）又需要先驗——B 的抗污染優勢實質上不成立。
- **時序平滑：要，且 A/B 都要**。現役顏色是單幀快照（F19）、brain 已被 jitter 逼到改 dedup key（F15）。沿用 supervision/bbalg 哲學（連續 N 幀確認，F21；`supervision-pawai-fit-report.md:64`），但注意 `DetectionsSmoother` 不平滑 label（`:160`）——**自己做事件級多數決**：同 class 最近 3 次取樣的色名多數決（節點內部 ring buffer，不動 contract）。

### Q6：gray-world 疊在 D435 AWB 上是改善還是打架？

**打架，裁定不疊**：
- D435 ISP 的 AWB 已在做全域光源估計（F33/F38）；幀級 gray-world 再校一次 = 雙重校正，且兩者失效模式相同——**場景被大面積木質家具主導時 gray-world 假設崩潰**（F36），AWB 校完 gray-world 會再往錯的方向推一把。
- **crop 級 gray-world 是自殺**：單色物件 crop 的平均色 = 物件色本身，按 gray-world 校正等於把紅杯的紅當成「光源偏紅」抹掉 → 物件被校成灰（F36 失效模式的極端版）。goal :42 問的「crop 級成本與副作用」：成本可忽略（一次均值除法），**副作用 = 摧毀訊號，直接出局**。
- 正解：光照變因交給 **AWB 管理（Q7）+ Lab 感知距離 + 時序平滑** 三層，不引入第四個互相打架的校正器。

### Q7：D435 AWB 該鎖定嗎？鎖定值怎麼選？

**分情境裁定：demo 固定場次→鎖；機器狗漫遊→保持 AUTO。**
- 鎖的理由：AWB 逐幀變動是邊界色抖動源之一（Q1/F15）；單一房間單一光源下鎖定可重複性最好。
- 鎖的操作（官方依據）：設任何手動 WB 值即自動關 AWB（**MartyG**，F32）；ROS wrapper 用 `rgb_camera.enable_auto_white_balance:=false` + `rgb_camera.white_balance:=<值>`（doronhi 的 launch rosparam 模式，F34）。
- 鎖定值怎麼選：**AWB 開著時讀不到它的當前值**（F33），所以只能現場掃：從預設 4600 起（F35），對白紙掃 3000→5500（step 100-200），取「白紙在 node 端 S 最低」的值；黃燈房間落點預期 3000-3800（鎢絲色溫，F37；假設標注）。低於 4600 偏藍、高於 4600 變亮變濃（warm）的方向感依 F35 的 MartyG 逐字引文。
- 不全面鎖的理由：Go2 會跨房移動（守護/巡邏線），固定 WB 在換光源房間會系統性錯色；且鎖了也除不盡 ISP 殘餘漂移（F38）。**預設 AUTO + 演算法端魯棒、demo take 前一鍵鎖定**是工程上正確的折衷。

### Q8：tiny color classifier 出局依據？

三條，全部有引用：
1. **精度無決定性優勢**：固定類別下 CNN 94.92% ≡ HSV histogram+SVM 94.92%（F39，arXiv 1510.07391）；輕量 CNN 至多 +0.7%（ScienceDirect）。
2. **硬約束直接違反**：「CPU 已被 face/pose/gesture 吃滿……零新模型優先」（goal :18）；新模型還要居家物件顏色訓練集（不存在）+ 部署維護。
3. 深度法真正領先的是極端條件（F40），而 PawAI 的極端條件可用 Q6/Q7 的光照管理 + 平滑壓掉大半；殺雞用牛刀成立，**出局**。

### Q9：上機驗收 protocol 最終版

**物件組 × 光照 × 距離矩陣**（直接進 synthesis 上機清單）：

| 維度 | 取值 | 依據 |
|---|---|---|
| 物件（9）| 紅杯、藍杯、綠碗、白杯、黑杯、**米色碗**（6 必備）+ 黃杯、咖啡馬克杯、粉紅杯（3 邊界色選配）| goal :43 基組 + F5/F6 邊界弱點針對 |
| 光照（3）| 白天窗光（~5500-6500K）/ 室內黃燈（~3000K）/ 暗（關主燈）| goal :43；Q1 飄移矩陣 |
| 距離（2）| **0.7m / 1.5m** | demo S3 實測穩定點與目標點（`demo_script.md:28`；scaleup goal :8）|
| AWB（+1 對照）| 全程 AUTO 跑滿 54 格；黃燈格加跑 AWB lock（Q7 掃描值）對照 | F32-F35 |

**執行與量測**：
- 每格 `ros2 bag record /camera/camera/color/image_raw /event/object_detected` ≥60s（cooldown 5s → 每格 ≥10 事件樣本，`object_perception_node.py:441-452`）。**bag 是關鍵**：同一份資料離線同場算 HSV12 baseline 與候選方案，免重拍。
- 指標：① per-color accuracy = 正確色名事件/總事件，**門檻 ≥0.8/色**（goal :56 建議值採納；米色等新色名首輪 ≥0.6 即收，標 stretch）② Unknown 率 ③ 翻動率（同格內色名變化次數/事件數，驗 Q5 平滑）。
- **HSV12 當 baseline 同場量：要**——這是把「不準」從體感變數字的唯一辦法，也是 verdict 的 falsification：若 HSV12 在鎖 AWB 後 per-color accuracy 已全 ≥0.8，則根因其實在光照/資料，回退 `NO_GO_KEEP_HSV12` 路線。
- 產出：54+ 格矩陣 CSV + 每格代表幀截圖 + 兩法對照表。

---

## §4 四方案裁決表

| 方案 | 解什麼根因 | 每 bbox 成本（Jetson 估）| 風險 | 裁決 |
|---|---|---|---|---|
| **A** Lab+CIEDE2000 最近色名（LUT 版）| ③ 全解、② 半解 | ~0.4-0.6ms（F41 外推）| 色名表 v0 邊界要上機調 | **主軸** |
| **C** 中央 50% 取樣 | ① 大半解 | ~0（少算 75% 像素，反而更快）| 偏心 bbox（把手側）漏物件 | **配套，與 A 同刀** |
| **B** k-means k=3 in Lab | ①（名義上）| ~0.7-1.0ms（F41 外推）| init 隨機→翻動（F31）；dominant≠物件 | 出局——A+C 以更低複雜度覆蓋 |
| **D** seg mask 取色 | ① 根治 | mask 後處理另計 | **前置（seg 變體）已被 goal 1 裁出局（F20）** | 出局；標注耦合：若 seg 未來因他案上線，A 的查表直接套 mask 內像素即可升級 |
| 光照前處理 gray-world | ② | ~0 | crop 級毀滅訊號、幀級與 AWB 打架（F36/Q6）| 出局；改 Q7 AWB 管理 |
| tiny classifier | ②③ | 模型推理 + 訓練集 | 違反零模型紅線（Q8）| 出局 |

**配套三件組（與 A 同一刀上）**：中央 50% 取樣（C）+ 事件級色名 3 次多數決（Q5）+ demo take 前 AWB lock SOP（Q7）。

## §5 色名表 v0（19 名 +1 保留位，zh-native，sRGB 錨點啟動時轉 Lab）

> 設計依據：Berlin & Kay 11 基本詞（F28）+ 米/木/深淺修飾變體（goal :38 提案範圍 20-30 內取下緣）+ 全表有自然 zh 念法（Q4）。錨點 hex 為 v0 工作值（常見慣用色，**上機日按 §3-Q9 bag 數據調**）；可一名多錨（red 配亮/暗兩錨改善邊界）。

| key | zh | 錨點 v0 | key | zh | 錨點 v0 |
|---|---|---|---|---|---|
| red | 紅色 | #D32F2F / #B71C1C | maroon | 酒紅色 | #7B2D26 |
| orange | 橘色 | #F57C00 | brown | 咖啡色 | #6D4C41 |
| yellow | 黃色 | #FBC02D | tan | 木色 | #B08D57 |
| green | 綠色 | #43A047 | beige | 米色 | #D7C4A3 |
| dark_green | 深綠色 | #1B5E20 | pink | 粉紅色 | #F06292 |
| cyan | 青色 | #00ACC1 | purple | 紫色 | #7B1FA2 |
| light_blue | 淺藍色 | #64B5F6 | white | 白色 | #F2F2F2 |
| blue | 藍色 | #1976D2 | gray | 灰色 | #9E9E9E |
| navy | 深藍色 | #1A337E | dark_gray | 深灰色 | #4A4A4A |
| — | — | — | black | 黑色 | #1C1C1C |

（19 名 +1 保留位；既有 12 名全為子集 → S3「紅色杯子」與 brain `OBJECT_COLOR_ZH` gate 向後相容，F14/F16。）

---

## §6 與 cross-validate 文件的矛盾標注

1. **方案 D vs goal 1 裁決（無矛盾，但耦合封死）**：scaleup result 已把 seg 變體踢出上機矩陣（box mAP −1.3、GFLOPs +65%、輸出契約不明，`2026-06-11-yolo26-scaleup-highres-seg-result.md:15,29,99-100`）。本研究**跟隨**該裁決把 D 降為「未來 seg 若上線後的免費升級」，不選 `GO_SEG_MASK_COLOR`——若有人想用顏色需求翻盤 seg，必須先推翻 goal 1 的 verdict，不能繞過。
2. **`coco_classes.py:124-126` 註解已過時**：寫「mirrored in: frontend object-config.ts, interaction_executive brain_node.py」，但 6/10 Plan C3 後 brain 是從 `pawai_contracts.zh_tables` import（`brain_node.py:44-52`），不再自持副本。文件漂移，擴表時順手修註解（本研究不動 code）。
3. **`test_object_perception.py:336-348` 的 regex 機制會被方案 A 弄壞**：該測試靠 regex 從 `analyze_bbox_color` 函數體抽 `"([a-z]+)"` 字面量驗 zh 覆蓋。A 的色名移到模組級表後 regex 抓不到 → 測試需改為直接 import 色名表比對（**測試意圖保留、機制必改**——goal :71「沿用測試形態」指模組級免 rclpy 可測，這點 A 完全保留，F11）。
4. **contract v2.5 enum 凍結 vs 擴名**：`interaction_contract.md:677` 是封閉 12 值 enum。擴成 19 名 = contract bump（v2.5→v2.6）+ `pawai contract check` + `pawai_contracts/zh_tables.py:27` + `object-config.ts:205` + parity test 五點同步——這不是矛盾，是 verdict 附帶的下游工單，列出避免 6/4 `.env` 式「靜默漂移」重演。
5. **與 supervision 報告一致性確認**：色名平滑不能用 `DetectionsSmoother`（不平滑 label，`supervision-pawai-fit-report.md:160`）——本研究的多數決方案與該報告結論相容，無重複量測（goal 1 cross-validate 關切點）。

---

## §7 Verdict：**GO_LAB_NEAREST_NAME**

**裁決**：方案 A（Lab + CIEDE2000 最近色名、自訂 zh 色名表 19 名 +1 保留位（§5）、啟動期 32³ LUT）為主軸，配套 = 中央 50% 取樣（C）+ 事件級 3 次多數決平滑 + demo take 前 AWB lock SOP。色名表 v0 見 §5、上機驗收 protocol 見 §3-Q9（含 HSV12 baseline 同場對照與 falsification 條件）。

**對應 verdict 的下一步（一個，具體）**：
在 WSL 寫 standalone spike script（不碰 node code、不碰 Jetson）：`benchmarks/scripts/color_naming_spike.py` —— 讀 demo 既有錄影幀（或任意杯碗照片），同畫面並排輸出「現役 `analyze_bbox_color`（直接 import）vs Lab-LUT 最近色名（§5 v0 表）×（整 bbox / 中央 50%）」四組色名 + 純度，先在桌面驗 §5 錨點的邊界合理性；通過後把 §3-Q9 的 54 格 bag 矩陣排進下次上機日，per-color accuracy ≥0.8 過門檻才進 node 實作與 contract bump。

### Falsification（什麼證據會推翻本 verdict）

- 上機矩陣中 **HSV12 + AWB lock 已全色 ≥0.8** → 改判 `NO_GO_KEEP_HSV12`（根因在光照管理，不在演算法）。
- Lab-LUT 在黃燈格對白/米/灰仍 <0.6 且鎖 AWB 無解 → 回 `NEEDS_NEW_RESEARCH`（需評估幀級可控色彩恆常性演算法，如 learning-free retinex 系）。

---

## 附錄 A：微基準腳本與原始輸出（F41 的可重跑 artifact）

> 執行方式：WSL x86 單核，`python3 - <<'EOF' ... EOF` 直接餵 stdin（read-only 紀律：不落地檔案）。環境：OpenCV **4.13.0**、NumPy **2.2.6**。注意事項：① 輸入為隨機噪聲 bbox（對 bincount 是中性 case、對 kmeans 收斂偏保守）；② LUT 建表用 Lab 歐氏距離代理 CIEDE2000——**runtime 查表路徑與建表度量完全無關**，只影響一次性建表時間；③ Jetson ×2-3 外推未上機實測（F41 假設標注）。§7 next step 會把本腳本擴成 `benchmarks/scripts/color_naming_spike.py` 入 repo。

```python
# color_naming_microbench — 顏色命名微基準（audit 重跑版，2026-06-11）
import time
import numpy as np
import cv2

rng = np.random.default_rng(42)
N_NAMES = 20  # 19 名 + 1 保留位

# ---- 啟動期：32^3 RGB->色名 LUT（Lab 歐氏距離代理 CIEDE2000 建表；runtime 與建表度量無關）----
anchors_rgb = rng.integers(0, 256, size=(N_NAMES, 3), dtype=np.uint8)
anchors_lab = cv2.cvtColor(anchors_rgb.reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
t0 = time.perf_counter()
grid = np.stack(np.meshgrid(np.arange(32), np.arange(32), np.arange(32), indexing="ij"), axis=-1)
grid_rgb = (grid * 8 + 4).astype(np.uint8).reshape(1, -1, 3)
grid_lab = cv2.cvtColor(grid_rgb, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
d = ((grid_lab[:, None, :] - anchors_lab[None, :, :]) ** 2).sum(-1)
LUT = d.argmin(axis=1).astype(np.uint8).reshape(32, 32, 32)
t_build = (time.perf_counter() - t0) * 1000

bbox = rng.integers(0, 256, size=(300, 300, 3), dtype=np.uint8)  # 典型 cup bbox
crop64 = cv2.resize(bbox, (64, 64), interpolation=cv2.INTER_AREA)

def lut_core(crop):
    q = crop >> 3
    idx = LUT[q[..., 2], q[..., 1], q[..., 0]]
    counts = np.bincount(idx.ravel(), minlength=N_NAMES)
    peak = counts.argmax()
    return peak, counts[peak] / idx.size

def lut_full(bbox):
    return lut_core(cv2.resize(bbox, (64, 64), interpolation=cv2.INTER_AREA))

criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
def kmeans_full(bbox):
    crop = cv2.resize(bbox, (64, 64), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    _, labels, centers = cv2.kmeans(lab, 3, None, criteria, 1, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=3)
    return centers[counts.argmax()]

hsv64 = cv2.cvtColor(crop64, cv2.COLOR_BGR2HSV)
def hsv_core(hsv):  # 現役 12 mask 的代表性子集（black/white/red 3 條），量級對照用
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return int((v < 50).sum()), int(((s < 40) & (v >= 200)).sum()), int(((h <= 8) | (h > 165)).sum())

def hsv_full(bbox):
    crop = cv2.resize(bbox, (64, 64), interpolation=cv2.INTER_AREA)
    return hsv_core(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))

def bench(fn, arg, rep, warm=50):
    for _ in range(warm): fn(arg)
    t0 = time.perf_counter()
    for _ in range(rep): fn(arg)
    return (time.perf_counter() - t0) / rep * 1000

print(f"LUT build 32^3 x {N_NAMES}: {t_build:.0f} ms（一次性啟動成本）")
print(f"A core  (LUT+bincount @64x64)          : {bench(lut_core, crop64, 2000):.3f} ms")
print(f"A full  (resize 300->64 + LUT+bincount): {bench(lut_full, bbox, 2000):.3f} ms/bbox")
print(f"B full  (resize + BGR2LAB + kmeans k=3): {bench(kmeans_full, bbox, 500, warm=20):.3f} ms/bbox")
print(f"HSV core (3/12 masks @64x64)           : {bench(hsv_core, hsv64, 2000):.4f} ms")
print(f"HSV full (resize + cvt + 3/12 masks)   : {bench(hsv_full, bbox, 2000):.3f} ms/bbox")
print(f"env: cv2 {cv2.__version__}, numpy {np.__version__}")
```

原始輸出（2026-06-11 重跑）：

```
LUT build 32^3 x 20: 17 ms（一次性啟動成本）
A core  (LUT+bincount @64x64)          : 0.026 ms
A full  (resize 300->64 + LUT+bincount): 0.190 ms/bbox
B full  (resize + BGR2LAB + kmeans k=3): 0.346 ms/bbox
HSV core (3/12 masks @64x64)           : 0.0188 ms
HSV full (resize + cvt + 3/12 masks)   : 0.186 ms/bbox
env: cv2 4.13.0, numpy 2.2.6
```

---

## Sources

### 本地（file:line 已在文中逐條標注）
- `object_perception/object_perception/object_perception_node.py`（:60-137 色彩分析、:91 crop、:133-137 peak/門檻、:401 呼叫點、:441-452 cooldown、:448-450 event gate）
- `object_perception/object_perception/coco_classes.py:124-142`（COLOR_ZH + 過時鏡像註解）
- `object_perception/test/test_object_perception.py`（:318-348 zh 覆蓋 regex、:354-387 event gate；全檔無 pixel-level 色彩測試）
- `interaction_executive/interaction_executive/brain_node.py`（:44-52 zh import、:56-58 D-4 color-jitter、:83-105 build_object_tts）
- `pawai_contracts/pawai_contracts/zh_tables.py:27`、`pawai_contracts/test/test_zh_parity.py:1`、`pawai-studio/frontend/components/object/object-config.ts:204-206`
- `docs/contracts/interaction_contract.md:668-680`（v2.5 color schema）
- `docs/runbook/demo_script.md:28,52,157-184,324,348`（S3 紅色杯子）
- `scripts/start_full_demo_tmux.sh:143-147`（D435 啟動參數，無 WB 設定）
- `docs/perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md:15,29,39,99-100,129`（seg 出局裁決）
- `docs/perception/research/goals/2026-06-11-yolo26-scaleup-highres-seg-goal.md:8`（「demo S3 實測 0.7m 才穩」——0.7m 的唯一出處）
- `docs/pawai-demo/2026-06-10-demo-snapshot.md:38,93`（S3 cup 段 Recorded（near-range and controlled）+ Forbidden Claims 禁宣稱 arbitrary lighting）
- `docs/perception/research/2026-06-11-supervision-pawai-fit-report.md:17,64,154,160`（時序平滑哲學與限制）

### Web
- [OpenCV — Color conversions（Lab 8-bit scaling、D65、HSV H/2）](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html)
- [OpenCV — core cluster（cv2.kmeans 介面/flags/float32）](https://docs.opencv.org/4.x/d5/d38/group__core__cluster.html)
- [arXiv 2604.03235 — Toward a Universal Color Naming System（19,555 名 → CIELAB+CIEDE2000 → 280 聚類）](https://arxiv.org/abs/2604.03235)
- [xkcd — Color Survey Results（954 色名、RGB 非絕對色彩空間）](https://blog.xkcd.com/2010/05/03/color-survey-results/)
- [peteroupc — Color Topics for Programmers（nearest color、CIEDE2000、Berlin & Kay 11 詞）](https://peteroupc.github.io/colorgen.html)
- [Wikipedia — Color difference（ΔE76/ΔE00 公式複雜度）](https://en.wikipedia.org/wiki/Color_difference)
- [Datacolor/Techkon — CIE ΔE equations（CIEDE2000 工業標準）](https://techkon.datacolor.com/cie-de-color-difference-equations/)
- [W3Schools — ISCC-NBS（267 名）](https://www.w3schools.com/colors/colors_nbs.asp)、[MIT CSAIL — Color-Name Dictionaries](https://people.csail.mit.edu/jaffer/Color/Dictionaries)
- [IEEE 9869653 — Color Feature Based Dominant Color Extraction](https://ieeexplore.ieee.org/document/9869653/)、[Doug Fenstermacher — X-means + CIE2000](https://dougfenstermacher.com/project/xmeans-cie2000-dominant-color-extraction-visualization-tutorial)、[TDS — From RGB to Lab](https://towardsdatascience.com/from-rgb-to-lab-addressing-color-artifacts-in-ai-image-compositing/)
- [realsense-ros issue #1354 comments（MartyG：手動 WB 即關 AWB、WB 下限 2800；doronhi：launch rosparam）](https://github.com/IntelRealSense/realsense-ros/issues/1354)
- [librealsense issue #10143（AWB 開啟時 WB 值不可讀；MartyG 2022-02-11 留言逐字：default 4600 + 低偏藍/高變亮變濃）](https://github.com/IntelRealSense/librealsense/issues/10143#issuecomment-1036056796)
- [Intel RealSense Help Center — Blueish tone in rgb image d435](https://support.intelrealsense.com/hc/en-us/community/posts/360049132913-Blueish-tone-in-rgb-image-d435)、[Auto vs manual white balance](https://support.intelrealsense.com/hc/en-us/community/posts/7338435151507-Auto-white-balance-vs-manual-white-balance)（**未逐字驗證的輔證**，該站 fetch 被拒；承重引用為上行 #10143 逐字留言）
- [ResearchGate — failure of Grayworld color constancy](https://www.researchgate.net/figure/An-example-illustrating-the-failure-of-Grayworld-color-constancy-solution-Sample-image_fig2_262426470)、[Nick Pai — Gray-World Assumption](https://medium.com/@weichenpai/gray-world-assumption-in-computer-vision-0a6612c1420a)、[The Refracted Light — Gray World & Retinex](http://therefractedlight.blogspot.com/2011/09/white-balance-part-2-gray-world.html)
- [arXiv 1510.07391 — Vehicle Color Recognition using CNN（CNN ≡ HSV+SVM 94.92%）](https://arxiv.org/pdf/1510.07391)、[ScienceDirect S016516841830029X — lightweight CNN](https://www.sciencedirect.com/science/article/abs/pii/S016516841830029X)、[arXiv 2408.11589 — Adverse Conditions](https://arxiv.org/html/2408.11589v2)
- [scikit-image — deltaE_ciede2000（向量化實作）](https://pydocs.github.io/p/skimage/0.17.2/api/skimage.color.delta_e.deltaE_ciede2000.html)
