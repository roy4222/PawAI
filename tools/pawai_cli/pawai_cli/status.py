from __future__ import annotations

import json
from dataclasses import dataclass

from . import shell
from .lock import Lock, is_stale


def _read_last_deploy_remote() -> dict | None:
    remote_path = f"{shell.jetson_repo()}/.pawai-last-deploy"
    result = shell.run_remote(
        f"cat {remote_path} 2>/dev/null",
        timeout=5,
    )
    if not result.ok or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _current_branch() -> str:
    r = shell.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else "unknown"


@dataclass
class LiveStatus:
    tmux: str
    ros_nodes: str
    git: str
    last_deploy: str
    reachable: bool

    @property
    def has_demo(self) -> bool:
        return any(line.startswith("demo:") for line in self.tmux.splitlines())


def collect() -> LiveStatus:
    tmux = shell.run_remote("tmux ls 2>/dev/null || true", timeout=10)
    ros = shell.run_remote(
        "source /opt/ros/humble/setup.zsh 2>/dev/null; "
        f"source {shell.jetson_repo()}/install/setup.zsh 2>/dev/null; "
        "ros2 node list 2>/dev/null || true",
        timeout=12,
    )
    git = shell.run_remote(
        f"cd {shell.jetson_repo()} && "
        "printf 'log=' && git log -1 --format='%h|%ci|%s' 2>/dev/null && "
        "printf 'status=' && git status --short --branch 2>/dev/null",
        timeout=12,
    )
    last = shell.run_remote(
        f"cat {shell.jetson_repo()}/.pawai-last-deploy 2>/dev/null || true",
        timeout=8,
    )
    reachable = tmux.code != 127 and tmux.code != 255
    return LiveStatus(tmux.stdout.strip(), ros.stdout.strip(), git.stdout.strip(), last.stdout.strip(), reachable)


def print_status(short: bool = False) -> LiveStatus:
    st = collect()
    host = shell.jetson_host()
    print(f"PawAI live status @ {host}")
    print("────────────────────────────")
    if not st.reachable:
        print("✗ Jetson unreachable over SSH")
        return st

    print("tmux sessions:")
    if st.tmux:
        for line in st.tmux.splitlines():
            print(f"  {line}")
    else:
        print("  none")

    if not short:
        nodes = [line for line in st.ros_nodes.splitlines() if line.strip()]
        print(f"\nROS nodes ({len(nodes)}):")
        if nodes:
            for node in nodes[:14]:
                print(f"  {node}")
            if len(nodes) > 14:
                print(f"  ... +{len(nodes) - 14} more")
        else:
            print("  none")

        print("\nJetson git:")
        if st.git:
            print(indent(st.git, "  "))
        else:
            print("  unavailable")

    print("\nLast deploy:")
    if st.last_deploy:
        try:
            data = json.loads(st.last_deploy)
            print(f"  {data.get('ts')} {data.get('user')} module={data.get('module')} sha={data.get('git_sha')}")
        except json.JSONDecodeError:
            print(indent(st.last_deploy, "  "))
    else:
        print("  none")

    heads = []
    if st.has_demo:
        heads.append("demo session is running; deploy may require restart.")
    if st.last_deploy:
        try:
            data = json.loads(st.last_deploy)
            if data.get("user") and data.get("user") != shell.local_identity():
                heads.append(f"last deploy was by {data.get('user')}; coordinate before overwriting.")
        except json.JSONDecodeError:
            pass
    if heads:
        print("\nHeads-up:")
        for item in heads:
            print(f"  ⚠ {item}")

    # Demo lock
    lk = Lock.read()
    print("\nDemo lock:")
    if lk is None:
        print("  (none)")
    else:
        stale = is_stale(lk)
        suffix = f" [STALE {stale}]" if stale else ""
        print(f"  owner: {lk.user}@{lk.host}")
        print(f"  branch: {lk.branch}")
        print(f"  state: {lk.state}{suffix}")
        print(f"  started: {lk.start_time}")

    # Branch mismatch
    last = _read_last_deploy_remote()
    if last is not None:
        local_branch = _current_branch()
        install_branch = last.get("branch", "?")
        dirty_flag = " (dirty)" if last.get("dirty") else ""
        print("\nBranch state:")
        print(f"  local:   {local_branch}")
        print(f"  install: {install_branch}{dirty_flag}")
        if local_branch != install_branch:
            print(f"  ⚠ MISMATCH — running install is from {install_branch}, you have {local_branch} checked out")

    return st


def indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())
