# Scoreboard Implementation Plan（TDD，給工程師照做）

> **✅ 實作狀態（2026-06-03）**：核心 deliverable 全部實作 + merged 進 main。Task 1 schema(#71, PR #92) / Task 2 grader(#72, #93) / Task 3 aggregator(#79, #94) / Task 3b build_scoreboard(#79, #94) / Task 4 perception_baseline_observer(#74, #98) / Task 4b face_baseline_observer(#75, #99) 全綠進 Fast Gate CI。另 readiness verdict + freeze（#87, PR #100，`benchmarks/core/readiness.py` + `pawai readiness` CLI）已 merged。**ROS node wrapper（Task 4/4b 的 Jetson 端）維持薄 sketch、v0.1 不在 CI**；actual baseline run（產真 JSONL）是 HITL（#80-#84）。下方 checkbox 為原始 TDD 指引、保留作參考。

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development 或 executing-plans 逐 task 實作。Steps use checkbox (`- [ ]`) syntax。
> **性質**：6 個 deliverable 的 TDD skeleton（test→impl→commit）。這份是「**怎麼寫 code**」的唯一真相源。
> **不放**：架構決策（見 Master Plan）、逐功能門檻（見 Capability Baseline Spec）、上機步驟（見 Runbook）。
> **關係**：
> - 架構決策 / 三軸定義 / 15 能力 index → `docs/archive/pawai-brain-legacy/plans/2026-05-31-capability-baseline-scoreboard-plan.md`（Master Plan）
> - 逐功能門檻（門檻數字的真相源）→ `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`
> - 上機跑 → `docs/runbook/2026-06-18-baseline-runbook.md`

**Goal:** 6 個 Python deliverable，dry-run 全綠：`scoreboard_schema` / `grader` / `scoreboard`(聚合器) / `perception_baseline_observer`(gesture+object) / `face_baseline_observer`(face state) / `build_scoreboard`(CLI)。

**建議實作序**：Task 1 → 2 → 3（含 F1/F2/F5）→ 3b → 4（gesture/object）→ 4b（face）。

**Step 0（執行前先確認）**：repo 測試目錄為 `benchmarks/test/`（已確認）。先確認 `python -m pytest benchmarks/test -q` 可跑再開始。

> **注意：門檻數字不在本檔**。Criterion 的 pass_min/degraded_min 一律從 Capability Baseline Spec 取（provisional until baseline）。本檔只定 code 結構與 TDD 步驟。

---

## Task 1: `scoreboard_schema.py`（14 欄 record + CAPABILITY_META + version_snapshot）

**Files:**
- Create: `benchmarks/core/scoreboard_schema.py`
- Test: `benchmarks/test/test_scoreboard_schema.py`

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_scoreboard_schema.py
from benchmarks.core.scoreboard_schema import (
    CapabilityResult, SCHEMA_VERSION, CAPABILITY_META, current_run_meta,
)


def test_to_record_has_schema_version_and_core_fields():
    r = CapabilityResult(
        capability_id="gesture.wave",
        scenario_id="wave_1.5m_frontal",
        run_id="run-abc",
        timestamp="2026-05-31T12:00:00Z",
        git_commit="deadbee",
        expected_label="wave",
        predicted_label="wave",
        pass_fail="pass",
        confidence=0.91,
        distance_m=1.5,
        latency_ms=120.0,
    )
    rec = r.to_record()
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["capability_id"] == "gesture.wave"
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["distance_source"] == "manual_declared"
    assert rec["failure_reason"] == ""


def test_capability_meta_has_claim_and_risk_for_every_canonical_id():
    # 每個 canonical capability 都要有靜態屬性（claim_level / risk_role / depth / dependency_role）
    for cap, meta in CAPABILITY_META.items():
        assert meta["claim_level"] in {"mainline", "studio_only", "future", "not_claimed"}
        assert meta["risk_role"] in {
            "safety_critical", "safety_support", "actuation", "convenience", "evidence_only",
        }
        assert meta["depth"] in {"deep", "thin", "future"}
        # dependency_role（2026-06-01 新增）：每能力必標，供設計段 C / v0.2 chain-gating
        assert meta["dependency_role"] in {
            "trigger", "content", "safety_guard", "actuation", "evidence",
        }
    # nav 已拆成單一能力，不可有複合 id
    assert "nav.safe_stop" in CAPABILITY_META
    assert "nav.short_move" in CAPABILITY_META
    assert "nav.short_move + nav.safe_stop" not in CAPABILITY_META
    # dependency_role 與 risk_role 正交：safety_critical 能力的 dependency_role 是 safety_guard，非 evidence
    assert CAPABILITY_META["nav.safe_stop"]["dependency_role"] == "safety_guard"
    assert CAPABILITY_META["gesture.wave"]["dependency_role"] == "trigger"
    assert CAPABILITY_META["face.recognition"]["dependency_role"] == "content"


def test_run_meta_records_dual_sha_and_run_id():
    meta = current_run_meta(
        jetson_manifest={"git_sha_full": "abc123def", "when": "2026-05-31T10:00:00Z",
                         "sync_method": "rsync", "dirty": False},
        demo_profile_env={"REACTIVE_DANGER_M": "0.85", "MAP": "v9"},
    )
    assert meta["schema_version"] == SCHEMA_VERSION
    assert "run_id" in meta and meta["run_id"]
    assert meta["jetson_install_sha"] == "abc123def"
    assert meta["jetson_deploy_ts"] == "2026-05-31T10:00:00Z"
    assert meta["demo_profile_env"]["MAP"] == "v9"
    # wsl_commit vs jetson_install_sha 不一致時要有 fail-closed 旗標
    assert "version_mismatch" in meta


def test_run_meta_without_manifest_flags_unknown_install():
    meta = current_run_meta(jetson_manifest=None)
    assert meta["jetson_install_sha"] is None
    assert meta["version_mismatch"] is True  # 無 manifest = 無法確認 Jetson 跑的是哪版 → fail-closed
    assert meta["manifest_exists"] is False


def test_run_meta_flags_stale_manifest_by_age():
    # 洞④：manifest 太舊（deploy 後沒重 deploy 就跑 baseline）→ version_stale=True（標註，非硬 block）
    old = current_run_meta(
        jetson_manifest={"git_sha_full": "abc123def", "when": "2020-01-01T00:00:00Z",
                         "sync_method": "rsync", "dirty": False},
        now_iso="2026-05-31T10:00:00Z", stale_after_h=6,
    )
    assert old["version_stale"] is True
    fresh = current_run_meta(
        jetson_manifest={"git_sha_full": "abc123def", "when": "2026-05-31T08:00:00Z",
                         "sync_method": "rsync", "dirty": False},
        now_iso="2026-05-31T10:00:00Z", stale_after_h=6,
    )
    assert fresh["version_stale"] is False


def test_run_meta_records_dirty_and_branch():
    meta = current_run_meta(jetson_manifest={"git_sha_full": "abc123def", "dirty": True})
    assert "wsl_dirty" in meta and "branch" in meta and "manifest_exists" in meta
    assert meta["jetson_dirty"] is True  # manifest 的 dirty 旗標要轉出來


def test_run_meta_layer0_preflight_pass_marks_run_trusted():
    # F2：preflight pass / pass_with_warnings → run_trusted=True
    meta = current_run_meta(layer0_preflight={"status": "pass"})
    assert meta["layer0_preflight_status"] == "pass"
    assert meta["run_trusted"] is True
    meta_w = current_run_meta(layer0_preflight={"status": "pass_with_warnings"})
    assert meta_w["run_trusted"] is True


def test_run_meta_layer0_preflight_fail_marks_untrusted():
    # F2：preflight fail / 缺結果 → run_trusted=False（fail-closed，to_snapshot 會覆寫全 grade）
    meta = current_run_meta(layer0_preflight={"status": "fail"})
    assert meta["layer0_preflight_status"] == "fail"
    assert meta["run_trusted"] is False
    meta_none = current_run_meta()  # 沒跑 preflight = 不可信
    assert meta_none["layer0_preflight_status"] == "unknown"
    assert meta_none["run_trusted"] is False
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_scoreboard_schema.py -q`
Expected: FAIL（`ModuleNotFoundError: benchmarks.core.scoreboard_schema`）

- [ ] **Step 3: 實作 schema**

```python
# benchmarks/core/scoreboard_schema.py
"""Capability baseline result schema + 靜態 capability metadata (v0.1)。

一筆 JSONL record = 一次 scenario-run。claim_level / risk_role 是 capability 的「靜態屬性」，
存 CAPABILITY_META，不進每筆 record（避免重複）。run-level meta 帶 version_snapshot 雙 sha
（Jetson 無 .git，dev commit ≠ Jetson install）。
"""
from __future__ import annotations

import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

SCHEMA_VERSION = "scoreboard-0.1"

# capability_id → 靜態屬性（claim_level/risk_role/dependency_role 是作者標的，不是量出來的）
# dependency_role（2026-06-01 加）：fail 時依賴它的 demo skill 怎麼降級——
#   trigger→不觸發該 skill；content→skill 觸發但內容降級；safety_guard→禁 motion；
#   actuation→禁該動作；evidence→只影響 Studio 顯示。與 risk_role 正交。v0.1 不被 grader 消費（design-only）。
CAPABILITY_META: dict[str, dict] = {
    "face.recognition":     {"depth": "deep",  "claim_level": "mainline",    "risk_role": "evidence_only",   "dependency_role": "content"},
    "voice.command":        {"depth": "deep",  "claim_level": "mainline",    "risk_role": "convenience",     "dependency_role": "trigger"},
    "voice.stop":           {"depth": "deep",  "claim_level": "mainline",    "risk_role": "convenience",     "dependency_role": "trigger"},
    "gesture.wave":         {"depth": "deep",  "claim_level": "mainline",    "risk_role": "convenience",     "dependency_role": "trigger"},
    "object.cup":           {"depth": "deep",  "claim_level": "mainline",    "risk_role": "evidence_only",   "dependency_role": "content"},
    "nav.safe_stop":        {"depth": "deep",  "claim_level": "mainline",    "risk_role": "safety_critical", "dependency_role": "safety_guard"},
    "nav.no_auto_resume":   {"depth": "deep",  "claim_level": "mainline",    "risk_role": "safety_critical", "dependency_role": "safety_guard"},
    "nav.short_move":       {"depth": "deep",  "claim_level": "mainline",    "risk_role": "actuation",       "dependency_role": "actuation"},
    "nav.dynamic_avoidance":{"depth": "future","claim_level": "future",      "risk_role": "actuation",       "dependency_role": "actuation"},
    "pose.basic":           {"depth": "thin",  "claim_level": "studio_only", "risk_role": "evidence_only",   "dependency_role": "content"},
    "pose.fall":            {"depth": "future","claim_level": "future",      "risk_role": "evidence_only",   "dependency_role": "evidence"},
    "brain.skill_gate":     {"depth": "deep",  "claim_level": "mainline",    "risk_role": "safety_critical", "dependency_role": "safety_guard"},
    "brain.trace":          {"depth": "deep",  "claim_level": "mainline",    "risk_role": "evidence_only",   "dependency_role": "evidence"},
    "studio.evidence":      {"depth": "deep",  "claim_level": "mainline",    "risk_role": "evidence_only",   "dependency_role": "evidence"},
    "cli.readiness":        {"depth": "thin",  "claim_level": "not_claimed", "risk_role": "safety_support",  "dependency_role": "evidence"},
}


@dataclass
class CapabilityResult:
    # --- 識別 ---
    capability_id: str            # 須在 CAPABILITY_META 內（單一能力，不可複合）
    scenario_id: str              # 如 "wave_1.5m_frontal" / "idle_hand_60s"
    run_id: str                   # 每個 baseline session 一個 uuid（caller 提供）
    timestamp: str                # UTC ISO8601（caller 提供，真實來源）
    git_commit: str               # WSL git rev-parse --short HEAD（caller 提供）
    # --- 判定 ---
    expected_label: str
    predicted_label: str
    pass_fail: str                # 單一 scenario 的 raw outcome："pass" | "fail"
    confidence: Optional[float] = None
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"   # "d435_depth" | "manual_declared"
    latency_ms: Optional[float] = None
    frame_age_ms: Optional[float] = None
    fps: Optional[float] = None
    false_trigger: bool = False
    stable_time_ms: Optional[float] = None
    # --- 資源（reuse JetsonMonitor 後填；v0.1 可留 None）---
    cpu_pct: Optional[float] = None
    gpu_pct: Optional[float] = None
    ram_mb: Optional[float] = None
    failure_reason: str = ""

    def to_record(self) -> dict:
        rec = asdict(self)
        rec["schema_version"] = SCHEMA_VERSION
        return rec


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:
        return "unknown"


def _git_short() -> str:
    return _git(["rev-parse", "--short", "HEAD"])


def _is_stale(when_iso: Optional[str], now_iso: Optional[str], stale_after_h: float) -> bool:
    """manifest deploy 時間距 now 超過 stale_after_h → stale（標註，非硬 block）。取不到時間 → 視為 stale。"""
    if not when_iso:
        return True
    try:
        now = datetime.fromisoformat((now_iso or datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
        when = datetime.fromisoformat(when_iso.replace("Z", "+00:00"))
        return (now - when).total_seconds() > stale_after_h * 3600
    except Exception:
        return True


def current_run_meta(jetson_manifest: Optional[dict] = None,
                     demo_profile_env: Optional[dict] = None,
                     layer0_preflight: Optional[dict] = None,
                     now_iso: Optional[str] = None,
                     stale_after_h: float = 6.0) -> dict:
    """run-level metadata。version_snapshot 雙 sha：dev commit + Jetson install sha。

    jetson_manifest = 讀 Jetson 的 .pawai-last-deploy（runbook 用 pawai status / scp 取得）。
    無 manifest 或與 dev commit 不符 → version_mismatch=True（fail-closed：不能把 dev 的
    commit 當成 Jetson 上實際跑的版本）。manifest 太舊 → version_stale=True（標註，非硬 block；
    裸 `~/sync once` 不更新 manifest → 由 `when` age 判）。

    layer0_preflight = jetson-verify demo.yaml 跑完的結果 dict（runbook 提供，至少含 {"status": ...}）。
    F2：status 非 pass/pass_with_warnings → run_trusted=False → to_snapshot() 全 grade 覆寫 insufficient_data
    （fail-closed：preflight 不可信的 run 不准吐 pass/fail）。
    """
    m = jetson_manifest or {}
    wsl_commit = _git_short()
    wsl_dirty = bool(_git(["status", "--porcelain"]))  # 非空 = 有未 commit 變動
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    jetson_sha = m.get("git_sha_full")
    manifest_exists = jetson_manifest is not None
    # mismatch 判定：無 manifest，或 jetson sha 不以 wsl_commit 開頭（short vs full）
    mismatch = (jetson_sha is None) or (not jetson_sha.startswith(wsl_commit) if wsl_commit != "unknown" else True)
    pf_status = (layer0_preflight or {}).get("status", "unknown")
    run_trusted = pf_status in ("pass", "pass_with_warnings")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wsl_commit": wsl_commit,
        "wsl_dirty": wsl_dirty,
        "branch": branch,
        "jetson_install_sha": jetson_sha,
        "jetson_deploy_ts": m.get("when"),
        "jetson_sync_method": m.get("sync_method"),
        "jetson_dirty": bool(m.get("dirty")),
        "manifest_exists": manifest_exists,
        "version_mismatch": bool(mismatch),
        "version_stale": _is_stale(m.get("when"), now_iso, stale_after_h),
        "layer0_preflight_status": pf_status,
        "run_trusted": run_trusted,
        "demo_profile_env": demo_profile_env or {},
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_scoreboard_schema.py -q`
Expected: PASS

- [ ] **Step 5: commit**

```bash
git add benchmarks/core/scoreboard_schema.py benchmarks/test/test_scoreboard_schema.py
git commit -m "feat(scoreboard): v0.1 schema + CAPABILITY_META + dual-sha run_meta"
```

---

## Task 2: `grader.py`（四段 grade 純函式 + brain_allowed derive）

**Files:**
- Create: `benchmarks/core/grader.py`
- Test: `benchmarks/test/test_grader.py`

> 設計：grade 結合「門檻」與「樣本充足度」。`insufficient_data` = 0 樣本**或**缺 criteria（fail-closed，防 fail-open）；`pass` = 所有 metric 達 pass band **且** confirmed（sample_count ≥ confirm_min，預設 3）；`degraded` = 達 pass band 但樣本 1–2（provisional / 標黃）**或**落在 degraded band；`fail` = 任一 metric 低於 degraded band（fail-closed：任一 fail → fail）。`brain_allowed` = grade 與 claim_level 合成（claim_level 只能更嚴）。

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_grader.py
from benchmarks.core.grader import (
    Criterion, grade_capability, brain_allowed,
    GRADE_PASS, GRADE_DEGRADED, GRADE_FAIL, GRADE_INSUFFICIENT,
)

HIGHER = Criterion(metric="success_rate", pass_min=0.90, degraded_min=0.80, higher_is_better=True)
LOWER = Criterion(metric="false_trigger_rate", pass_min=0.10, degraded_min=0.30, higher_is_better=False)


def test_zero_samples_is_insufficient():
    assert grade_capability({"success_rate": 0.99}, [HIGHER], sample_count=0) == GRADE_INSUFFICIENT


def test_empty_criteria_is_not_pass():
    # 缺 criteria 無從判斷 → fail-closed，絕不可 pass
    assert grade_capability({"success_rate": 0.99}, [], sample_count=5) == GRADE_INSUFFICIENT


def test_all_pass_but_unconfirmed_is_degraded():
    assert grade_capability({"success_rate": 0.95}, [HIGHER], sample_count=1) == GRADE_DEGRADED


def test_all_pass_and_confirmed_is_pass():
    assert grade_capability({"success_rate": 0.95}, [HIGHER], sample_count=3) == GRADE_PASS


def test_any_metric_fail_is_fail():
    metrics = {"success_rate": 0.95, "false_trigger_rate": 0.40}
    assert grade_capability(metrics, [HIGHER, LOWER], sample_count=5) == GRADE_FAIL


def test_lower_is_better_band():
    assert grade_capability({"false_trigger_rate": 0.05}, [LOWER], sample_count=5) == GRADE_PASS
    assert grade_capability({"false_trigger_rate": 0.20}, [LOWER], sample_count=5) == GRADE_DEGRADED


def test_degraded_band_dominates_over_unconfirmed():
    assert grade_capability({"success_rate": 0.85}, [HIGHER], sample_count=5) == GRADE_DEGRADED


def test_brain_allowed_only_pass_and_mainline():
    # claim_level 只能更嚴：pass 但 future → 不放行
    assert brain_allowed(GRADE_PASS, "mainline") is True
    assert brain_allowed(GRADE_PASS, "future") is False
    assert brain_allowed(GRADE_PASS, "studio_only") is False
    assert brain_allowed(GRADE_DEGRADED, "mainline") is False
    assert brain_allowed(GRADE_FAIL, "mainline") is False
    assert brain_allowed(GRADE_INSUFFICIENT, "mainline") is False
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_grader.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 grader**

```python
# benchmarks/core/grader.py
"""四段 capability grader (v0.1)。純函式、無 ROS 依賴。

範式對齊 speech_processor/speech_processor/speech_test_observer.py 的 _compute_grade
（PASS/MARGINAL/FAIL → 此處 pass/degraded/fail），擴成四段並加入「樣本充足度」維度 +
brain_allowed（grade × claim_level，claim_level 只能更嚴）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

GRADE_PASS = "pass"
GRADE_DEGRADED = "degraded"
GRADE_FAIL = "fail"
GRADE_INSUFFICIENT = "insufficient_data"


@dataclass
class Criterion:
    metric: str
    pass_min: float
    degraded_min: float
    higher_is_better: bool = True


def grade_one(value: Optional[float], crit: Criterion) -> str:
    """單一 metric → pass/degraded/fail。None 視為 fail（保守）。"""
    if value is None:
        return GRADE_FAIL
    if crit.higher_is_better:
        if value >= crit.pass_min:
            return GRADE_PASS
        if value >= crit.degraded_min:
            return GRADE_DEGRADED
        return GRADE_FAIL
    else:  # lower is better（誤觸率 / latency）
        if value <= crit.pass_min:
            return GRADE_PASS
        if value <= crit.degraded_min:
            return GRADE_DEGRADED
        return GRADE_FAIL


def grade_capability(metrics: dict, criteria: list[Criterion], sample_count: int,
                     confirm_min: int = 3) -> str:
    """結合門檻 + 樣本充足度的四段 grade。fail-closed：任一 metric fail → fail；缺 criteria → insufficient。"""
    if sample_count <= 0:
        return GRADE_INSUFFICIENT
    if not criteria:
        return GRADE_INSUFFICIENT  # 防 fail-open
    grades = [grade_one(metrics.get(c.metric), c) for c in criteria]
    if GRADE_FAIL in grades:
        return GRADE_FAIL
    if GRADE_DEGRADED in grades:
        return GRADE_DEGRADED
    if sample_count < confirm_min:
        return GRADE_DEGRADED  # provisional / 標黃
    return GRADE_PASS


def brain_allowed(grade: str, claim_level: str) -> bool:
    """Brain 主線放行 = grade==pass AND claim_level==mainline。claim_level 只能更嚴、不放寬。"""
    return grade == GRADE_PASS and claim_level == "mainline"
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_grader.py -q`
Expected: PASS（8 個測試全綠）

- [ ] **Step 5: commit**

```bash
git add benchmarks/core/grader.py benchmarks/test/test_grader.py
git commit -m "feat(scoreboard): v0.1 four-tier grader + brain_allowed gate derive"
```

---

## Task 3: `scoreboard.py`（聚合器 → snapshot，附 claim_level/brain_allowed）

**Files:**
- Create: `benchmarks/core/scoreboard.py`
- Test: `benchmarks/test/test_scoreboard.py`

> 讀 JSONL → 按 capability_id 分組 → 算 latest grade + success_rate + false_trigger_rate + latency P50/P90 + sample_count → snapshot 每能力附 `CAPABILITY_META`（claim_level/risk_role/depth）+ derived `brain_allowed`。**不接 Brain runtime**（v0.2）。

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_scoreboard.py
from benchmarks.core.scoreboard import aggregate, to_snapshot
from benchmarks.core.grader import Criterion, GRADE_PASS, GRADE_FAIL

CRIT = {
    "gesture.wave": [
        Criterion("success_rate", 0.90, 0.80, higher_is_better=True),
        Criterion("false_trigger_rate", 0.10, 0.30, higher_is_better=False),
    ],
}


def _rec(cap, ok, ft=False, lat=100.0, kind="positive"):
    return {"capability_id": cap, "pass_fail": "pass" if ok else "fail",
            "false_trigger": ft, "latency_ms": lat, "scenario_kind": kind}


def test_aggregate_success_rate_and_grade():
    recs = [_rec("gesture.wave", True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    s = scores["gesture.wave"]
    assert s.sample_count == 4
    assert s.success_rate == 1.0
    assert s.false_trigger_rate == 0.0
    assert s.confirmed is True
    assert s.grade == GRADE_PASS


def test_aggregate_false_trigger_forces_fail():
    recs = [_rec("gesture.wave", True, ft=True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    assert scores["gesture.wave"].grade == GRADE_FAIL


def test_aggregate_separates_recall_from_false_accept():
    # F2：known/unknown 不混算。3 positive 全中 + 2 idle 其中 1 誤接
    recs = [
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", False, ft=True, kind="idle"),   # 陌生人被誤接
        _rec("face.recognition", True, kind="idle"),             # 陌生人正確 reject
    ]
    s = aggregate(recs, {}, confirm_min=3)["face.recognition"]
    assert s.positive_count == 3 and s.idle_count == 2
    assert s.registered_recall == 1.0          # 3/3 positive 命中（不被 idle 稀釋）
    assert s.unknown_false_accept_rate == 0.5  # 1/2 idle 誤接（不被 positive 稀釋）
    assert s.wrong_person_count == 0           # positive round 無誤觸


def test_aggregate_wrong_person_counted_on_positive_round():
    # 該認出 roy 卻誤觸（認成別人）= wrong_person，計在 positive round
    recs = [
        _rec("face.recognition", True, kind="positive"),
        _rec("face.recognition", False, ft=True, kind="positive"),  # 認錯人
    ]
    s = aggregate(recs, {}, confirm_min=3)["face.recognition"]
    assert s.wrong_person_count == 1
    assert s.registered_recall == 0.5


def test_snapshot_carries_claim_level_and_brain_allowed():
    recs = [_rec("gesture.wave", True, lat=v) for v in (50, 100, 150, 200)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    # run_trusted=True：模擬 preflight 已通過（fail-closed 預設為 False，trusted case 須明確傳）
    snap = to_snapshot(scores, {"git_commit": "abc", "timestamp": "2026-05-31T00:00:00Z",
                                "run_trusted": True})
    assert snap["git_commit"] == "abc"
    cap = snap["capabilities"]["gesture.wave"]
    assert cap["latency_p50"] is not None and cap["latency_p90"] is not None
    # 靜態屬性 + derived gate 入 snapshot
    assert cap["claim_level"] == "mainline"
    assert cap["risk_role"] == "convenience"
    assert cap["dependency_role"] == "trigger"   # F5：降級語意入 snapshot
    assert cap["brain_allowed"] is True  # pass + mainline


def test_future_capability_not_brain_allowed_even_if_pass():
    recs = [_rec("nav.dynamic_avoidance", True) for _ in range(4)]
    crit = {"nav.dynamic_avoidance": [Criterion("success_rate", 0.9, 0.8)]}
    scores = aggregate(recs, crit, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc", "run_trusted": True})  # trusted：隔離 future-gate 與 fail-closed
    cap = snap["capabilities"]["nav.dynamic_avoidance"]
    # 即使量到 pass，claim_level=future → 不放行
    assert cap["brain_allowed"] is False


def test_snapshot_always_lists_all_15_capabilities():
    # F1：只測到 1 個能力，snapshot 仍列出全部 15，未測者 insufficient_data + sample_count=0
    recs = [_rec("gesture.wave", True) for _ in range(4)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc", "run_trusted": True})  # trusted：未測=insufficient 來自零樣本，非 fail-closed
    assert len(snap["capabilities"]) == 15
    untested = snap["capabilities"]["face.recognition"]
    assert untested["grade"] == "insufficient_data"
    assert untested["sample_count"] == 0
    assert untested["success_rate"] is None      # None=未測，非 0.0
    assert untested["brain_allowed"] is False
    assert untested["dependency_role"] == "content"   # 未測也帶靜態屬性
    # trusted 下已測能力維持原 grade（隔離：未測 insufficient ≠ fail-closed 全 insufficient）
    assert snap["capabilities"]["gesture.wave"]["grade"] == "pass"


def test_missing_run_trusted_defaults_failclosed():
    # F2 fail-open 防護：caller 漏帶 run_trusted（沒跑 preflight / 手刻 run_meta）→ 預設不可信 → 全 insufficient
    recs = [_rec("gesture.wave", True) for _ in range(5)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    snap = to_snapshot(scores, {"git_commit": "abc"})   # 故意不帶 run_trusted
    assert snap["capabilities"]["gesture.wave"]["grade"] == "insufficient_data"
    assert all(c["grade"] == "insufficient_data" for c in snap["capabilities"].values())


def test_layer0_preflight_fail_forces_all_insufficient():
    # F2：run_trusted=False（preflight fail）→ 連量到 pass 的能力也覆寫 insufficient_data（fail-closed）
    recs = [_rec("gesture.wave", True) for _ in range(5)]
    scores = aggregate(recs, CRIT, confirm_min=3)
    assert scores["gesture.wave"].grade == "pass"   # 原本量到 pass
    snap = to_snapshot(scores, {"git_commit": "abc", "run_trusted": False,
                                "layer0_preflight_status": "fail"})
    cap = snap["capabilities"]["gesture.wave"]
    assert cap["grade"] == "insufficient_data"       # 被覆寫
    assert cap["brain_allowed"] is False
    assert cap["failure_reason"] == "layer0_preflight=fail"
    assert cap["success_rate"] is not None           # raw metrics 保留（可 debug）
    # 全部 15 能力都 insufficient
    assert all(c["grade"] == "insufficient_data" for c in snap["capabilities"].values())
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_scoreboard.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作聚合器**

```python
# benchmarks/core/scoreboard.py
"""聚合 baseline JSONL → 每能力 scoreboard snapshot (v0.1)。

snapshot 每能力附 CAPABILITY_META（claim_level/risk_role/depth）+ derived brain_allowed，
供人判斷哪些能力允許進 demo 主線。不接 Brain runtime（v0.2 才在 effective_status 補
capability_health）。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from .grader import grade_capability, brain_allowed, Criterion, GRADE_INSUFFICIENT
from .scoreboard_schema import CAPABILITY_META


@dataclass
class CapabilityScore:
    capability_id: str
    grade: str
    sample_count: int
    success_rate: float
    false_trigger_rate: float
    latency_p50: Optional[float]
    latency_p90: Optional[float]
    confirmed: bool
    # F2（2026-06-01）：scenario_kind-aware 分離指標。positive round 算 recall、idle round 算 false-accept，
    # 不混算（否則 face 的 unknown 誤認會被 known 成功率稀釋）。非 face 能力這些可為 None / 0。
    positive_count: int = 0          # scenario_kind=="positive" 的 round 數
    idle_count: int = 0              # scenario_kind=="idle" 的 round 數
    registered_recall: Optional[float] = None        # = positive round 的 pass 率（face: 認出註冊者）
    unknown_false_accept_rate: Optional[float] = None  # = idle round 的 false_trigger 率（face: 誤認陌生人）
    wrong_person_count: int = 0      # 認錯人（false_trigger 且非 idle）的次數


def _pctl(values, p: float) -> Optional[float]:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    k = int(round((p / 100.0) * (len(xs) - 1)))
    k = max(0, min(len(xs) - 1, k))
    return xs[k]


def load_results(path: str) -> list[dict]:
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _kind(r: dict) -> str:
    """record 的 scenario_kind：positive（預期命中）/ idle（預期零事件，量誤觸）。預設 positive。"""
    return r.get("scenario_kind", "positive")


def aggregate(records: list[dict], criteria_by_capability: dict[str, list[Criterion]],
              confirm_min: int = 3) -> dict[str, CapabilityScore]:
    """F2（2026-06-01）：按 (capability_id, scenario_kind) 分離算指標，避免 known/unknown 混算稀釋。

    每能力同時輸出：
      - success_rate / false_trigger_rate：全 round（向後相容，gesture/object 仍用）
      - registered_recall = positive round 的 pass 率
      - unknown_false_accept_rate = idle round 的 false_trigger 率
      - wrong_person_count = 非 idle round 卻 false_trigger（認錯人/誤接）的次數
    grader 的 Criterion.metric 可指向上述任一 key（face 用 registered_recall + unknown_false_accept_rate；
    gesture/object 用 success_rate + false_trigger_rate）。
    """
    by_cap: dict[str, list[dict]] = {}
    for r in records:
        by_cap.setdefault(r["capability_id"], []).append(r)

    scores: dict[str, CapabilityScore] = {}
    for cap, recs in by_cap.items():
        n = len(recs)
        pos = [r for r in recs if _kind(r) == "positive"]
        idle = [r for r in recs if _kind(r) == "idle"]
        succ = sum(1 for r in recs if r.get("pass_fail") == "pass") / n
        ft = sum(1 for r in recs if r.get("false_trigger")) / n
        lat = [r.get("latency_ms") for r in recs]
        reg_recall = (sum(1 for r in pos if r.get("pass_fail") == "pass") / len(pos)) if pos else None
        ufa = (sum(1 for r in idle if r.get("false_trigger")) / len(idle)) if idle else None
        wrong = sum(1 for r in pos if r.get("false_trigger"))  # positive round 卻誤觸 = 認錯人/誤接
        metrics = {
            "success_rate": succ, "false_trigger_rate": ft, "latency_p50": _pctl(lat, 50),
            "registered_recall": reg_recall, "unknown_false_accept_rate": ufa,
            "wrong_person_count": wrong,
        }
        g = grade_capability(metrics, criteria_by_capability.get(cap, []), n, confirm_min)
        scores[cap] = CapabilityScore(
            capability_id=cap, grade=g, sample_count=n,
            success_rate=round(succ, 3), false_trigger_rate=round(ft, 3),
            latency_p50=_pctl(lat, 50), latency_p90=_pctl(lat, 90),
            confirmed=(n >= confirm_min),
            positive_count=len(pos), idle_count=len(idle),
            registered_recall=(round(reg_recall, 3) if reg_recall is not None else None),
            unknown_false_accept_rate=(round(ufa, 3) if ufa is not None else None),
            wrong_person_count=wrong,
        )
    return scores


def _empty_score_dict(cap_id: str) -> dict:
    """零樣本能力的骨架（F1：snapshot 永遠列出全部 15 能力，未測者 insufficient_data）。"""
    return {
        "capability_id": cap_id,
        "grade": GRADE_INSUFFICIENT,
        "sample_count": 0,
        "success_rate": None,        # None = 未測（非 0.0，避免誤讀成「0% 成功」）
        "false_trigger_rate": None,
        "latency_p50": None,
        "latency_p90": None,
        "confirmed": False,
    }


def to_snapshot(scores: dict[str, CapabilityScore], run_meta: dict) -> dict:
    """聚合 → snapshot。三個校正（2026-06-01）：
    F1：遍歷 CAPABILITY_META 全鍵（非 scores），未測能力補 insufficient_data 骨架——snapshot 永遠 15 列。
    F2：run_meta.run_trusted==False（Layer-0 preflight fail）→ 全 capability grade 覆寫 insufficient_data，
        但保留 raw metrics（可 debug），附 failure_reason。fail-closed：不可信的 run 不吐 pass/fail。
    F5：每能力附 dependency_role（供 v0.2 chain-gating / Studio 顯示降級語意）。
    """
    # fail-closed 預設：caller 漏帶 run_trusted（=沒跑 preflight / 手刻 run_meta）→ 視為不可信。
    # 正規路徑 build_scoreboard 一律經 current_run_meta()，永遠帶 run_trusted（preflight 缺→False）。
    run_trusted = bool(run_meta.get("run_trusted", False))
    caps = {}
    for cap_id, meta in CAPABILITY_META.items():
        if cap_id in scores:
            d = asdict(scores[cap_id])
        else:
            d = _empty_score_dict(cap_id)
        # F2：preflight fail → 覆寫 grade（保留 raw），fail-closed
        if not run_trusted:
            d["grade"] = GRADE_INSUFFICIENT
            d["failure_reason"] = f"layer0_preflight={run_meta.get('layer0_preflight_status', 'unknown')}"
        d["claim_level"] = meta["claim_level"]
        d["risk_role"] = meta["risk_role"]
        d["depth"] = meta["depth"]
        d["dependency_role"] = meta["dependency_role"]   # F5
        d["brain_allowed"] = brain_allowed(d["grade"], meta["claim_level"])
        caps[cap_id] = d
    return {"schema_version": "scoreboard-0.1", **run_meta, "capabilities": caps}


def write_snapshot(scores, run_meta, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(to_snapshot(scores, run_meta), f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_scoreboard.py -q`
Expected: PASS

- [ ] **Step 5: commit**

```bash
git add benchmarks/core/scoreboard.py benchmarks/test/test_scoreboard.py
git commit -m "feat(scoreboard): v0.1 aggregator (scenario-kind aware + claim_level + brain_allowed)"
```

---

## Task 3b: `build_scoreboard.py`（CLI thin wrapper，runbook step4 用）

**Files:**
- Create: `benchmarks/core/build_scoreboard.py`
- Test: `benchmarks/test/test_build_scoreboard.py`

> runbook step4 唯一工具：讀 `baseline_result.jsonl` + `--manifest`（Jetson `.pawai-last-deploy`，可缺）+ `--preflight`（jetson-verify demo.yaml 結果，可缺）→ `current_run_meta` → `aggregate` → `write_snapshot`。
> **fail-closed**：`--preflight` 缺或非 pass → `run_trusted=False` → snapshot 全 grade insufficient_data（對齊 to_snapshot F2）。criteria 缺省用 spec 的 provisional 門檻（`DEFAULT_CRITERIA`）。

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_build_scoreboard.py
import json
from benchmarks.core.build_scoreboard import build_scoreboard, DEFAULT_CRITERIA


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_build_scoreboard_preflight_pass_produces_snapshot(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(jsonl, [
        {"capability_id": "gesture.wave", "pass_fail": "pass", "false_trigger": False,
         "latency_ms": 100, "scenario_kind": "positive"} for _ in range(3)
    ])
    pf = tmp_path / "preflight.json"; pf.write_text(json.dumps({"status": "pass"}))
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=str(pf), out_path=str(out))
    snap = json.loads(out.read_text())
    assert snap["run_trusted"] is True
    assert len(snap["capabilities"]) == 15            # F1：永遠 15 列
    assert snap["capabilities"]["gesture.wave"]["grade"] == "pass"


def test_build_scoreboard_missing_preflight_is_failclosed(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(jsonl, [
        {"capability_id": "gesture.wave", "pass_fail": "pass", "false_trigger": False,
         "latency_ms": 100, "scenario_kind": "positive"} for _ in range(3)
    ])
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=None, out_path=str(out))   # 不帶 preflight
    snap = json.loads(out.read_text())
    assert snap["run_trusted"] is False
    assert snap["capabilities"]["gesture.wave"]["grade"] == "insufficient_data"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_build_scoreboard.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 CLI wrapper**

```python
# benchmarks/core/build_scoreboard.py
"""Runbook step4 工具：baseline_result.jsonl → scoreboard snapshot。

  python -m benchmarks.core.build_scoreboard RESULT.jsonl \
         [--manifest .pawai-last-deploy.json] [--preflight preflight.json] \
         [--criteria criteria.json] [--out snapshot.json]

fail-closed：--preflight 缺/非 pass → run_trusted=False → 全 grade insufficient_data。
"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from .grader import Criterion
from .scoreboard import load_results, aggregate, write_snapshot
from .scoreboard_schema import current_run_meta

# spec 的 provisional 門檻（門檻數字真相源在 Capability Baseline Spec；此為執行預設）
DEFAULT_CRITERIA: dict[str, list[Criterion]] = {
    "face.recognition": [
        Criterion("registered_recall", 0.80, 0.60, higher_is_better=True),
        Criterion("unknown_false_accept_rate", 0.03, 0.10, higher_is_better=False),
        Criterion("wrong_person_count", 0, 0, higher_is_better=False),
    ],
    "voice.command": [
        Criterion("success_rate", 0.80, 0.70, higher_is_better=True),
    ],
    "gesture.wave": [
        Criterion("success_rate", 0.90, 0.80, higher_is_better=True),
        Criterion("unknown_false_accept_rate", 0.10, 0.30, higher_is_better=False),
    ],
    "object.cup": [
        Criterion("success_rate", 0.80, 0.60, higher_is_better=True),
        Criterion("unknown_false_accept_rate", 0.01, 0.10, higher_is_better=False),
    ],
}


def _load_json(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_scoreboard(jsonl_path: str, manifest_path: Optional[str] = None,
                     preflight_path: Optional[str] = None,
                     criteria: Optional[dict] = None,
                     out_path: str = "artifacts/baseline/baseline_snapshot.json") -> str:
    records = load_results(jsonl_path)
    run_meta = current_run_meta(
        jetson_manifest=_load_json(manifest_path),
        layer0_preflight=_load_json(preflight_path),   # 缺 → run_trusted=False（fail-closed）
    )
    scores = aggregate(records, criteria or DEFAULT_CRITERIA)
    write_snapshot(scores, run_meta, out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--manifest")
    ap.add_argument("--preflight")
    ap.add_argument("--criteria")
    ap.add_argument("--out", default="artifacts/baseline/baseline_snapshot.json")
    a = ap.parse_args()
    crit = None
    if a.criteria:
        raw = _load_json(a.criteria)
        crit = {k: [Criterion(**c) for c in v] for k, v in raw.items()}
    path = build_scoreboard(a.jsonl, a.manifest, a.preflight, crit, a.out)
    print(f"snapshot → {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_build_scoreboard.py -q`
Expected: PASS

- [ ] **Step 5: commit**

```bash
git add benchmarks/core/build_scoreboard.py benchmarks/test/test_build_scoreboard.py
git commit -m "feat(scoreboard): v0.1 build_scoreboard CLI (fail-closed on missing preflight)"
```

---

## Task 4: `perception_baseline_observer.py`（選項 B：通用 perception observer）

**Files:**
- Create: `benchmarks/core/perception_baseline_observer.py`
- Test: `benchmarks/test/test_perception_baseline_observer.py`

> **為什麼要**：recon 證實 face/gesture/object 的 event topic 不帶 accuracy/false_trigger/latency，且 `verification_observer.py` 只計數無判定。沒有這個 observer，第一張 scoreboard 視覺三能力全 insufficient_data。
> **設計**：純比對邏輯（`evaluate_round` / `count_false_triggers`）dev-機 TDD；薄 ROS node（Jetson 跑）把三個 event topic 正規化成 `(label, confidence, ts)` 餵純函式。**不改模型、不修辨識、不接 Brain**。
> **2026-06-01 校正（F3，code 證實）**：本 Task 4 **只負責 gesture / object（event-only）**。**face 拆到 Task 4b 獨立 `face_baseline_observer`（state-based）**——因 `/event/face_identity` 只在 stable transition 才發（face_identity_node.py:561），**從不發 unknown**，event-only 量不出 `unknown-false-accept`、多臉、距離；face 必須吃 `/state/perception/face` 連續流。gesture/object 無 state topic、本就只能 event，維持不變。
> **observation 正規化規則**（Task 4 ROS node 端，僅 gesture/object）：`/event/gesture_detected → (gesture, confidence, stamp)`；`/event/object_detected → 每個 objects[]: (class_name, confidence, stamp)`。**face 不在此**（見 Task 4b）。

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_perception_baseline_observer.py
from benchmarks.core.perception_baseline_observer import (
    RoundMeta, evaluate_round, count_false_triggers,
)


def test_idle_round_no_observation_is_pass_no_false_trigger():
    meta = RoundMeta("gesture.wave", "idle_hand_60s", expected_label="none", window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[])
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["predicted_label"] == "none"


def test_idle_round_with_observation_is_false_trigger_fail():
    meta = RoundMeta("gesture.wave", "idle_hand_60s", expected_label="none", window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[("wave", 1.0, 103.0)])
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True
    assert rec["predicted_label"] == "wave"


def test_positive_round_matched_is_pass_with_latency():
    meta = RoundMeta("gesture.wave", "wave_1.5m", expected_label="wave",
                     distance_m=1.5, window_start_ts=100.0)
    rec = evaluate_round(meta, observations=[("wave", 1.0, 100.4)])
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["predicted_label"] == "wave"
    assert abs(rec["latency_ms"] - 400.0) < 1e-6
    assert rec["distance_m"] == 1.5


def test_positive_round_no_observation_is_miss_not_false_trigger():
    meta = RoundMeta("object.cup", "cup_1.5m", expected_label="cup", window_start_ts=0.0)
    rec = evaluate_round(meta, observations=[])
    assert rec["pass_fail"] == "fail"          # miss
    assert rec["false_trigger"] is False       # 漏報不是誤觸
    assert rec["predicted_label"] == "none"


def test_positive_round_wrong_label_is_miss_not_false_trigger():
    meta = RoundMeta("object.cup", "cup_1.5m", expected_label="cup", window_start_ts=0.0)
    rec = evaluate_round(meta, observations=[("bottle", 0.7, 1.0)])
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is False       # 認錯類別算 miss，誤觸只用於 idle round
    assert rec["predicted_label"] == "bottle"


def test_count_false_triggers_over_idle_rounds():
    rounds = [
        evaluate_round(RoundMeta("gesture.wave", "idle", "none", window_start_ts=0.0),
                       observations=[]),
        evaluate_round(RoundMeta("gesture.wave", "idle", "none", window_start_ts=0.0),
                       observations=[("point", 0.8, 1.0)]),
    ]
    assert count_false_triggers(rounds) == 1
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_perception_baseline_observer.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作純比對邏輯（+ 薄 ROS node sketch）**

```python
# benchmarks/core/perception_baseline_observer.py
"""通用 perception baseline observer (v0.1, 選項 B)。

純比對邏輯（dev-機 TDD）：把 operator 宣告的 round_meta（expected_label/scenario/distance）
與該 round 內觀測到的 (label, confidence, ts) 比對，產一筆 CapabilityResult-shaped dict。
idle round（expected_label in {"none",""}）：任何觀測 = false_trigger。
positive round：observed 含 expected → pass（latency=首個命中相對 window_start）；否則 miss（fail）。

ROS node wrapper（Jetson 跑，不在 CI）：訂 /event/{gesture_detected,object_detected}（face 見 Task 4b），
依 round_meta 檔（operator 宣告每 round 的 capability/scenario/expected/window）切窗，
把每 topic 正規化成 (label, confidence, ts) → evaluate_round → append JSONL。

idle 切窗規則（spec §4/§5）：idle round 以**固定長度窗**為單位各生一筆 record（gesture=60s×10 段、
object=60s/窗），每窗 `scenario_kind="idle"`、`false_trigger`=該窗內有無誤報；aggregator 的
unknown_false_accept_rate = 誤觸窗數/總窗數。positive round 則每次「擺好→宣告→觀測」生一筆。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_IDLE_LABELS = {"none", "idle", ""}


@dataclass
class RoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str            # "none"/"" = idle round（預期零事件）
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0


def evaluate_round(meta: RoundMeta, observations: list) -> dict:
    """observations: list[(label:str, confidence:float|None, ts:float)]，限定該 round 窗內。"""
    is_idle = meta.expected_label in _IDLE_LABELS

    if is_idle:
        ft = len(observations) > 0
        predicted = observations[0][0] if observations else "none"
        return _record(meta, predicted_label=predicted,
                       pass_fail=("fail" if ft else "pass"),
                       false_trigger=ft, confidence=None, latency_ms=None)

    # positive round
    matches = [o for o in observations if o[0] == meta.expected_label]
    if matches:
        label, conf, ts = matches[0]
        return _record(meta, predicted_label=label, pass_fail="pass", false_trigger=False,
                       confidence=conf, latency_ms=(ts - meta.window_start_ts) * 1000.0)
    # miss（沒看到 expected）：認錯或沒看到都算 miss，不是 false_trigger
    predicted = observations[0][0] if observations else "none"
    return _record(meta, predicted_label=predicted, pass_fail="fail", false_trigger=False,
                   confidence=None, latency_ms=None)


def _record(meta: RoundMeta, *, predicted_label: str, pass_fail: str,
            false_trigger: bool, confidence: Optional[float], latency_ms: Optional[float]) -> dict:
    return {
        "capability_id": meta.capability_id,
        "scenario_id": meta.scenario_id,
        # F2：scenario_kind 供 aggregate 分離算 recall vs false-accept（idle round=預期零事件）
        "scenario_kind": "idle" if meta.expected_label in _IDLE_LABELS else "positive",
        "expected_label": meta.expected_label,
        "predicted_label": predicted_label,
        "pass_fail": pass_fail,
        "false_trigger": false_trigger,
        "confidence": confidence,
        "latency_ms": latency_ms,
        "distance_m": meta.distance_m,
        "distance_source": meta.distance_source,
    }


def count_false_triggers(round_records: list[dict]) -> int:
    return sum(1 for r in round_records if r.get("false_trigger"))


# --- ROS node wrapper（Jetson 跑，v0.1 不在 CI；保持薄）---
# class PerceptionBaselineObserver(Node):
#   - 訂 /event/gesture_detected, /event/object_detected（face 見 Task 4b）
#   - _normalize(topic, msg) -> list[(label, confidence, ts)]
#   - 依 round_meta 檔（operator 宣告 capability/scenario/expected/window_start/window_end）切窗
#   - round 結束時 evaluate_round(meta, obs) → 補 run_id/timestamp/git_commit（current_run_meta）
#     → CapabilityResult(...).to_record() → append baseline_result.jsonl
#   * 不改任何感知 node、不接 Brain。
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_perception_baseline_observer.py -q`
Expected: PASS（6 個測試全綠）

- [ ] **Step 5: 全套 + commit**

Run: `python -m pytest benchmarks/test -q`
Expected: 全綠（4 檔）

```bash
git add benchmarks/core/perception_baseline_observer.py benchmarks/test/test_perception_baseline_observer.py
git commit -m "feat(scoreboard): v0.1 perception observer (gesture/object event round matching)"
```

---

## Task 4b: `face_baseline_observer.py`（F3：face 走 /state/perception/face 連續流，與 gesture/object 分流）

**Files:**
- Create: `benchmarks/core/face_baseline_observer.py`
- Test: `benchmarks/test/test_face_baseline_observer.py`

> **為什麼獨立**（2026-06-01 F3，code 證實）：`/event/face_identity` 只在 stable transition 才發（`face_identity_node.py:561` `if old_stable_name != new_stable_name`），**從不發 `stable_name=="unknown"`** → event-only **量不出** `unknown-false-accept`、多臉競爭、距離分桶。`/state/perception/face` 每 tick 發**全部 tracks**（`face_identity_node.py:634-641`，含 `track_id/stable_name/sim/distance_m/bbox/mode/face_count`）→ face baseline 必須吃連續 state 流。gesture/object 無 state topic、維持 Task 4 event 模型；故 **face 拆獨立 observer，不污染 Task 4 的 event 純邏輯**。

- [ ] **Step 1: 寫失敗測試**

```python
# benchmarks/test/test_face_baseline_observer.py
from benchmarks.core.face_baseline_observer import (
    FaceStateSnapshot, FaceRoundMeta, evaluate_face_round,
)


def _snap(ts, tracks):
    return FaceStateSnapshot(ts=ts, tracks=tracks)


def test_idle_round_with_known_person_is_false_trigger():
    # idle（預期沒有"已知人被穩定辨識"）：出現已知人 = false_trigger
    meta = FaceRoundMeta("face.recognition", "idle_unknown_1.5m",
                         expected_label="unknown", distance_m=1.5, window_start_ts=100.0)
    snaps = [_snap(101.0, [{"track_id": 1, "stable_name": "roy", "sim": 0.9,
                            "distance_m": 1.5, "mode": "stable"}])]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True
    assert rec["predicted_label"] == "roy"


def test_idle_round_only_unknown_tracks_is_pass():
    # 有人但全 unknown（沒誤認成註冊者）→ pass、非 false_trigger
    meta = FaceRoundMeta("face.recognition", "idle_unknown_1.5m",
                         expected_label="unknown", window_start_ts=100.0)
    snaps = [_snap(101.0, [{"track_id": 1, "stable_name": "unknown", "sim": 0.2,
                            "distance_m": 1.5, "mode": "hold"}])]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False


def test_positive_round_correct_match_is_pass_with_distance():
    meta = FaceRoundMeta("face.recognition", "known_roy_1.5m",
                         expected_label="roy", distance_m=1.5, window_start_ts=100.0)
    snaps = [_snap(100.5, [{"track_id": 1, "stable_name": "roy", "sim": 0.92,
                            "distance_m": 1.48, "mode": "stable"}])]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "pass"
    assert rec["false_trigger"] is False
    assert rec["confidence"] == 0.92
    assert rec["distance_m"] == 1.48
    assert rec["distance_source"] == "d435_depth"   # face state 帶真實深度


def test_positive_round_miss_is_fail_not_false_trigger():
    meta = FaceRoundMeta("face.recognition", "known_roy_3m",
                         expected_label="roy", distance_m=3.0, window_start_ts=100.0)
    snaps = [_snap(101.0, [{"track_id": 1, "stable_name": "unknown", "sim": 0.3,
                            "distance_m": 3.0, "mode": "hold"}])]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"      # 沒認出 = miss
    assert rec["false_trigger"] is False   # 漏報非誤觸


def test_positive_round_wrong_person_is_false_accept():
    # 該是 roy 卻穩定辨識成 alice = 誤接（unknown-false-accept 的嚴重型）
    meta = FaceRoundMeta("face.recognition", "known_roy_1.5m",
                         expected_label="roy", distance_m=1.5, window_start_ts=100.0)
    snaps = [_snap(101.0, [{"track_id": 1, "stable_name": "alice", "sim": 0.88,
                            "distance_m": 1.5, "mode": "stable"}])]
    rec = evaluate_face_round(meta, snaps)
    assert rec["pass_fail"] == "fail"
    assert rec["false_trigger"] is True    # 認錯人比漏認嚴重，計 false_trigger
    assert rec["predicted_label"] == "alice"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest benchmarks/test/test_face_baseline_observer.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 實作 face state 純邏輯**

```python
# benchmarks/core/face_baseline_observer.py
"""Face baseline observer (v0.1, F3) — 吃 /state/perception/face 連續狀態流。

與 perception_baseline_observer（gesture/object，event-only）分流：face 因 /event/face_identity
從不發 unknown、且無多臉/距離維度，必須走每-tick 全 tracks 的 /state/perception/face。
純邏輯 dev-機 TDD；ROS node wrapper（Jetson 跑）依 round window 累積 snapshots → evaluate_face_round。

判定規則：
- idle round（expected_label in {"unknown","none","idle",""}）：任一 snapshot 內有 track 被穩定辨識成
  「某個註冊者（stable_name 非 unknown）」→ false_trigger（誤把陌生人/環境認成註冊者）。全 unknown = pass。
- positive round（expected_label=註冊者名）：window 內出現該名 stable track → pass（confidence=該 track sim，
  distance 取 track 真實深度）；只出現別的註冊者名 → false_trigger（認錯人，比漏認嚴重）；
  只 unknown / 沒 track → miss（fail，但非 false_trigger）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

_IDLE_LABELS = {"unknown", "none", "idle", ""}


@dataclass
class FaceStateSnapshot:
    ts: float
    tracks: list = field(default_factory=list)   # 每個: {track_id, stable_name, sim, distance_m, mode}


@dataclass
class FaceRoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str            # 註冊者名 / "unknown"(idle)
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0


def _known_tracks(snap: FaceStateSnapshot) -> list:
    return [t for t in snap.tracks if t.get("stable_name", "unknown") != "unknown"]


def evaluate_face_round(meta: FaceRoundMeta, snapshots: list) -> dict:
    is_idle = meta.expected_label in _IDLE_LABELS

    if is_idle:
        for snap in snapshots:
            known = _known_tracks(snap)
            if known:   # 任一被穩定辨識成註冊者 = 誤接
                t = known[0]
                return _face_record(meta, predicted_label=t["stable_name"], pass_fail="fail",
                                    false_trigger=True, confidence=t.get("sim"),
                                    distance_m=t.get("distance_m"))
        return _face_record(meta, predicted_label="unknown", pass_fail="pass",
                            false_trigger=False, confidence=None, distance_m=None)

    # positive round：找 expected 名的 stable track（取最早出現）
    for snap in snapshots:
        for t in snap.tracks:
            if t.get("stable_name") == meta.expected_label:
                return _face_record(meta, predicted_label=meta.expected_label, pass_fail="pass",
                                    false_trigger=False, confidence=t.get("sim"),
                                    distance_m=t.get("distance_m"),
                                    latency_ms=(snap.ts - meta.window_start_ts) * 1000.0)
    # 沒看到 expected：若出現別的註冊者 → 認錯人（false_accept）；否則 miss
    for snap in snapshots:
        known = _known_tracks(snap)
        if known:
            t = known[0]
            return _face_record(meta, predicted_label=t["stable_name"], pass_fail="fail",
                                false_trigger=True, confidence=t.get("sim"),
                                distance_m=t.get("distance_m"))
    return _face_record(meta, predicted_label="unknown", pass_fail="fail",
                        false_trigger=False, confidence=None, distance_m=None)


def _face_record(meta: FaceRoundMeta, *, predicted_label: str, pass_fail: str,
                 false_trigger: bool, confidence: Optional[float],
                 distance_m: Optional[float], latency_ms: Optional[float] = None) -> dict:
    return {
        "capability_id": meta.capability_id,
        "scenario_id": meta.scenario_id,
        # F2：idle round（expected="unknown"/"none"）→ 算 unknown_false_accept；positive → 算 registered_recall
        "scenario_kind": "idle" if meta.expected_label in _IDLE_LABELS else "positive",
        "expected_label": meta.expected_label,
        "predicted_label": predicted_label,
        "pass_fail": pass_fail,
        "false_trigger": false_trigger,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "latency_ms": latency_ms,
        "distance_m": distance_m if distance_m is not None else meta.distance_m,
        # face state 帶 D435 真實深度（≠ gesture/object 的人工宣告）
        "distance_source": "d435_depth" if distance_m is not None else meta.distance_source,
    }


# --- ROS node wrapper（Jetson 跑，v0.1 不在 CI；保持薄）---
# class FaceBaselineObserver(Node):
#   - 訂 /state/perception/face（連續 ~20Hz），parse JSON → FaceStateSnapshot(ts, tracks)
#   - 依 round_meta（operator 宣告 capability=face.recognition / expected / distance / window）切窗
#   - round 結束時 evaluate_face_round(meta, window 內 snapshots) → 補 run_id/timestamp/git_commit
#     → CapabilityResult(...).to_record() → append baseline_result.jsonl（與 gesture/object 同一檔）
#   * 不改 face_identity_node、不接 Brain。
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest benchmarks/test/test_face_baseline_observer.py -q`
Expected: PASS（5 個測試全綠）

- [ ] **Step 5: commit**

```bash
git add benchmarks/core/face_baseline_observer.py benchmarks/test/test_face_baseline_observer.py
git commit -m "feat(scoreboard): v0.1 face baseline observer (state-stream, unknown-false-accept aware)"
```

---

