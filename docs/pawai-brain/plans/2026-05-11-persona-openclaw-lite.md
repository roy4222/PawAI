# Branch B — Persona OpenClaw-lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 LLM persona 從「功能型客服」拆成「住在家裡的小狗」— persona 拆 5 檔 + conversation mode classifier + capability lazy inject + 4 桶白名單 + identity few-shot。解 issue 2（LLM 死板）+ issue 3（不主動鏈式）。

**Architecture:** OpenClaw-lite 抓兩個核心設計：(L7 Workspace Files) persona 拆 5 檔（IDENTITY/STYLE/CAPABILITIES/EXAMPLES/OUTPUT），base 啟動載 4 檔，CAPABILITIES.md lazy inject；(L8 Bootstrap Hook) `_build_user_message` 按 conversation mode 條件注入 capability 和 mode hint。LangGraph node 介面不變；capability_context 仍每輪 build 給 skill_policy_gate v2 用，lazy 只在 prompt-level。

**Tech Stack:** Python 3.10 + ROS2 Humble + pytest（pawai_brain / interaction_executive）；Markdown（personas/v1/）。

**Spec 來源:** `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` P1-4 OpenClaw-lite Persona Architecture（1A-1I 共 9 子任務）。

**前置依賴**: Branch A (`feat/wave0-p11-observability`) 已 merged to main。

---

## File Structure

**新建檔案**:

```
pawai_brain/personas/v1/
├── IDENTITY.md       # 你是誰（70/20/10 小狗童心守護者、靈魂、住在哪）~40 行
├── STYLE.md          # 怎麼說話（DO/AVOID、長度、對話記憶、環境）~60 行
├── CAPABILITIES.md   # 你會什麼（17 技能 + 9 能力 bullet）~50 行（lazy inject）
├── EXAMPLES.md       # 18-22 few-shot（identity 6-8 + wiggle/stretch 9 + 負例 3）~80 行
└── OUTPUT.md         # JSON schema + audio tag + skill proposal 規則 ~40 行

pawai_brain/pawai_brain/nodes/mode_classifier.py   # NEW — 5 mode rule-based classifier
pawai_brain/test/test_mode_classifier.py           # NEW — 8 unit tests
```

**修改檔案**:

```
pawai_brain/setup.py                                          # ★ 加 data_files install personas/v1/*.md (Roy review #1)
pawai_brain/launch/pawai_conversation_graph.launch.py:20-40   # llm_persona_file default → get_package_share_directory; temperature 0.2 → 0.6
pawai_brain/pawai_brain/conversation_graph_node.py:67-126     # _INLINE_PERSONA + _load_persona file/dir 雙模 + _build_user_message lazy inject + face state subscription
pawai_brain/pawai_brain/nodes/world_state_builder.py          # current_speaker field（路徑修正：實際在 nodes/，不是 pawai_brain 直下）
pawai_brain/pawai_brain/capability/world_snapshot.py          # WorldSnapshot 加 current_speaker 欄位（給 nodes/world_state_builder.py 寫入）
pawai_brain/pawai_brain/graph.py:34-47                        # 加 mode_classifier 在 input 和 safety_gate 之間（實際 entry 是 "input" 不是 "input_normalizer"）
pawai_brain/pawai_brain/state.py                              # ConversationState 加 mode field
interaction_executive/interaction_executive/brain_node.py:447-456   # LLM_PROPOSAL_EXECUTE 4 桶
interaction_executive/interaction_executive/skill_policy_gate.py:18-27   # LLM_PROPOSABLE_SKILLS 移除 greet_known_person
scripts/start_pawai_brain_tmux.sh                             # ★ 整窗改：移除 llm_bridge_node window，新增 conversation_graph_node window（拆 Task 9 獨立做 + smoke）
tools/llm_eval/run_eval.py                                    # 1I A/B eval 加 case
```

**Roy 5/9 review 修正**：
- ❶ `setup.py data_files` 必須裝 `share/pawai_brain/personas/v1/*.md`，否則 colcon build 過但 runtime 從 install/share 跑時找不到
- ❷ launch default 用 `get_package_share_directory("pawai_brain")` + `personas/v1`，**不**用 `Path(__file__).parent.parent`（source path ≠ install path）
- ❸ graph entry 是 `"input"` 不是 `"input_normalizer"`；mode_classifier 接在 `input → mode_classifier → safety_gate`
- ❹ world_state_builder 實際在 `nodes/` 子資料夾；`WorldSnapshot` 在 `capability/world_snapshot.py`
- ❺ tmux script 切到 conversation_graph_node 是 runtime topology 變更，獨立 Task 9 做 + smoke
- ❻ test helper `_build_test_node` 用 `object.__new__(ConversationGraphNode)` + 手 patch logger，避免啟動 ROS context

---

## Task 1: 1A — Persona Loader file/dir 雙模

**Files**:
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py:295-315` (`_load_persona`)
- Modify: `pawai_brain/launch/pawai_conversation_graph.launch.py:20-22` (`llm_persona_file` default 用 `get_package_share_directory`)
- Modify: `pawai_brain/setup.py:13-17` (data_files 裝 personas/v1/*.md — Roy review #1)
- Test: `pawai_brain/test/test_conversation_graph_node.py`（新建或現有）

**注意（Roy review）**：
- tmux script 改動拆到 **Task 9** 獨立做 + smoke，這個 task 只動 loader
- launch default **不**用 `Path(__file__).parent.parent`（source 路徑 ≠ colcon install 路徑），用 `get_package_share_directory("pawai_brain") / "personas" / "v1"`
- `_build_test_node` 用 `object.__new__(ConversationGraphNode)` + monkeypatch `get_logger` 為 fake logger，避免啟 ROS node

- [ ] **Step 1.1: 讀現況**

```bash
sed -n '60,80p;285,320p' pawai_brain/pawai_brain/conversation_graph_node.py
sed -n '15,45p' pawai_brain/launch/pawai_conversation_graph.launch.py
sed -n '12,20p' scripts/start_pawai_brain_tmux.sh
```

- [ ] **Step 1.2: 寫 failing tests**

```python
def test_load_persona_legacy_file_mode(tmp_path):
    """Legacy persona.txt single file mode — backward compat."""
    persona_file = tmp_path / "persona.txt"
    persona_file.write_text("legacy persona content", encoding="utf-8")

    node = _build_test_node(llm_persona_file=str(persona_file))
    assert node._system_prompt == "legacy persona content"
    assert node._capabilities_md == ""


def test_load_persona_directory_mode_5_files(tmp_path):
    """Directory mode: 5 files required, base concat 4, CAPABILITIES cached separately."""
    persona_dir = tmp_path / "personas" / "v1"
    persona_dir.mkdir(parents=True)
    for fname, content in [
        ("IDENTITY.md", "id_content"),
        ("STYLE.md", "style_content"),
        ("OUTPUT.md", "output_content"),
        ("EXAMPLES.md", "examples_content"),
        ("CAPABILITIES.md", "cap_content"),
    ]:
        (persona_dir / fname).write_text(content, encoding="utf-8")

    node = _build_test_node(llm_persona_file=str(persona_dir))
    assert "id_content" in node._system_prompt
    assert "style_content" in node._system_prompt
    assert "output_content" in node._system_prompt
    assert "examples_content" in node._system_prompt
    assert "cap_content" not in node._system_prompt  # CAPABILITIES not in base
    assert node._capabilities_md == "cap_content"


def test_load_persona_directory_mode_missing_file_raises(tmp_path):
    """Missing required file → FileNotFoundError raise (not silent fallback)."""
    persona_dir = tmp_path / "personas" / "v1"
    persona_dir.mkdir(parents=True)
    (persona_dir / "IDENTITY.md").write_text("id", encoding="utf-8")
    # Missing STYLE / OUTPUT / EXAMPLES / CAPABILITIES

    with pytest.raises(FileNotFoundError):
        _build_test_node(llm_persona_file=str(persona_dir))
```

- [ ] **Step 1.3: 跑 test 確認 fail**

```bash
python3 -m pytest pawai_brain/test/test_conversation_graph_node.py -v -k load_persona
```

預期：FAIL（directory mode 尚未實作 / FileNotFoundError 不 raise）

- [ ] **Step 1.4: 改 `_load_persona()` 雙模 loader**

```python
import hashlib
from pathlib import Path

def _load_persona(self) -> str:
    path_str = (self.llm_persona_file or "").strip()
    if not path_str:
        return _INLINE_PERSONA
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    if path.is_file():
        # Legacy mode: single persona.txt (backward compat)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.get_logger().warning(
                f"[persona] file load failed ({path}): {exc} — using inline persona"
            )
            return _INLINE_PERSONA
        if not content.strip():
            self.get_logger().warning(f"[persona] file empty ({path}) — using inline persona")
            return _INLINE_PERSONA
        self._capabilities_md = ""  # legacy mode: no separate cache
        self.get_logger().info(f"[persona] loaded file {path} ({len(content)} bytes)")
        return content

    if path.is_dir():
        # New mode: directory; 5 files required, base concat 4
        REQUIRED = ["IDENTITY.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md", "CAPABILITIES.md"]
        BASE_ORDER = ["IDENTITY.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md"]
        contents = {}
        for fname in REQUIRED:
            f = path / fname
            if not f.is_file():
                self.get_logger().error(f"[persona] missing required {fname} in {path}")
                raise FileNotFoundError(f)
            contents[fname] = f.read_text(encoding="utf-8")

        base = "\n\n".join(contents[f] for f in BASE_ORDER)
        self._capabilities_md = contents["CAPABILITIES.md"]
        self.get_logger().info(
            f"[persona] loaded directory {path}, "
            f"5 files verified, base 4 files concat ({len(base)} chars), "
            f"CAPABILITIES.md cached separately ({len(self._capabilities_md)} chars), "
            f"base_sha={hashlib.sha256(base.encode()).hexdigest()[:12]}"
        )
        return base

    self.get_logger().error(f"[persona] path not file or dir: {path}")
    raise FileNotFoundError(path)
```

`__init__` 加：
```python
self._capabilities_md: str = ""  # set by _load_persona; used by _build_user_message lazy inject
```

- [ ] **Step 1.5: 改 setup.py 安裝 personas + launch default**

**setup.py**（必須先做，否則 launch 找不到 install/share/pawai_brain/personas/v1/）：

```python
# pawai_brain/setup.py
from glob import glob

# 既有 data_files 加：
data_files=[
    ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
    (f"share/{package_name}", ["package.xml"]),
    (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    (f"share/{package_name}/config", glob("config/*.yaml")),
    (f"share/{package_name}/personas/v1", glob("personas/v1/*.md")),  # ← NEW
],
```

**`pawai_conversation_graph.launch.py` L20-22**：

```python
from ament_index_python.packages import get_package_share_directory
from pathlib import Path

# 在 generate_launch_description() 內：
default_persona_dir = str(Path(get_package_share_directory("pawai_brain")) / "personas" / "v1")

DeclareLaunchArgument(
    "llm_persona_file",
    default_value=default_persona_dir,
    description="Path to persona file (legacy) or directory (5 files: IDENTITY/STYLE/OUTPUT/EXAMPLES/CAPABILITIES)",
),
```

**tmux script 不在這個 task 改**（拆到 Task 9 獨立做 + smoke `/brain/chat_candidate`）

- [ ] **Step 1.6: 跑 test 確認 pass**

```bash
python3 -m pytest pawai_brain/test/test_conversation_graph_node.py -v
```

- [ ] **Step 1.7: Commit**

```bash
git add pawai_brain/pawai_brain/conversation_graph_node.py \
        pawai_brain/launch/pawai_conversation_graph.launch.py \
        pawai_brain/setup.py \
        pawai_brain/test/test_conversation_graph_node.py
git commit -m "feat(brain): 1A persona loader file/dir dual mode

Legacy persona.txt single file → backward compat (returns whole file).
New directory mode → 5 files required (IDENTITY/STYLE/OUTPUT/EXAMPLES/CAPABILITIES);
base prompt concat 4 files; CAPABILITIES.md cached in self._capabilities_md
for lazy inject (Task 4 1D).

Missing file → FileNotFoundError (no silent fallback).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1A
"
```

---

## Task 2: 1B — Persona 5 檔拆解（純機械搬段落）

**Files**:
- Create: `pawai_brain/personas/v1/IDENTITY.md`
- Create: `pawai_brain/personas/v1/STYLE.md`
- Create: `pawai_brain/personas/v1/CAPABILITIES.md`
- Create: `pawai_brain/personas/v1/EXAMPLES.md`
- Create: `pawai_brain/personas/v1/OUTPUT.md`

**背景**：純機械搬。`tools/llm_eval/persona.txt` 184 行內容拆到 5 檔，**刪 L24-36 9 條 bullet 列表**（移到 CAPABILITIES.md）+ **刪 L65「自我介紹 2-4 句」字數規則**。其他內容 90% 保留。

- [ ] **Step 2.1: 讀原 persona.txt 確認段落範圍**

```bash
cat -n tools/llm_eval/persona.txt
```

確認段落對應（spec 表格）：
- L1-23 → IDENTITY.md
- L24-36 → CAPABILITIES.md（移出！）
- L38-55 → STYLE.md（個性原則 DO/AVOID）
- L62-68 → STYLE.md（長度規則，**刪 L65 自介 2-4 句這條**）
- L69-82 → STYLE.md（對話記憶）
- L83-88 → STYLE.md（環境資訊）
- L89-114 → CAPABILITIES.md（17 技能表）
- L115-118 → OUTPUT.md（audio tag）
- L119-127 → OUTPUT.md（JSON schema）
- L128-165 → EXAMPLES.md（13 既有 few-shot；Task 6 1F 補到 18-22）
- L166-185 → OUTPUT.md（capability_context 規則 10 條）

- [ ] **Step 2.2: 建 IDENTITY.md**

從 persona.txt L1-23 複製，加標題 + 文件 metadata：

```markdown
# IDENTITY.md — PawAI 身份核心

> personas/v1 base prompt 第 1 檔，永遠載入。
> 描述 PawAI 是誰、靈魂、住在哪。**不講「我會什麼」**（那在 CAPABILITIES.md）。

[原 persona.txt L1-23 內容]
```

- [ ] **Step 2.3: 建 STYLE.md**

從 L38-88 拼接（DO/AVOID + 長度 + 對話記憶 + 環境），**刪掉 L65「自我介紹：稍長，2-4 句」這行**：

```markdown
# STYLE.md — PawAI 說話風格

> personas/v1 base prompt 第 2 檔，永遠載入。
> 描述怎麼說話、避免什麼、長度情境決定、對話記憶用法、環境帶入。

[原 persona.txt L38-83 內容，刪 L65「自我介紹：稍長，2~4 句」]
[L83-88 環境資訊段]
```

- [ ] **Step 2.4: 建 CAPABILITIES.md**

從 L24-36 + L89-114 拼接（9 能力 bullet + 17 技能表），加說明：

```markdown
# CAPABILITIES.md — PawAI 能力清單

> personas/v1 第 3 檔。**Lazy inject** — 只在 mode = capability_question / action_request 時注入 user message。
> 一般聊天時 PawAI 看不到此檔，避免 anchor 到「能力選單」模式變工具人。

[原 persona.txt L24-36 9 條能力 bullet]
[原 persona.txt L89-114 17 技能表]
```

- [ ] **Step 2.5: 建 EXAMPLES.md（13 既有 few-shot，Task 6 補到 18-22）**

從 L128-165 複製：

```markdown
# EXAMPLES.md — PawAI Few-shot 範例

> personas/v1 base prompt 第 4 檔，永遠載入（尾段，prefix-cache 友善）。
> 13 個既有範例；Task 6 1F 補 6-8 identity + 9 wiggle/stretch + 3 負例 → 21-23 個總計。

[原 persona.txt L128-165 內容]
```

- [ ] **Step 2.6: 建 OUTPUT.md**

從 L115-127 + L166-185 拼接：

```markdown
# OUTPUT.md — PawAI 輸出規範

> personas/v1 base prompt 第 5 檔，永遠載入。
> JSON schema + audio tag list + skill proposal 規則。**不混情緒文字**（情緒在 IDENTITY/STYLE）。

[原 persona.txt L115-118 audio tag list]
[原 persona.txt L119-127 JSON schema]
[原 persona.txt L166-185 capability_context 規則 10 條]
```

- [ ] **Step 2.7: 跑 1A test 驗 5 檔載入**

```bash
python3 -m pytest pawai_brain/test/test_conversation_graph_node.py::test_load_persona_directory_mode_5_files -v
```

預期：用真實 personas/v1 載入過。

- [ ] **Step 2.8: Commit**

```bash
git add pawai_brain/personas/v1/
git commit -m "feat(brain): 1B persona split into 5 files

Mechanical split of tools/llm_eval/persona.txt (184 lines) into:
  IDENTITY.md   — who you are (soul, 70/20/10, where you live)
  STYLE.md      — how you talk (DO/AVOID, length, memory, env)
  CAPABILITIES.md — what you can do (9 bullets + 17 skills, lazy inject)
  EXAMPLES.md   — 13 existing few-shot (Task 6 expands to 18-22)
  OUTPUT.md     — JSON schema + audio tag + skill proposal rules

Removed: L24-36 capability bullets from base (moved to CAPABILITIES);
L65 'self-intro 2-4 sentences' length rule (was forcing template).

Backward compat: legacy single persona.txt still works via _load_persona file mode.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1B
"
```

---

## Task 3: 1C — Conversation Mode Classifier

**Files**:
- Create: `pawai_brain/pawai_brain/nodes/mode_classifier.py`
- Create: `pawai_brain/test/test_mode_classifier.py`
- Modify: `pawai_brain/pawai_brain/state.py`（加 `mode` field）
- Modify: `pawai_brain/pawai_brain/graph.py`（加 mode_classifier node）

- [ ] **Step 3.1: 寫 failing tests**

```python
import pytest
from pawai_brain.pawai_brain.nodes.mode_classifier import classify_mode

@pytest.mark.parametrize("text,expected", [
    ("停！", "safety"),
    ("小心一點", "safety"),
    ("stop", "safety"),
    ("你是誰？", "identity"),
    ("介紹一下你自己", "identity"),
    ("你叫什麼", "identity"),
    ("你會什麼？", "capability_question"),
    ("有什麼功能", "capability_question"),
    ("能做什麼", "capability_question"),
    ("扭一下", "action_request"),
    ("伸個懶腰", "action_request"),
    ("揮個手", "action_request"),
    ("天氣好嗎", "chat"),
    ("我今天累了", "chat"),
])
def test_classify_mode(text, expected):
    assert classify_mode(text) == expected


def test_classify_mode_empty():
    assert classify_mode("") == "chat"
    assert classify_mode("   ") == "chat"
```

- [ ] **Step 3.2: 跑 test 確認 fail**

```bash
python3 -m pytest pawai_brain/test/test_mode_classifier.py -v
```

預期：ImportError（module 不存在）

- [ ] **Step 3.3: 實作 mode_classifier.py**

```python
"""Rule-based conversation mode classifier — OpenClaw-lite L8 hook lite.

Used by _build_user_message and _assemble_system_prompt to decide
whether to inject CAPABILITIES.md and capability_context JSON.
"""
import re
from typing import Final

# Order matters: safety > identity > capability_question > action_request > chat
MODE_PATTERNS: Final[list[tuple[str, str]]] = [
    ("safety",
     r"停|停止|不要動|別動|先不要動|小心|警告|危險|stop"),
    ("identity",
     r"你是誰|你叫什麼|介紹.*自己|你誰啊|你是\s*AI"),
    ("capability_question",
     r"你會什麼|你會啥|有什麼功能|能做什麼|會做啥|有哪些能力|功能有哪些"),
    ("action_request",
     r"扭|搖|伸|懶腰|揮|過來|坐下|跳舞|走|看[你我].*OK|比.*OK"),
]


def classify_mode(user_text: str) -> str:
    """Return one of: safety / identity / capability_question / action_request / chat."""
    text = (user_text or "").strip()
    if not text:
        return "chat"
    for mode, pattern in MODE_PATTERNS:
        if re.search(pattern, text):
            return mode
    return "chat"
```

- [ ] **Step 3.4: 跑 test 確認 pass**

```bash
python3 -m pytest pawai_brain/test/test_mode_classifier.py -v
```

預期：16 個 test PASS。

- [ ] **Step 3.5: 把 mode 加進 ConversationState + graph**

`state.py`:
```python
class ConversationState(TypedDict, total=False):
    # 既有 fields...
    mode: str  # safety / identity / capability_question / action_request / chat (default)
```

`graph.py` 在現有 `g.add_edge("input", "safety_gate")` 之前插 mode_classifier（Roy review #4 — graph entry 是 `"input"` 不是 `"input_normalizer"`）：

```python
from pawai_brain.pawai_brain.nodes.mode_classifier import classify_mode

def mode_classifier_node(state: ConversationState) -> ConversationState:
    state["mode"] = classify_mode(state.get("user_text", ""))
    state.setdefault("trace", []).append({
        "stage": "mode_classifier",
        "status": "ok",
        "detail": state["mode"],
    })
    return state

# graph.py 改動（既有 entry "input" 保留）：
g.add_node("mode_classifier", mode_classifier_node)
# 把 g.add_edge("input", "safety_gate") 改成：
g.add_edge("input", "mode_classifier")
g.add_edge("mode_classifier", "safety_gate")
```

- [ ] **Step 3.6: Commit**

```bash
git add pawai_brain/pawai_brain/nodes/mode_classifier.py \
        pawai_brain/test/test_mode_classifier.py \
        pawai_brain/pawai_brain/state.py \
        pawai_brain/pawai_brain/graph.py
git commit -m "feat(brain): 1C conversation mode classifier (5 modes)

Rule-based classifier (no LLM call): safety / identity /
capability_question / action_request / chat (default).

Inserted as graph node between input and safety_gate.
state.mode flows to _build_user_message (Task 4) for lazy inject.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1C
"
```

---

## Task 4: 1D — Capability Lazy Injection in `_build_user_message`

**Files**:
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py:75-126` (`_build_user_message`)
- Test: `pawai_brain/test/test_conversation_graph_node.py`（既有檔，加 cases）

- [ ] **Step 4.1: 寫 failing tests**

```python
def test_build_user_message_chat_mode_no_capability():
    """chat mode: capability_context not injected."""
    state = {
        "user_text": "今天天氣好",
        "mode": "chat",
        "source": "speech",
        "world_state": {"period": "下午", "time": "14:30", "weather": "晴 25°C"},
        "capability_context": {"capabilities": [...], "limits": [...]},
    }
    msg = _build_user_message(state)
    assert "[語音] 使用者說：「今天天氣好」" in msg
    assert "[環境] 台北 下午 14:30，外面 晴 25°C" in msg
    assert "[能力" not in msg  # CAPABILITIES not injected
    assert "[mode_hint]" not in msg


def test_build_user_message_identity_mode_with_hint_no_capability():
    """identity mode: mode_hint injected, CAPABILITIES not injected."""
    state = {
        "user_text": "你是誰",
        "mode": "identity",
        "source": "speech",
        "world_state": {},
        "capability_context": {"capabilities": [...]},
    }
    msg = _build_user_message(state)
    assert "[mode_hint]" in msg
    assert "不要列功能清單" in msg
    assert "[能力" not in msg


def test_build_user_message_capability_question_mode_injects_capabilities():
    """capability_question mode: CAPABILITIES.md + capability_context JSON injected."""
    node = _build_test_node()
    node._capabilities_md = "FAKE CAPABILITIES MD"
    state = {
        "user_text": "你會什麼",
        "mode": "capability_question",
        "source": "speech",
        "world_state": {},
        "capability_context": {"capabilities": [{"name": "wave_hello"}], "limits": [], "recent_skill_results": []},
    }
    msg = node._build_user_message(state)
    assert "[能力描述]" in msg
    assert "FAKE CAPABILITIES MD" in msg
    assert "[能力 runtime]" in msg


def test_build_user_message_action_request_mode_injects_capabilities():
    """action_request mode: CAPABILITIES + capability_context both injected."""
    node = _build_test_node()
    node._capabilities_md = "CAP MD"
    state = {
        "user_text": "扭一下",
        "mode": "action_request",
        "source": "speech",
        "world_state": {},
        "capability_context": {"capabilities": [{"name": "wiggle"}], "limits": [], "recent_skill_results": []},
    }
    msg = node._build_user_message(state)
    assert "[能力描述]" in msg
    assert "CAP MD" in msg


def test_build_user_message_label_uses_source():
    """source field controls [語音] vs [文字] label."""
    state_speech = {"user_text": "嗨", "mode": "chat", "source": "speech", "world_state": {}, "capability_context": {}}
    state_text = {"user_text": "嗨", "mode": "chat", "source": "text", "world_state": {}, "capability_context": {}}
    assert "[語音]" in _build_user_message(state_speech)
    assert "[文字]" in _build_user_message(state_text)


def test_build_user_message_includes_current_speaker():
    """world_state.current_speaker (set by Task 8 1H) injected as [眼前的人]."""
    state = {
        "user_text": "嗨",
        "mode": "chat",
        "source": "speech",
        "world_state": {"current_speaker": "Roy"},
        "capability_context": {},
    }
    msg = _build_user_message(state)
    assert "[眼前的人] Roy" in msg


def test_build_user_message_omits_unknown_speaker():
    """current_speaker == 'unknown' or absent → no [眼前的人] line."""
    state = {
        "user_text": "嗨",
        "mode": "chat",
        "source": "speech",
        "world_state": {"current_speaker": "unknown"},
        "capability_context": {},
    }
    msg = _build_user_message(state)
    assert "[眼前的人]" not in msg
```

- [ ] **Step 4.2: 跑 test 確認 fail**

```bash
python3 -m pytest pawai_brain/test/test_conversation_graph_node.py -v -k build_user_message
```

預期：FAIL（lazy inject 邏輯尚未實作）

- [ ] **Step 4.3: 改 `_build_user_message()`**

```python
def _build_user_message(self, state) -> str:
    text = (state.get("user_text") or "").strip()
    mode = state.get("mode") or "chat"
    source = state.get("source") or "speech"

    # 1E: source-based label
    label = "[語音]" if source == "speech" else "[文字]"
    parts = [f"{label} 使用者說：「{text}」"]

    # world_state — always inject
    ws = state.get("world_state") or {}
    if ws.get("period") or ws.get("time"):
        line = f"[環境] 台北 {ws.get('period', '')} {ws.get('time', '')}".rstrip()
        if ws.get("weather"):
            line += f"，外面 {ws['weather']}"
        parts.append(line)
    if ws.get("current_speaker") and ws["current_speaker"] != "unknown":
        parts.append(f"[眼前的人] {ws['current_speaker']}")

    # 1D: CAPABILITIES.md + capability_context JSON — lazy inject
    if mode in ("capability_question", "action_request"):
        if self._capabilities_md:
            parts.append("[能力描述]\n" + self._capabilities_md)
        cap = state.get("capability_context") or {}
        if cap:
            compact_caps = self._compact_capabilities(cap)  # 既有 helper
            cap_payload = {
                "capabilities": compact_caps,
                "limits": list(cap.get("limits") or []),
                "recent_skill_results": list(cap.get("recent_skill_results") or []),
            }
            parts.append("[能力 runtime] " + json.dumps(cap_payload, ensure_ascii=False))

    # mode hint — only for identity
    if mode == "identity":
        parts.append("[mode_hint] 使用者問你是誰。請從性格、生活、剛剛發生的事切入，不要列功能清單，除非他追問。")

    return "\n".join(parts)
```

- [ ] **Step 4.4: 跑 test 確認 pass + 不 regression**

```bash
python3 -m pytest pawai_brain/test/ -v
```

- [ ] **Step 4.5: Commit**

```bash
git add pawai_brain/pawai_brain/conversation_graph_node.py pawai_brain/test/test_conversation_graph_node.py
git commit -m "feat(brain): 1D capability lazy injection + 1E source label

_build_user_message lazy injects CAPABILITIES.md + capability_context JSON
only for capability_question / action_request modes.

identity mode adds [mode_hint] forbidding capability listing.
chat mode (default): no capability injection — LLM not anchored to tool-menu mode.

source field drives [語音] vs [文字] label (1E).
current_speaker inject as [眼前的人] (omit on 'unknown').

capability_context still built every turn for skill_policy_gate v2 (lazy is prompt-level only).
system prompt unchanged (llm_decision.configure interface preserved).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1D + 1E
"
```

---

## Task 5: 1E — Temperature 0.6 + Runtime Sanity

**Files**:
- Modify: `pawai_brain/launch/pawai_conversation_graph.launch.py:40` (temperature default)

- [ ] **Step 5.1: 改 launch arg default**

```python
DeclareLaunchArgument(
    "temperature",
    default_value="0.6",  # was 0.2
    description="LLM temperature (0.6 demo main; OpenClaw chat 0.7-1.0; balance JSON stability + naturalness)",
),
```

- [ ] **Step 5.2: Commit**

```bash
git add pawai_brain/launch/pawai_conversation_graph.launch.py
git commit -m "feat(brain): 1E temperature 0.2 → 0.6 + label source-based (in 1D)

OpenClaw chat models recommend 0.7-1.0; PawAI compromise 0.6 keeps
JSON schema stability + improves naturalness vs 0.2 (which forced
templated, deterministic answers).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1E
"
```

---

## Task 6: 1F — Identity Few-shot 補 6-8 個 + Wiggle/Stretch 9 個 + 負例 3 個

**Files**:
- Modify: `pawai_brain/personas/v1/EXAMPLES.md`

- [ ] **Step 6.1: 補 6-8 identity case 到 EXAMPLES.md**

在「Identity」section 加：

```markdown
## Identity Few-shot (Task 6 補)

### 短應答（5-12 字，閒聊接話用）
使用者：你是誰？
output: {"reply": "[playful] 我啊？住你家的小狗～", "skill": "self_introduce", "args": {}}

使用者：你叫什麼？
output: {"reply": "[curious] PawAI 啊。", "skill": "self_introduce", "args": {}}

### 中應答（15-25 字，第一次見的人 / 略陌生情境）
使用者：嗨，自我介紹一下？
output: {"reply": "[curious] 嗯～我是 PawAI，住在這個家裡，平常都在客廳看看。", "skill": "self_introduce", "args": {}}

### 長應答（30-50 字，使用者明確追問「你會什麼」/ 介紹詳細一點）
使用者：你會什麼？
output: {"reply": "[curious] 我會聽你講話、認得熟人、看你比手勢，偶爾還會發呆。", "skill": "chat_reply", "args": {}}

### 情境式（不從零介紹，從「剛剛發生的事」切入）
使用者：你都做啥？（剛被問過天氣後）
output: {"reply": "[whispers] 剛剛在看外面下雨耶。", "skill": "chat_reply", "args": {}}

### 反例（被打斷 / 第二次被問）
使用者：你又是誰？（5 分鐘前已介紹過）
output: {"reply": "[playful] 又問一次喔～就那隻狗啊。", "skill": "say_canned", "args": {}}

使用者：你是 AI 嗎？
output: {"reply": "[thinking] 我是 PawAI 啊，住這裡的小狗。", "skill": "self_introduce", "args": {}}

### 婉拒（做不到的事）
使用者：幫我倒水。
output: {"reply": "[playful] 我又沒有手怎麼倒啦，可是我可以陪你。", "skill": "chat_reply", "args": {}}
```

- [ ] **Step 6.2: 補 9 wiggle/stretch case + 3 負例**

```markdown
## Wiggle Few-shot
使用者：扭一下
output: {"reply": "[playful] 好啊！比個 OK 我就扭給你看", "skill": "wiggle", "args": {}}

使用者：你會什麼可愛動作
output: {"reply": "[curious] 我會扭屁股呀～比個 OK 就扭給你看", "skill": "wiggle", "args": {}}

使用者：比 OK 會怎樣
output: {"reply": "[excited] 比 OK 我就扭給你看", "skill": "wiggle", "args": {}}

## Stretch Few-shot
使用者：伸個懶腰
output: {"reply": "[playful] 好喔～比個 OK 我就伸個懶腰", "skill": "stretch", "args": {}}

使用者：你想不想動一下
output: {"reply": "[curious] 想動！比個 OK 我來伸展一下", "skill": "stretch", "args": {}}

使用者：給我看伸展
output: {"reply": "[playful] 好啊！比個 OK 我就伸給你看", "skill": "stretch", "args": {}}

## 負例
使用者：不要動 / 別扭了
output: {"reply": "[gentle] 好喔～我不動了", "skill": "chat_reply", "args": {}}

使用者：跳舞 / 後空翻
output: {"reply": "[thinking] 那個對我來說太難了啦...", "skill": "chat_reply", "args": {}}

使用者：幫我訂便當
output: {"reply": "[playful] 我又不是哆啦 A 夢，可是我可以陪你。", "skill": "chat_reply", "args": {}}
```

- [ ] **Step 6.3: Commit**

```bash
git add pawai_brain/personas/v1/EXAMPLES.md
git commit -m "feat(brain): 1F identity + wiggle/stretch + negatives few-shot

Identity 8 cases: short (5-12) / mid (15-25) / long (30-50) / contextual / negatives.
Wiggle 3 + Stretch 3 + Negatives 3 — every LLM-proposable skill ≥ 3 cases hard rule.

Resolves issue 3 (LLM not chaining): EXAMPLES teaches LLM to output 'skill: wiggle'
when user says '扭一下', triggering PendingConfirm flow.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1F
"
```

---

## Task 7: 1G — LLM 4 桶白名單

**Files**:
- Modify: `interaction_executive/interaction_executive/brain_node.py:447-456` (`LLM_PROPOSAL_EXECUTE`)
- Modify: `interaction_executive/interaction_executive/skill_policy_gate.py:18-27` (`LLM_PROPOSABLE_SKILLS`)
- Test: `interaction_executive/test/test_brain_rules.py` 加 cases

- [ ] **Step 7.1: 改 LLM_PROPOSAL_EXECUTE dict**

```python
LLM_PROPOSAL_EXECUTE = {
    # Bucket 1: execute (直接執行)
    "wave_hello": "execute",
    "sit_along": "execute",
    "careful_remind": "execute",
    "show_status": "execute",
    # Bucket 2: confirm (需 OK 手勢)
    "wiggle": "confirm",
    "stretch": "confirm",
    # Bucket 3: trace_only (只說明不執行)
    "self_introduce": "trace_only",
    "greet_known_person": "trace_only",  # was execute — Roy 5/9 review: 改由 face stable 觸發
    # Bucket 4 (block): 不放這個 dict，被 skill_policy_gate v2 reject
}
```

- [ ] **Step 7.2: 改 LLM_PROPOSABLE_SKILLS（不刪 greet_known_person，因 trace_only 仍允許提案）**

維持原 list（trace_only 桶仍在 LLM_PROPOSABLE_SKILLS 中）。

- [ ] **Step 7.3: 加 unit test**

```python
def test_greet_known_person_now_trace_only():
    """LLM proposing greet_known_person → trace, not execute."""
    # ... use existing brain_node test infrastructure
    proposal = {"skill": "greet_known_person", "args": {"name": "Roy"}}
    # ... verify trace emitted with status="accepted_trace_only"
    # ... verify NO plan emitted to executive

def test_wiggle_proposal_enters_pending_confirm():
    """LLM proposing wiggle → PendingConfirm.request_confirm called."""
    # ... existing pending confirm test pattern
```

- [ ] **Step 7.4: 跑 test pass**

- [ ] **Step 7.5: Commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py interaction_executive/test/
git commit -m "feat(executive): 1G LLM 4-bucket whitelist

Move greet_known_person from execute → trace_only.
Reason: face stable detection already triggers greet — letting LLM also
propose greet_known_person caused passing-by interruptions during
'walk over to gesture OK' scenario.

Buckets:
  1 execute: wave_hello / sit_along / careful_remind / show_status
  2 confirm: wiggle / stretch (PendingConfirm + OK gesture)
  3 trace_only: self_introduce / greet_known_person
  4 block: dance / follow_me / etc (skill_policy_gate rejects)

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1G
"
```

---

## Task 8: 1H — current_speaker Injection

**Files**:
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py`（face subscription + recent identity tracking）
- Modify: `pawai_brain/pawai_brain/nodes/world_state_builder.py`（路徑修正：實際在 `nodes/` 子資料夾）
- Modify: `pawai_brain/pawai_brain/capability/world_snapshot.py`（`WorldSnapshot` 加 `current_speaker` field — Roy review #3）
- Test: `pawai_brain/test/test_conversation_graph_node.py`

**背景**：spec 寫 face_perception publish 8 Hz `/state/perception/face`。conversation_graph_node 訂閱 + 維護 `_recent_face_identity: tuple[str, float]`，> 3s 視為 unknown。`WorldSnapshot` 加 `current_speaker` field、`world_state_builder` 寫入。

**前置確認**：開工前 grep 確認哪個 face topic 較穩：
- `/event/face_identity`（brain_node 既有 sub）
- `/state/perception/face`（spec 寫的 — 需確認 face_perception 是否真的 publish）

如果 `/state/perception/face` 不存在或不穩，改用 `/event/face_identity`。

- [ ] **Step 8.1: 寫 failing tests**

```python
def test_face_subscription_updates_recent_identity():
    """/state/perception/face msg updates _recent_face_identity."""
    node = _build_test_node()
    msg = String()
    msg.data = json.dumps({"identity": "Roy", "stable": True})
    node._on_face_state(msg)
    assert node._recent_face_identity[0] == "Roy"


def test_current_speaker_in_world_state_within_3s():
    """world_state.current_speaker = identity if recent < 3s."""
    node = _build_test_node()
    node._recent_face_identity = ("Roy", time.time())
    state = {}
    node.world_state_builder(state)
    assert state["world_state"]["current_speaker"] == "Roy"


def test_current_speaker_unknown_after_3s():
    """world_state.current_speaker = 'unknown' if recent > 3s."""
    node = _build_test_node()
    node._recent_face_identity = ("Roy", time.time() - 5.0)
    state = {}
    node.world_state_builder(state)
    assert state["world_state"]["current_speaker"] == "unknown"
```

- [ ] **Step 8.2: 加 face subscription**

`__init__`:
```python
self._recent_face_identity: tuple[str, float] = ("unknown", 0.0)
self.create_subscription(
    String, "/state/perception/face", self._on_face_state, 10
)
```

```python
def _on_face_state(self, msg):
    try:
        payload = json.loads(msg.data)
        identity = payload.get("identity") or "unknown"
        if payload.get("stable"):
            self._recent_face_identity = (identity, time.time())
    except (json.JSONDecodeError, TypeError):
        pass
```

- [ ] **Step 8.3: world_state_builder 加 current_speaker**

```python
def world_state_builder(self, state):
    # ... 既有邏輯
    identity, ts = self._recent_face_identity
    if identity != "unknown" and (time.time() - ts) < 3.0:
        state["world_state"]["current_speaker"] = identity
    else:
        state["world_state"]["current_speaker"] = "unknown"
    return state
```

- [ ] **Step 8.4: 加 EXAMPLES.md 補 current_speaker case 3 個**

```markdown
## Current Speaker Few-shot

### 對 Roy（俏皮快）
[眼前的人] Roy
使用者：你好
output: {"reply": "[playful] 嘿 Roy！", "skill": "wave_hello", "args": {}}

### 對 grama（溫柔慢）
[眼前的人] grama
使用者：你好
output: {"reply": "[gentle] 阿嬤好～今天還好嗎？", "skill": "wave_hello", "args": {}}

### 對 unknown（禮貌試探）
[眼前的人]（無）
使用者：你好
output: {"reply": "[curious] 嗨～你是新朋友嗎？", "skill": "wave_hello", "args": {}}
```

- [ ] **Step 8.5: Commit**

```bash
git add pawai_brain/pawai_brain/conversation_graph_node.py \
        pawai_brain/pawai_brain/nodes/world_state_builder.py \
        pawai_brain/pawai_brain/capability/world_snapshot.py \
        pawai_brain/personas/v1/EXAMPLES.md \
        pawai_brain/test/
git commit -m "feat(brain): 1H current_speaker injection from face state

Subscribe /state/perception/face (8 Hz JSON), maintain _recent_face_identity tuple.
world_state_builder injects current_speaker (default 'unknown' if > 3s old).
_build_user_message (Task 4 1D) injects [眼前的人] line when not unknown.

EXAMPLES.md adds 3 cases: Roy (playful) / grama (gentle) / unknown (curious).

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1H
"
```

---

## Task 9: tmux Script Runtime Topology Switch（Roy review #5 — 獨立 task + smoke）

**Files**:
- Modify: `scripts/start_pawai_brain_tmux.sh`（移除 llm_bridge_node window，新增 conversation_graph_node window）

**背景**：原 plan Task 1 把 tmux script 切到 conversation_graph_node 跟 persona loader 綁同 commit。Roy review #5 拆獨立 — 因為 runtime topology change 風險獨立於 loader bug。

**Steps**:
- [ ] 改 `start_pawai_brain_tmux.sh`：
  - 移除 `llm_bridge_node --ros-args -p output_mode:=brain` 那個 window（已被 conversation_graph_node 取代）
  - 新增 `ros2 launch pawai_brain pawai_conversation_graph.launch.py llm_persona_file:=<install/share path>` window
- [ ] Jetson smoke：
  - 啟動 tmux
  - `ros2 topic echo /brain/chat_candidate` 確認新 conversation_graph_node 真的 publish
  - 文字輸入「你好」→ 期望 chat_candidate emit + ChatPanel 收到 reply
- [ ] 確認 demo flow 仍跑（self_introduce skill button 測試）
- [ ] commit

```bash
git add scripts/start_pawai_brain_tmux.sh
git commit -m "feat(scripts): switch start_pawai_brain_tmux to conversation_graph_node

Replace legacy llm_bridge_node window with pawai_conversation_graph launch.
Smoke verified /brain/chat_candidate publishes from new node.

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1A
Roy review #5: runtime topology change separate from loader patch.
"
```

---

## Task 10: 1I — A/B Eval Suite (4 組對照)

**Files**:
- Modify: `tools/llm_eval/run_eval.py`（加 4 組 config）
- Create: `tools/llm_eval/cases_5_9_review.yaml`（30 round case set）

**背景**：純驗證用，不換主線。Demo 主線維持 Gemini-3 + temp 0.6（1A-1H 後）。

- [ ] **Step 9.1: 建 eval case set**

`tools/llm_eval/cases_5_9_review.yaml`：

```yaml
# 30 round 涵蓋 5 mode：identity 6 + capability 6 + action_request 9 + chat 6 + safety 3
cases:
  - text: "你是誰？"
    mode: identity
    expect_no_capability_list: true
  - text: "介紹一下你自己"
    mode: identity
    expect_no_capability_list: true
  - text: "你會什麼？"
    mode: capability_question
    expect_skill_proposal_or_chat_reply: true
  - text: "扭一下"
    mode: action_request
    expect_skill: wiggle
  - text: "比 OK 我就扭一扭"
    mode: action_request
    expect_skill: wiggle
  - text: "伸個懶腰"
    mode: action_request
    expect_skill: stretch
  - text: "今天天氣好嗎"
    mode: chat
  - text: "我累了"
    mode: chat
    expect_skill_or_reply_includes: ["sit_along", "陪"]
  # ... 26 more
```

- [ ] **Step 9.2: 改 run_eval.py 加 4 組 config**

```python
CONFIGS = [
    {"name": "gemini_temp02_baseline", "model": "google/gemini-3-flash-preview", "temperature": 0.2},
    {"name": "gemini_temp06_demo_main", "model": "google/gemini-3-flash-preview", "temperature": 0.6},
    {"name": "deepseek_temp06_candidate", "model": "deepseek/deepseek-v4-flash", "temperature": 0.6},
    {"name": "gemini_temp09_explore", "model": "google/gemini-3-flash-preview", "temperature": 0.9},
]
```

- [ ] **Step 9.3: 跑 eval（4 × 30 = 120 round）**

```bash
cd tools/llm_eval
python3 run_eval.py --cases cases_5_9_review.yaml --configs all --rounds 30
```

評分維度（人工 + 自動）：
- persona 維持力（不講「我是 AI」、不客服腔）
- JSON schema 命中率
- skill 提案率
- 中文自然度（人工 1-5）
- 介紹死板度（identity mode「列功能 vs 講性格」比例）
- 延遲 P50/P95

- [ ] **Step 9.4: 寫結果到 dev-log**

`docs/pawai-brain/dev-logs/2026-05-12-persona-ab-eval.md`

- [ ] **Step 9.5: Commit eval results**

```bash
git add tools/llm_eval/cases_5_9_review.yaml \
        tools/llm_eval/run_eval.py \
        docs/pawai-brain/dev-logs/2026-05-12-persona-ab-eval.md
git commit -m "test(brain): 1I 4-config A/B eval results (validation only)

Gemini-3 temp 0.2 (baseline) vs 0.6 (demo main) vs 0.9 (explore) vs DeepSeek-V4 0.6.
30 rounds × 4 configs = 120 calls.

Demo 主線：Gemini-3 + 0.6（1A-1H 完成後）。
DeepSeek 切主線決策：5/16 demo 後若 ≥3 維度明顯贏才切。

Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P1-4 1I
"
```

---

## Self-Review

**Spec coverage**:
- ✅ 1A persona loader → Task 1
- ✅ 1B persona 5 檔 → Task 2
- ✅ 1C mode classifier → Task 3
- ✅ 1D capability lazy inject → Task 4
- ✅ 1E temperature + label → Task 5（含 Task 4 label）
- ✅ 1F identity + wiggle/stretch + 負例 few-shot → Task 6
- ✅ 1G 4 桶白名單 → Task 7
- ✅ 1H current_speaker → Task 8
- ✅ 1I A/B eval → Task 9

**Placeholder scan**: 所有 step 含實際 code。EXAMPLES.md 內容在 Task 6 + Task 8 全部實際 prose 寫出。

**Type consistency**:
- `mode: str` 5 enum-like values (`safety/identity/capability_question/action_request/chat`) 跨 mode_classifier + state + _build_user_message + Task 4/8 一致
- `_capabilities_md: str` 屬性在 Task 1 設置、Task 4 讀取
- `_recent_face_identity: tuple[str, float]` 在 Task 8 一致

**潛在風險**：
- Task 8 face subscription 若 face_perception node 沒啟，subscription 不會收到訊息（identity 維持 unknown，prompt 不報錯）— OK
- Task 7 改 LLM_PROPOSAL_EXECUTE dict 若 brain_node 既有 test 假設 greet_known_person 是 execute，會 fail regression — Step 7.4 要確認既有 test 不 hardcode

---

## 預期工時

| Task | 工時 |
|---|---|
| 1 1A persona loader 雙模 | 4h |
| 2 1B 拆 5 檔（純機械搬）| 1.5h |
| 3 1C mode classifier | 1h |
| 4 1D capability lazy inject | 1.5h |
| 5 1E temperature 0.6 | 0.5h |
| 6 1F identity + wiggle few-shot | 3h |
| 7 1G 4 桶白名單 | 0.5h |
| 8 1H current_speaker 注入 | 3h |
| 9 1I A/B eval 4 組 | 4h |
| **總計** | **~19h ≈ 1.5 天** |

5/11 上午寫 plan + 開工 → 5/12 evening 完成 1A-1H → 5/13 上午跑 1I eval。
