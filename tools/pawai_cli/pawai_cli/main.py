from __future__ import annotations

import io
import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv

from . import __version__, shell
from .modules import MODULES, existing_docs, get_module
from .status import print_status


def _load_env(root: Path) -> None:
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.local", override=True)


def _install_hint_map() -> dict[str, str]:
    """Per-binary install hint, platform-aware.

    Ubuntu/Debian's Node package is `nodejs` (binary is still `node`), and
    `npm` is a separate package — using `apt install node` lands the user on
    the unrelated `node` Amateur Packet Radio package, which is the wrong
    rabbit hole.
    """
    if platform.system() == "Darwin":
        return {
            "tmux": "brew install tmux",
            "node": "brew install node",
            "npm": "brew install node  # ships npm",
        }
    # Linux/WSL — default to apt syntax (most common). Other distros: adapt.
    return {
        "tmux": "sudo apt install tmux",
        "node": "sudo apt install nodejs npm",
        "npm": "sudo apt install nodejs npm",
    }


def _build_last_deploy_payload(module: str, packages: list[str], sync_method: str) -> dict:
    """Construct the .pawai-last-deploy JSON payload with full provenance.

    Captures: who deployed, from which host, current branch, full+short SHA,
    dirty flag, module alias, resolved package list, sync method, timestamp.
    """
    root = shell.repo_root()
    branch_r = shell.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    sha_r = shell.run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5)
    porcelain = shell.run(["git", "-C", str(root), "status", "--porcelain"], timeout=5)

    branch = branch_r.stdout.strip() if branch_r.ok else "unknown"
    sha_full = sha_r.stdout.strip() if sha_r.ok else ""
    sha_short = sha_full[:7] if sha_full else ""
    dirty = bool(porcelain.stdout.strip()) if porcelain.ok else False

    identity = shell.local_identity()
    deployed_by = identity.split("@")[0]
    deployed_from_host = identity.split("@")[-1] if "@" in identity else ""

    return {
        "deployed_by": deployed_by,
        "deployed_from_host": deployed_from_host,
        "branch": branch,
        "git_sha": sha_short,
        "git_sha_full": sha_full,
        "dirty": dirty,
        "module": module,
        "packages": packages,
        "when": datetime.now(timezone.utc).isoformat(),
        "sync_method": sync_method,
    }


def _patch_env_local(path: Path, key: str, value: str) -> None:
    """In-place replace or append `KEY=value` line in .env.local. Idempotent."""
    if not path.exists():
        path.write_text(f"{key}={value}\n")
        return
    lines = path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n")


def _ssh_config_has_host(cfg_text: str, host: str) -> bool:
    """Return True if ~/.ssh/config defines a Host block matching `host` exactly.

    Handles:
      - leading whitespace before `Host`
      - case-insensitive `Host` keyword
      - multi-host lines: `Host alpha beta gamma`
      - wildcard patterns are NOT treated as matches (we want an explicit alias)
      - commented-out `Host` lines are skipped
    """
    target = host.strip()
    for raw in cfg_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2 or parts[0].lower() != "host":
            continue
        for pattern in parts[1:]:
            if pattern == target:
                return True
    return False


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
def cli() -> None:
    """PawAI development and Jetson orchestration CLI."""
    _load_env(shell.repo_root())


@cli.command()
@click.option("--verbose", is_flag=True, help="Print SSH stderr details on failure.")
@click.option("--expect-demo", is_flag=True, help="Treat Gateway 8080 down as FAIL (default: SKIP).")
@click.option("--fix", is_flag=True, help="Prompt to write detected Tailscale IP into .env.local.")
@click.option("--deep", is_flag=True, help="Run live OpenRouter API call.")
@click.option("--cache", "cache_seconds", type=int, default=0,
              help="Cache result for N seconds.")
def doctor(verbose: bool, expect_demo: bool, fix: bool, deep: bool, cache_seconds: int) -> None:
    """Validate local environment and Jetson reachability."""
    from . import network
    from .cache import DoctorCache

    root = shell.repo_root()

    cache = None
    if cache_seconds > 0:
        cache_dir = Path(os.environ.get("PAWAI_CACHE_DIR",
                                        os.path.expanduser("~/.cache/pawai")))
        cache = DoctorCache(cache_dir / "doctor.json", ttl_seconds=cache_seconds)
        cached = cache.read()
        if cached is not None:
            click.echo(cached.get("output", ""))
            click.echo(f"(cached result, age <{cache_seconds}s — run without --cache to refresh)")
            return

    buf = io.StringIO() if cache is not None else None

    def emit(line: str = "") -> None:
        click.echo(line)
        if buf is not None:
            buf.write(line + "\n")

    blocking = 0
    warnings = 0

    def ok(msg: str) -> None:
        emit(f"✓ {msg}")

    def warn(msg: str) -> None:
        nonlocal warnings
        warnings += 1
        emit(f"⚠ {msg}")

    def fail(msg: str) -> None:
        nonlocal blocking
        blocking += 1
        emit(f"✗ {msg}")

    emit("PawAI environment doctor")
    emit("────────────────────────")

    # == Tailscale ==
    hint = shell.jetson_hostname_hint()
    env_ip = os.environ.get("JETSON_TAILSCALE_IP", "").strip()

    emit("== Tailscale ==")
    peer = network.find_jetson_peer(hint=hint)
    if peer is None:
        blocking += 1
        emit(f"  ✗ no Tailscale peer hostname matches '{hint}'")
        emit(f"    → ask Roy for the share link and accept it in your Tailscale account")
        emit(f"    → or set JETSON_HOSTNAME_HINT in .env.local if your share node has a different hostname")
    else:
        detected_ip = peer["ip"]
        emit(f"  ✓ Tailscale peer '{peer['hostname']}' online={peer['online']} ip={detected_ip}")
        if env_ip and env_ip != detected_ip:
            emit(f"  ⚠ JETSON_TAILSCALE_IP={env_ip} but Tailscale reports {detected_ip} (mismatch)")
            emit(f"    → run `pawai doctor --fix` to update .env.local")
            if fix:
                answer = click.prompt(
                    f"\nUpdate JETSON_TAILSCALE_IP in .env.local from {env_ip} to {detected_ip}?",
                    default="n", show_default=True,
                )
                if answer.lower().startswith("y"):
                    _patch_env_local(Path(shell.repo_root()) / ".env.local",
                                     "JETSON_TAILSCALE_IP", detected_ip)
                    emit(f"  ✓ wrote JETSON_TAILSCALE_IP={detected_ip} to .env.local")
        elif not env_ip:
            emit(f"  ℹ JETSON_TAILSCALE_IP unset — CLI will use detected {detected_ip}")

    # == Network topology ==
    emit("\n== Network topology ==")

    if peer is None:
        emit("  ✗ local → Jetson Tailscale: no peer found (see Tailscale section above)")
    else:
        emit(f"  ✓ local → Jetson Tailscale: OK {peer['ip']}")

    iface = network.jetson_internet_iface()
    if iface is None:
        if peer is not None:
            blocking += 1
        emit("  ✗ Jetson internet route: probe failed")
    elif iface == "eth0":
        warnings += 1
        emit(f"  ⚠ Jetson internet route: {iface} (Ethernet appears to be uplink — Go2 link may be lost)")
    else:
        emit(f"  ✓ Jetson internet route: {iface}")

    go2_link = network.jetson_go2_link()
    if go2_link is None:
        if peer is not None:
            blocking += 1
        emit("  ✗ Jetson Go2 link: no 192.168.123.x interface (Ethernet to Go2 not connected)")
    else:
        emit(f"  ✓ Jetson Go2 link: {go2_link['iface']} {go2_link['ip']}")

    robot_ip_topo = shell.env("ROBOT_IP", "192.168.123.161")
    if go2_link is None:
        emit(f"  ✗ Jetson → Go2 ping: skipped (no Go2 link)")
    elif network.jetson_ping_go2(robot_ip_topo):
        emit(f"  ✓ Jetson → Go2 ping: OK {robot_ip_topo}")
    else:
        blocking += 1
        emit(f"  ✗ Jetson → Go2 ping: FAIL {robot_ip_topo}")

    lock_state = None  # L2 will populate this from lock module
    gw_status = network.gateway_8080_status(expect_demo=expect_demo, lock_state=lock_state)
    icon = {"OK": "✓", "SKIP": "ℹ", "FAIL": "✗"}.get(gw_status, "?")
    detail = "" if gw_status != "SKIP" else " (no demo running)"
    if gw_status == "FAIL":
        blocking += 1
    emit(f"  {icon} Gateway 8080: {gw_status}{detail}")

    py = sys.version_info
    if py.major == 3 and py.minor >= 10:
        ok(f"Python {platform.python_version()}")
    else:
        fail(f"Python {platform.python_version()} (need >=3.10)")

    git = shell.run(["git", "--version"], timeout=5)
    if git.ok:
        status = shell.run(["git", "status", "--short"], cwd=root, timeout=8)
        clean = "clean" if status.ok and not status.stdout.strip() else "dirty"
        ok(f"{git.stdout.strip()} · repo {root} ({clean})")
    else:
        fail("git missing")

    if (root / ".env.local").exists():
        ok(".env.local present")
    elif (root / ".env").exists():
        warn(".env.local missing; using .env only")
        emit("  → cp .env.local.example .env.local  (then fill OPENROUTER_KEY)")
    else:
        warn(".env.local/.env missing")
        emit("  → cp .env.local.example .env.local")

    ssh = shell.run(shell.ssh_args("echo OK"), timeout=10)
    if ssh.ok and "OK" in ssh.stdout:
        ok(f"JETSON_HOST={shell.jetson_host()} reachable")
    else:
        fail(f"JETSON_HOST={shell.jetson_host()} unreachable")
        ssh_cfg = Path.home() / ".ssh" / "config"
        host = shell.jetson_host()
        if ssh_cfg.exists():
            has_host_block = _ssh_config_has_host(ssh_cfg.read_text(), host)
            if not has_host_block:
                emit(f"  → no `Host {host}` block in ~/.ssh/config")
                emit("    add one pointing at the Jetson Tailscale IP, or set JETSON_HOST in .env.local")
            else:
                emit(f"  → ssh-copy-id {host}   # if key not yet authorized")
                emit("  → tailscale up         # if Tailscale offline")
        if verbose:
            emit(ssh.stderr.strip())

    tailscale = shell.run(["tailscale", "status"], timeout=6)
    if tailscale.ok:
        ok("Tailscale command works")
    else:
        warn("Tailscale command unavailable or logged out")
        if platform.system() == "Darwin":
            emit("  → open -a Tailscale  (or `brew install --cask tailscale` if missing)")

    robot_ip = os.getenv("ROBOT_IP", "192.168.123.161")
    ok(f"ROBOT_IP={robot_ip} (not pinged)")

    install_hint = _install_hint_map()
    for bin_name, label, critical in (
        ("tmux", "tmux", False),
        ("node", "Node.js", False),
        ("npm", "npm", False),
    ):
        path = shutil.which(bin_name)
        if path:
            ok(f"{label} found")
            continue
        if critical:
            fail(f"{label} missing")
        else:
            warn(f"{label} missing")
        install_hint_val = install_hint.get(bin_name)
        if install_hint_val:
            emit(f"  → {install_hint_val}")

    studio_fe = root / "pawai-studio" / "frontend"
    if (studio_fe / "node_modules").exists():
        ok("Studio frontend node_modules present")
    else:
        warn("Studio frontend node_modules missing")
        emit(f"  → cd {studio_fe} && npm install   (or let `pawai demo start` auto-install)")

    if (studio_fe / ".env.local").exists():
        ok("Studio frontend .env.local present")
    else:
        warn("Studio frontend .env.local missing")
        emit(f"  → cp {studio_fe}/.env.local.example {studio_fe}/.env.local")
        emit("    (`pawai demo start` will auto-generate from JETSON_TAILSCALE_IP)")

    if os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY"):
        ok("OpenRouter key present")
    else:
        warn("OpenRouter key empty; cloud LLM unavailable")
        emit("  → set OPENROUTER_KEY in .env.local  (https://openrouter.ai/keys)")

    if deep:
        emit("\n== Deep checks (--deep) ==")
        key = os.environ.get("OPENROUTER_KEY") or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            emit("  ✗ OPENROUTER_KEY not set")
        else:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        emit("  ✓ OpenRouter API reachable, key authorized")
                    else:
                        emit(f"  ✗ OpenRouter API returned status {r.status}")
            except urllib.error.HTTPError as exc:
                emit(f"  ✗ OpenRouter HTTP {exc.code}: {exc.reason}")
            except Exception as exc:
                emit(f"  ✗ OpenRouter API call failed: {exc}")

    emit(f"\n{blocking} blocking · {warnings} warnings")

    if cache is not None and buf is not None:
        cache.write({"output": buf.getvalue()})

    raise SystemExit(2 if blocking else 0)


@cli.command()
@click.option("--short", is_flag=True, help="Skip ROS node detail.")
def status(short: bool) -> None:
    """Show Jetson tmux/ROS/git state."""
    print_status(short=short)


@cli.group()
def dev() -> None:
    """Development helpers."""


@dev.command("info")
@click.argument("module")
@click.option("--open", "open_doc", is_flag=True, help="Open the primary doc with $EDITOR or code.")
def dev_info(module: str, open_doc: bool) -> None:
    """Print module ownership, docs, tests, deploy and log hints."""
    root = shell.repo_root()
    try:
        info = get_module(module)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    print(f"Module: {info.key} — {info.title}")
    print("────────────────────────")
    docs = existing_docs(info, root)
    if docs:
        print("Architecture / references:")
        for doc in docs:
            print(f"  {doc}")
    else:
        print("Architecture: not yet consolidated")
        print("References:")
        for doc in info.docs:
            print(f"  {doc}")

    print("\nPackages:")
    if info.packages:
        for pkg in info.packages:
            print(f"  {pkg}")
    else:
        print("  none (non-ROS package)")

    print("\nLocal tests:")
    for test in info.tests:
        print(f"  {test}")

    print("\nDeploy:")
    print(f"  pawai jetson deploy --module {info.key}")

    print("\nLogs:")
    print(f"  pawai logs {info.key}")
    for target in info.logs:
        print(f"  → {target}")

    print("\nGo2 access:")
    print(f"  {info.go2_access}")

    if info.notes:
        print("\nNotes:")
        for note in info.notes:
            print(f"  - {note}")

    if open_doc:
        if not docs:
            raise click.ClickException("no existing doc path to open")
        target = root / docs[0]
        editor = os.getenv("EDITOR") or shutil.which("code")
        if not editor:
            print(f"\nOpen manually: {target}")
            return
        code = shell.stream([editor, str(target)])
        raise SystemExit(code)


@cli.group()
def jetson() -> None:
    """Jetson deployment helpers."""


def _do_rsync_and_build(root: Path, packages: list[str], no_sync: bool, no_build: bool,
                         module_key: str) -> tuple[int, str]:
    """Perform rsync and/or colcon build. Returns (exit_code, sync_method)."""
    if not no_sync:
        sync_once = Path.home() / "sync"
        if sync_once.exists() and os.access(sync_once, os.X_OK):
            print("Sync: ~/sync once")
            code = shell.stream([str(sync_once), "once"], cwd=root)
            if code != 0:
                return code, "sync-once"
            sync_method = "sync-once"
        else:
            print("Sync: rsync whole repo")
            dest = f"{shell.jetson_host()}:{shell.jetson_repo().rstrip('/')}/"
            argv = [
                "rsync",
                "-az",
                "--delete",
                "--exclude=.git/",
                "--exclude=build/",
                "--exclude=install/",
                "--exclude=log/",
                "--exclude=__pycache__/",
                "--exclude=.pytest_cache/",
                "--exclude=.venv/",
                "--exclude=node_modules/",
                "--exclude=.next/",
                "--exclude=.ruff_cache/",
                "--exclude=.mypy_cache/",
                "--exclude=.DS_Store",
                f"{root}/",
                dest,
            ]
            code = shell.stream(argv)
            if code != 0:
                return code, "rsync"
            sync_method = "rsync"
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


@jetson.command()
@click.option("--module", "module_name", help="Module to deploy.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompts.")
@click.option("--no-build", is_flag=True, help="Sync only; skip colcon build.")
@click.option("--no-sync", is_flag=True, help="Build only; skip sync.")
@click.option("--all", "all_modules", is_flag=True, help="Build all module packages.")
@click.option("--force", is_flag=True, help="Deploy even if another user is in active demo.")
def deploy(module_name: str, yes: bool, no_build: bool, no_sync: bool, all_modules: bool,
           force: bool) -> None:
    """Sync whole repo to Jetson and build module package(s)."""
    from .lock import Lock, is_own_lock

    root = shell.repo_root()
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    if all_modules:
        packages = sorted({pkg for info in MODULES.values() for pkg in info.packages})
        module_key = "all"
    else:
        if not module_name:
            raise click.UsageError("--module is required unless --all is set")
        try:
            info = get_module(module_name)
        except KeyError as exc:
            raise click.ClickException(str(exc)) from exc
        packages = list(info.packages)
        module_key = info.key
        if not packages and not no_build:
            raise click.ClickException(f"module {info.key} has no colcon package; use --no-build")

    # Lock-aware collision check
    existing = Lock.read()
    if existing is not None and existing.state == "running" \
            and not is_own_lock(existing, user, host) and not force:
        click.echo(f"⚠ {existing.user}@{existing.host} is running a demo on branch={existing.branch}.")
        click.echo("Deploying now may overwrite their install.")
        if yes:
            click.echo("`-y` does not override another user's demo. Use --force.")
            sys.exit(2)
        answer = click.prompt("Continue? [force/cancel]", default="cancel")
        if not answer.lower().startswith("f"):
            sys.exit(0)

    st = print_status(short=True)
    if st.has_demo and not yes and (existing is None or is_own_lock(existing, user, host)):
        if not click.confirm("Demo session is running. Deploy may require restart. Continue?", default=False):
            raise click.Abort()

    code, sync_method = _do_rsync_and_build(root=root, packages=packages, no_sync=no_sync,
                                             no_build=no_build, module_key=module_key)
    if code != 0:
        raise click.ClickException(f"deploy failed with exit code {code}")

    payload = _build_last_deploy_payload(module=module_key, packages=packages,
                                         sync_method=sync_method)
    # Keep legacy fields for backwards compat
    payload["user"] = shell.local_identity()
    payload["ts"] = payload["when"]
    remote_json = json.dumps(payload, ensure_ascii=False)
    shell.run_remote(
        f"cd {shell.jetson_repo()} && printf '%s\\n' {json.dumps(remote_json)} > .pawai-last-deploy",
        timeout=8,
    )
    print("Deploy complete.")
    if st.has_demo:
        print("Tip: restart demo when safe: pawai demo stop && pawai demo start")


@cli.group()
def demo() -> None:
    """Demo lane controls."""


def _invoke_start_sh(no_studio: bool, brain_only: bool) -> int:
    """Thin wrapper for tests — calls existing start.sh path."""
    args = ["bash", ".claude/skills/brain-studio-lane/scripts/start.sh"]
    if brain_only:
        args.append("minimal")
    elif no_studio:
        args.append("full")
    else:
        args.append("demo")
    return shell.stream(args, cwd=shell.repo_root())


def _invoke_cleanup_sh() -> int:
    return shell.stream(
        ["bash", ".claude/skills/brain-studio-lane/scripts/cleanup.sh"],
        cwd=shell.repo_root(),
    )


def _current_branch() -> str:
    r = shell.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else "unknown"


def _current_sha_short() -> str:
    r = shell.run(["git", "rev-parse", "--short", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else ""


@demo.command("start")
@click.option("--no-studio", is_flag=True, help="Start full mode without local Studio overlay.")
@click.option("--brain-only", is_flag=True, help="Start minimal brain stack only.")
@click.option("-y", "yes", is_flag=True, help="Skip ordinary confirmation prompts (does NOT override another user's lock).")
@click.option("--force", "force", is_flag=True, help="Take over another user's demo lock.")
def demo_start(no_studio: bool, brain_only: bool, yes: bool, force: bool) -> None:
    """Start brain-studio-lane."""
    from .lock import Lock, is_stale, is_own_lock

    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()
    branch = _current_branch()
    sha = _current_sha_short()

    existing = Lock.read()
    if existing is not None:
        if is_own_lock(existing, user, host):
            click.echo(f"Existing lock is yours ({existing.state}). Restarting demo.")
            Lock.release()
        else:
            stale = is_stale(existing)
            if stale:
                click.echo(f"⚠ Stale {stale} lock from {existing.user} (age exceeds threshold).")
            else:
                click.echo(f"Another user is in demo: {existing.user}@{existing.host} "
                           f"branch={existing.branch} state={existing.state}")
            if not force:
                if yes:
                    click.echo("`-y` does not override another user's lock. Use --force to take over.")
                    sys.exit(2)
                answer = click.prompt("Take over? [force/cancel]", default="cancel")
                if not answer.lower().startswith("f"):
                    sys.exit(0)
            click.echo(f"--force: clearing {existing.user}'s lock")
            Lock.release()

    # Acquire starting lock
    lk = Lock.acquire(user=user, host=host, branch=branch, sha=sha, state="starting")
    if lk is None:
        click.echo("Failed to acquire lock after 3 retries — flock held by another process or remote SSH issue. Investigate before retrying.")
        sys.exit(2)

    rc = _invoke_start_sh(no_studio=no_studio, brain_only=brain_only)
    if rc != 0:
        click.echo("Demo start failed — releasing lock.")
        Lock.release()
        sys.exit(rc)

    lk.transition_to("running")
    click.echo(f"✓ Demo running (lock owner: {user}@{host})")


@demo.command("stop")
@click.option("--force", is_flag=True, help="Stop another user's demo and release their lock.")
def demo_stop(force: bool) -> None:
    """Stop brain-studio-lane."""
    from .lock import Lock, is_own_lock
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    existing = Lock.read()
    if existing is None:
        click.echo("No demo lock present.")
        rc = _invoke_cleanup_sh()
        sys.exit(rc)

    if not is_own_lock(existing, user, host) and not force:
        click.echo(f"Lock is owned by {existing.user}@{existing.host}. "
                   f"Use --force to stop their demo.")
        sys.exit(2)

    rc = _invoke_cleanup_sh()
    Lock.release()
    sys.exit(rc)


@cli.command()
@click.argument("module")
@click.option("--lines", default=500, show_default=True, help="Lines to capture from tmux pane.")
def logs(module: str, lines: int) -> None:
    """Capture Jetson tmux logs for a module."""
    if module == "all":
        targets = [
            "demo:face",
            "demo:vision",
            "demo:object",
            "demo:asr",
            "demo:tts",
            "demo:llm",
            "demo:executive",
            "demo:gateway",
        ]
    else:
        try:
            targets = list(get_module(module).logs)
        except KeyError as exc:
            raise click.ClickException(str(exc)) from exc

    for target in targets:
        if target.startswith("local:"):
            path = target.removeprefix("local:")
            print(f"===== {target} =====")
            res = shell.run(["tail", "-n", str(lines), path], timeout=5)
            print(res.stdout or res.stderr)
            continue
        print(f"===== {target} =====")
        cmd = f"tmux capture-pane -p -t {target} -S -{int(lines)} 2>/dev/null || true"
        res = shell.run_remote(cmd, timeout=12)
        print(res.stdout.rstrip() or "(no output)")

    print("\nTip: interactive follow:")
    print(f"  ssh {shell.jetson_host()} 'tmux attach -t demo'")


if __name__ == "__main__":
    cli()
