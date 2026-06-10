# Plan B: CLI v2 First Slice（操作安全）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pawai jetson deploy` 永遠不可能再刪 Jetson `.env`；`pawai demo start` 不再假成功（healthcheck hard-block）；`pawai status` 看得到 gateway 與各感知模組。

**Architecture:** 三個修復都在現有 Click v1 內完成（**本刀不做 Typer 遷移**）。
deploy 安全 = 單一 exclude 真相源（`tools/sync/rsync-excludes.txt`）+ 優先序反轉
（內建 rsync 預設、`~/sync` 顯式 opt-in）+ post-sync protected-file guard。
demo start = start.sh rc==0 之後**必須** lane healthcheck pass 才把 lock 轉 running。
status = gateway `/health` probe + 模組 node 對照表。

**Tech Stack:** Click 8.1、python-dotenv、bash、pytest（144 既有測試為回歸網）。

---

## Scope

- Create: `tools/sync/rsync-excludes.txt`、`scripts/sync_to_jetson.sh`、`scripts/school_demo_ending.py`
- Modify: `tools/pawai_cli/pawai_cli/main.py`（`_do_rsync_and_build` 508-563、demo start 899-919、school 969-1064、新 `health nav`）
- Modify: `tools/pawai_cli/pawai_cli/status.py`（gateway probe + module nodes）
- Modify: `tools/pawai_cli/tests/test_cli.py`（新 guard tests + 既有 785-821 區更新）
- Modify: `docs/pawai_cli/usage-guide.md` §2.5、`docs/pawai_cli/README.md`（sync 邏輯段 + 指令表）

## Forbidden scope

- 不做 Typer/Rich 遷移（第 2 刀）、不加 smoke/object test 新命令（第 2 刀）
- lock.py 一行不改（lock 語意是全隊安全邊界；demo start 只在「轉 running 前」插入
  healthcheck 呼叫，acquire/release/transition 函式本體不動）
- `-y` ≠ `--force` 語意、platform exit 10、CRLF loader、IP 解析優先序：不准退化
  （test_lock/test_platform/test_cli 既有斷言為準）
- 不動 `.claude/skills/` 內任何檔案，**除了** healthcheck.sh 的 fallback IP 一行（Task B5 Step 4，獨立 commit）
- 錯誤訊息字串若改動，必須同 PR 更新 `docs/pawai_cli/usage-guide.md` §7 與對應測試斷言

## 執行前提

Plan A Task A2 已 merge（pawai_cli 144 測試在 CI 把關本 plan 的每個 commit）。

---

### Task B1: 單一 exclude 真相源

**Files:**
- Create: `tools/sync/rsync-excludes.txt`
- Test: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: 寫 failing test（exclude 檔存在且含保命條目）**

```python
# tools/pawai_cli/tests/test_cli.py — append to the deploy test section
EXCLUDES_FILE = Path(__file__).resolve().parents[3] / "tools" / "sync" / "rsync-excludes.txt"

def test_rsync_excludes_file_has_protected_entries():
    lines = {
        ln.strip() for ln in EXCLUDES_FILE.read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    }
    for required in (".git/", ".env", ".env.*", ".env.local", ".ssh/",
                     "build/", "install/", "log/", "__pycache__/",
                     ".pytest_cache/", ".venv/", "node_modules/", ".next/",
                     ".ruff_cache/", ".mypy_cache/", ".DS_Store"):
        assert required in lines, f"protected exclude missing: {required}"
```

- [ ] **Step 2: 跑確認 fail**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py::test_rsync_excludes_file_has_protected_entries -q
```
Expected: FAIL（FileNotFoundError）。

- [ ] **Step 3: 建 `tools/sync/rsync-excludes.txt`**（內容 = main.py:526-541 的 16 條，一行一條）

```text
# Single source of truth for WSL→Jetson sync excludes.
# Consumers: pawai jetson deploy (_do_rsync_and_build) + scripts/sync_to_jetson.sh.
# 2026-06-10 Plan B1 — born from the 6/10 incident where ~/sync deleted Jetson .env.
.git/
.env
.env.*
.env.local
.ssh/
build/
install/
log/
__pycache__/
.pytest_cache/
.venv/
node_modules/
.next/
.ruff_cache/
.mypy_cache/
.DS_Store
```

- [ ] **Step 4: 跑測試確認 PASS，commit**

```bash
python3 -m pytest tools/pawai_cli/tests/test_cli.py -q   # 144+1 passed
git add tools/sync/rsync-excludes.txt tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): single rsync exclude contract file (Plan B1)"
```

---

### Task B2: deploy 優先序反轉 + post-sync guard

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py:508-563`
- Test: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: 寫 failing tests（三條）**

```python
def test_deploy_prefers_builtin_rsync_even_when_home_sync_exists(tmp_path, monkeypatch):
    """6/10 incident regression: ~/sync exists+executable → MUST still use rsync."""
    sync = tmp_path / "sync"
    sync.write_text("#!/bin/sh\nexit 0\n"); sync.chmod(0o755)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(main_mod.shell, "stream", lambda argv, **kw: calls.append(argv) or 0)
    monkeypatch.setattr(main_mod.shell, "stream_remote", lambda cmd, **kw: 0)
    monkeypatch.setattr(main_mod, "_post_sync_guard", lambda pre: None)
    code, method = main_mod._do_rsync_and_build(
        root=Path("/repo"), packages=[], no_sync=False, no_build=True, module_key="x")
    assert method == "rsync"
    assert calls and calls[0][0] == "rsync"
    assert any(str(a).startswith("--exclude-from=") for a in calls[0])

def test_deploy_opt_in_external_sync_requires_env(tmp_path, monkeypatch):
    sync = tmp_path / "sync"
    sync.write_text("#!/bin/sh\nexit 0\n"); sync.chmod(0o755)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("PAWAI_SYNC_CMD", "1")
    calls = []
    monkeypatch.setattr(main_mod.shell, "stream", lambda argv, **kw: calls.append(argv) or 0)
    monkeypatch.setattr(main_mod, "_post_sync_guard", lambda pre: None)
    code, method = main_mod._do_rsync_and_build(
        root=Path("/repo"), packages=[], no_sync=False, no_build=True, module_key="x")
    assert method == "sync-once"

def test_post_sync_guard_fails_loud_when_env_disappears(monkeypatch):
    monkeypatch.setattr(main_mod.shell, "run_remote",
                        lambda cmd, **kw: SimpleNamespace(ok=True, stdout="MISSING\n", stderr="", code=0))
    with pytest.raises(click.ClickException) as exc:
        main_mod._post_sync_guard({"~/elder_and_dog/.env": True})
    assert ".env" in str(exc.value)
```
（`main_mod` = 既有測試檔對 `pawai_cli.main` 的 import 別名；`SimpleNamespace`、
`pytest`、`click` 檔頭已有或補 import。）

- [ ] **Step 2: 跑確認 fail**（`_post_sync_guard` 不存在 → AttributeError）

- [ ] **Step 3: 改寫 `_do_rsync_and_build` + 新增 guard**

```python
PROTECTED_REMOTE_FILES = (".env", ".env.local")


def _snapshot_protected() -> dict[str, bool]:
    """Record which protected files exist on Jetson BEFORE sync."""
    repo = shell.jetson_repo()
    out: dict[str, bool] = {}
    for name in PROTECTED_REMOTE_FILES:
        path = f"{repo}/{name}"
        r = shell.run_remote(f"test -f {path} && echo OK || echo MISSING", timeout=8)
        out[path] = bool(r.ok and "OK" in r.stdout)
    return out


def _post_sync_guard(pre: dict[str, bool]) -> None:
    """Fail loud if any protected file that existed pre-sync is gone post-sync."""
    deleted = []
    for path, existed in pre.items():
        if not existed:
            continue
        r = shell.run_remote(f"test -f {path} && echo OK || echo MISSING", timeout=8)
        if not (r.ok and "OK" in r.stdout):
            deleted.append(path)
    if deleted:
        raise click.ClickException(
            "PROTECTED FILE(S) DELETED BY SYNC: " + ", ".join(deleted) +
            "\n  Restore now:  ssh $JETSON_HOST 'cd ~/elder_and_dog && cp .env.local .env'"
            "\n  (CLAUDE.md §Demo 啟動/.env 環境陷阱 has the full SOP.)"
        )


def _do_rsync_and_build(root: Path, packages: list[str], no_sync: bool, no_build: bool,
                         module_key: str) -> tuple[int, str]:
    """Perform rsync and/or colcon build. Returns (exit_code, sync_method).

    2026-06-10 Plan B2: builtin rsync is ALWAYS the default. ~/sync is opt-in
    only via PAWAI_SYNC_CMD=1 (it deleted the Jetson .env on 6/10 — unaudited
    personal script, no exclude contract). Any sync method is followed by a
    protected-file guard.
    """
    if not no_sync:
        pre = _snapshot_protected()
        sync_once = Path.home() / "sync"
        use_external = os.environ.get("PAWAI_SYNC_CMD") == "1" \
            and sync_once.exists() and os.access(sync_once, os.X_OK)
        if use_external:
            print("Sync: ~/sync once  ⚠ UNAUDITED external sync (PAWAI_SYNC_CMD=1)")
            code = shell.stream([str(sync_once), "once"], cwd=root)
            if code != 0:
                return code, "sync-once"
            sync_method = "sync-once"
        else:
            excludes = root / "tools" / "sync" / "rsync-excludes.txt"
            print("Sync: rsync whole repo (exclude contract: tools/sync/rsync-excludes.txt)")
            dest = f"{shell.jetson_host()}:{shell.jetson_repo().rstrip('/')}/"
            argv = ["rsync", "-az", "--delete", f"--exclude-from={excludes}", f"{root}/", dest]
            code = shell.stream(argv)
            if code != 0:
                return code, "rsync"
            sync_method = "rsync"
        _post_sync_guard(pre)
    else:
        sync_method = "none"

    if not no_build and packages:
        pkg_arg = " ".join(packages)
        print(f"Build: colcon build --packages-select {pkg_arg}")
        code = shell.stream_remote(
            f"cd {shell.jetson_repo()} && "
            "source /opt/ros/humble/setup.zsh 2>/dev/null || true; "
            f"colcon build --packages-select {pkg_arg}"
        )
        if code != 0:
            return code, sync_method
    return 0, sync_method
```

- [ ] **Step 4: 更新既有 rsync exclude 測試（test_cli.py:785-821 區）**——原測試斷言
inline `--exclude=` 參數，改斷言 `--exclude-from=` + 檔案內容（B1 測試已蓋內容）。
刪掉 `:800` 那個「故意 patch Path.home 繞過 ~/sync」的 hack（新預設已不需要繞）。

- [ ] **Step 5: 全套跑綠 + commit**

```bash
python3 -m pytest tools/pawai_cli/tests -q   # 147 passed
git add -u tools/ && git commit -m "fix(cli): deploy defaults to audited rsync; ~/sync opt-in via PAWAI_SYNC_CMD; post-sync protected-file guard (Plan B2, 6/10 .env-deletion regression)"
```

---

### Task B3: `scripts/sync_to_jetson.sh`（手動 rsync 正式化）

**Files:**
- Create: `scripts/sync_to_jetson.sh`
- Test: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: failing test（腳本必須用同一份 exclude 檔）**

```python
def test_sync_script_uses_shared_exclude_contract():
    script = Path(__file__).resolve().parents[3] / "scripts" / "sync_to_jetson.sh"
    body = script.read_text()
    assert "--exclude-from=" in body and "tools/sync/rsync-excludes.txt" in body
    assert "--delete" in body
```

- [ ] **Step 2: 建腳本**

```bash
#!/usr/bin/env bash
# WSL → Jetson manual sync — formalizes the "safe manual rsync" the team has
# used since the 6/10 ~/sync .env-deletion incident. Same exclude contract as
# `pawai jetson deploy` (tools/sync/rsync-excludes.txt). Does NOT colcon build.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
JETSON_HOST="${JETSON_HOST:-jetson-nano}"
JETSON_REPO="${JETSON_REPO:-~/elder_and_dog}"
echo "rsync $REPO_ROOT/ → $JETSON_HOST:$JETSON_REPO/ (exclude contract: tools/sync/rsync-excludes.txt)"
rsync -az --delete \
  --exclude-from="$REPO_ROOT/tools/sync/rsync-excludes.txt" \
  "$REPO_ROOT/" "$JETSON_HOST:$JETSON_REPO/"
echo "✓ sync done. Remember: colcon build --packages-select <pkg> on Jetson if .py changed."
```

- [ ] **Step 3: `chmod +x`、`bash -n` 語法檢查、測試綠、commit**

```bash
chmod +x scripts/sync_to_jetson.sh && bash -n scripts/sync_to_jetson.sh
python3 -m pytest tools/pawai_cli/tests -q
git add scripts/sync_to_jetson.sh tools/pawai_cli/tests/test_cli.py
git commit -m "feat(scripts): sync_to_jetson.sh sharing the rsync exclude contract (Plan B3)"
```

---

### Task B4: demo start healthcheck hard-block + `--skip-healthcheck`

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`（demo start command：option 清單 + :899-919 區）
- Test: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: failing tests（三條）**

```python
def _patch_demo_start_happy(monkeypatch, hc_rc: int):
    """Common scaffolding: lock acquire OK, start.sh rc=0, healthcheck rc=hc_rc."""
    fake_lock = MagicMock()
    fake_lock.transition_if_owned.return_value = True
    monkeypatch.setattr(lock_mod.Lock, "read", staticmethod(lambda: None))
    monkeypatch.setattr(lock_mod.Lock, "acquire", staticmethod(lambda **kw: fake_lock))
    monkeypatch.setattr(main_mod, "_invoke_start_sh", lambda **kw: 0)
    monkeypatch.setattr(main_mod, "_run_lane_healthcheck", lambda lane: hc_rc)
    return fake_lock

def test_demo_start_blocks_running_on_healthcheck_fail(monkeypatch, runner):
    fake_lock = _patch_demo_start_happy(monkeypatch, hc_rc=1)
    result = runner.invoke(main_mod.cli, ["demo", "start"])
    assert result.exit_code != 0
    fake_lock.transition_if_owned.assert_not_called()      # lock 留在 starting
    assert "healthcheck FAILED" in result.output

def test_demo_start_transitions_running_on_healthcheck_pass(monkeypatch, runner):
    fake_lock = _patch_demo_start_happy(monkeypatch, hc_rc=0)
    result = runner.invoke(main_mod.cli, ["demo", "start"])
    assert result.exit_code == 0
    fake_lock.transition_if_owned.assert_called_once()

def test_demo_start_skip_healthcheck_prints_loud_banner(monkeypatch, runner):
    fake_lock = _patch_demo_start_happy(monkeypatch, hc_rc=1)  # hc would fail, but skipped
    result = runner.invoke(main_mod.cli, ["demo", "start", "--skip-healthcheck"])
    assert result.exit_code == 0
    assert "HEALTHCHECK SKIPPED" in result.output
```
（`runner` = 既有 CliRunner fixture；`lock_mod` = `pawai_cli.lock`。依既有 test_cli.py
的 demo-start 測試 scaffolding 風格調整 patch 點。）

- [ ] **Step 2: 實作 `_run_lane_healthcheck` + 插入 gate**

```python
_LANE_HEALTHCHECK = {
    "brain": ".claude/skills/brain-studio-lane/scripts/healthcheck.sh",
    "nav_capability": ".claude/skills/nav-avoidance-lane/scripts/healthcheck.sh",
}


def _run_lane_healthcheck(lane: str) -> int:
    """Post-start gate (Plan B4): start.sh rc==0 is NOT success — the 6/4
    CRLF incident proved tmux can silently never spawn. Returns healthcheck rc;
    255/None script-missing counts as failure (fail-closed)."""
    rel = _LANE_HEALTHCHECK.get(lane, _LANE_HEALTHCHECK["brain"])
    script = shell.repo_root() / rel
    if not script.exists():
        click.echo(f"✗ healthcheck script missing: {script} (fail-closed)")
        return 1
    env = _build_demo_env()
    env["JETSON_HOST"] = shell.jetson_host()
    return shell.stream(["bash", str(script)], cwd=shell.repo_root(), env=env)
```

demo start command 加 option（與既有 options 並列）：

```python
@click.option("--skip-healthcheck", is_flag=True,
              help="Escape hatch: trust start.sh rc and skip the post-start healthcheck gate.")
```

在 `rc = _invoke_nav_start_sh() ... sys.exit(rc)` 區塊（main.py:899-906）**之後**、
`transition_if_owned("running")`（:908）**之前**插入：

```python
    if skip_healthcheck:
        click.echo("⚠⚠ HEALTHCHECK SKIPPED (--skip-healthcheck) — start.sh rc is the "
                   "only evidence; demo may be silently broken (6/4-class failure). ⚠⚠")
    else:
        click.echo("Post-start healthcheck (hard gate — Plan B4)...")
        hc_rc = _run_lane_healthcheck(lane)
        if hc_rc != 0:
            click.echo("✗ Demo processes were launched but healthcheck FAILED — "
                       "lock kept in 'starting' as evidence.")
            click.echo("  Inspect:  pawai logs <module>   |   pawai status")
            click.echo("  Cleanup:  pawai demo stop")
            click.echo("  Escape hatch (only if healthcheck itself is broken): "
                       "pawai demo start --skip-healthcheck")
            sys.exit(1)
```

- [ ] **Step 3: 跑綠 + commit**

```bash
python3 -m pytest tools/pawai_cli/tests -q
git add -u tools/ && git commit -m "feat(cli): demo start hard-blocks on lane healthcheck; --skip-healthcheck escape hatch (Plan B4, kills 6/4 fake-success)"
```

- [ ] **Step 4: healthcheck.sh fallback IP 修正（獨立 commit）**

`.claude/skills/brain-studio-lane/scripts/healthcheck.sh:8` 的
`JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-100.83.109.89}"` 改為：

```bash
JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:?JETSON_TAILSCALE_IP not set — run via pawai (env injected) or export it}"
```
（違反 fail-hard 政策的 hardcoded fallback；CLI 路徑本來就注入。）
手動驗證：`JETSON_TAILSCALE_IP= bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh`
→ 立即報錯退出。commit：`fix(lane): healthcheck fail-hard when JETSON_TAILSCALE_IP unset`。

---

### Task B5: `pawai status` 真實性升級 + `pawai health nav`

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/status.py`、`tools/pawai_cli/pawai_cli/main.py`

- [ ] **Step 1: status.py 加 gateway probe + 模組 node 對照**

```python
_MODULE_NODE_HINTS: dict[str, str] = {
    "face": "face_identity_node",
    "vision(pose+gesture)": "vision_perception",
    "object": "object_perception",
    "speech(asr)": "stt_intent_node",
    "tts": "tts_node",
    "brain": "brain_node",
    "executive": "interaction_executive",
    "conv_graph": "conversation_graph_node",
    "go2_driver": "go2_driver_node",
}


def gateway_health() -> str:
    r = shell.run_remote("curl -s --max-time 3 http://localhost:8080/health || true", timeout=8)
    if r.ok and '"status":"ok"' in r.stdout:
        return "ok " + r.stdout.strip()[:120]
    return "down / not started"


def module_presence(ros_nodes: str) -> list[tuple[str, bool]]:
    return [(label, hint in ros_nodes) for label, hint in _MODULE_NODE_HINTS.items()]
```

`print_status` 在 `ROS nodes (...)` 區塊之後插入（僅非 short 模式）：

```python
        print("\nModules (node presence):")
        for label, present in module_presence(st.ros_nodes):
            print(f"  {'✅' if present else '— '} {label}")
        print(f"\nStudio gateway /health: {gateway_health()}")
```

- [ ] **Step 2: main.py 加 `health nav`（鏡像 health brain，main.py:710-722 同款）**

```python
@health.command("nav")
def health_nav() -> None:
    """Run nav-avoidance-lane healthcheck against Jetson."""
    script = (
        shell.repo_root() / ".claude" / "skills" / "nav-avoidance-lane" /
        "scripts" / "healthcheck.sh"
    )
    if not script.exists():
        raise click.ClickException(f"healthcheck script not found: {script}")
    env = _build_demo_env()
    env["JETSON_HOST"] = shell.jetson_host()
    rc = shell.stream(["bash", str(script)], cwd=shell.repo_root(), env=env)
    sys.exit(rc)
```

- [ ] **Step 3: tests（status helpers 純函數測試 + health nav 命令存在）**

```python
def test_module_presence_maps_nodes():
    from pawai_cli import status as st
    nodes = "/face_identity_node\n/brain_node\n/go2_driver_node"
    got = dict(st.module_presence(nodes))
    assert got["face"] and got["brain"] and got["go2_driver"]
    assert not got["object"]

def test_health_nav_command_registered(runner):
    result = runner.invoke(main_mod.cli, ["health", "nav", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 4: 跑綠 + commit**：`feat(cli): status shows gateway health + per-module node presence; add pawai health nav (Plan B5)`

---

### Task B6: `demo school` 歸檔拆 helper

**Files:**
- Create: `scripts/school_demo_ending.py`（從 main.py:969-1064 整段搬出：ending text、
  FINGER_HEART_API_ID=1036、wait-for-subscriber-then-publish 的 inline rclpy pattern——
  那個 pattern 解的是真實 DDS one-shot-pub race，保留為可重用 script）
- Modify: `tools/pawai_cli/pawai_cli/main.py`（school 命令本體改為 deprecation stub）

- [ ] **Step 1: 搬移**——school 區塊的 python -c 內容落成獨立腳本（含 shebang +
  docstring 註明「5/16 招生活動產物，活動已過；pattern 可重用」），CLI 命令改為：

```python
@demo.command("school")
def demo_school() -> None:
    """[DEPRECATED 2026-06-10] 5/16 school demo is over."""
    raise click.ClickException(
        "demo school retired (event passed 5/16). "
        "The ending publisher lives in scripts/school_demo_ending.py if ever needed."
    )
```

- [ ] **Step 2: 更新/刪除對應測試斷言、全套跑綠、commit**：
  `refactor(cli): retire demo school command; extract publisher pattern to scripts/ (Plan B6)`

---

### Task B7: 文件同步

**Files:**
- Modify: `docs/pawai_cli/usage-guide.md` §2.5（「.env/.ssh 不會被推上 Jetson」的
  overclaim 改寫：guarantee 來自 exclude 契約檔 + post-sync guard，並註明 ~/sync
  opt-in 路徑的風險與 PAWAI_SYNC_CMD）
- Modify: `docs/pawai_cli/README.md`：Sync 邏輯段改寫（優先序反轉）、指令表補
  `health nav`、demo start 補 `--skip-healthcheck` 與 healthcheck gate 行為、
  school 標 deprecated
- Modify: `docs/pawai_cli/troubleshooting.md` F3（~/sync precedence 從 feature 改為 opt-in）

- [ ] **Step 1: 改寫三份文件對應段落、commit**：`docs(cli): sync safety + healthcheck gate + health nav (Plan B7)`

---

## Tests / 驗收

- `python3 -m pytest tools/pawai_cli/tests -q` 全綠（144 → ~152）。
- CI（Plan A2 invocation）綠。
- **HITL gate（merge 後第一次上機，必做才可宣稱）**：
  1. `pawai jetson deploy --module brain` 對真 Jetson：post-sync 驗證 `.env`/`.env.local`
     存活、`.pawai-last-deploy` 正確寫入（6/10 事故反向驗證）。
  2. `pawai demo start`：正常路徑 healthcheck pass → running。
  3. 故意弄壞（`ssh jetson-nano "sed -i 's/$/\r/' ~/elder_and_dog/.env"`）→
     `pawai demo start` 必須 fail、lock 留 starting、印出指引 → 還原
     （`sed -i 's/\r$//' .env`）。重現 6/4 事故場景被擋下。

## Rollback

單 PR revert 即回 v1 行為。`PAWAI_SYNC_CMD=1` 是 ~/sync 的逃生口、
`--skip-healthcheck` 是閘的逃生口——rollback 不需要動 code 也有降級路徑。
