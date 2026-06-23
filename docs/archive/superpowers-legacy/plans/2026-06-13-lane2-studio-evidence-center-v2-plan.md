# Lane 2：Studio Evidence Center v2（trace 變成可看、可匯出、可回答「為什麼沒反應」）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)、[系統 Phase 2 plan](2026-06-11-phase2-core-brain-ops-refactor.md)（2B post-6/18 段：decision timeline / session report / annotated clip——本 plan 把前兩項提前）、A-4（PII 保守預設，RESOLVED）、A-11（export auth，RESOLVED）
> **Code 現實基準**：`trace_store.py`（222 行）、`studio_gateway.py`（1458 行）、前端 `skill-trace-content.tsx` / `state-store.ts`

---

## 1. Goal

把已落盤的 trace 升級成**證據中心**：操作者（含發表觀眾視角）能在 Studio 看到——哪個 session、什麼事件進來、Brain 接受還是壓掉、被哪個 gate 用什麼理由壓掉（**中文**）、ISM shadow/takeover 怎麼判——並能一鍵匯出 session 報告。debug 流程從「猜 + 讀 code」變成「開 Evidence Center 看 timeline」。

## 2. Current state（code 實證）

| 已有 | 細節 |
|---|---|
| 落盤 | `runtime/traces/{session_id}.jsonl`（session_id=`YYYYMMDD-HHMMSS`）、20MB rotation、留 20 sessions、enqueue+daemon writer、`PAWAI_TRACE_STORE_ENABLED=0` kill-switch |
| export | `GET /api/trace/export`：redacted 預設／`redact=0` 需 auth-on+token 否則 **403**／`since=` 過濾；**無 `session=` 參數**（只能拉現行 session 流） |
| redaction | `redact_trace_event()` 單一真相：PII keys（source_summary/transcript/text/name/identity/image_path/image/full_text）→ `[private]`；reason 內人名段 regex 遮蔽；結構欄位（gate/kind/verdict/decision_id/ism_*/demo_phase/cooldown_remaining_s）全可見 |
| WS | `/ws/events` envelope `source="brain:trace"`，data 已 redacted |
| 前端 | Suppressed viewer（`skill-trace-content.tsx`：gate/reason/decision_id 前 8 碼/shadow badge，cap 50）；`brainTraces` store cap 50；DevPanel + `/studio/dev` 共用 |
| 真機 | 6/12 全鏈驗過：JSONL 46→192 行、export 三模式、viewer WS 流 + `[private]` |

**缺**（gap 實查）：session list API、timeline view、前端 export 按鈕、detail drawer、filter、回放、session 級統計報告、reason 中文化、mock server 的 trace stub（前端 WSL 開發不便）。

## 3. Problems / gaps

1. **Suppressed viewer 不夠**：只有「最近 50 條扁平列表」——回答「剛剛那次為什麼沒反應」可以，回答「這個 session 整體哪些 gate 最常壓事件」「事件從 candidate 到 skill_result 的因果鏈」不行。
2. **歷史不可選**：JSONL 已留 20 sessions，但沒有任何 API/UI 能列出或讀取舊 session。
3. **reason 是英文 code 字串**（`gate:confirm_pending`、`cooldown:greet:[private]`）——發表時觀眾看不懂；隊友 debug 也要查表。
4. **沒有 session 報告**：Lane 1 的 soak 分歧分析（legacy vs ISM）目前要手算 JSONL。
5. **PII**：政策已定（A-4）且落地單源；新功能只需**全部走 redacted 路徑**，不需新政策。
6. **mock parity**：前端在 WSL 開發 Evidence UI 時 gateway 不在，mock server 無 trace 資料。

## 4. Scope

- `pawai-studio/gateway/`：`trace_store.py`（讀取側新增：list_sessions / read_session / summarize）、`studio_gateway.py`（3 個新 endpoint）、單測。
- `pawai-studio/frontend/`：新 Evidence Center 頁（或 `/studio/dev` 擴充）、timeline 元件、zh 對照、export 按鈕、detail drawer。
- `pawai_contracts/pawai_contracts/zh_tables.py`：gate/reason 前綴 → 中文對照（additive）。
- `pawai-studio/mock-server/`（或對應檔）：trace endpoints stub。

## 5. Forbidden scope

1. **不做 annotated evidence clip**（依賴 Lane 4 W4 spike 產物；W4 完成後 post-6/18 回流，本 plan 只留檔案格式接口註記）。
2. **不做回放（seek/播放速度）**——P2，6/18 前砍。
3. **不改 redaction 政策**：A-4 已 RESOLVED；新 endpoint/UI 一律消費 `redact_trace_event()` 後的資料；full export 的 403 規則不放寬。
4. **不做 Plan E 表外 6 處未插樁 suppression 的補樁**（trace v2 另案）。
5. **不動 `/brain/trace` 發射端**（Brain 側是 Lane 1 的事；D5 邊界：schema=contracts、發射=Brain、落盤=gateway、CLI 只讀）。
6. 不做 operator/presentation mode enforcement（A-7，系統 Phase 5）；本 plan 的頁面沿用現行 gateway auth 姿態。

## 6. Proposed tasks

| Task | 內容 | 優先 | 驗證 |
|---|---|---|---|
| **T2-1 session list API** | `trace_store` 加讀取側：`list_sessions()` 掃 `runtime/traces/*.jsonl` → `[{session_id, started_ts, line_count, file_size, parts}]`；gateway `GET /api/trace/sessions`（統計不含 PII，無需 redact；沿用 export 的 auth 姿態） | P0 | 純模組單測（含 rotation 多 part 檔）+ endpoint 測試 |
| **T2-2 export 補 session 參數** | `GET /api/trace/export?session=<id>` 讀指定 session JSONL（含 `.N` parts 串接）；與 `since`/`redact` 組合；session id 嚴格白名單字元（防路徑穿越，仿 Lane 5 消毒慣例） | P0 | endpoint 測試（惡意 id 400；redact 規則不變 403 案例沿用） |
| **T2-3 Evidence Center 頁 + decision timeline** | 前端新頁 `/studio/evidence`：① session 選擇器（T2-1）② timeline：按 ts 升冪、依 `decision_id` 分組摺疊（candidate→verdict→skill_result 同鏈同組）、verdict 圖示（accepted 綠/suppressed 琥珀/blocked 紅/shadow 紫 badge）③ 點開 detail drawer（redacted detail dict 全展開）④ live 模式（WS 接現行 session，沿用 brainTraces）與歷史模式（fetch export）切換 | P0 | vitest（store/分組邏輯）+ tsc + 瀏覽器走查（§9） |
| **T2-4 reason 中文化** | `zh_tables.py` 加 `TRACE_GATE_ZH`（gate → 中文）與 reason 前綴對照（`cooldown:greet:*`→「問候冷卻中」、`gate:confirm_pending`→「等待手勢確認中」、`phase:*`→「demo 場景遮罩」、`watchdog_timeout:*`→「逾時自癒」…完整覆蓋 §2 的 19 gate + ISM verdict/trigger 字串）；前端顯示「中文（原 code）」雙行；**單測鎖全覆蓋**（出現未對照 gate → 測試紅） | P0 | contracts 單測（19 gate + ISM 字串全覆蓋斷言）+ 前端 fallback（查無對照顯示原字串） |
| **T2-5 session report** | gateway `GET /api/trace/report?session=<id>`：JSON + markdown 兩格式——事件總數、verdict 分佈、**top suppressed gates 排行**、**shadow/takeover 分歧統計**（同 decision_id 下 legacy verdict vs `ism_verdict` 不一致計數，按 gate 分組）、時間範圍；全部基於 redacted 資料 | P0 | 單測（合成 JSONL 斷言統計值）；真機對 6/12 的 192 行 session 跑一次 |
| **T2-6 前端 export/report 按鈕** | Evidence 頁加「下載 redacted JSONL」「下載 session 報告（md）」按鈕（fetch T2-2/T2-5，帶 auth header 能力——token 欄位讀 env/localStorage，default-off 下不帶） | P1 | 瀏覽器實測下載 |
| **T2-7 mock parity** | mock server 加 `/api/trace/sessions`、`/api/trace/export`、`/api/trace/report` stub + 假 trace 資料產生器（覆蓋全部 verdict/gate 形態，供前端 WSL 開發） | P1 | 前端指 mock 可完整走 Evidence 頁 |
| **T2-8 回放 seek** | timeline 時間軸拖拉回放 | P2（砍得起） | — |

## 7. Pure software tasks（WSL，可 AFK）

全部 T2-1~T2-8 的實作與單測（gateway 純模組測試不需 rclpy——`trace_store` 是 ROS-free 先例；前端 vitest + tsc；T2-7 讓前端開發完全離線）。

## 8. Jetson / Go2 HITL tasks

不需 Go2。需 Jetson 一次（併入 HITL #1，~20 min）：

1. deploy gateway + frontend → demo lane 跑一段（產生真 trace）。
2. 瀏覽器開 `/studio/evidence`：session 列表含今晚 session；timeline 與剛才動作對得上；suppressed 中文理由正確；點 detail 無 PII 洩漏（人名處 `[private]`）。
3. 下載 redacted JSONL 與報告；報告的分歧統計與 `pawai evidence pull` 摘要一致。
4. 歷史模式選 6/12 的舊 session 可讀。

## 9. Tests

- gateway：`cd pawai-studio/gateway && python3 -m pytest -q`（93 existing 零修改 + 新增）；redaction 案例：含 PII 的合成事件經 sessions/export/report 全路徑無洩漏。
- contracts：zh 對照全覆蓋單測（紅綠：故意新增 gate 不加對照 → 紅）。
- 前端：vitest（timeline 分組、zh fallback、store）+ `tsc --noEmit`。
- 瀏覽器驗證步驟 = §8 清單（成文於 PR 描述，Roy 照走）。

## 10. Rollback strategy

- 新 endpoint / 新頁面全 additive：單 PR revert 即消失，不影響既有 Suppressed viewer 與 export。
- `PAWAI_TRACE_STORE_ENABLED=0` 仍可整體關落盤（Evidence 頁顯示空清單，不炸）。
- zh 表 additive、前端有 fallback（查無對照顯示原字串）——對照表錯誤不阻斷。
- timeline 效能問題（大 session）→ 前端 cap（預設只載最近 2000 行 + 「載入更多」），cap 值可調，極端時退回 Suppressed viewer。

## 11. Done criteria

1. 「為什麼沒反應」三步可答：開 Evidence → 選 session → timeline 找到該事件的 suppressed 中文理由。
2. session list / timeline / report / export 按鈕真機走查全過（§8），無 PII 洩漏。
3. T2-5 報告能直接餵 Lane 1 T1-5 的分歧分析（shadow 分歧統計欄位齊）。
4. 前端可在 WSL 以 mock 完整開發（T2-7）。

## 12. Execution order

T2-1 → T2-2 →（並行）T2-3 + T2-4 + T2-5 → T2-6 → T2-7 →（有餘力）T2-8。T2-1/2 是其餘的 API 基座，先行；6/14 HITL #1 驗 T2-1~T2-5。

## 13. 6/18 presentation impact

- 正面：發表現場可投影 Evidence Center——「PawAI 每個不回應都有理由、可回放證據」是這次重構最可視的成果；Lane 1 的 watchdog 自癒在 timeline 上直接看得到。
- 風險：零 runtime 行為（全 additive）；最壞 = 頁面難看 → 不投影，退回既有 Suppressed viewer。
- 不可講：「全感知 evidence 已可回放」（annotated clip 未做）。

## 14. Fable review checklist

- [ ] 所有新讀取路徑消費 `redact_trace_event()` 後資料（grep 證明無 raw 路徑外洩）
- [ ] `session=` 參數有白名單字元消毒（含 `.N` part 處理）
- [ ] full export 403 規則未被新參數繞過（redact=0 + session 組合有測試）
- [ ] zh 對照覆蓋單測鎖住 19 gate + ISM 字串；fallback 行為有測試
- [ ] timeline 分組以 decision_id 為鍵、無 O(n²) 渲染（大 session cap 落實）
- [ ] gateway 93 / 前端 16 既有測試零修改
- [ ] D5 邊界未破：本 lane 零 Brain 側改動

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 2 Task <T2-x>（見 docs/archive/superpowers-legacy/plans/2026-06-13-lane2-studio-evidence-center-v2-plan.md §6）。
紀律：
- TDD 紅綠；gateway 新讀取邏輯放 trace_store.py（ROS-free 純模組，比照既有）。
- 一切輸出走 redact_trace_event() 後資料；session 參數嚴格消毒；不放寬 403 規則。
- 前端改動跑 vitest + tsc --noEmit；zh 對照進 pawai_contracts/zh_tables.py（additive）。
- 不碰 /brain/trace 發射端、不碰 redaction 政策本體。
驗證命令：
  cd pawai-studio/gateway && python3 -m pytest -q
  PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
  cd pawai-studio/frontend && npm run test && npx tsc --noEmit
完成後：單 commit、PR 描述附紅綠證據 + 瀏覽器驗證步驟。不得 merge，等 Fable review。
```
