# Go2 智慧尋物系統文件索引

**專案名稱：** 基於 Go2 機器狗的智慧陪伴與尋物系統  
**文件版本：** v2.0  
**最後更新：** 2025/11/20（依 2025/11/19 會議重構）  
🎯 **第一階段發表：2025/12/17**

> 本頁是 docs/ 的地圖。所有文件依照功能分類到 `01-`〜`04-` 子資料夾，方便在 VS Code 或網頁檢視時快速定位。

---

## 🗂️ 目錄地圖

| 資料夾 | 用途 | 代表文件 |
|--------|------|----------|
| `00-overview/` | 高層計畫與現況報告 | `Goal.md`, `claude_plan.md`, `conformance_check_plan.md` |
| `01-guides/` | 環境建置、開發者日常操作指引 | `environment_setup_ubuntu.md`, `remote_gpu_setup.md`, `webrtc_troubleshooting.md` |
| `02-design/` | 系統設計、技術決策、模組開發指南 | `integration_plan.md`, `coco_vlm_development.md`, `package_structure.md` |
| `03-testing/` | 測試計畫與驗證腳本 | `testing_plan.md`, `testing_and_verification.md` |
| `04-notes/` | 歷史紀錄與開發手札 | `CHANGELOG.md`, `dev_notes/` |

### 00-overview · 專案概覽
- [Goal.md](./00-overview/Goal.md) — 系統願景、分期目標  
- [claude_plan.md](./00-overview/claude_plan.md) — 現況 vs 目標差異分析（55%，已依 2025/11/19 決議復核）  
- [conformance_check_plan.md](./00-overview/conformance_check_plan.md) — 模擬器/現況符合度評估與行動計畫

> ⚠️ 操作指南與 Quickstart 請改參閱 `01-guides/`（例如 `quickstart_w6_w9.md`、`remote_gpu_setup.md`、`QUICKSTART_GPU.md`、`QUICKSTART_NAVIGATION.md`）

### 01-guides · 操作手冊
- **基礎環境**
  - [dependency_management.md](./01-guides/dependency_management.md) — Python 依賴鎖定策略、`uv` 使用方式  
  - [environment_setup_ubuntu.md](./01-guides/environment_setup_ubuntu.md) — Ubuntu + ROS2 + Go2 SDK 安裝步驟（2025/11/19）  
  - [mac_utm_vm_setup.md](./01-guides/mac_utm_vm_setup.md) — Mac M1 + UTM 虛擬機部署、橋接 Go2 Wi-Fi（2025/11/21）  
  - [remote_gpu_setup.md](./01-guides/remote_gpu_setup.md) — Mac → Windows VM → Quadro RTX 8000 遠端 GPU 拓樸  
  - [webrtc_troubleshooting.md](./01-guides/webrtc_troubleshooting.md) — WebRTC 常見錯誤與對應處置  
  - [quickstart_w6_w9.md](./01-guides/quickstart_w6_w9.md) — W6-W9 每日任務 Checklist（2025/11/19）  
- **SLAM / Nav2**
  - [slam_nav/README.md](./01-guides/slam_nav/README.md) — Phase 1/2 測試總覽、交付物與故障排查導覽（2025/11/21）  
  - [slam_nav/phase1_execution_guide.md](./01-guides/slam_nav/phase1_execution_guide.md) — Phase 1（1–2 坪）建圖 + 單點導航（2025/11/19）  
  - [slam_nav/phase2_execution_guide.md](./01-guides/slam_nav/phase2_execution_guide.md) — Phase 2（4–5 坪）多點導航 + 巡邏（2025/11/19）  
  - [slam_nav/quick_reference.md](./01-guides/slam_nav/quick_reference.md) — 複製貼上指令、5 大陷阱、常用命令（2025/11/19）  
  - [phase1_quick_check.md](./01-guides/phase1_quick_check.md) — Phase 1 七項快速復核清單（3–5 分鐘）（2025/11/21）  
- **模擬器 / 測試**
  - [simulator_setup_checklist.md](./01-guides/simulator_setup_checklist.md) — Isaac Sim / go2_omniverse 部署進度與 topic 對應（2025/11/21）  
  - [testing_and_verification.md](./03-testing/testing_and_verification.md) — TEST.sh 自動化腳本、覆蓋率與驗證 Checklist（測試區共用，2025/11/19）

#### SLAM/Nav2 測試套件（`docs/01-guides/slam_nav/`）
- [README](./01-guides/slam_nav/README.md) — Phase 1/2 測試總覽、核心知識點、交付物與故障排查導覽。
- [Phase 1 指南](./01-guides/slam_nav/phase1_execution_guide.md) — 1-2 坪環境的建圖、Nav2 單點導航、地圖存檔。
- [Phase 2 指南](./01-guides/slam_nav/phase2_execution_guide.md) — 4-5 坪環境、多點導航、避障、巡邏測試與評分標準。
- [速查表](./01-guides/slam_nav/quick_reference.md) — 複製貼上指令、5 大陷阱與常用命令。
- [測試日誌](./04-notes/dev_notes/20251121_slam_test.md) — 每次實驗的觀測數據與結果紀錄。

### 02-design · 架構與模組
- [integration_plan.md](./02-design/integration_plan.md) — W6-W9 技術整合藍圖（Plan A：COCO）  
- [coco_vlm_development.md](./02-design/coco_vlm_development.md) — COCO VLM 主力方案指南  
- [gemini_vlm_backup.md](./02-design/gemini_vlm_backup.md) — Gemini VLM 備案（Plan B，僅在 COCO 失敗時使用）  
- [coordinate_transformation.md](./02-design/coordinate_transformation.md) — LiDAR 投影 / 地面假設兩種轉換策略  
- [search_fsm_design.md](./02-design/search_fsm_design.md) — 尋物狀態機與 Nav2 整合計畫  
- [isaac_sim_integration.md](./02-design/isaac_sim_integration.md) — Isaac Sim / go2_omniverse 流程  
- [package_structure.md](./02-design/package_structure.md) — `vision_vlm`, `coordinate_transformer`, `search_logic` 目錄規範

### 03-testing · 測試與驗收
- [testing_plan.md](./03-testing/testing_plan.md) — W9 端到端測試行程（2025/11/19）  
- [testing_and_verification.md](./03-testing/testing_and_verification.md) — 自動化腳本、覆蓋率與驗證 Checklist（2025/11/19）

### 04-notes · 歷程與手札
- [CHANGELOG.md](./04-notes/CHANGELOG.md) — 文件與程式異動歷史  
- [dev_notes/](./04-notes/dev_notes) — 每日開發紀錄、週報與測試檔案（含 `2025-11-18/19-dev.md`）  
- [WEEK1_SUMMARY.md](./04-notes/dev_notes/WEEK1_SUMMARY.md) — Week 1 完成事項、後續待辦與交付清單（2025/11/21）  
- [WEEK1_QUICKSTART.md](./04-notes/dev_notes/WEEK1_QUICKSTART.md) — Linux Phase 1 / UTM 安裝 / 模擬器清點複製貼上速查卡（2025/11/21）  
- [20251121_slam_test.md](./04-notes/dev_notes/20251121_slam_test.md) — Phase 1/2 測試日誌範本（頻率、TF、地圖等記錄）（2025/11/21）

---

## 🚀 快速開始（新成員必看）

1. **了解專案現況**  
   ```bash
   1. ./00-overview/Goal.md         # 專案目標與時程
   2. ./00-overview/claude_plan.md  # 現況報告（55% 完成度）
   3. ./02-design/integration_plan.md   # W6-W9 技術整合規劃
   ```

2. **鎖定依賴版本（🚨 很重要）**  
   ```bash
   uv pip install -r requirements.txt --force-reinstall
   python3 -c "import aiortc; print(f'aiortc: {aiortc.__version__}')"
   ```
   依賴策略詳見 [dependency_management.md](./01-guides/dependency_management.md)；若出現 WebRTC 問題，請參考 [webrtc_troubleshooting.md](./01-guides/webrtc_troubleshooting.md)。

3. **設定連線與遠端 GPU（每天開工的「刷卡」動作）**  
   - **先跑 `connect_dog`**：這會刷新 `enp0s2` 的靜態 IP/路由並關閉 ufw。手動 `sudo ip addr add...` 的網卡設定是暫時性的，VM 每次重開都會遺失，所以每天登入 Ubuntu 後要先執行一次。  
   - 實機連線：`bash start_go2_simple.sh` → `ros2 topic list` 應收到低頻狀態  
   - 遠端 GPU：依 [remote_gpu_setup.md](./01-guides/remote_gpu_setup.md) 建置 Mac → Windows VM → RTX 8000 拓樸  
   - Nav2 驗證：`ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true`

4. **選擇開發任務**
   - **VLM (Plan A)**：讀 [coco_vlm_development.md](./02-design/coco_vlm_development.md)，部署 `vision_vlm` 套件  
   - **座標轉換**：讀 [coordinate_transformation.md](./02-design/coordinate_transformation.md)，實作 LiDAR 投影  
   - **尋物 FSM**：讀 [search_fsm_design.md](./02-design/search_fsm_design.md)，完成 Nav2 Action 流程  
   - **模擬整合**：讀 [isaac_sim_integration.md](./02-design/isaac_sim_integration.md)，建置 go2_omniverse

5. **依循每日進度**  
   - [quickstart_w6_w9.md](./01-guides/quickstart_w6_w9.md) — 每日 Checklist  
   - [package_structure.md](./02-design/package_structure.md) — 套件規範  
   - [testing_plan.md](./03-testing/testing_plan.md) — 驗收條件

---

## 🎯 任務對照表（Goal.md ↔ 文件）

| [Goal.md](./00-overview/Goal.md) 目標 | 文件 | 週次 |
|-------------|------|------|
| **W6：VLM 整合（COCO 主力）** | [coco_vlm_development.md](./02-design/coco_vlm_development.md) | W6 |
| **W7：座標系統轉換 I** | [coordinate_transformation.md](./02-design/coordinate_transformation.md) | W7 |
| **W8：座標系統轉換 II / Isaac Sim** | [coordinate_transformation.md](./02-design/coordinate_transformation.md) · [isaac_sim_integration.md](./02-design/isaac_sim_integration.md) | W8 |
| **W9：尋物 FSM 與系統測試** | [search_fsm_design.md](./02-design/search_fsm_design.md) · [testing_plan.md](./03-testing/testing_plan.md) | W9 |
| **整體套件規劃** | [integration_plan.md](./02-design/integration_plan.md) · [package_structure.md](./02-design/package_structure.md) | 全期 |

---

## 🧭 關鍵決策（摘要）

| 項目 | 方案 | 備註 |
|------|------|------|
| 模擬器 | Isaac Sim 2023.1.1 + Orbit 0.3.0 | 參見 [isaac_sim_integration.md](./02-design/isaac_sim_integration.md) |
| VLM | **Plan A：COCO + 本地 GPU** / Plan B：Gemini Robotics API | 詳見 [coco_vlm_development.md](./02-design/coco_vlm_development.md) & [gemini_vlm_backup.md](./02-design/gemini_vlm_backup.md) |
| 座標轉換 | Plan A：LiDAR 投影 / Plan B：地面假設 / Plan C：手動標註 | [coordinate_transformation.md](./02-design/coordinate_transformation.md) |
| 遠端環境 | Mac → Windows VM (Ubuntu) → RTX 8000 GPU | [remote_gpu_setup.md](./01-guides/remote_gpu_setup.md) |

---

## 📅 關鍵時程 & 驗收

| 日期 | 項目 | 文件/依據 |
|------|------|-----------|
| 12/10 (二) | 文件完稿 | 參考 `docs/` 索引，對照 [CHANGELOG](./04-notes/CHANGELOG.md) |
| 12/12 (四) | 文件繳交 | 以 [integration_plan.md](./02-design/integration_plan.md) 驗證內容齊全 |
| 12/17 (三) | 第一階段發表 | Demo 內容：COCO VLM + Nav2 + Isaac Sim |
| W9 週末 | 端到端測試 | [testing_plan.md](./03-testing/testing_plan.md) |

---

## ✅ 下一步建議
1. 若要尋找特定文件，先檢視上方 **目錄地圖** 或使用 VS Code 的目錄排序 (`01-`, `02-` …)。  
2. 在每份 Markdown 中使用 `[[toc]]`（需安裝 *Markdown All in One* 擴充）自動產生章節導覽。  
3. 圖片與流程圖建議存放於 `docs/assets/`（如需新增，請建立資料夾並附註來源）。  
4. 重大技術決策請新增到 `docs/04-notes/CHANGELOG.md` 或建立 ADR（範本位於 `docs/04-notes/dev_notes/`）。

> 📌 **Docs as Code**：所有文件與程式一樣，使用 PR / Review 流程維護，並盡量保持與實作同步。
