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
