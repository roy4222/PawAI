# 文件修正記錄

## 2026/03/13 - Docs 結構級重構

### 背景

docs/ 累積大量幽靈文件（無對應程式碼）、重複內容散佈在多個入口、缺乏文件治理規則。
本輪重構目標：消除幽靈文件、建立責任邊界與衝突仲裁、讓所有入口指向單一真相來源。

設計規格：[`superpowers/specs/2026-03-13-docs-restructure-design.md`](./superpowers/specs/2026-03-13-docs-restructure-design.md)

### 1. 主幹入口重寫

| 文件 | 變更 |
|------|------|
| 根 `README.md` | 541→38 行，砍為純入口頁（一句話定位 + 4 連結 + quick start） |
| `docs/README.md` | 重寫為二級導航，移除「歷史與研究」區塊，新增文件治理規則專區 |
| `docs/archive/2026-05-docs-reorg/architecture-misc/README.md` | 200→33 行，砍為純導航，移除重複的三層架構圖，`face_perception.md` 標為 SUPERSEDED |
| `CLAUDE.md` | 304→208 行，完整規格表改引用連結，保留操作型內容（建構/除錯/已知陷阱） |

### 2. 文件治理規則確立

**責任邊界**：`mission` 定方向，`architecture` 定契約，`Pawai-studio` 定 Studio，`modules` 定模組，`setup` 定操作，程式碼庫定現況，`CLAUDE.md` 不定規格。

**衝突仲裁**（依問題類型）：
- 專案方向 → `mission/`
- ROS2 介面 → `architecture/`
- Studio 設計 → `Pawai-studio/`
- 模組內部 → 各模組 README
- 安裝部署 → `setup/`

### 3. 幽靈文件歸檔

| 來源 | 去向 | 說明 |
|------|------|------|
| `mission/vision.md` | `archive/mission/` | 已被 mission/README.md 取代 |
| `mission/roadmap.md` | `archive/mission/` | 已被 mission/README.md + handoff_316.md 取代 |
| `mission/agentic_embodied_ai_roadmap.md` | `archive/mission/` | 早期大規模技術路線 |
| `design/` | `archive/design/` | MCP prompt、Embodied AI 研究、開源致謝 |
| `refactor/` | `archive/refactor/` | 早期重構計畫 |
| `logs/` | `archive/logs/` | 2025/11 ~ 2026/02 開發日誌 |
| `testing/` | `archive/testing/` | SLAM Phase 1.5 測試報告 |

### 4. 標記與核對

- `mission/README.md` §10.1 加 NOTE 標記 `brain_v1.md`（幽靈引用）、已歸檔檔案
- `architecture/clean_architecture.md` banner 補充偏差清單（face_perception 不在 repo、gesture_module 未建立、speech_processor 未採用 CA）
- `architecture/data_flow.md` banner 補充結構性差異（/audio/ 不存在、topic 名稱錯誤、Executive 未落地）

### 5. 本輪不處理

- `modules/` — 規劃中，中期建立
- 中文模組資料夾（5 個）— 原地不動，中期收編 `modules/`
- `mission/meeting_notes_supplement.md` — 延後審查

### Commits

```
8078b3c docs: 砍薄根目錄 README 為純入口頁
f93f6a7 docs: 重寫 docs/README.md 為二級導航
01e4644 docs: 砍薄 architecture/README.md 為純導航頁
59b0889 docs: CLAUDE.md 瘦身為操作速查卡
261eaea docs: 標記 mission/README.md 文件地圖的失效連結
92de9f3 docs: 補充 architecture/ 現有文件 banner 偏差清單
9c0c140 docs: 幽靈文件審查與歸檔
d85f04a docs: 新增 CHANGELOG 條目記錄 2026-03-13 結構級重構
```

---

## 2025/11/19 - 會議決議與策略調整

### 決議摘要
- **時程**：第一階段發表改為 12/17（週三），文件繳交 12/12，12/10 完成內容、12/11 校對。
- **技術策略**：
  - VLM 以 **COCO 本地推論** 為主力（Plan A），Gemini Robotics API 降級為備案（Plan B），OpenAI/Claude 保留為最後手段。
  - 必須在遠端 GPU（Quadro RTX 8000）上部署 **Isaac Sim + go2_omniverse**，以解決實機過熱/噪音/空間限制，做為 Demo 保險。
  - **座標轉換 + 尋物 FSM** 列為 W7-W9 核心任務，與 Nav2 完成閉環；導入「模擬器→實機」驗證鏈。
- **展示策略**：強調「技術火力展示」，以模擬器影片 + 實機基本動作作為 Plan A/B；若 VLM 失敗，保留 COCO + 手動導航備援。
- **文件**：要求各文件明確註記依據 2025/11/19 會議決議，包含 User Story / DB Schema / 架構圖動畫化。

### 後續行動
1. 柏翊：11/26 前完成 Windows VM ↔ GPU ↔ Isaac Sim 串接與 SOP (`remote_gpu_setup.md`)。
2. 如薇、旭：12/03 前交付 COCO VLM Plan A（含 Detection2DArray、影像 topic remap 指南）。
3. 全組：12/05 前完成座標轉換基礎（LiDAR 投影 + tf2 → Nav2 目標），12/09 完成尋物 FSM 端到端。
4. 文件負責：12/10 前更新 `Goal.md`、`README.md`、`conformance_check_plan.md` 等，加入 User Story / DB 章節與會議標註；12/13 後產出具動畫效果的架構圖。

## 2025/11/16 - 文件一致性修正

### 修正項目總覽
基於專案現況與實際結構，修正 `/docs` 目錄下 7 份文件的不一致問題。

---

### 1. ✅ `integration_plan.md`

**修正內容**：
- **行 104**：將 `pip install -r src/requirements.txt` 改為 `pip install -r requirements.txt`
  - 原因：專案根目錄即為 requirements.txt 位置
- **行 159**：補齊 `coordinate_transformer` 套件依賴
  - 新增：`vision_msgs`, `message_filters`
  - 與 `package_structure.md` 和 `quickstart_w6_w9.md` 保持一致
- **行 188**：座標誤差驗收標準說明
  - 從「水平誤差 < 20cm（初步目標）」
  - 改為「水平誤差 < 20cm（W7-W8 驗收門檻，最終目標 < 15cm）」

---

### 2. ✅ `quickstart_w6_w9.md`

**修正內容**：
- **行 7-19（新增）**：專案結構說明
  ```
  ~/workspace/
  └── fju-go2-sdk/              # 本專案（Git 倉庫根目錄）
      ├── src/                  # ROS2 套件目錄
      ├── requirements.txt      # Python 依賴（專案根目錄）
      └── ...
  ```
- **行 93**：統一 pip 安裝路徑
  - 從 `pip install -r src/requirements.txt`
  - 改為 `pip install -r requirements.txt  # 專案根目錄的 requirements.txt`

---

### 3. ✅ `package_structure.md`

**修正內容**：
- **行 258**：註解說明更正
  - 從 `# src/requirements.txt（新增以下內容）`
  - 改為 `# requirements.txt（專案根目錄，新增以下內容）`
- **行 277**：pip 安裝路徑統一
  - 從 `pip install -r src/requirements.txt`
  - 改為 `pip install -r requirements.txt`
- **行 350（新增）**：補充缺少的 import
  ```python
  from launch.conditions import IfCondition  # ← 新增此行（修正缺少的 import）
  ```
  - 原因：範例程式碼使用 `IfCondition` 但未 import，照抄會出錯

---

### 4. ✅ `testing_plan.md`

**修正內容**：
- **行 42**：測試檔案命名統一
  - 從 `vision_vlm/test/test_gemini_api.py`
  - 改為 `vision_vlm/test/test_api_client.py`（與 `gemini_vlm_development.md` 一致）
- **行 104**：測試執行指令對應修正
  - 從 `pytest test/test_gemini_api.py -v`
  - 改為 `pytest test/test_api_client.py -v`
- **行 279**：座標誤差標準說明
  - 從「座標誤差 < 20cm（與模擬器真實位置比較）」
  - 改為「座標誤差 < 20cm（W7-W8 驗收門檻，與模擬器真實位置比較，最終目標 < 15cm）」

---

### 5. ✅ `gemini_vlm_development.md`

**修正內容**：
- **行 100（修正）**：`ros2 pkg create` 依賴清單
  - 新增 `std_msgs` 依賴（與其他文件保持一致）
- **行 102-109（新增）**：Python 依賴安裝說明
  ```bash
  # 安裝額外 Python 依賴（建議加到專案根目錄 requirements.txt）
  # 在專案根目錄的 requirements.txt 中新增：
  # google-generativeai>=0.3.0
  # pillow>=10.0.0
  # numpy
  cd ~/workspace/fju-go2-sdk
  pip install -r requirements.txt  # 或直接安裝
  ```
  - 提醒將依賴加到專案共用 requirements.txt，避免與其他文件的安裝方式衝突

---

### 6. ✅ `coordinate_transformation.md`

**修正內容**：
- **行 8-10（新增）**：重要提醒
  ```
  **重要提醒：**
  - 本文件中使用 `camera_link` 代表相機座標系 frame，實際實作時請對應真實 URDF 中的 frame 名稱（可能是 `front_camera_link` 或其他）
  - 使用前請先執行 `ros2 run tf2_tools view_frames` 確認實際 frame 名稱
  ```
- **行 237（修正）**：`project_3d_to_2d` 函數 type hint
  - 回傳類型從 `Tuple[np.ndarray, np.ndarray]`
  - 改為 `Tuple[np.ndarray, np.ndarray, np.ndarray]`
  - 文檔字串新增第三個回傳值：`valid_mask: N boolean array (有效點的遮罩，Z > 0)`
  - 原因：實際範例程式碼有回傳 valid_mask，但簽名未說明

---

### 7. ✅ `conformance_check_plan.md`

**修正內容**：
- **行 93**：GPU 伺服器規格更新
  - 從「RTX 4080 + 32GB RAM + 100GB SSD」（確認中）
  - 改為 ✅ **Quadro RTX 8000 48GB（遠端 SSH）**（已確認）
- **行 96**：Isaac Sim 狀態更新
  - 新增說明：「待部署至遠端伺服器（詳見 docs/01-guides/remote_gpu_setup.md）」
- **行 94**：Gemini API 備案說明
  - 新增備註：「（備案：本地 LLaVA）」
  - 原因：48GB VRAM 足以運行本地 VLM

---

## 修正類別統計

| 類別 | 文件數 | 範例 |
|------|--------|------|
| **路徑一致性** | 4 | requirements.txt 路徑統一 |
| **依賴完整性** | 3 | 補齊 vision_msgs, message_filters, std_msgs |
| **程式碼正確性** | 2 | 補充 import, 修正 type hint |
| **說明完整性** | 3 | 新增 workspace 結構、frame 提醒、誤差標準說明 |
| **現況更新** | 2 | GPU 規格、Isaac Sim 部署位置 |

---

## 驗證檢查清單

### ✅ 已驗證項目
- [x] 所有 `pip install` 指令指向同一 requirements.txt
- [x] `ros2 pkg create` 依賴清單完整
- [x] 範例程式碼可直接執行（無缺少 import）
- [x] 測試檔案命名一致
- [x] 座標誤差標準（W7-W8 vs 最終）說明清楚
- [x] GPU 規格反映實際現況（Quadro RTX 8000 48GB）
- [x] Workspace 結構明確說明

### 📋 建議後續行動
1. **更新專案根目錄 requirements.txt**：
   ```bash
   # 新增以下依賴（若尚未添加）
   google-generativeai>=0.3.0
   pillow>=10.0.0
   scipy>=1.10.0
   ```

2. **驗證實際 frame 名稱**：
   ```bash
   # 在實機或模擬器運行時
   ros2 run tf2_tools view_frames
   evince frames.pdf
   # 確認相機 frame 實際名稱（camera_link / front_camera_link / 其他）
   ```

3. **建立測試檔案**：
   ```bash
   # 確保測試檔案與文件一致
   touch src/vision_vlm/test/test_api_client.py
   touch src/vision_vlm/test/test_detection_converter.py
   touch src/coordinate_transformer/test/test_projection.py
   ```

---

## 文件版本對應

| 文件 | 修正前版本 | 修正後版本 | 主要變更 |
|------|-----------|-----------|---------|
| integration_plan.md | v1.0 | v1.1 | 路徑統一、依賴補齊、誤差標準 |
| quickstart_w6_w9.md | v1.0 | v1.1 | Workspace 結構說明 |
| package_structure.md | v1.0 | v1.1 | Import 補充、路徑統一 |
| testing_plan.md | v1.0 | v1.1 | 檔名統一、誤差標準 |
| gemini_vlm_development.md | v1.0 | v1.1 | 依賴說明、安裝流程 |
| coordinate_transformation.md | v1.0 | v1.1 | Type hint 修正、Frame 提醒 |
| conformance_check_plan.md | v1.0 | v1.1 | GPU 規格更新 |

---

## 審核者

- **提出者**：專案審核
- **修正者**：Claude (AI Assistant)
- **日期**：2025/11/16
- **狀態**：✅ 全部完成

---

**備註**：本次修正確保所有文件與專案實際結構（workspace 佈局、requirements.txt 位置、GPU 規格）完全一致，可直接照抄使用。
