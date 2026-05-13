# PawAI CLI — Collaboration Console Umbrella Design

**Written on**: 2026-05-13
**Author**: Roy + Claude Code brainstorm (3 parallel research agents: local audit, industry CLI patterns, platform strategy)
**Status**: design approved, Phase 1 implementation pending
**Phase 1 deadline**: 2026-05-16 (5/18 demo 前留 5/17 buffer day)
**Supersedes scope of**: `2026-05-12-pawai-cli-team-prep-design.md` (L1-L3 incremental → this umbrella reframes pawai CLI as a **Jetson on-site collaboration console**)

---

## Current State

- **PawAI CLI v0.1.0** lives at `tools/pawai_cli/`, 1586 LOC across 7 files (`main.py` 843 / `lock.py` 121 / `status.py` 229 / `network.py` 101 / `modules.py` 155 / `cache.py` 35 / `shell.py` 99).
- **Existing commands**: `doctor` / `status` / `dev` / `jetson deploy` / `demo start|stop` / `logs` / `docs` / `contract check`.
- **Half-built primitives**: `lock.py` has `Lock.acquire/read/release/transition_to + is_own_lock + is_stale`. `demo stop` does not yet wire own-stale auto-reclaim. `status.py` already prints lock + branch mismatch + nav-capability block.
- **Critical fix landed today (5/13 morning)**: `shell.py` `subprocess.run(..., encoding="utf-8", errors="replace")` — Windows cp950 decode crash gone (was blocking teammate `pawai doctor` on Windows).
- **Today's session validated**: deploy + demo start + lock acquire + clean stop work end-to-end after Jetson Wi-Fi recovery. Real friction lives in the seams.

---

## Context

PawAI CLI began as a one-developer (Roy) tool. From 2026-05-13 it serves **5 people sharing 1 Jetson Orin Nano + 1 Go2 Pro** via Tailscale + SSH. The 2026-05-13 morning session surfaced a recurring pattern: **every failure is in a seam, not in a feature**.

Seams that bit today or are predicted to bite next:

| # | Seam | Today's symptom |
|---|------|----------------|
| 1 | **Mac → Tailscale → Jetson Wi-Fi → Tailscale daemon** | Jetson 16h offline; doctor red lights cannot say "Tailscale `logged out`" vs "no internet" vs "daemon dead". Roy reproduced by trial-and-error. |
| 2 | **Lock state vs reality** | Yesterday's `running` lock survived overnight; `pawai demo stop` would not clear own stale lock without `--force` (CLI permission system flagged --force as "stealing"). |
| 3 | **Cross-platform shell** | Teammate on Windows hit `UnicodeDecodeError: cp950 codec` on `pawai doctor`; Python 3.13 + zh_TW locale. Fixed in `shell.py`. |
| 4 | **New teammate onboarding** | New Mac user `yamiko` got 2 blocking + 1 warning on first `pawai doctor`: no Tailscale share, no `Host jetson` SSH config, no frontend `.env.local`. Each fix was a separate message exchange. |
| 5 | **Status truthfulness** | After `pawai demo stop`, `ros2 node list` from `pawai status` showed 20+ "running" nodes from ros2 daemon cache; actual processes were gone. Cannot trust status output. |
| 6 | **Hardcoded host** | `.claude/skills/brain-studio-lane/scripts/healthcheck.sh` SSHes to literal `jetson-nano` — not `$JETSON_HOST`. Fails for any teammate using a different SSH alias. |
| 7 | **Deploy state lag** | `Last deploy` timestamp printed by `pawai status` was 24h stale until next `pawai status` invocation. CLI does not refresh state on deploy. |
| 8 | **rsync noise & risk** | rsync `cannot delete non-empty directory: ros-mcp-server/...` warnings on every deploy; `.env.local` is **not in rsync exclude list** → secret can be pushed to Jetson on accident. |
| 9 | **start.sh `pkill -f "next.*dev"`** | `brain-studio-lane/scripts/start.sh` kills any process whose argv matches `next.*dev` — would terminate teammate's unrelated Next.js project. |
| 10 | **start.sh hardcoded `100.83.109.89`** | Studio frontend URL hardcoded; if Jetson Tailscale IP ever rotates (Tailscale generally pins IPs but not contractually) the demo breaks silently. |

These seams have a common shape: **the CLI knows enough to give the right answer, but doesn't**. The redesign promotes `pawai` from **tool collection** → **collaboration console**: every failure must surface (a) who, (b) what state, (c) the exact next command. Industry patterns (Terraform state locking, Flutter doctor, kubectl conventions, GitHub CLI JSON) inform the contract.

---

## Goals

1. **No silent collisions**: every `demo start` / `demo stop` / `jetson deploy` checks lock first; conflicts produce an actionable message naming the holder, age, branch, and the exact escape hatch command.
2. **Every red light carries its fix**: `pawai doctor` and lock conflicts always print a runnable next-step command, including platform-aware variants (`brew install …` vs `apt install …` vs `wsl —install`).
3. **Cross-platform = macOS + Linux native + WSL2 Ubuntu**. Windows PowerShell/CMD/Git Bash, WSL1, and repos under `/mnt/c` are explicitly rejected with a one-screen migration guide.
4. **Status is truth**: `pawai status` never prints stale `ros2 node list` cache; `Last deploy` updates immediately after a successful deploy.
5. **Phase 1 ships by 5/16**: 10 named items, each independently committable and reversible.

---

## Non-Goals (in this umbrella; some belong to later phases)

- **Heartbeat lock** — explicitly rejected per D1. Stateless TTL only.
- **Native Windows (no WSL)** — explicitly rejected per D2. `ssh/rsync/flock/tmux/bash` dependencies make native Windows a tarpit.
- **Lock UI in Studio frontend** — out of scope; CLI is canonical.
- **Auto-fix every doctor red light** — only safe automations (e.g., write Tailscale IP to `.env.local`); destructive fixes always require explicit confirm.
- **Cloud-hosted audit log** — local file `.pawai-audit.log` on Jetson is sufficient for v1; ELK / S3 not in scope.
- **`pawai` Python package on PyPI** — keep editable install from repo.

---

## Architecture Invariants (Cross-Phase)

These five invariants are load-bearing and must hold across all 4 phases. Any phase plan that violates one of these must justify the deviation explicitly.

### I1. Platform Policy

```
✓ macOS native           (darwin)
✓ Linux native           (linux, /proc/version no "microsoft")
✓ WSL2 + Ubuntu          (/proc/version contains "microsoft" + WSL_DISTRO_NAME set + WSL interop available)
✗ WSL1                   (kernel version < 4.x or missing WSL2 markers)
✗ Windows native         (PowerShell / CMD / Git Bash without WSL)
✗ Repo path under /mnt/c (WSL2 but on Windows filesystem → 10x slower I/O, breaks rsync semantics)
```

Detection lives in `tools/pawai_cli/pawai_cli/platform.py` (new file, ~50 LOC). Every command entry point calls `platform.assert_supported()` before doing work. Failure prints:

```text
✗ Platform: Windows native unsupported
  PawAI CLI requires macOS, Linux, or WSL2 Ubuntu.
  → Install WSL2: wsl --install -d Ubuntu
  → Move repo: git clone <url> ~/elder_and_dog   (NOT under /mnt/c)
  → Reopen terminal in: Windows Terminal → Ubuntu
  See: docs/pawai_cli/platform-policy.md
```

`pawai doctor` makes platform check the very first item, before anything else.

### I2. Lock Schema (Stateless TTL, no Heartbeat)

`.pawai-demo-lock` on Jetson, JSON, single source of truth:

```json
{
  "schema_version": 1,
  "lock_id": "01J2VXR3K4HZQ8M6N7P9B5W2DA",
  "operation": "demo_start",
  "state": "starting",
  "user": "lubaiyu",
  "host": "Roy422deMacBook-Pro.local",
  "branch": "main",
  "sha": "d4cc759",
  "lane": "brain",
  "started_at": "2026-05-13T05:40:32.122Z",
  "expires_at": "2026-05-13T09:40:32.122Z",
  "ttl_seconds": 14400,
  "reason": null
}
```

**Field semantics**:
- `schema_version`: integer, current = 1. Future schema bumps must include migration shim.
- `lock_id`: ULID (lexicographically sortable, timestamp-prefixed). Required by `--force --lock-id <id>` per Terraform pattern.
- `operation`: enum `demo_start | deploy | demo_stop`. Drives which other operations may proceed concurrently (none today; future "deploy may proceed while demo running" hook stays open).
- `state`: enum `starting | running | stopping | deploying`. Transitions are CLI-driven (no background process).
- `lane`: `brain` | `nav_capability` (already in v0.1.0 schema).
- `expires_at` = `started_at + ttl_seconds`, stored explicitly so any reader can decide stale without timezone math.
- `reason`: string, **required** only when acquiring via `--force` over another user's lock (audit field).

**TTL by state**:
| state | ttl | auto-reclaim by next acquire? |
|-------|-----|-------------------------------|
| `starting` | 10 min | ✓ |
| `deploying` | 10 min | ✓ |
| `stopping` | 5 min | ✓ |
| `running` | 4 h | ✗ — warn only, never auto-clear; manual `pawai lock reclaim` (own) or `--force --reason` (other's) |

**Stale handling**:
- "Stale" = `now > expires_at`.
- For `starting/deploying/stopping`: next `acquire` call writes audit log entry `auto_reclaimed_stale=<lock_id>` and proceeds.
- For `running`: `acquire` returns `STALE_RUNNING_LOCK` error with the holder identity; caller must opt in via `pawai lock reclaim` (own) or `--force --reason "..."`.

**Audit log**: `$JETSON_REPO/.pawai-audit.log`, append-only JSONL, one line per non-trivial lock event (`acquire / release / force / reclaim / auto_reclaim_stale`). Rotation deferred to Phase 4.

### I3. Output Contract

Every command supports three output modes:

- **Default (terminal)**: human-readable, color-aware (respect `NO_COLOR=1` env per no-color.org), uses `✓/⚠/✗` glyphs.
- **`--json`**: stable schema per command, documented in `docs/pawai_cli/json-schemas.md`. Adds `schema_version` top-level. **Phase 4 deliverable; Phase 1 does not ship any `--json` output.**
- **`--quiet`**: only error output, exit code is canonical. Suitable for CI / scripts.

**Exit code convention** (kubectl-style):
- `0` success
- `1` general failure (preserved from current behaviour)
- `2` usage error (click default)
- `10` platform check failed
- `11` lock conflict (another user)
- `12` lock conflict (own stale running; need reclaim)
- `13` Jetson unreachable
- `14` Go2 unreachable (when expected)

Existing commands keep exit `1` until Phase 4 cleanup.

### I4. Config Precedence

For any tunable, precedence (highest wins):
```
1. CLI flag                         (e.g., --jetson-host)
2. Environment variable             (e.g., JETSON_HOST)
3. .env.local                       (parsed at CLI entry)
4. Repo default in pawai_cli/defaults.py
```

This already mostly holds; explicit documentation in `defaults.py` is Phase 2 deliverable.

### I5. Redaction Whitelist

Secrets that **must never** appear in CLI output, logs, debug bundle, or rsync target list:
```
OPENROUTER_KEY, OPENROUTER_API_KEY
TAILSCALE_AUTHKEY
ANTHROPIC_API_KEY
OPENAI_API_KEY
HF_TOKEN
*_PASSWORD, *_SECRET, *_TOKEN  (env name glob)
.env, .env.local                (file contents)
~/.ssh/*                        (SSH keys)
```

Single shared redactor at `pawai_cli/redact.py`. Phase 4 debug bundle uses this; Phase 1 only requires `.env.local` in rsync exclude.

---

## Phase Plan

Each phase is independently shippable with its own writing-plans-generated implementation plan. The umbrella spec is the cross-phase contract.

### Phase 1 — On-site Firefighting (deadline 2026-05-16, ~2 days)

11 items (item 0 = platform gate foundation, items 1-10 = today's seam bugs). None require schema migration; all are forward-compatible with later phases.

| # | Item | Files | Effort | Validates |
|---|------|-------|--------|-----------|
| 0 | New `pawai_cli/platform.py` (~50 LOC) implementing I1 detection (`assert_supported()`); wire as first call in every command entry point; add doctor section "Platform: …" as item #1 in doctor output. Unit tests for the 5 detection branches (Darwin / Linux native / WSL2 / WSL1 / Windows native) + `/mnt/c` path check. | new `pawai_cli/platform.py`, `main.py` entry guards, `tests/test_platform.py` | 1.5 h | Foundational invariant; prevents future cp950-class platform bugs from landing |
| 1 | `doctor` Gateway severity wires `Lock.read().state`: if `running` lock present and 8080 down → FAIL (not SKIP) | `main.py:248` (gateway_8080_status), `main.py:doctor()` | 30 min | Today's `Gateway 8080: SKIP (no demo running)` mis-state |
| 2 | rsync exclude `.env`, `.env.*`, `.env.local`, `.ssh/` from deploy. Home-dir SSH keys are outside repo scope (rsync only sees the repo tree); pattern is repo-relative on purpose. | `main.py:469` (jetson_deploy rsync args), or wrapper script | 20 min | Prevents secret leak to Jetson |
| 3 | `pawai demo start` propagates `JETSON_TAILSCALE_IP` → studio frontend, no hardcoded fallback | `brain-studio-lane/scripts/start.sh`, `main.py:demo_start` | 1 h | Today's 5/12 night carry-over bug (start.sh hardcoded `100.83.109.89`) |
| 4 | `pawai demo start` forwards `TTS_PROVIDER` / `ASR_PROVIDER_ORDER` to Jetson tmux | `brain-studio-lane/scripts/start.sh` (env propagation block) | 1 h | 5/12 night offline-fallback verification bug |
| 5 | `pawai status --short` skips `ros2 node list` (avoid daemon cache lie) | `status.py:print_status`, plumb `--short` to skip ROS section | 45 min | Today's "20 phantom nodes after stop" |
| 6 | `Lock.release()` owner-aware + flock guard; `demo stop` auto-reclaims own stale lock without `--force` | `lock.py:99`, `main.py:demo_stop` | 1.5 h | Today's `--force` permission prompt friction |
| 7 | `network.py:find_jetson_peer` treats Tailscale `online=false` as FAIL, not OK | `network.py:41`, doctor Tailscale section | 30 min | Today's "active; offline 16h" mis-state |
| 8 | New `pawai health brain` command wrapping current `healthcheck.sh`, **reads `$JETSON_HOST`** not hardcoded | new subcommand in `main.py`, fix `healthcheck.sh:6` | 1 h | Today's `jetson-nano` hardcode bug |
| 9 | Docs drift fix: `docs/runbook/mac-migration-setup.md` says CLI lacks hard lock; outdated | `docs/runbook/mac-migration-setup.md`, plus `docs/pawai_cli/team-onboarding.md` cross-ref | 30 min | Prevents teammate confusion |
| 10 | `start.sh` replaces `pkill -f "next.*dev"` with PID-file-only kill | `brain-studio-lane/scripts/start.sh`, frontend launcher writes pid | 1 h | Teammate's unrelated Next.js projects survive |

**Phase 1 explicit non-items (deferred to later phases)**:
- Lock audit log writing (schema field exists, writer in Phase 2)
- `pawai lock {status,reclaim,force}` subcommands (Phase 2)
- `--json` output for everything (Phase 4)
- `pawai net` / `pawai setup` (Phase 3)
- `pawai debug bundle` (Phase 4)

Platform gate is item 0 above — explicitly budgeted, not silently added.

### Phase 2 — Multi-Person Collaboration Formalization (~3-4 days, after Phase 1)

- Lock schema migration to v1 (current schema → adds `lock_id`, `operation`, `expires_at`, `ttl_seconds`, `reason`).
- `pawai lock {status, release, reclaim, force --reason "..." [--lock-id]}` subcommands.
- Audit log writer at `$JETSON_REPO/.pawai-audit.log` (per Open Question #1 default; on current Jetson resolves to `/home/jetson/elder_and_dog/.pawai-audit.log`).
- `pawai deploy plan --module <name>`: dry-run preview (local sha/branch/dirty, Jetson sha/branch, package list, build needed?, demo lock owner).
- Branch mismatch in deploy → require explicit `--allow-mismatch` confirm.

### Phase 3 — Onboarding & Network Subcommands (~3 days)

- `pawai setup` interactive wizard (Tailscale share check → SSH config gen → `.env.local` template → frontend env → first doctor pass).
- `pawai net {status, explain, fix-route, wifi}`.
  - `status`: layered diagnostic (Mac → Tailscale → SSH → Jetson route → Go2).
  - `explain`: human prose summary of what's broken and what to do.
  - `fix-route`: on Jetson, lower Wi-Fi metric so Go2 wired never becomes default.
  - `wifi`: show Jetson SSID/IP, suggest `nmcli` snippets (no password storage).
- Platform-aware install hints in setup (`brew install gh` vs `sudo apt install gh` vs WSL2-equivalent).

### Phase 4 — Debug Observability (~2 days)

- `pawai status --json`, `pawai doctor --json`: stable schema, version-tagged.
- `pawai logs --since <duration> --follow <module>`: tmux pane tail + colcon log tail.
- `pawai debug bundle [--since 30m]`: zip + manifest of doctor, status, lock, last-deploy, recent commands, tmux captures, gateway health, network probes — **redacted via I5**.
- `pawai wait demo --for gateway-ready --timeout 60s`: CI-friendly wait predicate.
- Exit code mapping cleanup (I3).

---

## Phase 1 Implementation Order (for writing-plans)

Suggested order minimizes lock conflicts during landing:

1. **Item 0** — platform gate (foundation; everything below assumes it's in)
2. **Items 7, 1, 5** — pure detection bugs in doctor/status (small, surgical)
3. **Items 2, 3, 4** — deploy/start.sh changes (security + env propagation)
4. **Items 6, 8, 10** — lock + healthcheck + start.sh kill (touches lock.py, healthcheck.sh)
5. **Item 9** — docs drift

Each item lands in its own commit. Phase 1 estimate: **~9-10 hours total wall clock** (item 0 = 1.5h foundation + items 1-10 = ~8h), fits 2 working days with testing & teammate verification.

---

## Open Questions

1. **Lock audit log file location**: `$JETSON_REPO/.pawai-audit.log` vs `~/.pawai-audit.log` on Jetson. Repo-local survives Jetson reflash via git ignore; home-dir survives repo deletion. Phase 2 decides; **default current: repo-local**.
2. **`reason` field in non-force acquire**: should `pawai demo start --reason "demo for 教授"` be allowed even without conflict, for richer audit log? Phase 2 design call.
3. **`pawai version --all` semantics** — Phase 4. Open: how to surface ROS package build timestamp without SSH overhead?
4. **WSL2 + Linux co-existence under same `pawai`**: when WSL2 user `cd /mnt/c/...`, do we just block, or offer migration command? Phase 1: block with message. Phase 3: setup wizard can `wsl --shutdown && wsl --import ...` if user requests.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Lock schema v1 migration breaks a teammate mid-demo | low | Phase 2 reads either schema_version absent (old) or `==1` (new); old schema is upgraded in-place on next acquire |
| Platform gate false-positives on weird Linux distros | medium | Detection uses `/proc/version` + `WSL_DISTRO_NAME` + `uname`; conservatively defaults to "supported" if signals contradict |
| Phase 1 items 6+10 (lock + start.sh) collide during landing | medium | Order in §"Implementation Order" above; each PR < 200 LOC |
| rsync excluding `.env.local` breaks a teammate who expected sync | low | `.env.local` was never meant to deploy; document in Phase 1 item 9 docs drift |
| `pawai health brain` name clashes with future `pawai health` umbrella command | low | Phase 1 reserves `pawai health <subsystem>` namespace; brain is first occupant |

---

## References

**Industry patterns informing design**:
- Terraform state locking + force-unlock: https://developer.hashicorp.com/terraform/language/state/locking
- Kubernetes Lease object pattern: https://kubernetes.io/docs/concepts/architecture/leases/
- Flutter doctor `[✓]/[!]/[✗]` + fix instructions: https://docs.flutter.dev/reference/flutter-cli
- kubectl exit code conventions: https://kubernetes.io/docs/reference/kubectl/conventions/
- GitHub CLI JSON output: https://cli.github.com/manual/gh_help_formatting
- AWS CLI troubleshooting/wizard: https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-troubleshooting.html
- Microsoft WSL filesystem performance: https://learn.microsoft.com/en-us/windows/wsl/filesystems
- no-color.org `NO_COLOR` env var: https://no-color.org

**Local sources**:
- Today's session full transcript (Jetson Wi-Fi recovery + 10 seam bugs surfaced)
- Industry CLI patterns research report: `docs/research/2026-05-13-cli-ux-best-practices.md` (608 lines, covers Terraform locking / Flutter doctor / WSL detection / Click vs Typer / debug bundle redaction)
- Local CLI audit report (from parallel Explore agent) — captured in §Context tables; not separately filed
- Prior MVP spec: `docs/superpowers/specs/2026-05-12-pawai-cli-mvp-design.md`
- Prior team-prep spec: `docs/superpowers/specs/2026-05-12-pawai-cli-team-prep-design.md`
- Current CLI source: `tools/pawai_cli/pawai_cli/`

---

## Approval Gate

This umbrella spec must be approved before Phase 1 implementation plan is generated (via `writing-plans`).

After approval:
1. `writing-plans` produces `docs/superpowers/plans/2026-05-13-pawai-cli-phase1-plan.md` covering 10 items with task breakdown.
2. Phase 1 implementation begins; goal 2026-05-16 EOD.
3. Phase 2 spec is written separately (refines lock schema v1, audit log, deploy plan) when Phase 1 is ~80% done.
4. Phases 3 and 4 spec'd when their predecessors are stable.
