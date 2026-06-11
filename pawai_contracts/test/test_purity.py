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
