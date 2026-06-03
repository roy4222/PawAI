import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "capture_baseline_round.py"


def _load():
    # benchmarks/scripts 不是 package；用檔案路徑載入。
    # 應在 CI（無 rclpy）下成功 import —— rclpy 只在 run_*() 內 lazy import。
    spec = importlib.util.spec_from_file_location("capture_baseline_round", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_is_ci_safe_without_rclpy():
    mod = _load()
    assert hasattr(mod, "run_face")
    assert hasattr(mod, "run_percep")
    assert hasattr(mod, "append_record")


def test_append_record_writes_jsonl_line(tmp_path):
    mod = _load()
    out = tmp_path / "baseline_result.jsonl"
    mod.append_record(str(out), {"capability_id": "face.recognition", "pass_fail": "pass"})
    mod.append_record(str(out), {"capability_id": "object.cup", "pass_fail": "fail"})
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["capability_id"] == "face.recognition"
    assert lines[1]["pass_fail"] == "fail"


def test_parser_face_and_percep_modes():
    mod = _load()
    parser = mod.build_parser()
    a = parser.parse_args(
        ["face", "--capability", "face.recognition", "--scenario-id", "roy_1m_01",
         "--expected", "roy", "--kind", "positive", "--window", "8"]
    )
    assert a.mode == "face" and a.capability == "face.recognition" and a.window == 8.0
    b = parser.parse_args(
        ["percep", "--capability", "gesture.wave", "--scenario-id", "wave_1",
         "--expected", "wave", "--kind", "idle"]
    )
    assert b.mode == "percep" and b.kind == "idle"
