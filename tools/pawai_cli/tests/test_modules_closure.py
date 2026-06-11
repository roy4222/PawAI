"""Module build-list dependency closure (2026-06-11 B-E smoke Gap 1).

Root cause class: `pawai jetson deploy --module X` runs
`colcon build --packages-select <module packages>`.  If a selected package's
package.xml depends on another *repo-local* package that is NOT in the build
list, a fresh machine (or a machine where that dependency was never built)
fails with "Failed to find .../share/<dep>/package.sh".

First hit: Plan C made interaction_executive depend on pawai_contracts, but
the brain module build list didn't include it — every fresh
`deploy --module brain` went red.  The same latent gap existed for
go2_interfaces in speech/gesture/pose/nav/brain (masked only because Jetson
had built it long ago).

This test pins the closure so the next extraction can't reintroduce the class.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from pawai_cli.modules import MODULES

REPO_ROOT = Path(__file__).resolve().parents[3]

# Dependency tags that require the dep to be colcon-built/deployable.
# test_depend intentionally excluded: not needed to build or run on Jetson.
_DEP_TAGS = ("depend", "build_depend", "exec_depend")


def _local_packages() -> dict[str, Path]:
    pkgs: dict[str, Path] = {}
    for px in REPO_ROOT.glob("*/package.xml"):
        m = re.search(r"<name>([^<]+)</name>", px.read_text(encoding="utf-8"))
        if m:
            pkgs[m.group(1).strip()] = px
    return pkgs


def _declared_deps(package_xml: Path) -> set[str]:
    txt = package_xml.read_text(encoding="utf-8")
    deps: set[str] = set()
    for tag in _DEP_TAGS:
        deps |= {d.strip() for d in re.findall(rf"<{tag}>([^<]+)</{tag}>", txt)}
    return deps


def test_repo_local_packages_discovered() -> None:
    """Sanity: discovery must see the packages this test exists to protect."""
    local = _local_packages()
    assert "pawai_contracts" in local
    assert "go2_interfaces" in local


@pytest.mark.parametrize("key", sorted(MODULES))
def test_module_build_list_is_dependency_closed(key: str) -> None:
    module = MODULES[key]
    local = _local_packages()
    selected = set(module.packages)
    missing: set[str] = set()
    for pkg in module.packages:
        xml = local.get(pkg)
        if xml is None:  # non-repo package (none today) — nothing to check
            continue
        for dep in _declared_deps(xml):
            if dep in local and dep not in selected:
                missing.add(dep)
    assert not missing, (
        f"module '{key}' build list {module.packages} is missing repo-local "
        f"dependencies {sorted(missing)} — fresh `pawai jetson deploy "
        f"--module {key}` will fail at colcon env setup. Add them to "
        f"pawai_cli/modules.py."
    )
