# Plan C: pawai_contracts Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 IE / pawai_brain / Studio / CLI 之間互相 import、互相複製的共用真相抽進 ROS-free 新套件 `pawai_contracts`，**零行為變更**——606 個既有測試一行不改全綠是驗收標準。

**Architecture:** Roy 2026-06-10 拍板：正式推翻「zh 表三份拷貝是故意的」
（brain_node.py:37-40）與「pawai_brain 不依賴 IE」（conversation_graph_node.py:78-80
的註解版）兩條舊規。**新規則：interaction_executive 與 pawai_brain 不互相依賴，
共同依賴 pawai_contracts。** v1 只搬資料不搬邏輯：`skill_contract.py` 整檔 git mv +
原地 shim；zh 表、LLM allowlist、execute-mode map 收斂單源；Studio TS 拷貝用
JSON artifact + parity test 守，不進 colcon 依賴圈。

**Tech Stack:** ament_python（colcon）、純 Python dataclass/enum、pytest parity tests。

---

## Scope

- Create: `pawai_contracts/`（package.xml / setup.py / resource / `pawai_contracts/{__init__,skill_contract,zh_tables,llm_policy}.py` / `test/`）
- Modify: `interaction_executive/interaction_executive/skill_contract.py` → shim
- Modify: `interaction_executive/interaction_executive/brain_node.py`（zh 表與 LLM 政策改 import；**只刪 dict/set 定義、換成 import 賦值，gate 邏輯零改動**）
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py`（:77-99 zh 局部表刪除改 import；:458 import 改指 contracts）
- Modify: `pawai_brain/pawai_brain/nodes/skill_policy_gate.py`（allowlist 改 import）
- Modify: `interaction_executive/package.xml`、`pawai_brain/package.xml`（加 `<depend>pawai_contracts</depend>`）
- Modify: `.github/workflows/ros_build.yaml`（contracts 測試 invocation + Tier-2 package-name 加 `pawai_contracts`）
- Modify: `pawai_brain/test/test_skill_policy_gate.py`（AST parity test 改為 import 相等斷言）

## Forbidden scope（Roy 拍板原文）

- **不准改任何 skill 定義**（30 個 skill 的 steps/args/cooldown/confirmation/文案一字不動）
- **不准改任何 gating**、不准改 demo 參數、不准改 motion safety
  （MOTION_NAME_MAP / BANNED_API_IDS 值零變動）
- `pawai_contracts` **不准 import rclpy / interaction_executive / pawai_brain**
  （ROS-free purity，有測試鎖）
- 不動 `executive.yaml`、不動 wire format（/brain/proposal、/brain/skill_result）
- 本 PR 不夾帶 PerceptionEvent / policy table / trace schema（那是 Plan D/E 與 ISM 的事）

## 執行前提

Plan A merge（IE/pawai_brain/CLI 測試已在 CI）。本 plan 單一 PR、依 task 順序 commit。

---

### Task C1: 套件腳手架 + ROS-free purity 測試

**Files:**
- Create: `pawai_contracts/package.xml`、`pawai_contracts/setup.py`、
  `pawai_contracts/resource/pawai_contracts`、`pawai_contracts/pawai_contracts/__init__.py`、
  `pawai_contracts/test/test_purity.py`

- [x] **Step 1: package.xml（注意：無 rclpy depend）**

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>pawai_contracts</name>
  <version>0.1.0</version>
  <description>ROS-free shared truths: SkillContract registry, zh tables, LLM policy. Both interaction_executive and pawai_brain depend on this; they must never depend on each other (Roy ruling 2026-06-10).</description>
  <maintainer email="roy@pawai.dev">Roy</maintainer>
  <license>MIT</license>
  <buildtool_depend>ament_python</buildtool_depend>
  <test_depend>python3-pytest</test_depend>
  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [x] **Step 2: setup.py（仿 interaction_executive/setup.py，無 entry_points）**

```python
from setuptools import find_packages, setup

package_name = "pawai_contracts"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Roy",
    maintainer_email="roy@pawai.dev",
    description="ROS-free shared truths for PawAI (skill registry / zh tables / LLM policy)",
    license="MIT",
)
```
（`resource/pawai_contracts` 為空檔，`touch` 建立；`__init__.py` 空檔。）

- [x] **Step 3: purity failing test**

```python
# pawai_contracts/test/test_purity.py
"""ROS-free purity gate (Roy ruling 2026-06-10): pawai_contracts must never
import rclpy, interaction_executive, or pawai_brain."""
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "pawai_contracts"
FORBIDDEN = re.compile(r"^\s*(import|from)\s+(rclpy|interaction_executive|pawai_brain)\b", re.M)


def test_no_forbidden_imports():
    offenders = [
        f"{py.name}: {m.group(0).strip()}"
        for py in PKG.glob("*.py")
        for m in FORBIDDEN.finditer(py.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders
```

- [x] **Step 4: 跑（此刻只有 __init__，PASS）+ commit**

```bash
PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
git add pawai_contracts/ && git commit -m "feat(contracts): pawai_contracts scaffold + ROS-free purity gate (Plan C1)"
```

---

### Task C2: skill_contract.py 整檔搬移 + shim

**Files:**
- Move: `interaction_executive/interaction_executive/skill_contract.py` → `pawai_contracts/pawai_contracts/skill_contract.py`
- Create(shim): `interaction_executive/interaction_executive/skill_contract.py`

- [x] **Step 1: git mv（byte-identical，零內容變更）**

```bash
git mv interaction_executive/interaction_executive/skill_contract.py \
       pawai_contracts/pawai_contracts/skill_contract.py
```
（已驗證該檔 imports 只有 time/uuid/dataclasses/enum/typing——純 Python，搬了就能跑。）

- [x] **Step 2: 原地建 shim**

```python
# interaction_executive/interaction_executive/skill_contract.py
"""Compat shim (Plan C2, 2026-06-10): the real module moved to
pawai_contracts.skill_contract. Every existing import — including the 606-test
regression net — keeps working unchanged. New code should import
pawai_contracts.skill_contract directly. Remove this shim only after a
dedicated migration PR rewrites all imports (post-ISM)."""
from pawai_contracts.skill_contract import *          # noqa: F401,F403
from pawai_contracts.skill_contract import (          # noqa: F401  (underscore/explicit re-exports)
    SKILL_REGISTRY,
    MOTION_NAME_MAP,
    BANNED_API_IDS,
    build_plan,
)
```
（star-import 蓋 public 名；第二段顯式 re-export 防 `__all__` 缺席時的大小寫/常數疏漏。
若搬移後發現檔內有底線開頭名稱被外部引用——grep `from .skill_contract import _`
確認，有就逐一加進顯式段。）

- [x] **Step 3: 全量驗證（zero-behavior 的核心證明）**

```bash
PYTHONPATH=pawai_contracts:interaction_executive python3 -c \
  "from interaction_executive.skill_contract import SKILL_REGISTRY; print(len(SKILL_REGISTRY))"
# Expected: 30
python3 -m pytest interaction_executive/test/ -q          # 258 passed
PYTHONPATH=pawai_brain python3 -m pytest pawai_brain/test/ -q   # 348 passed
```
（本機 colcon 環境外跑：repo-root 執行時 pytest 的 rootdir 插入讓兩個套件都可見；
若 import 解析失敗，per-invocation 前綴 `PYTHONPATH=pawai_contracts`。）

- [x] **Step 4: commit**：`refactor(contracts): move skill_contract.py wholesale to pawai_contracts + compat shim — zero behavior change (Plan C2)`

---

### Task C3: zh 表單源化

**Files:**
- Create: `pawai_contracts/pawai_contracts/zh_tables.py`
- Modify: `interaction_executive/interaction_executive/brain_node.py:37-66`
- Modify: `pawai_brain/pawai_brain/conversation_graph_node.py:77-99`
- Test: `pawai_contracts/test/test_zh_parity.py`

- [x] **Step 1: failing parity test（遷移前先鎖三方一致）**

```python
# pawai_contracts/test/test_zh_parity.py
"""zh tables single-source parity (Plan C3). Guards: contracts == producer
canon (object_perception COLOR_ZH) == Studio TS copy. Replaces the
'three copies kept in sync by comment' regime (old brain_node.py:37-40)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_color_zh_matches_object_perception_canon():
    from pawai_contracts.zh_tables import OBJECT_COLOR_ZH
    import sys
    sys.path.insert(0, str(ROOT / "object_perception"))
    from object_perception.coco_classes import COLOR_ZH
    assert OBJECT_COLOR_ZH == COLOR_ZH


def test_studio_ts_copy_matches_contracts():
    from pawai_contracts.zh_tables import OBJECT_CLASS_ZH, OBJECT_COLOR_ZH
    ts = (ROOT / "pawai-studio/frontend/components/object/object-config.ts").read_text("utf-8")
    pairs = dict(re.findall(r'["\']?([a-z_]+)["\']?\s*:\s*["\']([^"\']+)["\']', ts))
    for key, zh in {**OBJECT_CLASS_ZH, **OBJECT_COLOR_ZH}.items():
        if key in pairs:                      # TS 檔可有額外 UI 條目；契約鍵必須一致
            assert pairs[key] == zh, f"{key}: contracts={zh} ts={pairs[key]}"
    missing = [k for k in OBJECT_COLOR_ZH if k not in pairs]
    assert not missing, f"Studio object-config.ts missing colour keys: {missing}"
```

- [x] **Step 2: 建 `zh_tables.py`**——內容 = brain_node.py:41-66 的三個 dict
**逐字搬移**（OBJECT_CLASS_ZH 31 鍵、OBJECT_COLOR_ZH 12 鍵、OBJECT_TTS_SPECIAL_SUFFIX
3 鍵），檔頭 docstring 註明「single source；producer canon 見
object_perception/coco_classes.py；Studio TS 由 parity test 守」。

- [x] **Step 3: brain_node.py 換 import（gate/邏輯零改動）**

刪 :37-66 的三個 dict 定義（含「three copies on purpose」舊註解），改為：

```python
# zh tables single-sourced in pawai_contracts (Plan C3, 2026-06-10 Roy ruling —
# supersedes the old "three copies on purpose" comment). Producer canon:
# object_perception/coco_classes.py; Studio TS copy guarded by parity test.
from pawai_contracts.zh_tables import (
    OBJECT_CLASS_ZH,
    OBJECT_COLOR_ZH,
    OBJECT_TTS_SPECIAL_SUFFIX,
)
```

- [x] **Step 4: conversation_graph_node.py 同款**——刪 :81-99 的 `_OBJECT_CLASS_ZH`/
`_OBJECT_COLOR_ZH` 局部副本與「duplication is intentional」註解，改：

```python
from pawai_contracts.zh_tables import (
    OBJECT_CLASS_ZH as _OBJECT_CLASS_ZH,
    OBJECT_COLOR_ZH as _OBJECT_COLOR_ZH,
)
```
（保留底線別名 → 檔內既有引用零改動。）

**遷移安全步驟**：刪除前先跑一次性比對腳本確認新舊 dict 完全相等：

```bash
PYTHONPATH=pawai_contracts python3 - <<'EOF'
import ast, pathlib
src = pathlib.Path("pawai_brain/pawai_brain/conversation_graph_node.py").read_text()
# (在尚未刪除前) 用 git show HEAD 抓舊定義比對
EOF
```
實務上更簡單：**先加 import、跑 parity test 與全套件測試綠了才刪舊 dict、再跑一次**。

- [x] **Step 5: 全量驗證 + commit**

```bash
python3 -m pytest interaction_executive/test/ -q && \
PYTHONPATH=pawai_brain python3 -m pytest pawai_brain/test/ -q && \
PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q
git add -u && git add pawai_contracts/ && \
git commit -m "refactor(contracts): zh tables single-sourced; brain_node + conversation_graph import from contracts; 3-way parity test (Plan C3)"
```

---

### Task C4: LLM allowlist + execute-mode map 單源化

**Files:**
- Create: `pawai_contracts/pawai_contracts/llm_policy.py`
- Modify: `interaction_executive/interaction_executive/brain_node.py:782-807`
- Modify: `pawai_brain/pawai_brain/nodes/skill_policy_gate.py:17-29`
- Modify: `pawai_brain/test/test_skill_policy_gate.py`（AST parity → import 相等）
- Test: `pawai_contracts/test/test_llm_policy.py`

- [x] **Step 1: 建 `llm_policy.py`**——內容 = brain_node.py:782-807 兩個結構**逐字搬移**：

```python
"""LLM proposal policy — single source (Plan C4, 2026-06-10).
Previously: canonical set in pawai_brain/nodes/skill_policy_gate.py + mirror in
brain_node guarded only by an AST parity test; the execute-mode map had NO
guard at all. Values are 1:1 from brain_node.py @ post-demo-refactor-baseline."""

LLM_PROPOSABLE_SKILLS = frozenset({
    "show_status",
    "self_introduce",
    "wave_hello",
    "sit_along",
    "stand",
    "greet_known_person",
    "careful_remind",
    "wiggle",
    "stretch",
})

LLM_PROPOSAL_EXECUTE = {
    # Bucket 1 — execute (direct)
    "show_status": "execute",
    "wave_hello": "execute",
    "sit_along": "execute",
    "stand": "execute",
    "careful_remind": "execute",
    # Bucket 2 — confirm (needs OK gesture)
    "wiggle": "confirm",
    "stretch": "confirm",
    # Bucket 3 — trace_only (LLM can mention, system does not fire motion)
    "self_introduce": "trace_only",
    "greet_known_person": "trace_only",
}
```

- [x] **Step 2: 消費端換 import**

brain_node.py 的 class attribute 區改為（保持 class-attribute 形態 → 所有
`self.LLM_PROPOSABLE_SKILLS` 引用零改動）：

```python
    from pawai_contracts.llm_policy import (   # noqa: E301 — class-level import 保持原引用形態
        LLM_PROPOSABLE_SKILLS as LLM_PROPOSABLE_SKILLS,
        LLM_PROPOSAL_EXECUTE as LLM_PROPOSAL_EXECUTE,
    )
```
（若 flake8 對 class 內 import 不滿 → 改 module-level import + class attr 賦值
`LLM_PROPOSABLE_SKILLS = _llm_policy.LLM_PROPOSABLE_SKILLS`，效果相同。）
skill_policy_gate.py 刪本地 frozenset，改 `from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS`。

- [x] **Step 3: 測試升級**

```python
# pawai_contracts/test/test_llm_policy.py
def test_execute_map_keys_subset_of_allowlist():
    from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS, LLM_PROPOSAL_EXECUTE
    assert set(LLM_PROPOSAL_EXECUTE) == set(LLM_PROPOSABLE_SKILLS)

def test_every_proposable_skill_exists_in_registry():
    from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS
    from pawai_contracts.skill_contract import SKILL_REGISTRY
    missing = LLM_PROPOSABLE_SKILLS - set(SKILL_REGISTRY)
    assert not missing, missing

def test_modes_are_valid():
    from pawai_contracts.llm_policy import LLM_PROPOSAL_EXECUTE
    assert set(LLM_PROPOSAL_EXECUTE.values()) <= {"execute", "confirm", "trace_only"}
```
`pawai_brain/test/test_skill_policy_gate.py` 的 AST parity test
（test_allowlist_single_source_of_truth）改為三行 import 相等斷言：

```python
def test_allowlist_single_source_of_truth():
    from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS as contracts_set
    from pawai_brain.nodes.skill_policy_gate import LLM_PROPOSABLE_SKILLS as gate_set
    from interaction_executive.brain_node import BrainNode
    assert gate_set is contracts_set
    assert BrainNode.LLM_PROPOSABLE_SKILLS == contracts_set
```
（注意：import BrainNode 需 rclpy → 此測試屬本機 L1 層；若該測試檔在 CI 清單內，
改用讀檔斷言「brain_node.py 含 `from pawai_contracts.llm_policy import`」保持 CI-safe。）

- [x] **Step 4: 全量驗證 + commit**：三套件測試綠 →
`refactor(contracts): LLM allowlist + execute-mode map single-sourced; retire AST parity hack (Plan C4)`

---

### Task C5: colcon / CI / 部署接線

**Files:**
- Modify: `interaction_executive/package.xml`、`pawai_brain/package.xml`（`<depend>pawai_contracts</depend>`）
- Modify: `.github/workflows/ros_build.yaml`

- [x] **Step 1: package.xml 各加一行 depend**

- [x] **Step 2: CI**——fast-gate 加 invocation：

```yaml
          # Invocation 8 (Plan C5): pawai_contracts parity + purity tests
          PYTHONPATH=pawai_contracts:object_perception pytest pawai_contracts/test/ -v --tb=short
```
並把既有 IE / pawai_brain invocations 的 PYTHONPATH 前綴補上 `pawai_contracts:`
（shim 需要找得到新套件）。Tier-2 `package-name` 清單加 `pawai_contracts`。

- [x] **Step 3: 本機 colcon 驗證（模擬 Jetson 部署鏈）**

```bash
colcon build --packages-select pawai_contracts interaction_executive pawai_brain
source install/setup.bash   # WSL 用 bash；Jetson 上是 setup.zsh
python3 -c "from interaction_executive.skill_contract import SKILL_REGISTRY; print(len(SKILL_REGISTRY))"
```
Expected: build 三套件成功（colcon 依 package.xml 排序，contracts 先建）、輸出 30。

- [x] **Step 4: commit + PR**

```bash
git add -u && git commit -m "build(contracts): package deps + CI invocation + colcon wiring (Plan C5)"
gh pr create --title "pawai_contracts extraction — data-only, zero behavior change (Plan C)" --fill
```
PR description 必含：606 測試零改動全綠的 CI link + 「推翻兩舊規」的 Roy 拍板引用
（master plan §4 D4）。

---

## Tests / 驗收

- `interaction_executive` 258 + `pawai_brain` 348 + `pawai_contracts` 新增 ~8 → 全綠，
  **既有測試檔除 test_skill_policy_gate.py（C4 Step 3）外零修改**。
- registry len == 30、MOTION_NAME_MAP/BANNED_API_IDS 值與 baseline 逐項相等
  （可在 contracts test 加一條凍結 hash 斷言）。
- colcon 三套件可建、import 鏈通。

## Jetson 部署註記

merge 後第一次部署：`pawai jetson deploy --module brain`（或手動 rsync）+
`colcon build --packages-select pawai_contracts interaction_executive pawai_brain`
+ 重啟 brain lane。**rsync 只搬源碼不 rebuild install/ 的舊坑適用**（CLAUDE.md）。

## Rollback

單 PR revert = 完整回滾（git mv 會還原、shim 消失、舊 dict 回來）。
無 feature flag 需求——shim 本身就是相容層。

---

## 執行結果（2026-06-11）

**PR #152 merged**（6 commits C1-C5 + review）。IE 258 + brain 348 + contracts 6 = **612 全綠**，零值變動（終審逐值核對）。
Review 戰果：mock_server sys.path 漏 contracts（靜默空表）+ ros2-test-suite skill 裸跑炸 — 兩個 dev-path 行為改變實證後修復；pre-commit hook 在 C2 第一次 commit 當場攔截接線缺口。
**Jetson 部署註記**：首次部署需 `colcon build --packages-select pawai_contracts interaction_executive pawai_brain` + 重啟 brain lane。
