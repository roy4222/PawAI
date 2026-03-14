# Git Workflow — PawAI Studio 前端分工

**版本**：v1.0
**建立日期**：2026-03-14

---

## 1. 分支命名

```
main                          # 穩定版，只接 PR merge
├── feat/face-panel           # 鄔
├── feat/speech-panel         # 陳
├── feat/gesture-panel        # 黃
└── feat/pose-panel           # 楊
```

### 建立分支

```bash
git checkout main
git pull origin main
git checkout -b feat/face-panel    # 換成你的功能名
```

---

## 2. 你只能改的檔案

每人只在自己的元件目錄工作，**不要改其他人的檔案**。

| 人 | 可改的檔案 | 不要碰 |
|----|-----------|--------|
| 鄔 | `frontend/components/face/*` | 其他 components/、hooks/、stores/ |
| 陳 | `frontend/components/speech/*` | 同上 |
| 黃 | `frontend/components/gesture/*` | 同上 |
| 楊 | `frontend/components/pose/*` | 同上 |

如果你需要修改共用元件（`shared/`、`hooks/`），先在群組討論，不要直接改。

---

## 3. Commit 訊息格式

```
<type>(<scope>): <簡短描述>

type: feat | fix | style | refactor
scope: face | speech | gesture | pose
```

### 範例

```bash
git commit -m "feat(face): 實作多人追蹤列表 UI"
git commit -m "style(face): 調整 FacePanel 卡片間距"
git commit -m "fix(speech): 修正 ASR 文字溢出問題"
```

---

## 4. 發 PR 流程

### 步驟

```bash
# 1. 確認你的分支是最新的
git checkout feat/face-panel
git fetch origin
git rebase origin/main

# 2. 推到遠端
git push origin feat/face-panel -u

# 3. 到 GitHub 開 PR
#    - Base: main
#    - Compare: feat/face-panel
#    - Title: feat(face): FacePanel 實作
```

### PR 標題格式

```
feat(<scope>): <你做了什麼>
```

### PR 描述模板

```markdown
## 做了什麼
- [ ] 列出你實作的元件/功能

## 截圖
（貼上你的 UI 截圖）

## 驗收標準對照
- [ ] 對照你的 spec 中的驗收標準，逐項打勾

## 測試方式
- [ ] `npm run dev` 可正常顯示
- [ ] 接 Mock Server 資料可正常更新
- [ ] 響應式：sidebar 寬度 280-400px 自適應
```

---

## 5. 開發流程

```bash
# 1. 啟動 Mock Server（後端）
cd pawai-studio/backend
pip install -r requirements.txt   # 或 uv pip install -r requirements.txt
python mock_server.py
# Mock Server 跑在 http://localhost:8001

# 2. 啟動前端
cd pawai-studio/frontend
npm install
npm run dev
# 前端跑在 http://localhost:3000

# 3. 開始開發你的 Panel
# 編輯 frontend/components/<你的功能>/
# 存檔後瀏覽器會自動刷新
```

---

## 6. 常見問題

### Q: 我需要新的 npm 套件怎麼辦？

先在群組問，確認不會跟別人衝突後再裝。安裝後 `package.json` 和 `package-lock.json` 的變更要一起 commit。

### Q: 我的 Panel 需要新的 props 欄位？

不要自己加。跟 Roy 說，他會更新 `contracts/types.ts` 和 Mock Server。

### Q: merge 衝突怎麼辦？

因為每人改不同目錄，理論上不會衝突。如果真的衝了，先 `git stash`，pull 最新，再 `git stash pop` 解衝突。

### Q: 我不確定某個 UI 該怎麼做？

1. 先看你的 `<功能>-panel-spec.md`
2. 看 `design-tokens.md` 的共用元件範例
3. 還是不確定就問 AI 或群組討論

---

*最後更新：2026-03-14*
