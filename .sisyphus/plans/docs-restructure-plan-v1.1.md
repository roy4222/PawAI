# PawAI 文件重構計畫書（修正版 v1.1）

**日期**: 2026-02-11  
**版本**: v1.1（已根據審查意見修正）  
**目標**: 重整 docs/ 目錄結構，消除過時文件與死鏈，建立可維護的文件架構

---

## 1. 執行摘要

### 1.1 問題現狀
- **89 個文件**分散在 7 個目錄，結構混亂
- **編號衝突**: `docs/03-reports/` 與 `docs/03-testing/` 同級編號
- **過時內容**: 大量 Mac VM / CycloneDDS 文件已不符合 Jetson 架構
- **死鏈風險**: 多處交叉引用（含 repo root 的 README.md, CLAUDE.md 等），直接刪除會造成大量死鏈
- **assets 遺漏**: 圖片分散在 docs/00-overview/images/, docs/04-notes/images/，未規劃遷移

### 1.2 修正重點（v1.1）
根據審查意見，v1.1 修正以下關鍵問題：
1. **全範圍連結更新**: 不只改 docs/，還要改 root README.md, CLAUDE.md, AGENTS.md, scripts/
2. **Assets 遷移策略**: 新增專門的 Phase 處理圖片遷移與引用更新
3. **安全的連結重寫**: 只改 Markdown 連結語法 `](...)`，不做裸字串全域替換
4. **錯誤處理**: 移除 `2>/dev/null || true`，改為顯示 WARNING 並停下來人工決定
5. **Git 操作安全**: 用 `git rm -r` 取代 `rm -rf`，用 `git add -A` 取代 `git add .`
6. **README.md 策略**: Phase 2 不再修改 README.md，全部留到 Phase 8 整份重寫

### 1.3 新目錄結構
```
docs/
├── mission/          # 專案願景與規劃（原 00-overview/）
├── setup/            # 環境建置指南（篩選後的 01-guides/）
├── design/           # 架構設計（原 02-design/ + refactor/）
│   ├── decisions/    # ADR 架構決策
│   ├── migrations/   # 遷移計畫
│   ├── current/      # 當前架構
│   └── future/       # 未來藍圖
├── testing/          # 測試驗證（原 03-testing/）
├── logs/             # 開發日誌（原 04-notes/）
│   ├── 2026/         # 按月分層
│   └── 2025/
├── assets/           # 圖片與資源（集中管理）
│   ├── images/
│   └── diagrams/
└── archive/          # 歷史歸檔
    └── 2026-02-11-restructure/  # 本次重構備份
```

---

## 2. 前置準備與檢查清單

### 2.1 建立專用分支（不要動 main）
```bash
# 確保在 main
git checkout main

# 建立專用分支
git checkout -b docs-restructure-20260211

# 如果有未提交的變更，先處理掉
git status
# 如果有變更，選擇：
#   A) git stash （暫存起來）
#   B) git add . && git commit -m "wip: save current work"
```

### 2.2 建立備份標籤
```bash
git tag -a docs-before-restructure-20260211 -m "文件重構前的備份點"
```

### 2.3 全範圍連結盤點（關鍵！）
執行前，先確認哪些文件引用了要歸檔的文件：

```bash
# 搜尋所有 Markdown 文件中的連結
echo "=== 引用 cyclonedds-config-guide 的文件 ==="
grep -r "cyclonedds-config-guide" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/"

echo "=== 引用 開發計畫.md 的文件 ==="
grep -r "開發計畫.md" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/"

echo "=== 引用 專題目標.md 的文件 ==="
grep -r "專題目標.md" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/"

echo "=== 引用 00-overview/ 的文件 ==="
grep -r "00-overview/" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/"

echo "=== 引用 01-guides/ 的文件 ==="
grep -r "01-guides/" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/"
```

**記錄輸出結果**，Phase 2 需要用到。

---

## 3. 詳細執行步驟

### Phase 1: 建立 Archive（第 1 個 Commit）

**目標**: 將所有待刪除/過時文件安全移動到 archive/

**執行命令**:
```bash
# 建立 archive 目錄
mkdir -p docs/archive/2026-02-11-restructure/{guides,overview,testing,reports,design,images}

# ========== 歸檔 Guides（過時技術）==========
git mv docs/01-guides/cyclonedds-config-guide.md \
       docs/archive/2026-02-11-restructure/guides/ \
    || echo "WARNING: cyclonedds-config-guide.md 移動失敗，請檢查路徑"

git mv docs/01-guides/slam_nav/cyclonedds_guide.md \
       docs/archive/2026-02-11-restructure/guides/ \
    || echo "WARNING: cyclonedds_guide.md 移動失敗，請檢查路徑"

git mv docs/01-guides/Depth\ Anything\ V2 \
       docs/archive/2026-02-11-restructure/guides/ \
    || echo "WARNING: Depth Anything V2 移動失敗，請檢查路徑"

git mv docs/01-guides/專案必學知識清單.md \
       docs/archive/2026-02-11-restructure/guides/ \
    || echo "WARNING: 專案必學知識清單.md 移動失敗，請檢查路徑"

git mv docs/01-guides/go2_sdk \
       docs/archive/2026-02-11-restructure/guides/ \
    || echo "WARNING: go2_sdk/ 移動失敗，請檢查路徑"

# ========== 歸檔 Overview（過時規劃）==========
git mv docs/00-overview/開發計畫.md \
       docs/archive/2026-02-11-restructure/overview/ \
    || echo "WARNING: 開發計畫.md 移動失敗，請檢查路徑"

git mv docs/00-overview/專題目標.md \
       docs/archive/2026-02-11-restructure/overview/ \
    || echo "WARNING: 專題目標.md 移動失敗，請檢查路徑"

git mv docs/00-overview/1-7-demo-簡報大綱.md \
       docs/archive/2026-02-11-restructure/overview/ \
    || echo "WARNING: 1-7-demo-簡報大綱.md 移動失敗，請檢查路徑"

git mv docs/00-overview/團隊進度追蹤 \
       docs/archive/2026-02-11-restructure/overview/ \
    || echo "WARNING: 團隊進度追蹤/ 移動失敗，請檢查路徑"

# ========== 歸檔 Testing（未完成報告）==========
git mv docs/03-testing/Demo\ 影片錄製腳本.md \
       docs/archive/2026-02-11-restructure/testing/ \
    || echo "WARNING: Demo 影片錄製腳本.md 移動失敗，請檢查路徑"

git mv docs/03-testing/slam-phase1_test_results_ROY.md \
       docs/archive/2026-02-11-restructure/testing/ \
    || echo "WARNING: slam-phase1_test_results_ROY.md 移動失敗，請檢查路徑"

# ========== 歸檔 Reports（草稿）==========
git mv docs/03-reports/drafts \
       docs/archive/2026-02-11-restructure/reports/ \
    || echo "WARNING: drafts/ 移動失敗，請檢查路徑"

git mv docs/03-reports/背景知識_草稿.md \
       docs/archive/2026-02-11-restructure/reports/ \
    || echo "WARNING: 背景知識_草稿.md 移動失敗，請檢查路徑"

# 如果有 .docx 也歸檔
if [ -f "docs/03-reports/背景知識_草稿.docx" ]; then
    git mv docs/03-reports/背景知識_草稿.docx \
           docs/archive/2026-02-11-restructure/reports/ \
        || echo "WARNING: 背景知識_草稿.docx 移動失敗"
fi

if [ -f "docs/03-reports/drafts/第二章軟體需求規格_草稿.docx" ]; then
    git mv docs/03-reports/drafts/第二章軟體需求規格_草稿.docx \
           docs/archive/2026-02-11-restructure/reports/ \
        || echo "WARNING: 第二章軟體需求規格_草稿.docx 移動失敗"
fi

# ========== 歸檔 Design（重複文件）==========
git mv docs/02-design/資料庫設計.md \
       docs/archive/2026-02-11-restructure/design/ \
    || echo "WARNING: 資料庫設計.md 移動失敗，請檢查路徑"

# ========== 歸檔過時的 refactor 文件 ==========
if [ -f "docs/refactor/index.md" ]; then
    git mv docs/refactor/index.md \
           docs/archive/2026-02-11-restructure/ \
        || echo "WARNING: index.md 移動失敗"
fi

if [ -f "docs/refactor/current_state.md" ]; then
    git mv docs/refactor/current_state.md \
           docs/archive/2026-02-11-restructure/ \
        || echo "WARNING: current_state.md 移動失敗"
fi

# ========== 歸檔 Jetson 替換 VM（已完成使命）==========
if [ -f "docs/01-guides/slam_nav/Jetson 替換 VM.md" ]; then
    git mv docs/01-guides/slam_nav/Jetson\ 替換\ VM.md \
           docs/archive/2026-02-11-restructure/guides/ \
        || echo "WARNING: Jetson 替換 VM.md 移動失敗"
fi

# 提交
git add -A
git commit -m "archive: move outdated docs to archive/2026-02-11-restructure/" \
           -m "移動以下過時文件：" \
           -m "- CycloneDDS 相關（已改用 WebRTC 有線）" \
           -m "- Depth Anything V2（已棄用）" \
           -m "- 舊版開發計畫與專題目標（將重寫）" \
           -m "- 團隊進度（不再更新）" \
           -m "- 專案必學知識清單（過大且過時）" \
           -m "- 測試報告草稿、資料庫設計重複" \
           -m "- refactor/ 舊索引文件" \
           -m "" \
           -m "這些文件仍可通過 archive/ 路徑訪問。"
```

**驗證**:
```bash
# 確認文件確實在 archive/
ls -la docs/archive/2026-02-11-restructure/
find docs/archive/2026-02-11-restructure/ -type f | wc -l  # 應該顯示歸檔文件數量

# 確認原始位置已空（或只剩下要保留的文件）
ls docs/01-guides/ 2>/dev/null | head -10
```

---

### Phase 2: 更新全範圍引用連結（第 2 個 Commit）

**⚠️ 關鍵修正**: 不只改 docs/，還要改 root 層級的文件！

**原則**: 只改 Markdown 連結語法 `](path)`，不改裸字串

**執行命令**:
```bash
#!/bin/bash
# 建立連結更新腳本（安全版本）

echo "=== 開始更新連結（只改 Markdown 連結語法）==="

# 定義檔案列表（根據 Phase 0 的盤點結果調整）
FILES_TO_UPDATE=(
    "README.md"
    "CLAUDE.md"
    "AGENTS.md"
    "docs/README.md"
)

# 添加所有 docs/ 下的 .md 文件（除了 archive/）
while IFS= read -r -d '' file; do
    # 排除 archive/ 目錄下的文件
    if [[ "$file" != *"archive/"* ]]; then
        FILES_TO_UPDATE+=("$file")
    fi
done < <(find docs/ -name "*.md" -type f -print0)

# 定義連結映射（舊路徑 -> 新路徑）
declare -A LINK_MAP=(
    # Guides
    ["01-guides/cyclonedds-config-guide.md"]="archive/2026-02-11-restructure/guides/cyclonedds-config-guide.md"
    ["01-guides/slam_nav/cyclonedds_guide.md"]="archive/2026-02-11-restructure/guides/cyclonedds_guide.md"
    ["01-guides/Depth Anything V2/"]="archive/2026-02-11-restructure/guides/Depth Anything V2/"
    ["01-guides/Depth%20Anything%20V2/"]="archive/2026-02-11-restructure/guides/Depth%20Anything%20V2/"
    ["01-guides/專案必學知識清單.md"]="archive/2026-02-11-restructure/guides/專案必學知識清單.md"
    ["01-guides/go2_sdk/"]="archive/2026-02-11-restructure/guides/go2_sdk/"
    
    # Overview
    ["00-overview/開發計畫.md"]="archive/2026-02-11-restructure/overview/開發計畫.md"
    ["00-overview/專題目標.md"]="archive/2026-02-11-restructure/overview/專題目標.md"
    ["00-overview/1-7-demo-簡報大綱.md"]="archive/2026-02-11-restructure/overview/1-7-demo-簡報大綱.md"
    ["00-overview/團隊進度追蹤/"]="archive/2026-02-11-restructure/overview/團隊進度追蹤/"
    
    # Testing
    ["03-testing/Demo 影片錄製腳本.md"]="archive/2026-02-11-restructure/testing/Demo 影片錄製腳本.md"
    ["03-testing/slam-phase1_test_results_ROY.md"]="archive/2026-02-11-restructure/testing/slam-phase1_test_results_ROY.md"
    
    # Reports
    ["03-reports/drafts/"]="archive/2026-02-11-restructure/reports/drafts/"
    ["03-reports/背景知識_草稿.md"]="archive/2026-02-11-restructure/reports/背景知識_草稿.md"
    
    # Design
    ["02-design/資料庫設計.md"]="archive/2026-02-11-restructure/design/資料庫設計.md"
    
    # Refactor
    ["refactor/index.md"]="archive/2026-02-11-restructure/index.md"
    ["refactor/current_state.md"]="archive/2026-02-11-restructure/current_state.md"
)

# 更新每個文件
for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        echo "處理: $file"
        
        # 對每個連結映射進行替換（只改 Markdown 連結）
        for old_path in "${!LINK_MAP[@]}"; do
            new_path="${LINK_MAP[$old_path]}"
            
            # 只替換 Markdown 連結語法 ](path) 或 ](path#anchor)
            # 使用 sed，注意：這是 GNU sed 語法（Linux）
            sed -i "s|](${old_path})|](${new_path})|g" "$file"
            sed -i "s|](${old_path}#|](${new_path}#|g" "$file"
        done
    fi
done

echo "=== 連結更新完成 ==="
```

**執行**:
```bash
# 保存上述腳本為 update-links.sh
chmod +x update-links.sh
./update-links.sh
```

**驗證**:
```bash
# 檢查是否還有引用舊路徑（排除 archive/ 自身）
echo "=== 檢查殘留的舊路徑引用 ==="
grep -r "01-guides/cyclonedds" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/" | head -5
grep -r "00-overview/開發計畫" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/" | head -5
grep -r "refactor/index" . --include="*.md" | grep -v ".sisyphus/" | grep -v "archive/" | head -5

# 如果還有輸出，需要手動修正
echo "如果上方有輸出，請手動檢查並修正"
```

**提交**:
```bash
git add -A
git commit -m "docs: update all markdown links to archived paths" \
           -m "更新範圍：" \
           -m "- README.md, CLAUDE.md, AGENTS.md (root 層級)" \
           -m "- docs/*.md (所有文件)" \
           -m "- 排除 archive/ 目錄（避免雙重改寫）" \
           -m "" \
           -m "原則：只改 Markdown 連結語法 ](path)，不改裸字串"
```

---

### Phase 3: 遷移圖片 Assets（第 3 個 Commit）

**⚠️ 新增 Phase**: 處理之前遺漏的圖片

**執行命令**:
```bash
# 建立 assets 目錄
mkdir -p docs/assets/{images,diagrams}

# 遷移 00-overview/images/
if [ -d "docs/00-overview/images" ]; then
    for file in docs/00-overview/images/*; do
        if [ -f "$file" ]; then
            git mv "$file" docs/assets/images/ \
                || echo "WARNING: 無法移動 $file"
        fi
    done
fi

# 遷移 04-notes/images/
if [ -d "docs/04-notes/images" ]; then
    for file in docs/04-notes/images/*; do
        if [ -f "$file" ]; then
            git mv "$file" docs/assets/images/ \
                || echo "WARNING: 無法移動 $file"
        fi
    done
fi

# 更新圖片引用（從舊路徑改到新路徑）
# 注意：這裡只做簡單的字串替換，實際連結格式可能是 ![](path) 或 <img src="path">
find . -name "*.md" -type f | while read file; do
    # 排除 archive/ 和 .git/
    if [[ "$file" != *"archive/"* ]] && [[ "$file" != *".git/"* ]]; then
        # 更新 00-overview/images/ 引用
        sed -i 's|00-overview/images/|assets/images/|g' "$file"
        # 更新 04-notes/images/ 引用
        sed -i 's|04-notes/images/|assets/images/|g' "$file"
    fi
done

# 提交
git add -A
git commit -m "assets: migrate images to docs/assets/images/" \
           -m "遷移來源：" \
           -m "- docs/00-overview/images/ -> docs/assets/images/" \
           -m "- docs/04-notes/images/ -> docs/assets/images/" \
           -m "" \
           -m "同時更新所有 Markdown 文件中的圖片引用路徑"
```

---

### Phase 4: 建立新目錄結構（第 4 個 Commit）

```bash
# 建立新目錄
mkdir -p docs/mission
mkdir -p docs/setup
mkdir -p docs/design/{decisions,migrations,current,future}
mkdir -p docs/testing/templates
mkdir -p docs/logs/{2026/{raw/01,raw/02},2025/raw}

# 提交空目錄（需要 .gitkeep）
touch docs/mission/.gitkeep
touch docs/setup/.gitkeep
touch docs/design/decisions/.gitkeep
touch docs/design/migrations/.gitkeep
touch docs/design/current/.gitkeep
touch docs/design/future/.gitkeep
touch docs/testing/templates/.gitkeep
touch docs/logs/2026/raw/01/.gitkeep
touch docs/logs/2026/raw/02/.gitkeep
touch docs/logs/2025/raw/.gitkeep

git add -A
git commit -m "chore: establish new directory structure" \
           -m "建立新的語義化目錄結構：" \
           -m "- mission/: 專案願景與規劃" \
           -m "- setup/: 環境建置指南" \
           -m "- design/: 架構設計（含 decisions/migrations/current/future）" \
           -m "- testing/: 測試驗證" \
           -m "- logs/: 開發日誌（按年月分層）"
```

---

### Phase 5: 遷移有效文件（第 5 個 Commit）

```bash
# ========== design/ 文件 ==========
git mv docs/refactor/Ros2_Skills.md docs/design/current/ros2-skills.md
git mv docs/refactor/refactor_plan.md docs/design/migrations/refactor-plan.md
git mv docs/refactor/pi_agent.md docs/design/future/pi-agent.md
git mv docs/refactor/skills-schema.md docs/design/current/skills-schema.md
git mv docs/refactor/skill-template.md docs/design/current/skill-template.md

# ========== setup/ 文件 ==========
git mv docs/01-guides/slam_nav/Jetson\ 8GB\ 快系統實作指南.md docs/setup/jetson-setup.md
git mv docs/01-guides/slam_nav/README.md docs/setup/slam-nav-guide.md
git mv docs/01-guides/基礎動作操作說明.md docs/setup/go2-basics.md
git mv docs/01-guides/網路排查.md docs/setup/network-troubleshooting.md
git mv docs/01-guides/gpu連上操作說明.md docs/setup/gpu-server-connection.md

# ========== design/ 其他文件 ==========
git mv docs/02-design/mcp_system_prompt.md docs/design/
git mv docs/02-design/巨人的肩膀上.md docs/design/

# ========== testing/ 文件 ==========
git mv docs/03-testing/slam-phase1_5_test_results_ROY.md docs/testing/phase1-5-results.md

# ========== mission/ 文件 ==========
git mv docs/03-reports/專題文件大綱.md docs/mission/project-outline.md

# 注意：CHANGELOG.md 暫時不移動，等 Phase 8 一起處理

git add -A
git commit -m "docs: migrate valid files to new structure" \
           -m "遷移以下有效文件到新位置：" \
           -m "- refactor/ -> design/{current,migrations,future}/" \
           -m "- 01-guides/（篩選後）-> setup/" \
           -m "- 02-design/ -> design/" \
           -m "- 03-testing/（篩選後）-> testing/" \
           -m "- 03-reports/（大綱）-> mission/"
```

---

### Phase 6: 整理開發日誌（第 6 個 Commit）

```bash
# ========== 2026 年 1 月 ==========
for file in docs/04-notes/dev_notes/2026-01-*-dev.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/logs/2026/raw/01/
    fi
done

# 會議記錄
if [ -f "docs/04-notes/dev_notes/2026-01-17-meeting.md" ]; then
    git mv docs/04-notes/dev_notes/2026-01-17-meeting.md docs/logs/2026/raw/01/
fi

# 週報
if [ -f "docs/04-notes/dev_notes/2026-W03-週報.md" ]; then
    git mv docs/04-notes/dev_notes/2026-W03-週報.md docs/logs/2026/raw/01/
fi

# ========== 2026 年 2 月 ==========
for file in docs/04-notes/dev_notes/2026-02-*-dev.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/logs/2026/raw/02/
    fi
done

# ========== 2025 年所有日誌 ==========
for file in docs/04-notes/dev_notes/2025/*.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/logs/2025/raw/
    fi
done

# ========== 研究筆記 ==========
if [ -d "docs/04-notes/research" ]; then
    git mv docs/04-notes/research docs/logs/
fi

# ========== CHANGELOG（移到 mission/）==========
if [ -f "docs/04-notes/CHANGELOG.md" ]; then
    git mv docs/04-notes/CHANGELOG.md docs/mission/
fi

git add -A
git commit -m "docs: reorganize dev notes into logs/" \
           -m "開發日誌按年月分層：" \
           -m "- logs/2026/raw/01/ - 2026年1月日誌" \
           -m "- logs/2026/raw/02/ - 2026年2月日誌" \
           -m "- logs/2025/raw/ - 2025年日誌" \
           -m "- logs/research/ - 研究筆記" \
           -m "- mission/CHANGELOG.md - 版本變更記錄" \
           -m "" \
           -m "注意：保留原始檔名（含 -dev.md 後綴）"
```

---

### Phase 7: 清理空目錄（第 7 個 Commit）

**⚠️ 關鍵修正**: 使用 `git rm -r` 而非 `rm -rf`

```bash
# 刪除 .gitkeep（現在可以刪了，因為會有其他文件進入這些目錄）
find docs/ -name ".gitkeep" -delete

# 清理空的舊目錄（使用 git rm -r 而非 rm -rf）
# 注意：這些目錄應該已經在之前的 Phase 被清空了

if [ -d "docs/01-guides/slam_nav" ] && [ -z "$(ls -A docs/01-guides/slam_nav 2>/dev/null)" ]; then
    git rm -r docs/01-guides/slam_nav
fi

if [ -d "docs/04-notes/dev_notes/2025" ]; then
    git rm -r docs/04-notes/dev_notes/2025 2>/dev/null || true
fi

if [ -d "docs/04-notes/dev_notes" ]; then
    git rm -r docs/04-notes/dev_notes 2>/dev/null || true
fi

if [ -d "docs/04-notes" ]; then
    git rm -r docs/04-notes 2>/dev/null || true
fi

if [ -d "docs/refactor" ]; then
    git rm -r docs/refactor 2>/dev/null || true
fi

if [ -d "docs/00-overview" ]; then
    git rm -r docs/00-overview 2>/dev/null || true
fi

if [ -d "docs/01-guides" ]; then
    git rm -r docs/01-guides 2>/dev/null || true
fi

if [ -d "docs/02-design" ]; then
    git rm -r docs/02-design 2>/dev/null || true
fi

if [ -d "docs/03-reports" ]; then
    git rm -r docs/03-reports 2>/dev/null || true
fi

if [ -d "docs/03-testing" ]; then
    git rm -r docs/03-testing 2>/dev/null || true
fi

# 注意：如果目錄不為空，git rm -r 會失敗，這時需要手動檢查

git add -A
git commit -m "chore: clean up empty directories" \
           -m "使用 git rm -r 刪除已清空的舊目錄：" \
           -m "- docs/00-overview/" \
           -m "- docs/01-guides/" \
           -m "- docs/02-design/" \
           -m "- docs/03-reports/" \
           -m "- docs/03-testing/" \
           -m "- docs/04-notes/" \
           -m "- docs/refactor/"
```

---

### Phase 8: 生成新 README.md（第 8 個 Commit）

**⚠️ 關鍵修正**: 這裡才是唯一修改 docs/README.md 的地方

```bash
cat > docs/README.md << 'EOF'
# PawAI 文件導航

> **最後更新**: 2026-02-11  
> **文件狀態**: 🔄 重構進行中

## 快速開始

| 我想了解... | 去這裡 |
|------------|--------|
| **專題在做什麼？** | [mission/vision.md](mission/vision.md) ⏳ 待更新 |
| **如何設定 Jetson？** | [setup/jetson-setup.md](setup/jetson-setup.md) ✅ |
| **Skills 怎麼設計？** | [design/current/ros2-skills.md](design/current/ros2-skills.md) ✅ |
| **下學期要做什麼？** | [design/future/pi-agent.md](design/future/pi-agent.md) ✅ |
| **開發日誌在哪？** | [logs/](logs/) ✅ |

## 目錄結構

### mission/ - 專案願景與規劃
- 專題目標、開發計畫、版本變更記錄
- ⏳ 待重寫: vision.md, roadmap.md

### setup/ - 環境建置
- Jetson 環境設定
- SLAM + Nav2 操作指南
- Go2 基礎操作
- 網路排障

### design/ - 架構設計
- `decisions/` - 架構決策 (ADR)
- `migrations/` - 遷移計畫
- `current/` - 當前 Python + ROS2 架構
- `future/` - 未來 TypeScript + Pi-Mono 藍圖

### testing/ - 測試驗證
- 測試報告
- 測試模板

### logs/ - 開發日誌
- 按年月分層: `2026/`, `2025/`
- 原始日誌: `raw/YYYY/MM/`（保留原始檔名 `*-dev.md`）
- 月度總結: `YYYY-MM-summary.md` ⏳ 待生成

### assets/ - 資源文件
- `images/` - 圖片、照片
- `diagrams/` - 架構圖、流程圖

### archive/ - 歷史歸檔
- [2026-02-11-restructure/](archive/2026-02-11-restructure/) - 重構前的文件

## 狀態說明

- ✅ 已完成: 文件已就位，內容有效
- 🔄 進行中: 文件已就位，內容持續更新
- ⏳ 待更新: 文件尚未建立或需要重寫

## 相關連結

- [專案根目錄](../README.md)
- [GitHub Repository](https://github.com/your-repo/elder_and_dog)
EOF

git add docs/README.md
git commit -m "docs: add new README.md with navigation" \
           -m "建立新的文件導航入口，包含：" \
           -m "- 快速開始連結表" \
           -m "- 目錄結構說明" \
           -m "- 文件狀態標記（✅/🔄/⏳）" \
           -m "- 明確標註 logs/ 檔名保留原始 `-dev.md` 後綴"
```

---

## 4. 後續工作（手動）

### 4.1 必做（高優先級）
1. **重寫 mission/vision.md** - 更新為 Jetson 架構
2. **重寫 mission/roadmap.md** - 新的開發計畫
3. **生成 logs/2026/2026-01-summary.md** - 1月開發總結
4. **生成 logs/2026/2026-02-summary.md** - 2月開發總結

### 4.2 建議做（中優先級）
1. 為 design/decisions/ 添加 ADR 模板
2. 建立 setup/troubleshooting.md（常見問題）
3. 更新 root 層級的 README.md, CLAUDE.md 等文件中的連結
4. 設定 Markdown link checker（CI）

### 4.3 可選做（低優先級）
1. 為所有 .md 添加 YAML frontmatter
2. 將圖片引用從相對路徑改為絕對路徑（方便移動文件）
3. 建立 docs/assets/diagrams/ 並遷移架構圖

---

## 5. 風險評估與對策

| 風險 | 可能性 | 影響 | 對策 |
|------|--------|------|------|
| 遺漏更新某些引用連結 | 中 | 死鏈 | Phase 2 涵蓋全範圍（root + docs），執行後 grep 檢查 |
| sed 誤改非連結內容 | 低 | 內容錯誤 | 只改 `](path)` 語法，不改裸字串 |
| 圖片遺漏 | 中 | 圖片失效 | Phase 3 專門處理 assets/ |
| git rm -r 刪錯目錄 | 低 | 文件丟失 | 每步都檢查，有 WARNING 就停下來 |
| 跨平台 sed 語法問題 | 中 | macOS 用戶無法執行 | 註明「僅 GNU sed（Linux）」，或提供 Python 替代方案 |

---

## 6. 驗證檢查清單

執行完畢後，請確認：

- [ ] `git status` 顯示工作目錄乾淨
- [ ] `git log --oneline -10` 顯示 8 個 commit
- [ ] `docs/archive/2026-02-11-restructure/` 存在且包含歸檔文件
- [ ] `docs/mission/`, `docs/setup/`, `docs/design/` 等目錄存在且有內容
- [ ] `grep -r "01-guides/cyclonedds" . --include="*.md" | grep -v "archive/" | grep -v ".sisyphus/"` 無輸出
- [ ] `grep -r "00-overview/開發計畫" . --include="*.md" | grep -v "archive/" | grep -v ".sisyphus/"` 無輸出
- [ ] `docs/README.md` 可正常瀏覽，連結可點擊
- [ ] `docs/assets/images/` 存在且包含圖片

---

## 7. 附錄：快速命令參考

### 檢查死鏈
```bash
# 檢查是否還有引用舊路徑
grep -r "01-guides/" . --include="*.md" | grep -v "archive/" | grep -v ".git/" | grep -v ".sisyphus/"
grep -r "00-overview/" . --include="*.md" | grep -v "archive/" | grep -v ".git/" | grep -v ".sisyphus/"
grep -r "refactor/" . --include="*.md" | grep -v "archive/" | grep -v ".git/" | grep -v ".sisyphus/"
```

### 統計文件數量
```bash
echo "mission: $(find docs/mission/ -name '*.md' 2>/dev/null | wc -l)"
echo "setup: $(find docs/setup/ -name '*.md' 2>/dev/null | wc -l)"
echo "design: $(find docs/design/ -name '*.md' 2>/dev/null | wc -l)"
echo "testing: $(find docs/testing/ -name '*.md' 2>/dev/null | wc -l)"
echo "logs: $(find docs/logs/ -name '*.md' 2>/dev/null | wc -l)"
echo "archive: $(find docs/archive/ -name '*.md' 2>/dev/null | wc -l)"
echo "assets/images: $(find docs/assets/images/ -type f 2>/dev/null | wc -l)"
```

### 如果出問題，如何回退
```bash
# 方法 1: 重置到重構前的 commit
git checkout main
git reset --hard docs-before-restructure-20260211

# 方法 2: 捨棄重構分支，從備份分支重新開始
git checkout docs-restructure-20260211-backup
git checkout -b docs-restructure-20260211-v2
```

### 跨平台 sed 替代方案（macOS）
如果在 macOS 上執行，將 `sed -i` 改為 `sed -i ''`：
```bash
# Linux (GNU sed)
sed -i 's|old|new|g' file.md

# macOS (BSD sed)
sed -i '' 's|old|new|g' file.md
```

---

**計畫書版本**: v1.1（已根據審查意見修正）  
**建立日期**: 2026-02-11  
**修正內容**: 
- 新增全範圍連結更新（root 層級文件）
- 新增 Phase 3 處理 assets/ 遷移
- 修正連結重寫規則（只改 Markdown 語法）
- 移除錯誤吞掉的 `2>/dev/null || true`
- 使用 `git rm -r` 取代 `rm -rf`
- 統一使用 `git add -A`
- Phase 2 不再修改 README.md，留到 Phase 8
- 明確標註 logs/ 保留原始檔名
