# Spec 6 — Studio Scroll 重現驗證 Checklist

> **Status**: ✅ COMPLETED 2026-05-10 night
> **Date**: 2026-05-10
> **依據**：[Spec 6](../specs/2026-05-10-spec6-studio-ux-polish.md) §3
> **Fix commits**：`87e2d5d` (5/9 evening, scroll behaviour) + `fdd5c93` (5/10 night, layout 重構)
> **實際工時**：~3 小時（原估 5–10 分鐘，因發現新 layout bug 升級為 composer 重構）
> **執行者**：Roy
> **目的**：確認 5/9 fix 是否解決 scroll 跳動問題；無重現 → P0 砍掉、Spec 6 P1/P2 留 demo 後

---

## 1. 前置

```bash
# 從 repo 根啟動 Studio
bash pawai-studio/start.sh
# → Frontend:    http://localhost:3000/studio
# → Mock Server: http://localhost:8080
# → WebSocket:   ws://localhost:8080/ws/events
```

無需 Jetson、無需 Go2、無需後端 ROS2。
（CLAUDE.md 寫的 `8001` 是過時值；以 `pawai-studio/start.sh:46` 為準 → port 8080。）

---

## 2. 驗證 4 個 case

| # | 操作 | 預期行為 | 通過? |
|---|------|---------|:----:|
| C1 | 連發 5+ 句 user message（任意內容） | 每次新訊息進來，自動滾到底 | ☐ |
| C2 | 滑到底後，**手動 scroll up** 看舊訊息，停留 5 秒 | 不會被新訊息強拉回底 | ☐ |
| C3 | C2 狀態下，**再發一句新訊息** | 不強拉底；視角保持在使用者讀的位置 | ☐ |
| C4 | C3 後，手動滑回底部（距底 < 30px） | 重新進入 stick-to-bottom；下一句新訊息自動滾到底 | ☐ |

**通過判定**：4/4 通過 → P0 砍。

**不通過判定**：任一 case fail → 開小 plan（記錄哪個 case fail、什麼狀況）。

---

## 3. 觀察點（debug 用）

如果 fail，打開 DevTools Console 看：

```js
// 在 chat-panel.tsx:116 附近，可暫時加 log 看 distance
console.log('distance to bottom:', el.scrollHeight - el.scrollTop - el.clientHeight);
```

可能的 fail 模式：
- **動畫高度未穩**：訊息有打字機動畫 / image / markdown render 撐高 → distance 計算晚一拍
- **iframe / nested scroll**：scroll 事件沒掛到正確 container
- **mobile / 縮放**：觸控滾動的 momentum 階段判定錯誤（demo 用筆電，可暫時忽略）

---

## 4. 結果記錄（5/10 night 實測）

| Case | Pass / Fail | 備註 |
|------|:-----------:|------|
| C1 | ✅ Pass | 連發訊息會自動滾到底（5/9 fix work） |
| C2 | ✅ Pass | 上滑後不被新訊息強拉回（5/9 fix work） |
| C3 | ✅ Pass | 同 C2 |
| C4 | ✅ Pass | 滑回底部後 stick-to-bottom 恢復 |

**5/9 stick-to-bottom fix 在原 issue 不重現** — 但測試過程中暴露**另一個更深層的 layout bug**：composer（輸入框）會被訊息推離 viewport 底部、發長訊息有空白 catch-up。

### 衍生工作（已完成）

5/10 一連串嘗試 → 最後改為 composer 重構：
- 抽 `components/chat/composer.tsx`（純 view component）
- ChatPanel conversation view 重組為 `relative h-full overflow-hidden` + absolute layout（header / scroll / composer-bar 三層）
- ResizeObserver 動態量 headerH / composerBarH，scroll area 用 inline `style={{ top, bottom }}` 鉗制
- z-index：composer z-20 < DevButton z-30 < Sheet z-40/50

Commit：`fdd5c93 fix(studio): composer absolute-bottom layout (ChatGPT-like)`
詳細設計 plan：`/home/roy422/.claude/plans/subagent-pawai-studio-frontend-vectorized-bunny.md`

---

## 5. 結論

✅ **Spec 6 P0 完成**。但範圍從「驗證 5/9 fix」升級為「composer layout 重構」。
Spec 6 P1（五功能 sidebar）/ P2（demo 操作面板）按原計畫留 demo 後。
焦點移回 Spec 1（5/11 起 P0 + P1）。
