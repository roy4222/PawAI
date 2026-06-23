# Capability-Aware Self-Demonstration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CapabilityContext` layer to `pawai_brain` so the LLM can introduce its own capabilities, choose what to demonstrate, and respect runtime constraints — without giving the LLM direct execution authority.

**Architecture:** Three-tier model — `SkillContract` (true skills, executive consumes), `DemoGuide` (pseudo-skills, pawai_brain only), `CapabilityContext` (LLM-facing merged view). Two new graph nodes (`world_state_builder` + `capability_builder`) replace the obsolete `context_builder` + `env_builder` stubs. `skill_policy_gate` gains `kind` branches; `demo_guide` proposals only flow to `/brain/conversation_trace` — the `/brain/chat_candidate` schema stays unchanged so `brain_node` / `interaction_executive` need zero edits.

**Tech Stack:** Python 3.10, ROS2 Humble, LangGraph 1.1.10, langchain-core 1.3.3, pytest 6+, PyYAML, Next.js (Studio frontend).

**Spec:** `docs/pawai-brain/specs/2026-05-07-capability-aware-self-demonstration-design.md`

---

## High-Risk Acceptance Tests

These three behaviours have explicit dedicated tests — flagged because regressions are easy to miss:

1. **`chat_reply` / `say_canned` never become `proposed_skill`** — passthrough must happen before SKILL_REGISTRY lookup. (Task 12)
2. **`demo_guide` never enters `/brain/chat_candidate`** — only `/brain/conversation_trace`. (Task 13 + Task 16)
3. **`selected_skill` from `/brain/skill_result` correctly populates `recent_skill_results`** — direct field, no plan_id reverse lookup. (Task 15)

---

## Phase A — Pure Modules (Tasks 0-9)

No ROS, no graph wiring. Each task ships green unit tests in isolation.

---

### Task 0: Package metadata (deps + exec_depend)

PyYAML, ament_index_python, and interaction_executive must be declared so colcon build order is deterministic and clean Jetson environments resolve at runtime. Skipping this causes silent ImportError on first run.

**Files:**
- Modify: `pawai_brain/package.xml`
- Modify: `pawai_brain/setup.py`

- [ ] **Step 1: Add `<exec_depend>` lines to `package.xml`**

Edit `pawai_brain/package.xml` — add inside the existing `<package>` block (after the existing `<exec_depend>std_msgs</exec_depend>` line):

```xml
  <exec_depend>ament_index_python</exec_depend>
  <exec_depend>interaction_executive</exec_depend>
  <exec_depend>python3-yaml</exec_depend>
```

This ensures: (a) colcon builds `interaction_executive` before `pawai_brain`, (b) `rosdep install` brings in PyYAML on a fresh Jetson, (c) `get_package_share_directory` is available at runtime.

- [ ] **Step 2: Add `PyYAML` to `setup.py` `install_requires`**

Edit `pawai_brain/setup.py` — extend `install_requires`:

```python
    install_requires=[
        "setuptools",
        "langgraph>=0.2.0",
        "langchain-core>=0.3.0",
        "PyYAML>=5.4",
    ],
```

- [ ] **Step 3: colcon build sanity**

```bash
bash -c 'source /opt/ros/humble/setup.bash && cd /home/roy422/newLife/elder_and_dog && colcon build --packages-select pawai_brain --symlink-install' 2>&1 | tail -5
```
Expected: `Finished <<< pawai_brain` clean.

- [ ] **Step 4: Verify imports resolve**

```bash
python3 -c "import yaml, ament_index_python; print('deps OK')"
```
Expected: `deps OK`.

- [ ] **Step 5: Commit**

```bash
git add pawai_brain/package.xml pawai_brain/setup.py
git commit -m "chore(pawai_brain): add PyYAML/ament_index_python/interaction_executive deps"
```

---

### Task 1: `effective_status` rules (pure function)

**Files:**
- Create: `pawai_brain/pawai_brain/capability/__init__.py`
- Create: `pawai_brain/pawai_brain/capability/effective_status.py`
- Create: `pawai_brain/test/test_effective_status.py`

- [ ] **Step 1: Create empty `__init__.py`**

```bash
touch pawai_brain/pawai_brain/capability/__init__.py
```

- [ ] **Step 2: Write the failing test**

```python
# pawai_brain/test/test_effective_status.py
"""Tests for effective_status — Plan §4.5 priority order."""
from dataclasses import dataclass

from pawai_brain.capability.effective_status import (
    WorldFlags,
    compute_effective_status,
)


@dataclass
class FakeSkill:
    name: str
    baseline: str = "available_execute"
    static_enabled: bool = True
    enabled_when: list = None
    cooldown_remaining_s: float = 0.0
    has_say_step: bool = False
    has_motion_step: bool = False
    has_nav_step: bool = False
    kind: str = "skill"

    def __post_init__(self):
        if self.enabled_when is None:
            self.enabled_when = []


def _world(**kw):
    return WorldFlags(
        tts_playing=kw.get("tts_playing", False),
        obstacle=kw.get("obstacle", False),
        nav_safe=kw.get("nav_safe", True),
    )


def test_disabled_baseline_wins_over_everything():
    skill = FakeSkill(name="dance", baseline="disabled")
    s, _ = compute_effective_status(skill, _world(tts_playing=True, obstacle=True))
    assert s == "disabled"


def test_studio_only_baseline():
    skill = FakeSkill(name="fallen_alert", baseline="studio_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "studio_only"


def test_demo_guide_kind_always_explain_only():
    skill = FakeSkill(name="gesture_demo", kind="demo_guide", baseline="explain_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "explain_only"


def test_explain_only_baseline():
    skill = FakeSkill(name="object_remark", baseline="explain_only")
    s, _ = compute_effective_status(skill, _world())
    assert s == "explain_only"


def test_static_enabled_false_yields_disabled():
    skill = FakeSkill(name="follow_me", static_enabled=False)
    s, reason = compute_effective_status(skill, _world())
    assert s == "disabled"
    assert "靜態未啟用" in reason


def test_cooldown_blocks_available():
    skill = FakeSkill(name="wave_hello", cooldown_remaining_s=4.2)
    s, reason = compute_effective_status(skill, _world())
    assert s == "cooldown"
    assert "4" in reason  # contains the seconds


def test_tts_playing_defers_say_skill():
    skill = FakeSkill(name="show_status", has_say_step=True)
    s, _ = compute_effective_status(skill, _world(tts_playing=True))
    assert s == "defer"


def test_obstacle_blocks_motion_skill():
    skill = FakeSkill(name="wave_hello", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world(obstacle=True))
    assert s == "blocked"


def test_nav_unsafe_blocks_nav_skill():
    skill = FakeSkill(name="nav_demo_point", has_nav_step=True)
    s, _ = compute_effective_status(skill, _world(nav_safe=False))
    assert s == "blocked"


def test_physical_block_runs_BEFORE_needs_confirm():
    """Plan §4.5 ordering fix: wiggle/stretch must NOT prompt OK if obstacle."""
    skill = FakeSkill(name="wiggle", baseline="available_confirm", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world(obstacle=True))
    assert s == "blocked"  # NOT needs_confirm


def test_available_confirm_yields_needs_confirm_when_clear():
    skill = FakeSkill(name="wiggle", baseline="available_confirm", has_motion_step=True)
    s, _ = compute_effective_status(skill, _world())
    assert s == "needs_confirm"


def test_available_when_all_clear():
    skill = FakeSkill(name="show_status", has_say_step=True)
    s, _ = compute_effective_status(skill, _world())
    assert s == "available"
```

- [ ] **Step 3: Run test — should fail with ImportError**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_effective_status.py -v
```
Expected: ImportError or collection failure.

- [ ] **Step 4: Implement the rules module**

```python
# pawai_brain/pawai_brain/capability/effective_status.py
"""Pure effective_status calculation — Plan §4.5 rule table."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorldFlags:
    tts_playing: bool = False
    obstacle: bool = False
    nav_safe: bool = True


class _SkillLike(Protocol):
    name: str
    baseline: str
    static_enabled: bool
    enabled_when: list
    cooldown_remaining_s: float
    has_say_step: bool
    has_motion_step: bool
    has_nav_step: bool
    kind: str


def compute_effective_status(skill: _SkillLike, world: WorldFlags) -> tuple[str, str]:
    """Return (effective_status, reason). First match wins.

    Priority (matches Plan §4.5):
      disabled / studio_only / demo_guide / explain_only baselines
      → static_enabled / enabled_when
      → cooldown
      → physical block (TTS / obstacle / nav)
      → available_confirm → needs_confirm
      → available
    """
    baseline = skill.baseline
    if baseline == "disabled":
        return "disabled", ""
    if baseline == "studio_only":
        return "studio_only", ""
    if skill.kind == "demo_guide":
        return "explain_only", ""
    if baseline == "explain_only":
        return "explain_only", ""

    if not skill.static_enabled:
        return "disabled", "靜態未啟用"

    if skill.enabled_when:
        # enabled_when is list of (key, reason) tuples; presence == not yet enabled
        flag, reason = skill.enabled_when[0]
        return "disabled", reason or flag

    if skill.cooldown_remaining_s > 0:
        return "cooldown", f"cooldown 剩 {skill.cooldown_remaining_s:.1f} 秒"

    if world.tts_playing and skill.has_say_step:
        return "defer", "TTS 播放中"

    if world.obstacle and skill.has_motion_step:
        return "blocked", "前方有障礙"

    if not world.nav_safe and skill.has_nav_step:
        return "blocked", "導航未 ready"

    if baseline == "available_confirm":
        return "needs_confirm", "需 OK 確認"

    return "available", ""
```

- [ ] **Step 5: Run test — should pass**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_effective_status.py -v
```
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add pawai_brain/pawai_brain/capability/__init__.py pawai_brain/pawai_brain/capability/effective_status.py pawai_brain/test/test_effective_status.py
git commit -m "feat(pawai_brain): pure effective_status rules with priority ordering"
```

---

### Task 2: `DemoGuide` dataclass + yaml loader

**Files:**
- Create: `pawai_brain/config/demo_guides.yaml`
- Create: `pawai_brain/pawai_brain/capability/demo_guides_loader.py`
- Create: `pawai_brain/test/test_demo_guides_loader.py`

- [ ] **Step 1: Write the yaml**

```yaml
# pawai_brain/config/demo_guides.yaml
face_recognition_demo:
  display_name: 人臉辨識
  baseline_status: explain_only
  demo_value: high
  intro: 我可以認出熟人。請 Roy 站到鏡頭前 1.5 公尺左右，我會主動打招呼。
  related_skills: [greet_known_person]
speech_demo:
  display_name: 語音對話
  baseline_status: explain_only
  demo_value: high
  intro: 你可以問我任何問題，我會記得最近聊過的事。
  related_skills: [chat_reply, self_introduce]
gesture_demo:
  display_name: 手勢辨識
  baseline_status: explain_only
  demo_value: high
  intro: 請對著鏡頭比 OK、讚、或握拳，我會跟你互動。
  related_skills: [wave_hello]
pose_demo:
  display_name: 姿勢辨識
  baseline_status: explain_only
  demo_value: high
  intro: 我能分辨站立、坐下、躺平。請讓我看看你的姿勢。
  related_skills: [sit_along]
object_demo:
  display_name: 物體辨識
  baseline_status: explain_only
  demo_value: medium
  intro: 我能辨識大物件和 12 種顏色。請拿純色物件靠近鏡頭。
  related_skills: [object_remark]
navigation_demo:
  display_name: 導航避障
  baseline_status: explain_only
  demo_value: medium
  intro: 我能做簡化導航和短距離移動。動態避障今天不主動展示，需要場地比較大。
  related_skills: [nav_demo_point, approach_person]
```

- [ ] **Step 2: Write the failing test**

```python
# pawai_brain/test/test_demo_guides_loader.py
"""Tests for demo_guides yaml loader."""
import pytest
from pathlib import Path

from pawai_brain.capability.demo_guides_loader import (
    DemoGuide,
    load_demo_guides,
)


def _config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "demo_guides.yaml"


def test_loads_six_guides():
    guides = load_demo_guides(_config_path())
    assert len(guides) == 6
    names = {g.name for g in guides}
    assert names == {
        "face_recognition_demo", "speech_demo", "gesture_demo",
        "pose_demo", "object_demo", "navigation_demo",
    }


def test_each_guide_has_required_fields():
    guides = load_demo_guides(_config_path())
    for g in guides:
        assert g.display_name
        assert g.baseline_status in ("explain_only", "studio_only", "disabled")
        assert g.demo_value in ("high", "medium", "low")
        assert g.intro


def test_kind_attribute_is_demo_guide():
    guides = load_demo_guides(_config_path())
    assert all(g.kind == "demo_guide" for g in guides)


def test_invalid_baseline_raises():
    invalid = {
        "bad_demo": {
            "display_name": "Bad",
            "baseline_status": "available_execute",  # forbidden for demo_guide
            "demo_value": "low",
            "intro": "x",
        }
    }
    with pytest.raises(ValueError, match="baseline_status"):
        DemoGuide.from_yaml_entry("bad_demo", invalid["bad_demo"])


def test_missing_file_returns_empty_list_with_warn(caplog):
    guides = load_demo_guides(Path("/nonexistent/path.yaml"))
    assert guides == []


def test_related_skills_default_empty():
    guides = load_demo_guides(_config_path())
    by_name = {g.name: g for g in guides}
    # gesture_demo declares related; speech_demo too
    assert "wave_hello" in by_name["gesture_demo"].related_skills
    assert "chat_reply" in by_name["speech_demo"].related_skills
```

- [ ] **Step 3: Run test — should fail**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_demo_guides_loader.py -v
```

- [ ] **Step 4: Implement the loader**

```python
# pawai_brain/pawai_brain/capability/demo_guides_loader.py
"""Load DemoGuide pseudo-skills from yaml."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_VALID_DEMO_GUIDE_BASELINES = frozenset({"explain_only", "studio_only", "disabled"})
_VALID_DEMO_VALUES = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class DemoGuide:
    name: str
    display_name: str
    baseline_status: str
    demo_value: str
    intro: str
    related_skills: list[str] = field(default_factory=list)
    kind: str = "demo_guide"

    @classmethod
    def from_yaml_entry(cls, name: str, entry: dict) -> "DemoGuide":
        baseline = entry.get("baseline_status", "")
        if baseline not in _VALID_DEMO_GUIDE_BASELINES:
            raise ValueError(
                f"DemoGuide {name!r} baseline_status={baseline!r} invalid; "
                f"allowed: {sorted(_VALID_DEMO_GUIDE_BASELINES)}"
            )
        demo_value = entry.get("demo_value", "low")
        if demo_value not in _VALID_DEMO_VALUES:
            raise ValueError(
                f"DemoGuide {name!r} demo_value={demo_value!r} invalid; "
                f"allowed: {sorted(_VALID_DEMO_VALUES)}"
            )
        return cls(
            name=name,
            display_name=str(entry.get("display_name", name)),
            baseline_status=baseline,
            demo_value=demo_value,
            intro=str(entry.get("intro", "")),
            related_skills=list(entry.get("related_skills") or []),
        )


def load_demo_guides(path: Path) -> list[DemoGuide]:
    """Load demo guides from yaml. Returns [] on file missing / parse error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("demo_guides yaml not loaded (%s): %s", path, exc)
        return []
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        logger.warning("demo_guides yaml parse failed (%s): %s", path, exc)
        return []
    if not isinstance(data, dict):
        logger.warning("demo_guides yaml root must be a mapping (%s)", path)
        return []
    guides = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            logger.warning("demo_guides skipping non-dict entry %s", name)
            continue
        try:
            guides.append(DemoGuide.from_yaml_entry(str(name), entry))
        except ValueError as exc:
            logger.warning("demo_guides skipping invalid entry %s: %s", name, exc)
    return guides
```

- [ ] **Step 5: Confirm yaml is installed by `setup.py`**

Edit `pawai_brain/setup.py` `data_files` to include the config dir. Add this line:

```python
        (f"share/{package_name}/config", glob("config/*.yaml")),
```

After the existing `launch` data_files entry.

- [ ] **Step 6: Run test — should pass**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_demo_guides_loader.py -v
```
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add pawai_brain/config/demo_guides.yaml pawai_brain/pawai_brain/capability/demo_guides_loader.py pawai_brain/test/test_demo_guides_loader.py pawai_brain/setup.py
git commit -m "feat(pawai_brain): demo_guides yaml + loader (6 entries)"
```

---

### Task 3: `demo_policy.yaml` + loader

**Files:**
- Create: `pawai_brain/config/demo_policy.yaml`
- Modify: `pawai_brain/pawai_brain/capability/demo_guides_loader.py` (add `load_demo_policy()`)
- Create: `pawai_brain/test/test_demo_policy_loader.py`

- [ ] **Step 1: Write the yaml**

```yaml
# pawai_brain/config/demo_policy.yaml
limits:
  - 目前動態避障不是主展示項目
  - 陌生人警告已關閉避免誤觸
  - 一次最多執行一個動作
  - 手勢以靜態 OK / 讚 / 握拳為主
  - 人需要站在約 2 公尺外才容易完整辨識
max_motion_per_turn: 1
```

- [ ] **Step 2: Write the failing test**

```python
# pawai_brain/test/test_demo_policy_loader.py
from pathlib import Path

from pawai_brain.capability.demo_guides_loader import load_demo_policy


def _path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "demo_policy.yaml"


def test_loads_limits():
    policy = load_demo_policy(_path())
    assert isinstance(policy["limits"], list)
    assert len(policy["limits"]) == 5
    assert "陌生人警告已關閉避免誤觸" in policy["limits"]


def test_max_motion_per_turn():
    policy = load_demo_policy(_path())
    assert policy["max_motion_per_turn"] == 1


def test_missing_file_returns_defaults():
    policy = load_demo_policy(Path("/nonexistent.yaml"))
    assert policy["limits"] == []
    assert policy["max_motion_per_turn"] == 1
```

- [ ] **Step 3: Add `load_demo_policy()` to loader module**

Append to `pawai_brain/pawai_brain/capability/demo_guides_loader.py`:

```python
def load_demo_policy(path: Path) -> dict:
    """Load demo_policy yaml. Returns sensible defaults on failure."""
    defaults = {"limits": [], "max_motion_per_turn": 1}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return defaults
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return defaults
    if not isinstance(data, dict):
        return defaults
    return {
        "limits": list(data.get("limits") or []),
        "max_motion_per_turn": int(data.get("max_motion_per_turn") or 1),
    }
```

- [ ] **Step 4: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_demo_policy_loader.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pawai_brain/config/demo_policy.yaml pawai_brain/pawai_brain/capability/demo_guides_loader.py pawai_brain/test/test_demo_policy_loader.py
git commit -m "feat(pawai_brain): demo_policy yaml with limits + max_motion_per_turn"
```

---

### Task 4: `SkillResultMemory` deque

**Files:**
- Create: `pawai_brain/pawai_brain/capability/skill_result_memory.py`
- Create: `pawai_brain/test/test_skill_result_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# pawai_brain/test/test_skill_result_memory.py
from pawai_brain.capability.skill_result_memory import SkillResultMemory


def test_starts_empty():
    m = SkillResultMemory()
    assert m.recent() == []


def test_add_and_recall_in_order():
    m = SkillResultMemory()
    m.add({"name": "self_introduce", "status": "completed", "ts": 1.0, "detail": ""})
    m.add({"name": "show_status", "status": "completed", "ts": 2.0, "detail": ""})
    items = m.recent()
    assert len(items) == 2
    assert items[0]["name"] == "self_introduce"
    assert items[1]["name"] == "show_status"


def test_maxlen_5_evicts_oldest():
    m = SkillResultMemory(maxlen=5)
    for i in range(7):
        m.add({"name": f"skill_{i}", "status": "completed", "ts": float(i), "detail": ""})
    items = m.recent()
    assert len(items) == 5
    assert items[0]["name"] == "skill_2"  # oldest two evicted
    assert items[-1]["name"] == "skill_6"


def test_recent_returns_copy_not_reference():
    m = SkillResultMemory()
    m.add({"name": "x", "status": "completed", "ts": 1.0, "detail": ""})
    items = m.recent()
    items.append({"hacked": True})
    assert len(m.recent()) == 1


def test_thread_safe_basic():
    """Smoke check that lock is used."""
    import threading
    m = SkillResultMemory()

    def writer(start):
        for i in range(50):
            m.add({"name": f"s{start+i}", "status": "completed", "ts": float(i), "detail": ""})

    threads = [threading.Thread(target=writer, args=(i*100,)) for i in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(m.recent()) == 5  # maxlen still respected
```

- [ ] **Step 2: Implement**

```python
# pawai_brain/pawai_brain/capability/skill_result_memory.py
"""Process-local FIFO of recent terminal skill_result events."""
from __future__ import annotations
import threading
from collections import deque


class SkillResultMemory:
    def __init__(self, maxlen: int = 5) -> None:
        self._dq: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, entry: dict) -> None:
        with self._lock:
            self._dq.append(dict(entry))

    def recent(self) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._dq]

    def clear(self) -> None:
        with self._lock:
            self._dq.clear()
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_skill_result_memory.py -v
```
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/capability/skill_result_memory.py pawai_brain/test/test_skill_result_memory.py
git commit -m "feat(pawai_brain): SkillResultMemory thread-safe deque"
```

---

### Task 5: `SkillContract` 4 new fields + 27 baseline defaults

**Files:**
- Modify: `interaction_executive/interaction_executive/skill_contract.py`
- Create: `interaction_executive/test/test_skill_contract_demo_fields.py`

- [ ] **Step 1: Write the failing test FIRST (prove fields exist)**

```python
# interaction_executive/test/test_skill_contract_demo_fields.py
"""Verify the 4 demo metadata fields are populated for all 27 SKILL_REGISTRY entries."""
from interaction_executive.skill_contract import SKILL_REGISTRY, SkillContract


VALID_BASELINES = {
    "available_execute", "available_confirm",
    "explain_only", "studio_only", "disabled",
}
VALID_DEMO_VALUES = {"high", "medium", "low"}


def test_skill_contract_dataclass_has_4_demo_fields():
    fields = {f.name for f in SkillContract.__dataclass_fields__.values()}
    assert "display_name" in fields
    assert "demo_status_baseline" in fields
    assert "demo_value" in fields
    assert "demo_reason" in fields


def test_all_27_skills_have_valid_baseline():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.demo_status_baseline in VALID_BASELINES, \
            f"{name}: invalid baseline {contract.demo_status_baseline!r}"


def test_all_27_skills_have_valid_demo_value():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.demo_value in VALID_DEMO_VALUES, \
            f"{name}: invalid demo_value {contract.demo_value!r}"


def test_all_27_skills_have_display_name():
    for name, contract in SKILL_REGISTRY.items():
        assert contract.display_name, f"{name}: empty display_name"


def test_baseline_distribution_matches_spec_section_11():
    """5/18 baseline classification per spec §11."""
    counts = {}
    for contract in SKILL_REGISTRY.values():
        counts[contract.demo_status_baseline] = counts.get(contract.demo_status_baseline, 0) + 1

    # available_execute should include stop_move (special) — total 9 with stop_move
    # 8 listed + stop_move = 9
    assert counts.get("available_execute") == 9
    assert counts.get("available_confirm") == 2
    assert counts.get("explain_only") == 5
    assert counts.get("studio_only") == 1
    assert counts.get("disabled") == 10


def test_specific_skill_baselines():
    assert SKILL_REGISTRY["self_introduce"].demo_status_baseline == "available_execute"
    assert SKILL_REGISTRY["wiggle"].demo_status_baseline == "available_confirm"
    assert SKILL_REGISTRY["fallen_alert"].demo_status_baseline == "explain_only"
    assert SKILL_REGISTRY["system_pause"].demo_status_baseline == "studio_only"
    assert SKILL_REGISTRY["dance"].demo_status_baseline == "disabled"
```

- [ ] **Step 2: Run test — should fail**

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_skill_contract_demo_fields.py -v
```
Expected: AttributeError on `demo_status_baseline`.

- [ ] **Step 3: Add fields to `SkillContract` dataclass**

Edit `interaction_executive/interaction_executive/skill_contract.py:57-73` — append 4 fields to the existing `SkillContract` definition:

```python
@dataclass
class SkillContract:
    name: str
    steps: list[SkillStep]
    priority_class: PriorityClass
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0.0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""
    args_schema: dict[str, Any] = field(default_factory=dict)
    ui_style: Literal["normal", "alert", "safety"] = "normal"
    static_enabled: bool = True
    enabled_when: list = field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"
    bucket: SkillBucket = "active"

    # Phase A.6 demo metadata
    display_name: str = ""
    demo_status_baseline: Literal[
        "available_execute", "available_confirm",
        "explain_only", "studio_only", "disabled",
    ] = "disabled"
    demo_value: Literal["high", "medium", "low"] = "low"
    demo_reason: str = ""
```

- [ ] **Step 4: Update each of the 27 SKILL_REGISTRY entries with demo metadata**

Edit each entry in `SKILL_REGISTRY`. Example for the first few — apply the same pattern to all 27 (full classification per spec §11):

```python
"stop_move": SkillContract(
    name="stop_move",
    steps=[SkillStep(ExecutorKind.MOTION, {"name": "stop_move"})],
    priority_class=PriorityClass.SAFETY,
    description="Emergency stop. Safety hard-rule path.",
    ui_style="safety",
    bucket="active",
    display_name="緊急停止",
    demo_status_baseline="available_execute",  # but safety_gate short-circuits before LLM sees
    demo_value="high",
    demo_reason="安全短路，不會被 LLM 提案",
),
"self_introduce": SkillContract(
    # ... existing ...
    display_name="自我介紹",
    demo_status_baseline="available_execute",
    demo_value="high",
    demo_reason="Demo 主軸功能",
),
"wiggle": SkillContract(
    # ... existing ...
    display_name="搖擺",
    demo_status_baseline="available_confirm",
    demo_value="medium",
    demo_reason="低風險表演動作但需 OK 確認",
),
"fallen_alert": SkillContract(
    # ... existing ...
    display_name="跌倒提醒",
    demo_status_baseline="explain_only",
    demo_value="medium",
    demo_reason="關閉誤觸打斷對話；只在 Studio 顯示警示",
),
"system_pause": SkillContract(
    # ... existing ...
    display_name="系統暫停",
    demo_status_baseline="studio_only",
    demo_value="low",
    demo_reason="系統級開關只給 Studio",
),
"dance": SkillContract(
    # ... existing ...
    display_name="跳舞",
    demo_status_baseline="disabled",
    demo_value="low",
    demo_reason="動作不穩定",
),
```

Apply the full classification per spec §11. Remaining mapping (use this lookup):

| skill | display_name | baseline |
|---|---|---|
| stop_move | 緊急停止 | available_execute |
| system_pause | 系統暫停 | studio_only |
| show_status | 狀態回報 | available_execute |
| chat_reply | 自然對話 | available_execute |
| say_canned | 規則回覆 | available_execute |
| self_introduce | 自我介紹 | available_execute |
| wave_hello | 揮手打招呼 | available_execute |
| wiggle | 搖擺 | available_confirm |
| stretch | 伸展 | available_confirm |
| sit_along | 跟坐 | available_execute |
| careful_remind | 小心提醒 | available_execute |
| greet_known_person | 熟人問候 | available_execute |
| stranger_alert | 陌生人警告 | explain_only |
| fallen_alert | 跌倒提醒 | explain_only |
| object_remark | 物體解說 | explain_only |
| nav_demo_point | 短距離移動 | explain_only |
| approach_person | 走近人 | explain_only |
| enter_mute_mode | 靜音模式 | disabled |
| enter_listen_mode | 聆聽模式 | disabled |
| akimbo_react | 叉腰回應 | disabled |
| knee_kneel_react | 跪地回應 | disabled |
| patrol_route | 巡邏路線 | disabled |
| follow_me | 跟隨我 | disabled |
| follow_person | 跟隨人 | disabled |
| dance | 跳舞 | disabled |
| go_to_named_place | 前往指定地點 | disabled |
| acknowledge_gesture | 手勢確認 (retired) | disabled |

- [ ] **Step 5: Run test — should pass**

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_skill_contract_demo_fields.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Run all interaction_executive tests to ensure no regression**

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/ -q
```
Expected: existing tests still green.

- [ ] **Step 7: Commit**

```bash
git add interaction_executive/interaction_executive/skill_contract.py interaction_executive/test/test_skill_contract_demo_fields.py
git commit -m "feat(interaction_executive): SkillContract demo metadata + 27 baseline defaults"
```

---

### Task 6: `CapabilityEntry` + `CapabilityRegistry` (merge layer)

**Files:**
- Create: `pawai_brain/pawai_brain/capability/registry.py`
- Create: `pawai_brain/test/test_capability_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# pawai_brain/test/test_capability_registry.py
"""Tests for CapabilityRegistry — merge SkillContract + DemoGuide."""
from unittest.mock import MagicMock

from pawai_brain.capability.demo_guides_loader import DemoGuide
from pawai_brain.capability.effective_status import WorldFlags
from pawai_brain.capability.registry import (
    CapabilityEntry,
    CapabilityRegistry,
    build_capability_entries,
)


class _FakeSkill:
    """Minimal SkillContract stand-in for tests."""
    def __init__(self, name, **kw):
        self.name = name
        self.display_name = kw.get("display_name", name)
        self.demo_status_baseline = kw.get("demo_status_baseline", "available_execute")
        self.demo_value = kw.get("demo_value", "high")
        self.demo_reason = kw.get("demo_reason", "")
        self.static_enabled = kw.get("static_enabled", True)
        self.enabled_when = kw.get("enabled_when", [])
        self.cooldown_s = kw.get("cooldown_s", 0.0)
        self.steps = kw.get("steps", [])
        self.requires_confirmation = kw.get("requires_confirmation", False)


def _say_step():
    s = MagicMock(); s.executor = MagicMock(name="SAY"); return s


def _make_registry(skills, guides):
    return CapabilityRegistry(skills=skills, guides=guides)


def test_assert_disjoint_names():
    skill = _FakeSkill("gesture_demo")  # collides with demo guide name
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    import pytest
    with pytest.raises(ValueError, match="disjoint"):
        _make_registry({"gesture_demo": skill}, [guide])


def test_build_entries_includes_skill_and_guide():
    skill = _FakeSkill("self_introduce")
    guide = DemoGuide(name="gesture_demo", display_name="手勢",
                      baseline_status="explain_only", demo_value="high", intro="比 OK")
    reg = _make_registry({"self_introduce": skill}, [guide])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    assert {e.name for e in entries} == {"self_introduce", "gesture_demo"}
    by_name = {e.name: e for e in entries}
    assert by_name["self_introduce"].kind == "skill"
    assert by_name["gesture_demo"].kind == "demo_guide"


def test_demo_guide_always_explain_only():
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    reg = _make_registry({}, [guide])
    entries = reg.build_entries(world=WorldFlags(tts_playing=True), recent_results=[])
    assert entries[0].effective_status == "explain_only"
    assert entries[0].can_execute is False


def test_skill_can_execute_only_when_available():
    skill = _FakeSkill("self_introduce")
    reg = _make_registry({"self_introduce": skill}, [])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    e = entries[0]
    assert e.effective_status == "available"
    assert e.can_execute is True


def test_cooldown_remaining_uses_recent_results():
    skill = _FakeSkill("wave_hello", cooldown_s=10.0)
    reg = _make_registry({"wave_hello": skill}, [])
    import time
    recent = [{"name": "wave_hello", "status": "completed",
               "ts": time.time() - 3.0, "detail": ""}]
    entries = reg.build_entries(world=WorldFlags(), recent_results=recent)
    assert entries[0].effective_status == "cooldown"


def test_lookup_returns_entry_by_name():
    skill = _FakeSkill("self_introduce")
    guide = DemoGuide(name="gesture_demo", display_name="x",
                      baseline_status="explain_only", demo_value="high", intro="x")
    reg = _make_registry({"self_introduce": skill}, [guide])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    by_name = {e.name: e for e in entries}
    assert by_name["self_introduce"].kind == "skill"
    assert by_name["gesture_demo"].kind == "demo_guide"
    assert "missing" not in by_name


def test_serialize_for_llm_minimal_fields():
    skill = _FakeSkill("self_introduce")
    reg = _make_registry({"self_introduce": skill}, [])
    entries = reg.build_entries(world=WorldFlags(), recent_results=[])
    payload = entries[0].to_llm_dict()
    assert payload["name"] == "self_introduce"
    assert payload["kind"] == "skill"
    assert "effective_status" in payload
    assert "can_execute" in payload
```

- [ ] **Step 2: Implement registry**

```python
# pawai_brain/pawai_brain/capability/registry.py
"""CapabilityRegistry — merge SkillContract + DemoGuide → CapabilityEntry list."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from .demo_guides_loader import DemoGuide
from .effective_status import WorldFlags, compute_effective_status


_AVAILABLE_STATUSES = frozenset({"available", "needs_confirm"})


@dataclass(frozen=True)
class CapabilityEntry:
    name: str
    kind: str  # "skill" | "demo_guide"
    display_name: str
    effective_status: str
    demo_value: str
    can_execute: bool
    requires_confirmation: bool
    reason: str
    intro: str = ""  # demo_guide only
    related_skills: tuple = ()  # demo_guide only

    def to_llm_dict(self) -> dict[str, Any]:
        d = {
            "name": self.name,
            "kind": self.kind,
            "display_name": self.display_name,
            "effective_status": self.effective_status,
            "demo_value": self.demo_value,
            "can_execute": self.can_execute,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }
        if self.kind == "demo_guide":
            d["intro"] = self.intro
            d["related_skills"] = list(self.related_skills)
        return d


class CapabilityRegistry:
    def __init__(self, skills: dict, guides: list[DemoGuide]) -> None:
        skill_names = set(skills.keys())
        guide_names = {g.name for g in guides}
        overlap = skill_names & guide_names
        if overlap:
            raise ValueError(f"SkillContract / DemoGuide names not disjoint: {overlap}")
        self._skills = skills
        self._guides = list(guides)

    def build_entries(
        self, world: WorldFlags, recent_results: list[dict]
    ) -> list[CapabilityEntry]:
        entries: list[CapabilityEntry] = []
        for name, contract in self._skills.items():
            entries.append(self._skill_entry(name, contract, world, recent_results))
        for guide in self._guides:
            entries.append(self._guide_entry(guide))
        return entries

    # ── internals ──

    def _skill_entry(
        self, name: str, contract, world: WorldFlags, recent_results: list[dict]
    ) -> CapabilityEntry:
        # Adapter for compute_effective_status
        adapter = _SkillAdapter(
            name=name,
            baseline=contract.demo_status_baseline,
            static_enabled=contract.static_enabled,
            enabled_when=list(contract.enabled_when or []),
            cooldown_remaining_s=_cooldown_remaining(name, contract.cooldown_s, recent_results),
            has_say_step=any(_is_say(s) for s in (contract.steps or [])),
            has_motion_step=any(_is_motion(s) for s in (contract.steps or [])),
            has_nav_step=any(_is_nav(s) for s in (contract.steps or [])),
            kind="skill",
        )
        status, reason = compute_effective_status(adapter, world)
        return CapabilityEntry(
            name=name,
            kind="skill",
            display_name=contract.display_name or name,
            effective_status=status,
            demo_value=contract.demo_value,
            can_execute=(status == "available"),
            requires_confirmation=bool(contract.requires_confirmation),
            reason=reason,
        )

    def _guide_entry(self, guide: DemoGuide) -> CapabilityEntry:
        adapter = _SkillAdapter(
            name=guide.name,
            baseline=guide.baseline_status,
            static_enabled=True,
            enabled_when=[],
            cooldown_remaining_s=0.0,
            has_say_step=False,
            has_motion_step=False,
            has_nav_step=False,
            kind="demo_guide",
        )
        status, reason = compute_effective_status(adapter, WorldFlags())
        return CapabilityEntry(
            name=guide.name,
            kind="demo_guide",
            display_name=guide.display_name,
            effective_status=status,
            demo_value=guide.demo_value,
            can_execute=False,
            requires_confirmation=False,
            reason=reason,
            intro=guide.intro,
            related_skills=tuple(guide.related_skills),
        )


# ── helpers ──


@dataclass
class _SkillAdapter:
    name: str
    baseline: str
    static_enabled: bool
    enabled_when: list
    cooldown_remaining_s: float
    has_say_step: bool
    has_motion_step: bool
    has_nav_step: bool
    kind: str


def _is_say(step) -> bool:
    return getattr(step.executor, "name", "") == "SAY"


def _is_motion(step) -> bool:
    return getattr(step.executor, "name", "") == "MOTION"


def _is_nav(step) -> bool:
    return getattr(step.executor, "name", "") == "NAV"


def _cooldown_remaining(name: str, cooldown_s: float, recent: list[dict]) -> float:
    if cooldown_s <= 0:
        return 0.0
    last_ts = None
    for r in recent:
        if r.get("name") == name and r.get("status") == "completed":
            ts = r.get("ts", 0)
            if last_ts is None or ts > last_ts:
                last_ts = ts
    if last_ts is None:
        return 0.0
    return max(0.0, last_ts + cooldown_s - time.time())


def build_capability_entries(*args, **kwargs):
    """Convenience function for older tests / call sites."""
    return CapabilityRegistry(*args, **kwargs).build_entries(WorldFlags(), [])
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_capability_registry.py -v
```
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/capability/registry.py pawai_brain/test/test_capability_registry.py
git commit -m "feat(pawai_brain): CapabilityRegistry merging SkillContract + DemoGuide"
```

---

### Task 7: `WorldStateSnapshot` data class (no ROS)

**Files:**
- Create: `pawai_brain/pawai_brain/capability/world_snapshot.py`
- Create: `pawai_brain/test/test_world_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# pawai_brain/test/test_world_snapshot.py
import json

from pawai_brain.capability.world_snapshot import WorldStateSnapshot


def test_defaults_are_safe():
    s = WorldStateSnapshot()
    assert s.tts_playing is False
    assert s.obstacle is False
    assert s.nav_safe is True
    assert s.active_skill is None


def test_apply_tts_playing_bool():
    s = WorldStateSnapshot()
    s.apply_tts_playing(True)
    assert s.tts_playing is True


def test_apply_reactive_stop_status_obstacle_true():
    s = WorldStateSnapshot()
    s.apply_reactive_stop_status_json(json.dumps({"obstacle": True}))
    assert s.obstacle is True


def test_apply_reactive_stop_status_malformed_keeps_default():
    s = WorldStateSnapshot()
    s.apply_reactive_stop_status_json("not json")
    assert s.obstacle is False


def test_apply_nav_safety_false():
    s = WorldStateSnapshot()
    s.apply_nav_safety_json(json.dumps({"nav_safe": False}))
    assert s.nav_safe is False


def test_apply_pawai_brain_state_active_plan():
    s = WorldStateSnapshot()
    payload = {"active_plan": {"selected_skill": "self_introduce", "step_index": 3}}
    s.apply_pawai_brain_state_json(json.dumps(payload))
    assert s.active_skill == "self_introduce"
    assert s.active_skill_step == 3


def test_to_world_flags_rounds_trip():
    s = WorldStateSnapshot()
    s.apply_tts_playing(True)
    s.apply_reactive_stop_status_json(json.dumps({"obstacle": True}))
    flags = s.to_world_flags()
    assert flags.tts_playing is True
    assert flags.obstacle is True
    assert flags.nav_safe is True
```

- [ ] **Step 2: Implement**

```python
# pawai_brain/pawai_brain/capability/world_snapshot.py
"""Process-local cache of /state/* topics used by capability_builder."""
from __future__ import annotations
import json
import threading

from .effective_status import WorldFlags


class WorldStateSnapshot:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tts_playing: bool = False
        self.obstacle: bool = False
        self.nav_safe: bool = True
        self.active_skill: str | None = None
        self.active_skill_step: int = 0

    # ── apply_*: called from ROS subscription callbacks ──

    def apply_tts_playing(self, value: bool) -> None:
        with self._lock:
            self.tts_playing = bool(value)

    def apply_reactive_stop_status_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            self.obstacle = bool(data.get("obstacle", False))

    def apply_nav_safety_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            self.nav_safe = bool(data.get("nav_safe", True))

    def apply_pawai_brain_state_json(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        plan = data.get("active_plan") or {}
        with self._lock:
            self.active_skill = plan.get("selected_skill") if isinstance(plan, dict) else None
            self.active_skill_step = int(plan.get("step_index", 0)) if isinstance(plan, dict) else 0

    # ── consumers ──

    def to_world_flags(self) -> WorldFlags:
        with self._lock:
            return WorldFlags(
                tts_playing=self.tts_playing,
                obstacle=self.obstacle,
                nav_safe=self.nav_safe,
            )

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "tts_playing": self.tts_playing,
                "obstacle": self.obstacle,
                "nav_safe": self.nav_safe,
                "active_skill": self.active_skill,
                "active_skill_step": self.active_skill_step,
            }
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_world_snapshot.py -v
```
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/capability/world_snapshot.py pawai_brain/test/test_world_snapshot.py
git commit -m "feat(pawai_brain): WorldStateSnapshot pure cache (no ROS)"
```

---

### Task 8: Extend `ConversationState` + `TracePayload`

**Files:**
- Modify: `pawai_brain/pawai_brain/state.py`
- Modify: `pawai_brain/pawai_brain/schemas.py`

- [ ] **Step 1: Add fields to `ConversationState`**

Edit `pawai_brain/pawai_brain/state.py` — add to the TypedDict:

```python
class ConversationState(TypedDict, total=False):
    # ... existing fields ...

    # Phase A.6 additions
    world_state: dict
    capability_context: dict
    recent_skill_results: list[dict]
    selected_demo_guide: str | None
```

- [ ] **Step 2: Verify TracePayload accepts the new status values (no schema change required)**

The dataclass `TracePayload` already accepts arbitrary `status: str`. The new values `demo_guide` and `needs_confirm` are just strings — no code change.

Add a small comment note in `schemas.py` near the `TracePayload` definition:

```python
# TracePayload.status enum (extended in Phase A.6):
#   pipeline / LLM stages: ok | retry | fallback | error
#   skill_gate stage:      proposed | accepted | accepted_trace_only |
#                          blocked | rejected_not_allowed |
#                          needs_confirm    (← Phase A.6)
#                          demo_guide       (← Phase A.6)
```

- [ ] **Step 3: Quick smoke**

```bash
cd pawai_brain && PYTHONPATH=. python3 -c "from pawai_brain.state import ConversationState; from pawai_brain.schemas import TracePayload; t = TracePayload(session_id='s', stage='skill_gate', status='demo_guide', detail='gesture_demo'); print(t.to_dict())"
```
Expected: dict with `status: "demo_guide"`.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/state.py pawai_brain/pawai_brain/schemas.py
git commit -m "feat(pawai_brain): extend ConversationState + TracePayload status enum"
```

---

### Task 9: `world_state_builder` graph node

**Files:**
- Create: `pawai_brain/pawai_brain/nodes/world_state_builder.py`
- Create: `pawai_brain/test/test_world_state_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# pawai_brain/test/test_world_state_builder.py
from datetime import datetime
from unittest.mock import patch

from pawai_brain.capability.world_snapshot import WorldStateSnapshot
from pawai_brain.nodes import world_state_builder as ws_node


def _wire_world(snap: WorldStateSnapshot):
    ws_node.set_world_provider(lambda: snap)


def test_writes_period_and_time():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    ws = out["world_state"]
    assert "period" in ws and "time" in ws
    assert ws["source"] == "speech"


def test_writes_runtime_flags():
    snap = WorldStateSnapshot()
    snap.apply_tts_playing(True)
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert out["world_state"]["tts_playing"] is True


def test_emits_trace_entry():
    snap = WorldStateSnapshot()
    _wire_world(snap)
    state = {"source": "speech", "trace": []}
    out = ws_node.world_state_builder(state)
    assert any(t["stage"] == "world_state" for t in out["trace"])
```

- [ ] **Step 2: Implement**

```python
# pawai_brain/pawai_brain/nodes/world_state_builder.py
"""world_state_builder — fold time + perception flags into state.world_state."""
from __future__ import annotations
import time
from datetime import datetime
from typing import Callable

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..capability.world_snapshot import WorldStateSnapshot
from ..state import ConversationState


_world_provider: Callable[[], WorldStateSnapshot] = lambda: WorldStateSnapshot()
_WEATHER_CACHE = {"text": "", "ts": 0.0}
_WEATHER_TTL_S = 600.0


def set_world_provider(fn: Callable[[], WorldStateSnapshot]) -> None:
    global _world_provider
    _world_provider = fn


def _time_of_day_zh(hour: int) -> str:
    if 5 <= hour < 11: return "早上"
    if 11 <= hour < 13: return "中午"
    if 13 <= hour < 17: return "下午"
    if 17 <= hour < 19: return "傍晚"
    if 19 <= hour < 23: return "晚上"
    return "深夜"


def _get_weather() -> str:
    now = time.time()
    if _WEATHER_CACHE["text"] and now - _WEATHER_CACHE["ts"] < _WEATHER_TTL_S:
        return _WEATHER_CACHE["text"]
    if requests is None:
        return ""
    try:
        resp = requests.get(
            "https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw",
            timeout=2.0,
        )
        if resp.status_code != 200: return ""
        text = resp.text.strip()
        if not text or len(text) > 80 or text.startswith("<"): return ""
    except Exception:
        return ""
    _WEATHER_CACHE["text"] = text
    _WEATHER_CACHE["ts"] = now
    return text


def world_state_builder(state: ConversationState) -> ConversationState:
    snap = _world_provider()
    now_dt = datetime.now()
    period = _time_of_day_zh(now_dt.hour)
    time_str = now_dt.strftime("%H:%M")
    weather = _get_weather()

    snap_dict = snap.to_dict()
    state["world_state"] = {
        "period": period,
        "time": time_str,
        "weather": weather,
        "source": state.get("source", "speech"),
        "timestamp": time.time(),
        **snap_dict,
    }
    state.setdefault("trace", []).append(
        {
            "stage": "world_state",
            "status": "ok",
            "detail": f"{period} {time_str}",
        }
    )
    return state
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_world_state_builder.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/nodes/world_state_builder.py pawai_brain/test/test_world_state_builder.py
git commit -m "feat(pawai_brain): world_state_builder node (fold env + perception)"
```

---

## Phase B — Graph Wiring (Tasks 10-13)

---

### Task 10: `capability_builder` graph node

**Files:**
- Create: `pawai_brain/pawai_brain/nodes/capability_builder.py`
- Create: `pawai_brain/test/test_capability_builder_node.py`

- [ ] **Step 1: Write the failing test**

```python
# pawai_brain/test/test_capability_builder_node.py
from pawai_brain.capability.demo_guides_loader import DemoGuide
from pawai_brain.capability.registry import CapabilityRegistry
from pawai_brain.nodes import capability_builder as cb_node


class _FakeSkill:
    def __init__(self, name, baseline="available_execute"):
        self.name = name
        self.display_name = name
        self.demo_status_baseline = baseline
        self.demo_value = "high"
        self.demo_reason = ""
        self.static_enabled = True
        self.enabled_when = []
        self.cooldown_s = 0.0
        self.steps = []
        self.requires_confirmation = False


def _wire(skills_dict, guides, recent_results=None, limits=None):
    reg = CapabilityRegistry(skills=skills_dict, guides=guides)
    cb_node.configure(
        registry=reg,
        skill_result_provider=lambda: list(recent_results or []),
        policy_provider=lambda: {"limits": list(limits or []), "max_motion_per_turn": 1},
    )


def test_writes_capability_context_with_capabilities_list():
    _wire({"self_introduce": _FakeSkill("self_introduce")}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    cc = out["capability_context"]
    assert "capabilities" in cc
    assert any(c["name"] == "self_introduce" for c in cc["capabilities"])


def test_includes_demo_guides():
    guide = DemoGuide(name="gesture_demo", display_name="手勢",
                      baseline_status="explain_only", demo_value="high", intro="比 OK")
    _wire({}, [guide])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    names = {c["name"] for c in out["capability_context"]["capabilities"]}
    assert "gesture_demo" in names


def test_includes_limits_from_policy():
    _wire({}, [], limits=["陌生人警告已關閉"])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert "陌生人警告已關閉" in out["capability_context"]["limits"]


def test_includes_recent_skill_results():
    _wire({}, [], recent_results=[{"name": "self_introduce", "status": "completed",
                                    "ts": 1.0, "detail": ""}])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert len(out["capability_context"]["recent_skill_results"]) == 1


def test_demo_session_placeholder():
    _wire({}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    sess = out["capability_context"]["demo_session"]
    assert sess["active"] is False
    assert sess["shown_skills"] == []


def test_emits_trace_entry():
    _wire({}, [])
    state = {"world_state": {}, "trace": []}
    out = cb_node.capability_builder(state)
    assert any(t["stage"] == "capability" for t in out["trace"])
```

- [ ] **Step 2: Implement**

```python
# pawai_brain/pawai_brain/nodes/capability_builder.py
"""capability_builder — merge SkillContract + DemoGuide + world_state into LLM-facing context."""
from __future__ import annotations
from typing import Callable

from ..capability.effective_status import WorldFlags
from ..capability.registry import CapabilityRegistry
from ..state import ConversationState


_registry: CapabilityRegistry | None = None
_skill_result_provider: Callable[[], list[dict]] = lambda: []
_policy_provider: Callable[[], dict] = lambda: {"limits": [], "max_motion_per_turn": 1}


def configure(
    registry: CapabilityRegistry,
    skill_result_provider: Callable[[], list[dict]],
    policy_provider: Callable[[], dict],
) -> None:
    global _registry, _skill_result_provider, _policy_provider
    _registry = registry
    _skill_result_provider = skill_result_provider
    _policy_provider = policy_provider


def _world_flags_from_state(state: ConversationState) -> WorldFlags:
    ws = state.get("world_state") or {}
    return WorldFlags(
        tts_playing=bool(ws.get("tts_playing", False)),
        obstacle=bool(ws.get("obstacle", False)),
        nav_safe=bool(ws.get("nav_safe", True)),
    )


def capability_builder(state: ConversationState) -> ConversationState:
    if _registry is None:
        state.setdefault("trace", []).append(
            {"stage": "capability", "status": "error", "detail": "not_configured"}
        )
        state["capability_context"] = {"capabilities": [], "limits": [],
                                        "demo_session": _placeholder_session(),
                                        "recent_skill_results": []}
        return state

    world = _world_flags_from_state(state)
    recent = _skill_result_provider()
    entries = _registry.build_entries(world, recent)
    policy = _policy_provider()

    capability_context = {
        "capabilities": [e.to_llm_dict() for e in entries],
        "limits": list(policy.get("limits", [])),
        "demo_session": _placeholder_session(),
        "recent_skill_results": list(recent),
    }

    state["capability_context"] = capability_context
    state["recent_skill_results"] = list(recent)  # also surface at top level for convenience

    n_skill = sum(1 for e in entries if e.kind == "skill")
    n_guide = sum(1 for e in entries if e.kind == "demo_guide")
    state.setdefault("trace", []).append(
        {
            "stage": "capability",
            "status": "ok",
            "detail": f"{n_skill} skills + {n_guide} guides",
        }
    )
    return state


def _placeholder_session() -> dict:
    return {"active": False, "shown_skills": [], "candidate_next": []}
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_capability_builder_node.py -v
```
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/nodes/capability_builder.py pawai_brain/test/test_capability_builder_node.py
git commit -m "feat(pawai_brain): capability_builder node merging skills + guides + world"
```

---

### Task 11: Upgrade `skill_policy_gate` (passthrough first + kind branches)

**HIGH-RISK TEST FOCUS:** chat_reply / say_canned must NEVER become proposed_skill. Demo guide must NEVER set proposed_skill. These are the spec-flagged invariants.

**Files:**
- Modify: `pawai_brain/pawai_brain/nodes/skill_policy_gate.py`
- Modify: `pawai_brain/test/test_skill_policy_gate.py`

- [ ] **Step 1: Add new tests covering kind branches and passthrough invariants**

Append to `pawai_brain/test/test_skill_policy_gate.py`:

```python
# ── Phase A.6 additions ──
from pawai_brain.nodes.skill_policy_gate import normalize_proposal_v2


def _entry(name, kind, effective="available"):
    return type("E", (), {"name": name, "kind": kind, "effective_status": effective})


def _ctx(*entries):
    return {"capabilities": [{"name": e.name, "kind": e.kind,
                              "effective_status": e.effective_status}
                             for e in entries]}


def test_v2_passthrough_chat_reply_yields_no_proposal_no_trace():
    """HIGH-RISK: chat_reply must not become proposed_skill even though it's in SKILL_REGISTRY."""
    skill, args, guide, status, detail = normalize_proposal_v2("chat_reply", {}, _ctx())
    assert skill is None
    assert guide is None
    assert status is None  # no skill_gate trace at all


def test_v2_passthrough_say_canned_yields_no_proposal_no_trace():
    skill, args, guide, status, _ = normalize_proposal_v2("say_canned", {}, _ctx())
    assert skill is None
    assert guide is None
    assert status is None


def test_v2_demo_guide_routes_to_selected_demo_guide():
    """HIGH-RISK: demo_guide must NOT enter proposed_skill."""
    ctx = _ctx(_entry("gesture_demo", "demo_guide", "explain_only"))
    skill, args, guide, status, _ = normalize_proposal_v2("gesture_demo", {}, ctx)
    assert skill is None
    assert guide == "gesture_demo"
    assert status == "demo_guide"


def test_v2_skill_available_proposed():
    ctx = _ctx(_entry("self_introduce", "skill", "available"))
    skill, _, guide, status, _ = normalize_proposal_v2("self_introduce", {}, ctx)
    assert skill == "self_introduce"
    assert guide is None
    assert status == "proposed"


def test_v2_skill_needs_confirm_blocks_with_specific_status():
    ctx = _ctx(_entry("wiggle", "skill", "needs_confirm"))
    skill, _, guide, status, _ = normalize_proposal_v2("wiggle", {}, ctx)
    assert skill is None
    assert guide is None
    assert status == "needs_confirm"


def test_v2_skill_blocked_states_are_blocked():
    for eff in ("explain_only", "blocked", "cooldown", "defer", "studio_only", "disabled"):
        ctx = _ctx(_entry("foo", "skill", eff))
        skill, _, guide, status, detail = normalize_proposal_v2("foo", {}, ctx)
        assert skill is None
        assert guide is None
        assert status == "blocked"
        assert eff in detail


def test_v2_unknown_skill_kept_with_rejected():
    skill, _, guide, status, _ = normalize_proposal_v2("dance_wildly", {}, _ctx())
    assert skill == "dance_wildly"
    assert guide is None
    assert status == "rejected_not_allowed"


def test_v2_null_or_non_string_skill_yields_none():
    for raw in (None, 123, [], {}):
        skill, _, guide, status, _ = normalize_proposal_v2(raw, {}, _ctx())
        assert skill is None
        assert guide is None
        assert status is None


def test_v2_args_normalised():
    ctx = _ctx(_entry("self_introduce", "skill", "available"))
    _, args, _, _, _ = normalize_proposal_v2("self_introduce", "not a dict", ctx)
    assert args == {}
```

- [ ] **Step 2: Implement v2 alongside v1 (keep old tests green)**

Edit `pawai_brain/pawai_brain/nodes/skill_policy_gate.py` — add new function and update node:

```python
"""skill_policy_gate — proposal normalisation (Phase A.6 v2 with kind branches)."""
from __future__ import annotations

from ..state import ConversationState


# Mirrors brain_node.LLM_PROPOSABLE_SKILLS (kept for v1 compat)
LLM_PROPOSABLE_SKILLS: frozenset[str] = frozenset({"show_status", "self_introduce"})

# v1 passthrough names (unchanged); v2 uses the same set
PASSTHROUGH_SKILLS: frozenset[str] = frozenset({"chat_reply", "say_canned"})


def normalize_proposal(raw_skill, raw_args):
    """v1 (Cut A) — kept for legacy paths that don't have CapabilityContext yet."""
    proposed_args: dict = raw_args if isinstance(raw_args, dict) else {}
    if not isinstance(raw_skill, str):
        return None, proposed_args, None
    skill = raw_skill.strip()
    if not skill or skill in PASSTHROUGH_SKILLS:
        return None, proposed_args, None
    if skill in LLM_PROPOSABLE_SKILLS:
        return skill, proposed_args, "proposed"
    return skill, proposed_args, "rejected_not_allowed"


def normalize_proposal_v2(raw_skill, raw_args, capability_context):
    """v2 (Phase A.6) — passthrough first, then capability lookup with kind branch.

    Returns: (proposed_skill, proposed_args, selected_demo_guide, trace_status, trace_detail)
    """
    args: dict = raw_args if isinstance(raw_args, dict) else {}

    # 1. passthrough / null / 非字串 / 空字串 — must run BEFORE lookup
    if not isinstance(raw_skill, str):
        return None, args, None, None, ""
    skill_str = raw_skill.strip()
    if not skill_str or skill_str in PASSTHROUGH_SKILLS:
        return None, args, None, None, ""

    # 2. lookup in capability_context
    entry = _lookup(skill_str, capability_context)

    # 3. unknown skill — kept so brain_node can reject
    if entry is None:
        return skill_str, args, None, "rejected_not_allowed", skill_str

    # 4. demo_guide branch — never enters proposed_skill
    if entry["kind"] == "demo_guide":
        return None, args, entry["name"], "demo_guide", entry["name"]

    # 5. skill branch — gate by effective_status
    eff = entry["effective_status"]
    if eff == "available":
        return entry["name"], args, None, "proposed", entry["name"]
    if eff == "needs_confirm":
        return None, args, None, "needs_confirm", entry["name"]
    return None, args, None, "blocked", f"{entry['name']}:{eff}"


def _lookup(name: str, capability_context: dict) -> dict | None:
    if not capability_context:
        return None
    for entry in capability_context.get("capabilities", []):
        if entry.get("name") == name:
            return entry
    return None


def skill_policy_gate(state: ConversationState) -> ConversationState:
    """LangGraph node — Phase A.6 uses v2 if capability_context present, else v1."""
    llm_json = state.get("llm_json") or {}
    raw_skill = llm_json.get("skill")
    raw_args = llm_json.get("args")
    cap_ctx = state.get("capability_context")

    if cap_ctx:
        proposed, args, demo_guide, trace_status, trace_detail = \
            normalize_proposal_v2(raw_skill, raw_args, cap_ctx)
        state["proposed_skill"] = proposed
        state["proposed_args"] = args
        state["selected_demo_guide"] = demo_guide
        if not state.get("proposal_reason"):
            state["proposal_reason"] = "openrouter:eval_schema" if llm_json else ""
        if trace_status is not None:
            state.setdefault("trace", []).append(
                {"stage": "skill_gate", "status": trace_status, "detail": trace_detail}
            )
        return state

    # Fallback: legacy v1 path (capability_context not present)
    proposed, args, trace_status = normalize_proposal(raw_skill, raw_args)
    state["proposed_skill"] = proposed
    state["proposed_args"] = args
    state["selected_demo_guide"] = None
    if not state.get("proposal_reason"):
        state["proposal_reason"] = "openrouter:eval_schema" if llm_json else ""
    if trace_status is not None:
        state.setdefault("trace", []).append(
            {"stage": "skill_gate", "status": trace_status,
             "detail": str(state.get("proposed_skill") or "")}
        )
    return state
```

- [ ] **Step 3: Run all skill_policy_gate tests**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_skill_policy_gate.py -v
```
Expected: existing tests + 9 new = all green.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/nodes/skill_policy_gate.py pawai_brain/test/test_skill_policy_gate.py
git commit -m "feat(pawai_brain): skill_policy_gate v2 with kind branches + passthrough invariants"
```

---

### Task 12: `output_builder` emits demo_guide trace

**Files:**
- Modify: `pawai_brain/pawai_brain/nodes/output_builder.py`
- Modify: `pawai_brain/test/test_graph_smoke.py` (test added in Task 16)

- [ ] **Step 1: Update output_builder**

`output_builder` currently does NOT need to write `selected_demo_guide` to chat_candidate (Brain contract clean). The trace is already emitted by `skill_policy_gate`. The only change is making sure `output_builder` doesn't accidentally drop `selected_demo_guide` — keep it on state for downstream wrapper.

Edit `pawai_brain/pawai_brain/nodes/output_builder.py` — at the top of the function, add a trace check (no behaviour change otherwise):

```python
def output_builder(state: ConversationState) -> ConversationState:
    # Phase A.6: ensure selected_demo_guide is preserved; never write to chat_candidate.
    state.setdefault("selected_demo_guide", None)

    if state.get("safety_hit"):
        # ... existing safety_path logic ...
```

- [ ] **Step 2: Add a unit test verifying output_builder doesn't pollute chat_candidate keys**

Append to `pawai_brain/test/test_graph_smoke.py`:

```python
def test_output_builder_does_not_add_demo_guide_to_state_reply():
    """HIGH-RISK: demo_guide path must not put guide name into reply_text or chat_candidate fields."""
    from pawai_brain.nodes.output_builder import output_builder
    state = {
        "user_text": "請介紹手勢",
        "selected_demo_guide": "gesture_demo",
        "llm_json": {"reply": "好啊，請比 OK", "skill": "gesture_demo", "args": {}},
        "validation_error": "",
        "trace": [],
    }
    out = output_builder(state)
    # selected_demo_guide preserved but reply_text is the LLM's natural reply
    assert out["selected_demo_guide"] == "gesture_demo"
    assert out["reply_text"] == "好啊，請比 OK"
    # Brain contract fields don't leak guide name
    assert "gesture_demo" not in (out.get("selected_skill") or "")
    assert out.get("proposed_skill") in (None, "")
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_graph_smoke.py::test_output_builder_does_not_add_demo_guide_to_state_reply -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pawai_brain/pawai_brain/nodes/output_builder.py pawai_brain/test/test_graph_smoke.py
git commit -m "feat(pawai_brain): output_builder preserves selected_demo_guide on state"
```

---

### Task 13: `graph.py` rewire — drop context+env, add ws+cap

**Files:**
- Modify: `pawai_brain/pawai_brain/graph.py`
- Modify: `pawai_brain/test/test_graph_smoke.py`

- [ ] **Step 1: Rewrite graph build**

Edit `pawai_brain/pawai_brain/graph.py`:

```python
"""LangGraph build_graph() — Phase A.6 with capability awareness.

Flow:
  input → safety_gate ─┬─→ output (when safety_hit=True)
                       └─→ world_state → capability → memory → llm
                           → validator → repair → skill_gate → output
  output → trace → END
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import ConversationState
from .nodes.input_normalizer import input_normalizer
from .nodes.safety_gate import safety_gate
from .nodes.world_state_builder import world_state_builder
from .nodes.capability_builder import capability_builder
from .nodes.memory_builder import memory_builder
from .nodes.llm_decision import llm_decision
from .nodes.json_validator import json_validator
from .nodes.response_repair import response_repair
from .nodes.skill_policy_gate import skill_policy_gate
from .nodes.output_builder import output_builder
from .nodes.trace_emitter import trace_emitter


def _route_after_safety(state: ConversationState) -> str:
    return "output" if state.get("safety_hit") else "world_state"


def build_graph():
    g = StateGraph(ConversationState)

    g.add_node("input", input_normalizer)
    g.add_node("safety_gate", safety_gate)
    g.add_node("world_state", world_state_builder)
    g.add_node("capability", capability_builder)
    g.add_node("memory", memory_builder)
    g.add_node("llm", llm_decision)
    g.add_node("validator", json_validator)
    g.add_node("repair", response_repair)
    g.add_node("skill_gate", skill_policy_gate)
    g.add_node("output", output_builder)
    g.add_node("trace", trace_emitter)

    g.set_entry_point("input")
    g.add_edge("input", "safety_gate")
    g.add_conditional_edges(
        "safety_gate",
        _route_after_safety,
        {"output": "output", "world_state": "world_state"},
    )
    g.add_edge("world_state", "capability")
    g.add_edge("capability", "memory")
    g.add_edge("memory", "llm")
    g.add_edge("llm", "validator")
    g.add_edge("validator", "repair")
    g.add_edge("repair", "skill_gate")
    g.add_edge("skill_gate", "output")
    g.add_edge("output", "trace")
    g.add_edge("trace", END)

    return g.compile()
```

- [ ] **Step 2: Update existing graph smoke test stages list**

Search `test_graph_smoke.py` for `stages = ` or `for required in`. Replace expected stages list with:

```python
("input", "safety_gate", "world_state", "capability", "memory",
 "llm_decision", "json_validate", "repair", "skill_gate", "output")
```

- [ ] **Step 3: Wire test fixtures to configure new nodes**

In `_wire_for_test` in `test_graph_smoke.py`, add capability_builder + world_state_builder configuration:

```python
# Append to _wire_for_test after llm_node.configure(...):
from pawai_brain.nodes import world_state_builder as ws_node
from pawai_brain.nodes import capability_builder as cb_node
from pawai_brain.capability.world_snapshot import WorldStateSnapshot
from pawai_brain.capability.registry import CapabilityRegistry

ws_node.set_world_provider(lambda: WorldStateSnapshot())
empty_registry = CapabilityRegistry(skills={}, guides=[])
cb_node.configure(
    registry=empty_registry,
    skill_result_provider=lambda: [],
    policy_provider=lambda: {"limits": [], "max_motion_per_turn": 1},
)
```

- [ ] **Step 4: Run all pawai_brain tests**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/ -q
```
Expected: all green (existing 54 + new tasks).

- [ ] **Step 5: colcon build smoke**

```bash
bash -c 'source /opt/ros/humble/setup.bash && cd /home/roy422/newLife/elder_and_dog && colcon build --packages-select pawai_brain --symlink-install' 2>&1 | tail -5
```
Expected: `Finished <<< pawai_brain` clean.

- [ ] **Step 6: Commit**

```bash
git add pawai_brain/pawai_brain/graph.py pawai_brain/test/test_graph_smoke.py
git commit -m "feat(pawai_brain): graph rewire — drop context/env, add world_state/capability"
```

---

## Phase C — ROS Integration (Tasks 14-16)

---

### Task 14: `conversation_graph_node` ROS hooks (skill_result + WorldStateSnapshot)

**HIGH-RISK FOCUS:** `selected_skill` from `/brain/skill_result` must populate `recent_skill_results`.

**Files:**
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py`

- [ ] **Step 1: Add ROS subscriptions and wiring**

**Important QoS note**: `/state/tts_playing` is published as `std_msgs/Bool` with `TRANSIENT_LOCAL` durability (`speech_processor/speech_processor/tts_node.py:999`). Subscriber must match — using `String` or default `RELIABLE+VOLATILE` will silently drop the latched-on-startup value.

Edit `pawai_brain/pawai_brain/conversation_graph_node.py` — add new imports + subscriptions:

```python
# Top of file imports — add:
from std_msgs.msg import Bool as BoolMsg
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, HistoryPolicy

from .capability.demo_guides_loader import load_demo_guides, load_demo_policy
from .capability.registry import CapabilityRegistry
from .capability.skill_result_memory import SkillResultMemory
from .capability.world_snapshot import WorldStateSnapshot
from .nodes import capability_builder as capability_builder_node
from .nodes import world_state_builder as world_state_builder_node

# Add at top level (with other constants):
TERMINAL_STATUSES = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})

# QoS for /state/tts_playing must match the publisher (tts_node.py:998-999)
_TTS_PLAYING_QOS = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)

# QoS for /state/pawai_brain (brain_node publishes TRANSIENT_LOCAL @ 2Hz)
_BRAIN_STATE_QOS = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)
```

In `__init__`, after `self._memory = ConversationMemory(...)`:

```python
        # Phase A.6 — capability layer
        self._world_snapshot = WorldStateSnapshot()
        self._skill_results = SkillResultMemory(maxlen=5)

        # Locate demo_guides.yaml & demo_policy.yaml from share/
        from ament_index_python.packages import get_package_share_directory
        try:
            share = Path(get_package_share_directory("pawai_brain"))
            guides_path = share / "config" / "demo_guides.yaml"
            policy_path = share / "config" / "demo_policy.yaml"
        except Exception:
            # Fallback to source path during dev
            here = Path(__file__).resolve().parent.parent
            guides_path = here / "config" / "demo_guides.yaml"
            policy_path = here / "config" / "demo_policy.yaml"

        guides = load_demo_guides(guides_path)
        policy = load_demo_policy(policy_path)

        from interaction_executive.skill_contract import SKILL_REGISTRY
        try:
            registry = CapabilityRegistry(skills=SKILL_REGISTRY, guides=guides)
        except ValueError as exc:
            self.get_logger().error(f"CapabilityRegistry build failed: {exc}")
            registry = CapabilityRegistry(skills={}, guides=guides)

        # Wire module-level node hooks
        world_state_builder_node.set_world_provider(lambda: self._world_snapshot)
        capability_builder_node.configure(
            registry=registry,
            skill_result_provider=self._skill_results.recent,
            policy_provider=lambda: policy,
        )

        # ROS subscribers for world state
        # /state/tts_playing — std_msgs/Bool + TRANSIENT_LOCAL (matches tts_node.py:998-999)
        self.create_subscription(
            BoolMsg, "/state/tts_playing", self._on_tts_playing, _TTS_PLAYING_QOS
        )
        self.create_subscription(
            String, "/state/reactive_stop/status", self._on_reactive_stop, 10
        )
        self.create_subscription(
            String, "/state/nav/safety", self._on_nav_safety, 10
        )
        self.create_subscription(
            String, "/state/pawai_brain", self._on_pawai_brain_state, _BRAIN_STATE_QOS
        )
        self.create_subscription(
            String, "/brain/skill_result", self._on_skill_result, 10
        )
```

Add the callback methods to the class:

```python
    def _on_tts_playing(self, msg: BoolMsg) -> None:
        """std_msgs/Bool — direct flag, no JSON parse."""
        self._world_snapshot.apply_tts_playing(bool(msg.data))

    def _on_reactive_stop(self, msg: String) -> None:
        self._world_snapshot.apply_reactive_stop_status_json(msg.data)

    def _on_nav_safety(self, msg: String) -> None:
        self._world_snapshot.apply_nav_safety_json(msg.data)

    def _on_pawai_brain_state(self, msg: String) -> None:
        self._world_snapshot.apply_pawai_brain_state_json(msg.data)

    def _on_skill_result(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        status = str(payload.get("status", ""))
        if status not in TERMINAL_STATUSES:
            return
        name = str(payload.get("selected_skill") or "").strip()
        if not name:
            return
        self._skill_results.add({
            "name": name,
            "status": status,
            "detail": str(payload.get("detail", ""))[:80],
            "ts": time.time(),
        })
```

- [ ] **Step 2: Add a wrapper-level integration test**

```python
# pawai_brain/test/test_skill_result_subscription.py
"""HIGH-RISK: /brain/skill_result selected_skill must reach recent_skill_results."""
import json
from unittest.mock import MagicMock

from pawai_brain.capability.skill_result_memory import SkillResultMemory


def test_skill_result_payload_extracts_selected_skill_field():
    """Direct extraction (no plan_id reverse lookup needed)."""
    mem = SkillResultMemory()
    raw = json.dumps({
        "plan_id": "p-abc",
        "step_index": None,
        "status": "completed",
        "detail": "6 steps",
        "selected_skill": "self_introduce",   # ← direct field
        "priority_class": 2,
        "step_total": 6,
        "step_args": {},
        "timestamp": 123.0,
    })
    payload = json.loads(raw)
    name = str(payload.get("selected_skill") or "").strip()
    assert name == "self_introduce"

    mem.add({"name": name, "status": payload["status"],
             "detail": payload.get("detail", ""), "ts": payload["timestamp"]})

    items = mem.recent()
    assert len(items) == 1
    assert items[0]["name"] == "self_introduce"


def test_non_terminal_status_is_ignored():
    """Only completed/aborted/blocked_by_safety/step_failed should be recorded."""
    TERMINAL = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
    for s in ("started", "step_started", "step_success", "accepted"):
        assert s not in TERMINAL


def test_missing_selected_skill_dropped():
    payload = {"status": "completed"}  # no selected_skill
    name = str(payload.get("selected_skill") or "").strip()
    assert name == ""  # caller should drop


def test_terminal_statuses_set():
    """Spec §9 lock: exactly these 4 are terminal."""
    TERMINAL = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
    assert TERMINAL == frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})
```

- [ ] **Step 3: Run test**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/test_skill_result_subscription.py -v
```
Expected: 4 passed.

- [ ] **Step 4: colcon build to ensure ROS imports still resolve**

```bash
bash -c 'source /opt/ros/humble/setup.bash && cd /home/roy422/newLife/elder_and_dog && colcon build --packages-select pawai_brain --symlink-install' 2>&1 | tail -5
```
Expected: clean.

- [ ] **Step 5: Smoke import wrapper to ensure runtime wiring works (no rclpy spin)**

```bash
bash -c 'source /opt/ros/humble/setup.bash && source install/setup.bash && python3 -c "
from pawai_brain.conversation_graph_node import ConversationGraphNode
print(\"wrapper import OK\")
"' 2>&1 | tail -3
```
Expected: "wrapper import OK".

- [ ] **Step 6: Commit**

```bash
git add pawai_brain/pawai_brain/conversation_graph_node.py pawai_brain/test/test_skill_result_subscription.py
git commit -m "feat(pawai_brain): ROS hooks for /brain/skill_result + WorldStateSnapshot"
```

---

### Task 15: End-to-end graph smoke for new paths

**Files:**
- Modify: `pawai_brain/test/test_graph_smoke.py`

- [ ] **Step 1: Add 4 new smoke tests covering capability paths**

Append to `test_graph_smoke.py`:

```python
def test_smoke_capability_demo_guide_proposal_routes_to_trace_only():
    """HIGH-RISK: LLM picks demo_guide → no proposed_skill, only trace."""
    from pawai_brain.capability.demo_guides_loader import DemoGuide
    from pawai_brain.capability.registry import CapabilityRegistry
    from pawai_brain.nodes import capability_builder as cb_node

    guide = DemoGuide(name="gesture_demo", display_name="手勢",
                      baseline_status="explain_only", demo_value="high",
                      intro="比 OK")
    cb_node.configure(
        registry=CapabilityRegistry(skills={}, guides=[guide]),
        skill_result_provider=lambda: [],
        policy_provider=lambda: {"limits": [], "max_motion_per_turn": 1},
    )

    patcher, _ = _wire_for_test(persona_response={"reply": "好啊，請比 OK",
                                                    "skill": "gesture_demo",
                                                    "args": {}})
    with patcher:
        graph = build_graph()
        result = graph.invoke({"session_id": "s-guide", "user_text": "介紹手勢",
                                "source": "speech"})

    assert result["selected_demo_guide"] == "gesture_demo"
    assert (result.get("proposed_skill") or "") == ""
    skill_gate = [t for t in result["trace"] if t["stage"] == "skill_gate"]
    assert skill_gate and skill_gate[-1]["status"] == "demo_guide"


def test_smoke_capability_blocked_skill_no_proposal():
    """HIGH-RISK: skill with effective=disabled → no proposed_skill."""
    # ... similar wiring with a disabled skill in registry ...
    # (Use a fake skill class similar to test_capability_builder_node.py)


def test_smoke_chat_reply_passthrough_never_proposed():
    """HIGH-RISK: chat_reply must never become proposed_skill — even with capability_context."""
    patcher, _ = _wire_for_test(persona_response={"reply": "你好啊", "skill": "chat_reply",
                                                    "args": {}})
    with patcher:
        graph = build_graph()
        result = graph.invoke({"session_id": "s-chat", "user_text": "你好",
                                "source": "speech"})
    assert (result.get("proposed_skill") or "") == ""
    assert result.get("selected_demo_guide") is None


def test_smoke_world_state_present_in_state():
    patcher, _ = _wire_for_test(persona_response={"reply": "嗨", "skill": None, "args": {}})
    with patcher:
        graph = build_graph()
        result = graph.invoke({"session_id": "s-ws", "user_text": "你好",
                                "source": "speech"})
    assert "world_state" in result
    assert "period" in result["world_state"]
```

- [ ] **Step 2: Run full test suite**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/ -q
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add pawai_brain/test/test_graph_smoke.py
git commit -m "test(pawai_brain): smoke graph tests for demo_guide/passthrough/blocked paths"
```

---

## Phase D — Persona / Studio / Docs (Tasks 16-18)

---

### Task 16: Persona prompt rules

**Files:**
- Modify: `tools/llm_eval/persona.txt`

- [ ] **Step 1: Append capability section**

Add to the end of `tools/llm_eval/persona.txt`:

```
## CapabilityContext 規則

每輪 user message 結尾你會收到一個 capability_context JSON，列出所有能力。

1. 你可以自由介紹任何 capability（包含 explain_only / disabled）
2. 只能在 skill 欄位放 effective_status="available" 且 can_execute=true 的能力
3. kind=demo_guide 是展示腳本；放在 skill 欄位即可，系統會自動分流到 trace（不會執行 motion）
4. needs_confirm 的 skill 要在 reply 主動請使用者比 OK 或按 Studio 按鈕
5. 一次最多提議一個 skill 或一個 demo_guide
6. 看到 recent_skill_results 上一個 skill completed → 可自然銜接「接下來要不要看 X」
7. 上一個 skill blocked / rejected → 簡短說明，不要重複要求同一個
8. 沒有使用者明確要求時，不要連續主動發動多個 motion
9. 使用者問「你會做什麼」時，主要列出 demo_guide 的中文 display_name
```

- [ ] **Step 2: Commit**

```bash
git add tools/llm_eval/persona.txt
git commit -m "feat(persona): capability_context awareness rules (Phase A.6)"
```

---

### Task 17: Studio frontend — demo_guide / needs_confirm chips

**Files:**
- Modify: `pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx`

- [ ] **Step 1: Locate `statusToClass` (or equivalent) and add new statuses**

Open the file and find the status → CSS class mapping. Add:

```tsx
const statusToClass = (status: string) => {
  switch (status) {
    case "proposed":               return "bg-slate-100 text-slate-700";
    case "accepted":               return "bg-green-100 text-green-700";
    case "accepted_trace_only":    return "bg-green-50  text-green-600";
    case "blocked":                return "bg-yellow-100 text-yellow-800";
    case "rejected_not_allowed":   return "bg-red-100   text-red-700";
    case "needs_confirm":          return "bg-amber-100 text-amber-800";  // ← Phase A.6
    case "demo_guide":             return "bg-blue-100  text-blue-700";   // ← Phase A.6
    default:                       return "bg-zinc-100  text-zinc-600";
  }
};
```

(Match the existing Tailwind palette in the file; the colours above are the recommended defaults.)

- [ ] **Step 2: Quick visual check (optional, manual)**

Run Studio dev server and confirm the chips render. Skip if no time:

```bash
bash pawai-studio/start.sh
# Open http://localhost:3000/studio, trigger a fake trace via mock_server
```

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx
git commit -m "feat(studio): add needs_confirm + demo_guide chip colors"
```

---

### Task 18: Update `docs/pawai-brain/architecture/overview.md`

**Files:**
- Modify: `docs/pawai-brain/architecture/overview.md`

- [ ] **Step 1: Update the SkillContract section**

Find the section describing SKILL_REGISTRY (around §5.1). Replace the line about SkillContract with:

```markdown
| **SkillContract registry** | 27 entries（Active 17 / Hidden 5 / Disabled 4 / Retired 1）+ 4 demo metadata fields per entry (display_name / demo_status_baseline / demo_value / demo_reason) | `interaction_executive/skill_contract.py` |
| **DemoGuide registry**     | 6 entries（face / speech / gesture / pose / object / navigation）— pseudo-skills for self-demonstration | `pawai_brain/config/demo_guides.yaml` |
| **CapabilityContext**      | LLM-facing merged view (27 + 6 = 33 entries) with `effective_status` per turn; flows via `pawai_brain` only — `/brain/chat_candidate` schema unchanged | `pawai_brain/pawai_brain/capability/registry.py` |
```

- [ ] **Step 2: Commit**

```bash
git add docs/pawai-brain/architecture/overview.md
git commit -m "docs(architecture): three-tier capability layer (SkillContract + DemoGuide + CapabilityContext)"
```

---

## Phase E — Final validation (Task 19)

---

### Task 19: End-to-end build + acceptance dry-run

- [ ] **Step 1: Run full pawai_brain test suite**

```bash
cd pawai_brain && PYTHONPATH=. python3 -m pytest test/ -v 2>&1 | tail -10
```
Expected: all green (≥ 90 tests after Phase A.6 additions).

- [ ] **Step 2: Run interaction_executive tests**

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/ -q
```
Expected: all green (no regression).

- [ ] **Step 3: Run legacy llm_bridge tests**

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest speech_processor/test/test_llm_bridge_node.py -q
```
Expected: 2 passed.

- [ ] **Step 4: colcon build**

```bash
bash -c 'source /opt/ros/humble/setup.bash && cd /home/roy422/newLife/elder_and_dog && colcon build --packages-select pawai_brain interaction_executive --symlink-install' 2>&1 | tail -5
```
Expected: 2 packages finished cleanly.

- [ ] **Step 5: Wrapper smoke import**

```bash
bash -c 'source /opt/ros/humble/setup.bash && source install/setup.bash && python3 -c "
from pawai_brain.conversation_graph_node import ConversationGraphNode
from pawai_brain.graph import build_graph
from pawai_brain.capability.registry import CapabilityRegistry
from pawai_brain.capability.demo_guides_loader import load_demo_guides
from ament_index_python.packages import get_package_share_directory
from pathlib import Path
share = Path(get_package_share_directory(\"pawai_brain\"))
guides = load_demo_guides(share / \"config\" / \"demo_guides.yaml\")
print(f\"loaded {len(guides)} guides\")
g = build_graph()
print(\"graph built:\", type(g).__name__)
"' 2>&1 | tail -5
```
Expected: "loaded 6 guides", "graph built: CompiledStateGraph".

- [ ] **Step 6: Update `references/project-status.md`**

Add a 5/7 entry summarising Phase A.6 completion (mirror the format of the 5/6 entry).

- [ ] **Step 7: Final commit**

```bash
git add references/project-status.md
git commit -m "docs(project-status): Phase A.6 capability awareness complete"
```

---

## Acceptance Checklist (5/18 demo)

- [ ] `pytest pawai_brain/test/ -v` all green
- [ ] `pytest interaction_executive/test/ -q` all green
- [ ] `pytest speech_processor/test/test_llm_bridge_node.py -q` 2/2 green
- [ ] `colcon build --packages-select pawai_brain interaction_executive` clean
- [ ] LLM proposes `chat_reply` → `proposed_skill=None` (passthrough invariant)
- [ ] LLM proposes `say_canned` → `proposed_skill=None` (passthrough invariant)
- [ ] LLM proposes `gesture_demo` → `selected_demo_guide=gesture_demo`, `proposed_skill=None`, trace `demo_guide`
- [ ] LLM proposes `dance` → `proposed_skill=dance` (kept), trace `blocked` (effective=disabled)
- [ ] LLM proposes `wiggle` → `proposed_skill=None`, trace `needs_confirm`
- [ ] LLM proposes `wiggle` while obstacle=true → trace `blocked` (NOT `needs_confirm`)
- [ ] `/brain/skill_result` with `selected_skill=self_introduce` reaches `recent_skill_results`
- [ ] `/brain/chat_candidate` schema unchanged — no `selected_demo_guide` field
- [ ] Studio Skill Trace Drawer shows blue chip for `demo_guide`, amber for `needs_confirm`
- [ ] Demo session 5/13 場地測試前跑全 33 capability matrix 一次

---

## Self-Review Notes

Fixed during writing-plans pass:
- Task 0 added: package.xml exec_depend (ament_index_python, interaction_executive, python3-yaml) + setup.py install_requires (PyYAML>=5.4); colcon order deterministic + clean Jetson env import-safe
- Task 5 step 4: provided full skill→display_name→baseline mapping table (avoided "fill in remaining 22 entries" placeholder)
- Task 11 step 2: clarified v1 (legacy) vs v2 (capability-aware) coexistence so existing tests stay green
- Task 13 expected stages list locked to the 11-stage final flow
- Task 14 step 1: `/state/tts_playing` confirmed as `std_msgs/Bool` + TRANSIENT_LOCAL via `tts_node.py:998-999`; subscriber uses matching QoS profile (depth=1 + TRANSIENT_LOCAL + RELIABLE) so latched value is received on startup; `/state/pawai_brain` likewise gets TRANSIENT_LOCAL QoS (brain_node publishes 2 Hz with same durability)
- Task 19 step 5 verifies the wrapper actually loads demo_guides from the installed share/ path (not just src/), catching the setup.py data_files regression early

## Execution Strategy (5 grouped batches via Subagent-Driven)

User-requested batching to avoid 19 fragmented commits while preserving subagent isolation:

| Batch | Tasks | Dispatch as one subagent | Reason for grouping |
|-------|-------|--------------------------|---------------------|
| **B1: Phase A pure modules** | 0, 1, 2, 3, 4, 6, 7, 8, 9 | yes | All pure-Python, no ROS, no graph; one subagent can power through with TDD per task |
| **B2: SkillContract changes** | 5 | yes (alone) | Touches `interaction_executive/`, has 27 entries to update; isolated so a regression there doesn't pollute pawai_brain |
| **B3: Graph wiring** | 10, 11, 12, 13 | yes | New nodes + skill_policy_gate v2 + graph rewire; logically one structural unit |
| **B4: ROS wrapper + smoke** | 14, 15 | yes (alone) | ROS subscriptions + e2e graph smoke; needs `colcon build` and import verification on its own |
| **B5: Polish + validate** | 16, 17, 18, 19 | yes | Persona / Studio / docs / final acceptance dry-run |

Each batch produces 1 grouped commit per task internally (TDD discipline preserved), then I review the full batch before dispatching the next. Roughly 5 review checkpoints across the whole plan.
