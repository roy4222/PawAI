# Spec 6 — Studio Scroll 重現驗證 Checklist

> **Status**: ready-to-verify
> **Date**: 2026-05-10
> **依據**：[Spec 6](../specs/2026-05-10-spec6-studio-ux-polish.md) §3
> **Fix commit**：`87e2d5d` (5/9 evening) — chat-panel.tsx:116
> **預期工時**：5–10 分鐘
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

## 4. 結果記錄

| Case | Pass / Fail | 備註 |
|------|:-----------:|------|
| C1 | | |
| C2 | | |
| C3 | | |
| C4 | | |

**結論**（驗證後填）：
- [ ] 4/4 通過 → Spec 6 P0 完成、本檢查項砍。Spec 6 P1/P2 留 demo 後。
- [ ] 有 fail → 開 `docs/pawai-brain/plans/2026-05-10-spec6-scroll-fix-plan.md`，記錄 fail case + 修法假設。

---

## 5. 後續

- 若通過：在 [demo-quality roadmap index](../specs/2026-05-10-demo-quality-roadmap-index.md) 標 Spec 6 P0 ✅，焦點移回 Spec 1。
- 若不通過：補小 plan 後再決定是否 demo 前修（看 fail 嚴重程度）。
