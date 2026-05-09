# Branch C — ASR 繁中 + Context Reset Skeleton Plan

> **Skeleton plan** — task list 列改哪檔做什麼，不寫 TDD step 細節。實際開工前 expand。

**Goal:** 解 issue 6（ASR 簡→繁）+ issue 7（refresh 重置 context）。兩個小而清楚的修改，並行做。

**Spec 來源:** `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` P1-3（ASR）+ P1-2（Context Reset）。

**前置依賴**: Branch A merged。可與 Branch B 並行（不衝突）。

**工時**: ~3h（P1-3 1h + P1-2 1.5h + 收尾 0.5h）

---

## File Structure

```
speech_processor/speech_processor/text_normalization.py        # NEW (P1-3 helper)
speech_processor/speech_processor/stt_intent_node.py:1100      # MODIFY (P1-3 入口 A)
pawai-studio/gateway/studio_gateway.py:627                     # MODIFY (P1-3 入口 B)
pawai-studio/gateway/studio_gateway.py:385                     # MODIFY (P1-2 /api/reset endpoint)
pawai-studio/frontend/components/chat/chat-panel.tsx           # MODIFY (P1-2 「新對話」按鈕 + confirm)
pawai-studio/frontend/hooks/use-websocket.ts                   # MODIFY (P1-2 F5 hybrid auto-detect dev flag)
pawai_brain/pawai_brain/conversation_graph_node.py             # MODIFY (P1-2 subscribe /brain/reset_context)
interaction_executive/interaction_executive/brain_node.py      # MODIFY (P1-2 subscribe + cancel pending)
speech_processor/setup.py                                      # MODIFY (P1-3 加 opencc-python-reimplemented)
pawai-studio/gateway/requirements.txt                          # MODIFY (P1-3 加 opencc-python-reimplemented)
```

---

## Task C-1: P1-3 ASR s2twp Helper（避免 cross-package import 陷阱）

**Roy review #1：gateway 不能直接 `import speech_processor.speech_processor.text_normalization`**（gateway 是 FastAPI 進程，不一定在 ROS package Python path 下）。兩個解法擇一：

- **方案 A（推薦）**：兩個地方各放一份 `to_traditional_tw()` 小 helper（< 20 行），共用 `s2twp.json` config name
  - `speech_processor/speech_processor/text_normalization.py`（給 stt_intent_node import）
  - `pawai-studio/gateway/text_normalization.py`（給 gateway import；複製貼上同 code）
  - 工程整潔輸 reuse、避免 cross-package import 陷阱
- **方案 B**：建 `pawai_common/` shared package 兩邊 install — 風險：跨 package install 設置複雜，demo 前不適合

**選 A**。

- [ ] 建 `speech_processor/speech_processor/text_normalization.py`：lazy-import OpenCC `s2twp.json`，fallback 原文（spec L307-331 已給完整 code）
- [ ] 建 `pawai-studio/gateway/text_normalization.py`：複製同 code（DRY 違反但邊界清楚）
- [ ] 加 unit test 各一份（speech_processor + gateway 各跑）
- [ ] commit

## Task C-2: P1-3 雙入口注入

- [ ] `stt_intent_node.py:1100` `_publish_asr_result` 前加 `from speech_processor.text_normalization import to_traditional_tw` + 注入
- [ ] `studio_gateway.py:627` `/ws/speech` handler 在 `text = asr_result["text"].strip()` 後加 `from gateway.text_normalization import to_traditional_tw` + 注入
- [ ] launch arg `enable_s2twp` default true（speech_processor）
- [ ] env var `PAWAI_ENABLE_S2TWP` 給 gateway（fastapi process）
- [ ] 加 dependency `opencc-python-reimplemented`：
  - `speech_processor/setup.py` install_requires
  - `pawai-studio/gateway/requirements.txt`（已存在，append）
- [ ] **Jetson 確認**：colcon build 後 Jetson 上 `python3 -c "from opencc import OpenCC"` 不 ImportError
- [ ] integration test：實機 mic + Studio mic 兩入口都過繁化
- [ ] commit

## Task C-3: P1-2 Reset endpoint + topic

- [ ] `studio_gateway.py:385` 加 `POST /api/reset` endpoint → publish `/brain/reset_context` (std_msgs/Empty)
- [ ] `conversation_graph_node` 訂 `/brain/reset_context` → `self._memory.clear()` + `self._seen_sessions.clear()`
- [ ] `brain_node` 訂同 topic → `self._pending_confirm.cancel(reason="page_reset")`
- [ ] **不清** `_active_plans` / `_state.attention`（demo 中不打斷正在做的動作）
- [ ] integration test：POST /api/reset → topic 發出 → 兩 node 收到 → memory.clear 被呼叫
- [ ] commit

## Task C-4: P1-2 Frontend「新對話」按鈕 + confirm

- [ ] `chat-panel.tsx` header 加按鈕 → `fetch('/api/reset', {method: 'POST'})` + 清前端 messages array
- [ ] 加 confirm dialog：「將清除目前所有對話記憶，包括其他開啟的 Studio 視窗。確定？」
- [ ] tooltip：「重置全局對話記憶（所有 device 共用）」
- [ ] vitest case：按鈕點擊 → confirm 接受 → fetch 呼叫 + 清前端
- [ ] commit

## Task C-5: P1-2 F5 hybrid auto-detect (dev-only flag)

**Roy review #3 前置確認**：開工前 grep 確認 frontend app router 結構（pages router vs app router）：

```bash
ls pawai-studio/frontend/app/ pawai-studio/frontend/pages/ 2>/dev/null
grep -rn "beforeunload" pawai-studio/frontend/ 2>/dev/null | head -5
find pawai-studio/frontend -name "layout.tsx" -o -name "_app.tsx" | head -3
```

確認後選實際對應檔（layout.tsx 在 app router；_app.tsx 在 pages router）。

- [ ] `use-websocket.ts` 加 onopen handler check `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH === 'true'`
- [ ] 對應 layout/app 檔加 `beforeunload` 寫 `sessionStorage.setItem('paw_refresh_at', ...)`
- [ ] dev mode env：`.env.development.local` 加 `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=true`
- [ ] demo 預設 false（**確保 production .env / 預設 build 不開**）
- [ ] commit

## Task C-6: 全套 smoke

- [ ] tsc + vitest + pytest 全 PASS
- [ ] Jetson smoke：
  - ASR 5/5 round 100% 繁中（USB mic + Studio mic 兩路徑）
  - 新對話按鈕 → 第一句不帶舊 context
  - F5 (dev mode) → reset；F5 (demo mode default) → 不 reset
- [ ] dev-log 寫結果

---

## Verification

- [ ] `python3 -m pytest speech_processor/test/ pawai-studio/gateway/ -v`：新 test PASS + 0 regression
- [ ] `cd pawai-studio/frontend && npx vitest run && npx tsc --noEmit`：0 errors
- [ ] Jetson smoke：實機 mic「天氣」、「今天好嗎」、「我累了」5 round 全繁中
- [ ] Studio mic（瀏覽器麥克風）相同 5 round 全繁中
- [ ] 「新對話」按鈕 confirm + 清 memory：第一句問「我剛才說什麼」→ LLM 回「不知道」（context cleared）
- [ ] F5 demo mode（NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=false）→ 刷新後 memory 仍在
- [ ] F5 dev mode（=true）→ 刷新後 memory 清

---

## Out of Scope

- per-session memory（多 tab 隔離）— demo 後 P1-2.5 可選
- 語音指令觸發 reset（「重新開始」keyword）— 不需要，按鈕已夠
- gateway `/api/reset` rate-limit — 全局單例，多次呼叫等價於一次
