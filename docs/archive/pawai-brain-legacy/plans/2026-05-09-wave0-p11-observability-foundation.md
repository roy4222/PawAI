# Wave 0 + P1-1 觀測底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解決 demo 級 TTS 跳句 + 讓 Studio ChatPanel 顯示所有 PawAI utterance（含自主語音、skill SAY），建立後續 persona/attention 改動的測試底座。

**Architecture:** 三段疊加。(1) `tts_node` chunk 失敗改 all-or-nothing 走 fallback chain；(2) `studio_gateway` `/tts` 訂閱解析 JSON envelope；(3) 前端 state-store 加 `ttsMessages` ring buffer，ChatPanel 永遠 append + spontaneous 樣式分離 + IE-node SAY source 條件分類。`pendingRequestIdRef` 角色重定義為「管 isThinking」而非 gate display。

**Tech Stack:** Python 3.10 + ROS2 Humble + pytest（speech_processor / interaction_executive / gateway）；Next.js 14 + zustand + TypeScript（frontend）；Vitest（frontend unit tests）。

**Spec 來源:** `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` Wave 0 (P0-1 + P0-2) + Wave 1 P1-1（Phase 1 a/b/c/d + Phase 2-mini）。

---

## File Structure

**修改 / 新建檔案**：

```
speech_processor/
├── speech_processor/tts_node.py            # MODIFY L621-630: all-or-nothing fallback
└── test/test_tts_split_chunks.py           # MODIFY: 加 test_partial_chunk_failure_returns_none

interaction_executive/
└── interaction_executive/skill_contract.py # MODIFY: build_plan() 在 SAY step args 塞 source

interaction_executive/
└── interaction_executive/interaction_executive_node.py  # MODIFY L185-194: envelope 加 source 欄位

pawai-studio/gateway/
├── studio_gateway.py                       # MODIFY L298-306: _on_tts_msg JSON envelope parse
└── test_gateway.py                         # MODIFY: 加 test_tts_envelope_parse / test_tts_plain_text_compat

pawai-studio/frontend/
├── stores/state-store.ts                   # MODIFY: 加 ttsMessages array + appendTtsMessage
├── hooks/use-event-stream.ts               # MODIFY: case "tts" 改呼叫 appendTtsMessage
├── components/chat/chat-panel.tsx          # MODIFY: 監聽 ttsMessages 全部 append + 樣式分離
└── stores/__tests__/state-store.test.ts    # CREATE: ttsMessages ring buffer + rate-limit dedup unit tests
```

**Task → File 對應**：
- Task 1: `tts_node.py` + `test_tts_split_chunks.py`
- Task 2: `studio_gateway.py` + `test_gateway.py`
- Task 3: `state-store.ts` + new test
- Task 4: `chat-panel.tsx` + `use-event-stream.ts`
- Task 5: client-side rate-limit (state-store)
- Task 6: `skill_contract.py` build_plan source 注入
- Task 7: `interaction_executive_node.py` envelope source 欄位 + gateway parse
- Task 8: ChatPanel CSS 三色 + 預設淡灰
- Task 9: Jetson smoke test

---

## Task 1: P0-1 TTS Silent-Skip → All-or-Nothing Fallback

**Files:**
- Modify: `speech_processor/speech_processor/tts_node.py:621-630`
- Test: `speech_processor/test/test_tts_split_chunks.py`

**背景**：現況 `_synthesize_chunked()` 在任一 chunk 失敗時 silent skip (`ok_parts = [p for p in results if p is not None]`)，使用者聽到「念一念跳到結尾」。改成任一 chunk None 即整段 `return None` 讓 provider chain fallback 接 edge-tts。

- [ ] **Step 1.1: 讀現有 chunked synthesize 邏輯**

```bash
sed -n '600,650p' speech_processor/speech_processor/tts_node.py
```

確認 L621-630 的 `ok_parts` filter 結構，並找出函式名稱（預期 `_synthesize_chunked` 或同等）。

- [ ] **Step 1.2: 寫 failing test**

修改 `speech_processor/test/test_tts_split_chunks.py`，加：

```python
def test_partial_chunk_failure_returns_none():
    """Any chunk failure → entire synthesize returns None for fallback chain."""
    from speech_processor.speech_processor.tts_node import TTSNode

    # Mock provider where chunk 2 returns None
    mock_provider = Mock()
    mock_provider.synthesize.side_effect = [b"chunk1_pcm", None, b"chunk3_pcm"]

    node = _build_test_node()  # existing helper
    result = node._synthesize_chunked(mock_provider, "三句測試文本，分成三段。", chunk_size=10)

    assert result is None, "Partial chunk failure must return None to trigger fallback chain"


def test_all_chunks_success_returns_concat():
    """All chunks succeed → concat PCM bytes."""
    mock_provider = Mock()
    mock_provider.synthesize.side_effect = [b"a", b"b", b"c"]

    node = _build_test_node()
    result = node._synthesize_chunked(mock_provider, "abc", chunk_size=1)

    assert result == b"abc"
```

- [ ] **Step 1.3: 跑 test 確認 fail**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest speech_processor/test/test_tts_split_chunks.py::test_partial_chunk_failure_returns_none -v
```

預期：FAIL（現有邏輯會回傳 b"chunk1_pcm" + b"chunk3_pcm" concat，不是 None）

- [ ] **Step 1.4: 改 `_synthesize_chunked` 邏輯**

`tts_node.py:621-630` 改為：

```python
# All-or-nothing: any chunk failure → fallback chain
if any(p is None for p in results):
    self.get_logger().warning(
        f"[tts] chunked synth partial failure ({sum(1 for p in results if p is None)}/{len(results)} chunks None) — returning None for provider chain fallback"
    )
    return None
full_pcm = b"".join(results)
```

注意：移除原 `ok_parts = [...]` filter line。

- [ ] **Step 1.5: 跑 test 確認 pass**

```bash
python3 -m pytest speech_processor/test/test_tts_split_chunks.py -v
```

預期：兩個新 test 都 PASS，原有 test 不 regression。

- [ ] **Step 1.6: Commit**

```bash
git add speech_processor/speech_processor/tts_node.py speech_processor/test/test_tts_split_chunks.py
git commit -m "fix(tts): P0-1 all-or-nothing chunk synthesis

Any chunk failure now returns None to trigger fallback chain (edge-tts → Piper),
instead of silent-skipping failed chunks and concatenating partial output.

Resolves demo-level bug where users heard '念一念跳到結尾'.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P0-1
"
```

---

## Task 2: P0-2 Gateway `/tts` JSON Envelope Parse

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py:298-306` (`_on_tts_msg`)
- Modify: `pawai-studio/gateway/studio_gateway.py:78-90` (`build_tts_event` accept origin/source)
- Test: `pawai-studio/gateway/test_gateway.py`

**背景**：IE-node L185-194 在 `input_origin` 存在時發 JSON envelope `{"text": ..., "input_origin": ...}`，gateway 現用 `msg.data.strip()` 當純文字塞 ChatPanel → 使用者看到原始 JSON 字串。

- [ ] **Step 2.1: 讀現有 `_on_tts_msg` + `build_tts_event` 邏輯**

```bash
sed -n '78,90p;295,310p' pawai-studio/gateway/studio_gateway.py
```

- [ ] **Step 2.2: 寫 failing tests**

加到 `test_gateway.py`：

```python
def test_tts_envelope_parse_extracts_text_and_origin():
    """JSON envelope: {text, input_origin, source} → broadcast with parsed fields."""
    from pawai_studio.gateway.studio_gateway import _parse_tts_payload

    raw = '{"text":"我是 PawAI","input_origin":"studio_text","source":"chat_reply"}'
    parsed = _parse_tts_payload(raw)

    assert parsed["text"] == "我是 PawAI"
    assert parsed["origin"] == "studio_text"
    assert parsed["source"] == "chat_reply"


def test_tts_plain_text_backward_compat():
    """Plain text (no JSON) → text only, origin/source default."""
    from pawai_studio.gateway.studio_gateway import _parse_tts_payload

    raw = "嗨，今天好嗎？"
    parsed = _parse_tts_payload(raw)

    assert parsed["text"] == "嗨，今天好嗎？"
    assert parsed["origin"] == "tts"
    assert parsed.get("source") is None


def test_tts_envelope_malformed_falls_back_to_text():
    """Malformed JSON → treat as plain text."""
    from pawai_studio.gateway.studio_gateway import _parse_tts_payload

    raw = '{"text": "broken'  # truncated
    parsed = _parse_tts_payload(raw)

    assert parsed["text"] == raw  # original string preserved


def test_tts_envelope_missing_text_field_falls_back():
    """JSON dict without 'text' field → treat as plain text."""
    from pawai_studio.gateway.studio_gateway import _parse_tts_payload

    raw = '{"foo": "bar"}'
    parsed = _parse_tts_payload(raw)

    assert parsed["text"] == raw
```

- [ ] **Step 2.3: 跑 test 確認 fail**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest pawai-studio/gateway/test_gateway.py -v -k tts_envelope
```

預期：FAIL（`_parse_tts_payload` 不存在）

- [ ] **Step 2.4: 加 `_parse_tts_payload` helper**

在 `studio_gateway.py` 適當位置（建議 `build_tts_event` 上方）加：

```python
def _parse_tts_payload(raw: str) -> dict:
    """Parse /tts msg.data: JSON envelope {text, input_origin, source} or plain text.

    Returns dict with keys: text (str), origin (str, default 'tts'), source (str|None).
    """
    raw = (raw or "").strip()
    if not raw:
        return {"text": "", "origin": "tts", "source": None}

    # Try JSON envelope
    if raw.startswith("{"):
        try:
            envelope = json.loads(raw)
            if isinstance(envelope, dict) and isinstance(envelope.get("text"), str):
                return {
                    "text": envelope["text"],
                    "origin": envelope.get("input_origin") or "tts",
                    "source": envelope.get("source"),
                }
        except (json.JSONDecodeError, TypeError):
            pass  # fall through to plain text

    # Plain text fallback (backward compat with §5.2)
    return {"text": raw, "origin": "tts", "source": None}
```

- [ ] **Step 2.5: 改 `_on_tts_msg` + `build_tts_event` 用 helper**

`_on_tts_msg` 改為：

```python
def _on_tts_msg(self, msg) -> None:
    parsed = _parse_tts_payload(msg.data)
    if not parsed["text"]:
        return
    event = build_tts_event(
        text=parsed["text"],
        origin=parsed["origin"],
        source=parsed["source"],
    )
    self._broadcast(event)
```

`build_tts_event` 加 `source` 參數：

```python
def build_tts_event(text: str, origin: str = "tts", source: str | None = None) -> dict:
    data = {"text": text, "origin": origin}
    if source:
        data["source"] = source
    return {
        "stamp": time.time(),
        "event_type": "tts",
        "data": data,
    }
```

- [ ] **Step 2.6: 跑 test 確認 pass**

```bash
python3 -m pytest pawai-studio/gateway/test_gateway.py -v -k tts
```

預期：4 個新 test 全 PASS，原有 test 不 regression。

- [ ] **Step 2.7: Commit**

```bash
git add pawai-studio/gateway/studio_gateway.py pawai-studio/gateway/test_gateway.py
git commit -m "fix(gateway): P0-2 parse /tts JSON envelope

IE-node sends JSON {text, input_origin, source} when input_origin exists.
Gateway now parses envelope and extracts text/origin/source for broadcast.
Plain text backward compat preserved per contract §5.2.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P0-2
"
```

---

## Task 3: P1-1a State-Store `ttsMessages` Ring Buffer

**Files:**
- Modify: `pawai-studio/frontend/stores/state-store.ts`
- Test: `pawai-studio/frontend/stores/__tests__/state-store.test.ts` (CREATE)

**背景**：保留 `lastTtsText` / `lastTtsAt`（其他 panel 還用）。新增 `ttsMessages` array (max 200) 由 ChatPanel 監聽 append。

- [ ] **Step 3.1: 讀現有 state-store**

```bash
sed -n '1,100p' pawai-studio/frontend/stores/state-store.ts
```

- [ ] **Step 3.2: 寫 failing test (CREATE 新檔)**

`pawai-studio/frontend/stores/__tests__/state-store.test.ts`：

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useStateStore } from "../state-store";

describe("ttsMessages ring buffer", () => {
  beforeEach(() => {
    useStateStore.setState({ ttsMessages: [] });
  });

  it("appendTtsMessage adds entry to ttsMessages", () => {
    useStateStore.getState().appendTtsMessage({
      id: "evt-1",
      text: "嗨",
      timestamp: 1000,
      origin: "tts",
    });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
    expect(useStateStore.getState().ttsMessages[0].text).toBe("嗨");
  });

  it("dedups by event id", () => {
    const msg = { id: "evt-1", text: "嗨", timestamp: 1000, origin: "tts" };
    useStateStore.getState().appendTtsMessage(msg);
    useStateStore.getState().appendTtsMessage(msg);
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });

  it("trims to max 200 (shift oldest)", () => {
    for (let i = 0; i < 205; i++) {
      useStateStore.getState().appendTtsMessage({
        id: `evt-${i}`,
        text: `msg-${i}`,
        timestamp: i,
        origin: "tts",
      });
    }
    const msgs = useStateStore.getState().ttsMessages;
    expect(msgs).toHaveLength(200);
    expect(msgs[0].id).toBe("evt-5"); // first 5 dropped
    expect(msgs[199].id).toBe("evt-204");
  });

  it("preserves source field when present", () => {
    useStateStore.getState().appendTtsMessage({
      id: "evt-1",
      text: "我來扭給你看",
      timestamp: 1000,
      origin: "tts",
      source: "skill_say",
    });
    expect(useStateStore.getState().ttsMessages[0].source).toBe("skill_say");
  });
});
```

- [ ] **Step 3.3: 跑 test 確認 fail**

```bash
cd pawai-studio/frontend
npx vitest run stores/__tests__/state-store.test.ts
```

預期：FAIL（`appendTtsMessage` / `ttsMessages` 不存在）

- [ ] **Step 3.4: 加 `ttsMessages` + `appendTtsMessage` 到 state-store**

修改 `state-store.ts`：

```typescript
// 既有 type 旁加：
export interface TtsMessage {
  id: string;
  text: string;
  timestamp: number;
  origin: string;
  source?: string;  // skill_say | chat_reply | say_canned | undefined
}

interface State {
  // 既有：
  lastTtsText: string | null;
  lastTtsAt: number | null;
  // 新增：
  ttsMessages: TtsMessage[];
  // ... 其他既有欄位
}

interface Actions {
  // 既有：
  updateTts: (text: string) => void;
  // 新增：
  appendTtsMessage: (msg: TtsMessage) => void;
  // ... 其他既有
}

// initial state:
ttsMessages: [],

// action 實作：
appendTtsMessage: (msg) => set((state) => {
  // dedup by id
  if (state.ttsMessages.some((m) => m.id === msg.id)) {
    return state;
  }
  // ring buffer max 200
  const next = [...state.ttsMessages, msg];
  if (next.length > 200) {
    return { ttsMessages: next.slice(next.length - 200) };
  }
  return { ttsMessages: next };
}),
```

- [ ] **Step 3.5: 跑 test 確認 pass**

```bash
npx vitest run stores/__tests__/state-store.test.ts
```

預期：4 個 test PASS。

- [ ] **Step 3.6: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add pawai-studio/frontend/stores/state-store.ts pawai-studio/frontend/stores/__tests__/state-store.test.ts
git commit -m "feat(studio): P1-1a add ttsMessages ring buffer to state-store

200-entry ring buffer with id dedup. Preserves lastTtsText/lastTtsAt for
other panels. Ready for ChatPanel to subscribe and append all PawAI utterances.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-1a
"
```

---

## Task 4: P1-1b/c/d ChatPanel Subscribe + pendingRequestIdRef Redefine + Style Split

**Files:**
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts` (case "tts" → appendTtsMessage)
- Modify: `pawai-studio/frontend/components/chat/chat-panel.tsx:62-112`

**背景**：ChatPanel 監聽 `ttsMessages` 全部 append。`pendingRequestIdRef` 重新定義為「管 isThinking」不再 gate display。樣式區分 pending（一般灰）vs spontaneous（淡灰 + 小時鐘圖標）。

- [ ] **Step 4.1: 讀現有 ChatPanel useEffect + use-event-stream tts case**

```bash
sed -n '55,140p' pawai-studio/frontend/components/chat/chat-panel.tsx
grep -n "case \"tts\"\|updateTts" pawai-studio/frontend/hooks/use-event-stream.ts
```

- [ ] **Step 4.2: 改 `use-event-stream.ts` case "tts"**

找到 `case "tts":` 區塊，改為：

```typescript
case "tts": {
  const data = evt.data;
  if (!data?.text) break;

  // 既有 updateTts 維持（其他 panel 用 lastTtsText）
  store.updateTts(data.text);

  // 新增：append 到 ttsMessages (P1-1)
  store.appendTtsMessage({
    id: evt.id || `tts-${evt.stamp}`,  // event id 沒給就用 stamp
    text: data.text,
    timestamp: evt.stamp,
    origin: data.origin || "tts",
    source: data.source,  // skill_say / chat_reply / say_canned / undefined
  });
  break;
}
```

- [ ] **Step 4.3: 改 `chat-panel.tsx` 監聽 ttsMessages**

L62-112 區塊改造：

```typescript
// 既有：
const lastTtsText = useStateStore((s) => s.lastTtsText);
const lastTtsAt = useStateStore((s) => s.lastTtsAt);
// 新增：
const ttsMessages = useStateStore((s) => s.ttsMessages);
const lastSeenTtsIdRef = useRef<string | null>(null);

// pendingRequestIdRef 角色重新定義 — 仍管 isThinking + speech intent 配對 + timeout，但不再 gate display
const pendingRequestIdRef = useRef<string | null>(null);

// 移除舊 useEffect (L97-112) 改為監聽 ttsMessages 全部 append:
useEffect(() => {
  if (ttsMessages.length === 0) return;

  // 找出 lastSeen 之後的所有 message
  const lastSeenIdx = lastSeenTtsIdRef.current
    ? ttsMessages.findIndex((m) => m.id === lastSeenTtsIdRef.current)
    : -1;
  const newMessages = ttsMessages.slice(lastSeenIdx + 1);

  if (newMessages.length === 0) return;

  // append 為 PawAI bubble；pending 配對的當一般灰，spontaneous 當淡灰
  setMessages((prev) => [
    ...prev,
    ...newMessages.map((m) => ({
      id: m.id,
      role: "assistant" as const,
      text: m.text,
      timestamp: m.timestamp,
      // P1-1d 樣式分類：
      variant: pendingRequestIdRef.current ? "pending" : "spontaneous",
      // P1-1 Phase 2-mini source 細分（若 source 存在用 source 樣式）：
      source: m.source,  // skill_say | chat_reply | say_canned | undefined
    })),
  ]);

  // 更新 lastSeen
  lastSeenTtsIdRef.current = ttsMessages[ttsMessages.length - 1].id;

  // 若 pending request 存在 → 收到第一條 TTS 視為配對成功，清掉 pending（取消 isThinking）
  if (pendingRequestIdRef.current) {
    pendingRequestIdRef.current = null;
  }
}, [ttsMessages]);
```

確認：原 L97-112 useEffect（依賴 `lastTtsAt, lastTtsText`）已刪除。

- [ ] **Step 4.4: 加 bubble 樣式（P1-1d + Phase 2-mini source 三色）**

找到渲染 bubble 的 JSX。為 assistant message 加 className 條件：

```tsx
{messages.map((m) => {
  if (m.role !== "assistant") return <UserBubble key={m.id} ... />;

  // P1-1d + Phase 2-mini variant + source styling
  let className = "rounded-lg px-3 py-2 max-w-[80%]";
  if (m.source === "skill_say") {
    className += " bg-emerald-100 text-emerald-900";  // 綠 = skill SAY
  } else if (m.source === "say_canned") {
    className += " bg-orange-100 text-orange-900";    // 橙 = canned fallback
  } else if (m.source === "chat_reply" || m.variant === "pending") {
    className += " bg-slate-200 text-slate-900";      // 一般灰 = chat reply / pending
  } else {
    className += " bg-slate-100 text-slate-700 opacity-90";  // 淡灰 = spontaneous (no source)
  }

  return (
    <div key={m.id} className={className}>
      {m.variant === "spontaneous" && !m.source && (
        <span className="mr-1 opacity-60">⏰</span>
      )}
      {m.text}
    </div>
  );
})}
```

注意：Tailwind class 名要對齊 frontend 既有 design-tokens；如果用 shadcn/ui 主題，請改成對應 tokens。

- [ ] **Step 4.5: dev server 啟動 + 手動驗**

```bash
cd /home/roy422/newLife/elder_and_dog
bash pawai-studio/start.sh  # mock server :8001 + frontend :3000
```

開瀏覽器到 `http://localhost:3000/studio`，用 Studio Skill Buttons 觸發 `self_introduce`，確認：
1. 10 步 SAY 都顯示在 ChatPanel
2. 沒 pending request 時觸發 → spontaneous 樣式（淡灰）
3. 文字輸入「介紹一下」→ pending 樣式（一般灰）

- [ ] **Step 4.6: Commit**

```bash
git add pawai-studio/frontend/hooks/use-event-stream.ts pawai-studio/frontend/components/chat/chat-panel.tsx
git commit -m "feat(studio): P1-1b/c/d ChatPanel subscribes ttsMessages

- use-event-stream tts case appends to ttsMessages with id/source
- ChatPanel useEffect on ttsMessages.length, append all unseen
- pendingRequestIdRef redefined: manages isThinking only, no display gate
- Bubble variant: pending (slate-200) vs spontaneous (slate-100 + clock icon)

All PawAI utterances now visible in ChatPanel regardless of pending state.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-1
"
```

---

## Task 5: P1-1 Client-Side Rate-Limit (Spontaneous Only)

**Files:**
- Modify: `pawai-studio/frontend/stores/state-store.ts` (`appendTtsMessage` 加 rate-limit)
- Test: `pawai-studio/frontend/stores/__tests__/state-store.test.ts`

**背景**：5/10-12 P2-1 attention policy 還沒上線時，spontaneous TTS 可能洪水。同 source 5s 內最多 1 條 append；不擋 user pending / safety / stop。

- [ ] **Step 5.1: 寫 failing test**

加到 `state-store.test.ts`：

```typescript
describe("ttsMessages rate-limit", () => {
  beforeEach(() => {
    useStateStore.setState({ ttsMessages: [] });
  });

  it("rate-limits same source within 5s window", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "看到杯子", timestamp: 1000, origin: "tts", source: "object_remark" });
    append({ id: "2", text: "看到椅子", timestamp: 2000, origin: "tts", source: "object_remark" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });

  it("allows same source after 5s", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "看到杯子", timestamp: 1000, origin: "tts", source: "object_remark" });
    append({ id: "2", text: "看到椅子", timestamp: 7000, origin: "tts", source: "object_remark" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);
  });

  it("never rate-limits chat_reply (pending user reply)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "嗨", timestamp: 1000, origin: "tts", source: "chat_reply" });
    append({ id: "2", text: "好啊", timestamp: 1500, origin: "tts", source: "chat_reply" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);
  });

  it("never rate-limits skill_say (active skill SAY steps)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "我是 PawAI", timestamp: 1000, origin: "tts", source: "skill_say" });
    append({ id: "2", text: "會看臉聽聲", timestamp: 1500, origin: "tts", source: "skill_say" });
    append({ id: "3", text: "隨時跟我互動", timestamp: 2000, origin: "tts", source: "skill_say" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(3);
  });

  it("rate-limits no-source spontaneous (alert/object_remark/greet)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "陌生人警示", timestamp: 1000, origin: "tts" });
    append({ id: "2", text: "再次警示", timestamp: 2000, origin: "tts" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });
});
```

- [ ] **Step 5.2: 跑 test 確認 fail**

```bash
cd pawai-studio/frontend
npx vitest run stores/__tests__/state-store.test.ts -t rate-limit
```

預期：FAIL（rate-limit 邏輯尚未實作）

- [ ] **Step 5.3: 改 `appendTtsMessage` 加 rate-limit**

```typescript
// state-store.ts:

// 不擋的 source 白名單
const RATE_LIMIT_BYPASS = new Set(["chat_reply", "skill_say"]);
const RATE_LIMIT_WINDOW_MS = 5000;

appendTtsMessage: (msg) => set((state) => {
  // dedup by id
  if (state.ttsMessages.some((m) => m.id === msg.id)) {
    return state;
  }

  // rate-limit: spontaneous (no source) or unspecified spontaneous source
  // bypass: chat_reply (pending reply) / skill_say (active skill SAY)
  const isBypass = msg.source && RATE_LIMIT_BYPASS.has(msg.source);
  if (!isBypass) {
    const sourceKey = msg.source || "spontaneous";
    const recentSame = state.ttsMessages
      .filter((m) => (m.source || "spontaneous") === sourceKey)
      .slice(-1)[0];
    if (recentSame && msg.timestamp - recentSame.timestamp < RATE_LIMIT_WINDOW_MS) {
      // silently drop
      return state;
    }
  }

  const next = [...state.ttsMessages, msg];
  if (next.length > 200) {
    return { ttsMessages: next.slice(next.length - 200) };
  }
  return { ttsMessages: next };
}),
```

- [ ] **Step 5.4: 跑 test 確認 pass**

```bash
npx vitest run stores/__tests__/state-store.test.ts
```

預期：所有 test (Task 3 + Task 5) 全 PASS。

- [ ] **Step 5.5: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add pawai-studio/frontend/stores/state-store.ts pawai-studio/frontend/stores/__tests__/state-store.test.ts
git commit -m "feat(studio): P1-1 client-side rate-limit for spontaneous TTS

Same-source spontaneous TTS rate-limited to 1 per 5s window.
Bypass: chat_reply (pending user reply) and skill_say (active skill SAY).

Bridges 5/10-12 gap before P2-1 attention policy ships, prevents object_remark
flood when 5+ objects detected. Belt-and-suspenders kept post-P2-1.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-1 spam scroll
"
```

---

## Task 6: Phase 2-mini build_plan() Source 注入

**Files:**
- Modify: `interaction_executive/interaction_executive/skill_contract.py` (`build_plan()` SAY step args 塞 source)
- Test: `interaction_executive/test/test_skill_contract.py` 或現有 plan test 檔

**背景**：首選方案 — `build_plan()` 生成 SAY step 時直接塞 `args["source"]`，dispatch 階段不用「猜」。三類映射：`chat_reply` / `say_canned` / 其他 → `skill_say`。

- [ ] **Step 6.1: 找 build_plan() 與 SAY step 生成位置**

```bash
grep -n "def build_plan\|ExecutorKind.SAY\|SkillStep" interaction_executive/interaction_executive/skill_contract.py | head -30
```

- [ ] **Step 6.2: 寫 failing test**

加到適當 test 檔（推測 `interaction_executive/test/test_skill_contract.py`，若無則建立）：

```python
def test_build_plan_chat_reply_source():
    """chat_reply skill SAY step gets source='chat_reply'."""
    from interaction_executive.interaction_executive.skill_contract import build_plan

    plan = build_plan(skill="chat_reply", args={"text": "嗨"})
    say_steps = [s for s in plan.steps if s.executor.value == "SAY"]
    assert len(say_steps) >= 1
    assert say_steps[0].args.get("source") == "chat_reply"


def test_build_plan_say_canned_source():
    """say_canned SAY step gets source='say_canned'."""
    from interaction_executive.interaction_executive.skill_contract import build_plan

    plan = build_plan(skill="say_canned", args={"text": "我聽不太懂"})
    say_steps = [s for s in plan.steps if s.executor.value == "SAY"]
    assert say_steps[0].args.get("source") == "say_canned"


def test_build_plan_other_skill_source():
    """Other skill (self_introduce / wave_hello) SAY steps get source='skill_say'."""
    from interaction_executive.interaction_executive.skill_contract import build_plan

    plan = build_plan(skill="self_introduce")
    say_steps = [s for s in plan.steps if s.executor.value == "SAY"]
    assert len(say_steps) >= 1
    for step in say_steps:
        assert step.args.get("source") == "skill_say"


def test_build_plan_preserves_existing_args():
    """Existing args (like input_origin) preserved alongside source injection."""
    from interaction_executive.interaction_executive.skill_contract import build_plan

    plan = build_plan(skill="chat_reply", args={"text": "嗨", "input_origin": "studio_text"})
    say_steps = [s for s in plan.steps if s.executor.value == "SAY"]
    assert say_steps[0].args.get("input_origin") == "studio_text"
    assert say_steps[0].args.get("source") == "chat_reply"
```

- [ ] **Step 6.3: 跑 test 確認 fail**

```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest interaction_executive/test/test_skill_contract.py -v -k source
```

預期：FAIL（source 欄位尚未注入）

- [ ] **Step 6.4: 改 `build_plan()` 注入 source**

在 `build_plan()` 找到組裝 SAY step 的迴圈處，加 source 推斷：

```python
def _resolve_say_source(skill_name: str) -> str:
    """Map skill name to TTS source classification for ChatPanel CSS routing."""
    if skill_name == "chat_reply":
        return "chat_reply"
    if skill_name == "say_canned":
        return "say_canned"
    return "skill_say"


def build_plan(skill: str, args: dict | None = None, ...) -> SkillPlan:
    args = dict(args or {})
    contract = SKILL_REGISTRY[skill]
    source = _resolve_say_source(skill)

    steps = []
    for tmpl in contract.steps:
        new_args = dict(tmpl.args)
        # 模板替換 (text_template / name_template) 既有邏輯保留
        # ...

        # SAY step 注入 source
        if tmpl.executor == ExecutorKind.SAY:
            new_args.setdefault("source", source)
            # input_origin 從外層 args 透傳（既有邏輯）
            if "input_origin" in args:
                new_args["input_origin"] = args["input_origin"]

        steps.append(SkillStep(executor=tmpl.executor, args=new_args))

    return SkillPlan(steps=steps, ...)
```

注意：`setdefault` 確保模板若已寫死 source 不被覆蓋。

- [ ] **Step 6.5: 跑 test 確認 pass + regression**

```bash
python3 -m pytest interaction_executive/test/ -v
```

預期：4 個新 test PASS，原有 test 不 regression。

- [ ] **Step 6.6: Commit**

```bash
git add interaction_executive/interaction_executive/skill_contract.py interaction_executive/test/test_skill_contract.py
git commit -m "feat(executive): Phase 2-mini inject source into SAY step args

build_plan() now sets args['source'] for SAY steps:
  chat_reply → 'chat_reply'
  say_canned → 'say_canned'
  others (self_introduce / wave_hello / etc) → 'skill_say'

Enables ChatPanel CSS routing without dispatch-time guessing.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-1 Phase 2-mini
"
```

---

## Task 7: IE-node Envelope 加 source 欄位

**Files:**
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py:185-194`
- Test: 同檔 unit test（找現有 `test_interaction_executive_node.py` 加 case）

**背景**：IE-node `_dispatch_step` SAY 在發 `/tts` 時，把 `args.source` 從 step 傳到 envelope。

- [ ] **Step 7.1: 讀現有 SAY dispatch 邏輯**

```bash
sed -n '180,200p' interaction_executive/interaction_executive/interaction_executive_node.py
```

- [ ] **Step 7.2: 寫 failing test**

加到 `interaction_executive/test/test_interaction_executive_node.py`：

```python
def test_say_dispatch_includes_source_in_envelope():
    """SAY step with args.source publishes JSON envelope including source field."""
    from interaction_executive.interaction_executive.skill_contract import (
        SkillStep, ExecutorKind
    )

    node = _build_test_node()  # existing helper
    step = SkillStep(
        executor=ExecutorKind.SAY,
        args={"text": "我來扭給你看", "source": "skill_say", "input_origin": "studio_text"},
    )

    # Mock pub
    captured = []
    node._pub_tts.publish = lambda msg: captured.append(msg.data)

    node._dispatch_step(plan=Mock(), step=step)

    assert len(captured) == 1
    envelope = json.loads(captured[0])
    assert envelope["text"] == "我來扭給你看"
    assert envelope["source"] == "skill_say"
    assert envelope["input_origin"] == "studio_text"


def test_say_dispatch_plain_text_no_source():
    """SAY step without source/input_origin publishes plain text (backward compat)."""
    from interaction_executive.interaction_executive.skill_contract import (
        SkillStep, ExecutorKind
    )

    node = _build_test_node()
    step = SkillStep(executor=ExecutorKind.SAY, args={"text": "嗨"})

    captured = []
    node._pub_tts.publish = lambda msg: captured.append(msg.data)
    node._dispatch_step(plan=Mock(), step=step)

    assert captured[0] == "嗨"  # plain text, no JSON
```

- [ ] **Step 7.3: 跑 test 確認 fail**

```bash
python3 -m pytest interaction_executive/test/test_interaction_executive_node.py -v -k source
```

預期：FAIL（envelope 不含 source）

- [ ] **Step 7.4: 改 IE-node SAY dispatch 加 source**

`interaction_executive_node.py:185-194` 改為：

```python
# SAY steps (no input_origin AND no source) keep byte-identical wire format.
input_origin = step.args.get("input_origin")
source = step.args.get("source")
msg = String()
if input_origin or source:
    envelope = {"text": text}
    if input_origin:
        envelope["input_origin"] = input_origin
    if source:
        envelope["source"] = source
    msg.data = json.dumps(envelope, ensure_ascii=False)
else:
    msg.data = text
self._pub_tts.publish(msg)
return True, "ok"
```

- [ ] **Step 7.5: 跑 test 確認 pass + regression**

```bash
python3 -m pytest interaction_executive/test/ -v
```

預期：兩個新 test PASS，原有 test 不 regression（plain text path 仍走純文字）。

- [ ] **Step 7.6: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_executive_node.py interaction_executive/test/test_interaction_executive_node.py
git commit -m "feat(executive): Phase 2-mini publish source field in /tts envelope

SAY step args.source (set by build_plan in Task 6) now flows into JSON envelope.
Gateway will parse and forward to Studio for ChatPanel CSS routing.

Backward compat: SAY without source AND without input_origin still publishes plain text.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-1 Phase 2-mini
"
```

---

## Task 8: Jetson Smoke Test (Wave 0 + P1-1 整段)

**Files:** 無修改，純驗證

**目的**：把 Task 1-7 的改動部署到 Jetson 跑端到端。

- [ ] **Step 8.1: rsync 同步 + colcon build**

```bash
ssh jetson-nano "cd ~/elder_and_dog && git pull && colcon build --packages-select speech_processor interaction_executive --symlink-install"
```

- [ ] **Step 8.2: 啟 demo tmux**

```bash
ssh jetson-nano "bash ~/elder_and_dog/scripts/start_full_demo_tmux.sh"
```

- [ ] **Step 8.3: 開瀏覽器 Studio**

筆電：`http://jetson-nano:3000/studio`（或對應 IP）

- [ ] **Step 8.4: 5 個 smoke 案例**

| 案例 | 操作 | 預期 |
|---|---|---|
| 1. 跳句修復 | Studio 文字輸入「講個故事」（5 句故事） | TTS 播完整 5 句，無跳句；若有 chunk fail 直接走 edge-tts fallback |
| 2. Studio 文字 chat_reply 顯示 | 輸入「介紹一下」 | ChatPanel 顯示一般灰氣泡（pending → 配對到 reply） |
| 3. Skill button self_introduce | 按 self_introduce 按鈕 | ChatPanel 顯示 3 條綠氣泡（skill_say）|
| 4. say_canned fallback | 斷 OpenRouter tunnel 後輸入「介紹一下」 | 1500ms 後 ChatPanel 顯示橙氣泡「我聽不太懂」（say_canned） |
| 5. spontaneous rate-limit | 帶 5 個物體入鏡 | 1 分鐘內最多 ~12 條 object_remark 氣泡（5s 1 條 × 60s）|

- [ ] **Step 8.5: 收集驗收紀錄**

把 5 個案例結果寫入 `docs/pawai-brain/dev-logs/2026-05-XX-wave0-p11-smoke.md`（XX = 實際日期）。

- [ ] **Step 8.6: Commit smoke log**

```bash
git add docs/pawai-brain/dev-logs/
git commit -m "docs(dev-log): Wave 0 + P1-1 Jetson smoke test results

5 smoke cases: chunk fallback / chat_reply bubble / skill_say green /
say_canned orange / object_remark rate-limit.

Wave 0 + P1-1 observability foundation ready for Wave 1 persona/attention work.
"
```

---

## Self-Review

**Spec coverage**:
- ✅ P0-1 silent-skip → Task 1 (all-or-nothing)
- ✅ P0-2 envelope parse → Task 2 (gateway helper + parse)
- ✅ P1-1a ttsMessages array → Task 3
- ✅ P1-1b ChatPanel listen + append → Task 4
- ✅ P1-1c pendingRequestIdRef redefine → Task 4 (in same effect)
- ✅ P1-1d pending vs spontaneous styling → Task 4
- ✅ P1-1 client-side rate-limit → Task 5
- ✅ Phase 2-mini source injection → Tasks 6 + 7
- ✅ Smoke test → Task 8

**Placeholder scan**: 所有 step 含實際 code / command / 預期輸出。test 內容完整可跑。

**Type consistency**:
- `TtsMessage.source` 為 `string | undefined`（state-store + use-event-stream + ChatPanel 一致）
- `args["source"]` 在 Python 一律 string（`build_plan` + IE-node 一致）
- `_resolve_say_source` 命名在 spec + plan 一致

**File path consistency**:
- frontend test 路徑 `pawai-studio/frontend/stores/__tests__/state-store.test.ts`（Task 3 CREATE，Task 5 MODIFY）
- IE-node test 推測 `interaction_executive/test/test_interaction_executive_node.py`（Task 7 假設存在；若不存在 Task 7 step 7.2 改 CREATE）

**潛在風險**：
- Task 4 ChatPanel CSS Tailwind class name 若 frontend 用 design-tokens 抽象，要對齊既有 token（plan 已 flag）
- Task 7 假設 `interaction_executive/test/test_interaction_executive_node.py` 存在；executor 若用其他 test 檔名請調整

---

## 預期完成時間

| Task | 工時估 |
|---|---|
| 1. P0-1 TTS silent-skip | 1h |
| 2. P0-2 Gateway envelope | 1h |
| 3. P1-1a state-store ring buffer | 1h |
| 4. P1-1b/c/d ChatPanel + style | 2h |
| 5. P1-1 rate-limit | 1h |
| 6. build_plan source 注入 | 1h |
| 7. IE-node envelope source | 0.5h |
| 8. Jetson smoke test | 1h |
| **總計** | **~8.5h（約 1 天）** |

可在 5/10 一天內完成 Wave 0 + P1-1 全部，5/11 進 Wave 1（persona / ASR / context / attention）。
