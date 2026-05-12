# PawAI CLI Team-Development Prep — Design

**Written on**: 2026-05-12 (for 2026-05-13 team development day)
**Author**: Roy + Claude Code brainstorm
**Status**: design approved, implementation pending
**Successor of**: `2026-05-12-pawai-cli-mvp-design.md` (MVP shipped; this adds team coordination + diagnostics)

---

## Current State

- **`pawai-cli` skill**: implemented as conservative self-discovery skill at `.claude/skills/pawai-cli/` (SKILL.md + 3 references + 1 script). Skill instructs AI to verify flags via `pawai --help` rather than assuming designed-but-unimplemented behavior.
- **`.gitignore`**: patched so `.claude/skills/pawai-cli/**` is no longer swallowed by the blanket `.claude/skills/` ignore.
- **CLI L1 / L2 / L3 changes**: design approved tonight, **not implemented yet**.
- **`docs/pawai_cli/` doc updates**: design approved, **pending**.
- **`.env.local.example` IP change**: design approved, **pending**.

---

## Context

Tomorrow (2026-05-13) is the first team-development day after Go2 leaves Roy's home. Five people will share one Jetson + one Go2, each on their own git branch developing their assigned module (face / gesture / pose / object / nav / brain / studio / speech). Network changes (Jetson moves from home Wi-Fi to school network) and shared-resource collisions (two people running `pawai demo start` simultaneously) are the predicted top friction sources.

PawAI CLI MVP already exists with `doctor` / `status` / `dev info` / `jetson deploy` / `demo start|stop` / `logs`. It is insufficient for five-person concurrent use:

- No demo lock → silent overwrite of someone else's running install
- `.pawai-last-deploy` lacks branch / dirty / sha-full → unclear what is actually running
- `doctor` does not auto-detect Tailscale-shared Jetson, does not probe Go2 from Jetson, does not surface network topology
- `.env.local.example` hardcodes the home Tailscale IP `100.83.109.89`
- No standalone team-onboarding doc

The single most likely failure mode tomorrow morning: a teammate accepts the Tailscale share link, runs `pawai doctor`, and sees a red light they cannot interpret. This design makes that path green.

---

## Goals

1. **Any teammate can go from "share link accepted" to "first successful `pawai demo start`" in 30 minutes** with no Roy intervention.
2. **No accidental cross-user damage**: deploying while teammate B has demo running must prompt, not silently overwrite.
3. **Network problems are self-diagnostic**: `pawai doctor` output points to the failing link in the chain (laptop → Tailscale → Jetson → Ethernet → Go2 → Gateway).
4. **CLI design changes do not destabilize MVP**: every layer (L1, L2, L3) ships as an independent commit testable in isolation.

---

## Non-Goals

- Reset / rollback automation (`pawai reset`) — too destructive for tonight's scope.
- Real OpenRouter live probe on default `doctor` — moved behind `--deep` to avoid 5× API calls per morning.
- ROS2 DDS topic cross-machine routing — teammates SSH into Jetson; no DDS tunneling needed.
- Mobile / responsive Studio UI parity — orthogonal.

---

## Architecture Decisions

### Demo Lock

- **Location**: `$JETSON_REPO/.pawai-demo-lock` (Jetson-side, single source of truth).
- **Format** (JSON):
  ```json
  {
    "user": "roy422",
    "host_machine": "Roy-MBP",
    "branch": "feat/face-improve",
    "sha": "abc1234",
    "start_time": "2026-05-13T08:30:00+08:00",
    "demo_mode": "full",
    "tmux_session": "demo",
    "state": "starting"
  }
  ```
- **State machine**: `starting` (acquired pre-launch) → `running` (after `start.sh` returns success) → deleted (on `demo stop` or launch failure).
- **Atomic write**: `flock -n /tmp/pawai-demo-lock.flock -c 'printf JSON > .tmp && mv .tmp .pawai-demo-lock'`. flock acquisition failure → retry up to 3× with 2s backoff, then surface error.
- **Stale policy**:
  - `state=starting` and `start_time > 10min ago` → prompt user to clear (likely failed startup).
  - `state=running` and `start_time > 4hr ago` → status flags `STALE` but **does not auto-delete**. Clearing requires `--force` or explicit user confirmation.

### `-y` versus `--force` semantic separation

| Flag | Effect | Cross-user? |
|---|---|---|
| `-y` | Skip ordinary confirmation prompts on your own operation | **No** — cannot take over another user's lock |
| `--force` | Take over or stop another user's demo / stale lock | **Yes** |

Combining the two is allowed but the lock-takeover trigger is `--force` only.

### `.pawai-last-deploy` schema extension

Current fields: `user`, `when`, `module`, `sha`, `sync_method`.

New fields:
- `deployed_by` (replaces / clarifies `user`)
- `deployed_from_host`
- `branch`
- `git_sha_full`
- `dirty` (true if `git status --porcelain` non-empty at deploy time)
- `packages` (resolved list, not just module alias)

Rationale: `rsync` excludes `.git/`, so Jetson git state does not reflect what was actually deployed. This file becomes the authoritative runtime provenance.

### Tailscale auto-detect

- `.env.local.example` change:
  ```diff
  - JETSON_TAILSCALE_IP=100.83.109.89
  + # JETSON_TAILSCALE_IP=
  + # leave blank — CLI auto-detects via `tailscale status` using JETSON_HOSTNAME_HINT
  + JETSON_HOSTNAME_HINT=jetson
  ```
- `pawai doctor` default behavior: detect, report; **do not mutate** `.env.local`.
- `pawai doctor --fix` behavior: prompt user, then write auto-detected IP into `.env.local`.
- Both root `.env.local` and `pawai-studio/frontend/.env.local` are checked for consistency.

### Tailscale sharing model

- **Only Jetson is shared**, not Go2. Go2 lives on the Jetson↔Go2 Ethernet link at `192.168.123.161` and is reached *through* Jetson.
- Sharing path: Tailscale console → Jetson node → Share → produce link → distribute to four teammates → each accepts on their own free Tailscale account.
- IP from teammate's view is **expected to be the same `100.83.109.89`** (Tailscale CGNAT is globally unique within Tailscale infrastructure under normal conditions). Treat this as the expected/current shared-node IP — **do not hardcode**. CLI must always resolve via `tailscale status` auto-detect to tolerate node re-creation, IP reallocation, or share-link reissue.
- ACL not required for share model (sharee sees only the shared node).

### Network topology check

`pawai doctor` adds a dedicated output block:

```
Network topology:
  local → Jetson Tailscale: OK 100.83.109.89 latency=12ms
  Jetson internet route:    OK wlan0
  Jetson Go2 link:          OK eth0 192.168.123.X
  Jetson → Go2 ping:        OK 192.168.123.161
  Gateway 8080:             SKIP (no demo running) | OK | FAIL
```

**Gateway 8080 severity rule**: this check is **INFO/SKIP by default** (no demo running is expected state, not a failure). It only escalates to **FAIL/red** when `pawai doctor --expect-demo` is passed *or* a lock file shows `state=running`. This prevents `doctor` from looking red before demo starts.

Each line maps to one diagnostic command run on the Jetson via SSH (see `docs/pawai_cli/troubleshooting.md` G/I/J chapters in implementation):

| Line | Command |
|---|---|
| local → Jetson Tailscale | `tailscale ping <ip>` from laptop |
| Jetson internet route | `ssh jetson 'ip route get 8.8.8.8'` → confirm not via Go2 ethernet |
| Jetson Go2 link | `ssh jetson 'ip -br addr | grep 192.168.123'` |
| Jetson → Go2 ping | `ssh jetson 'ping -c 1 -W 2 $ROBOT_IP'` |
| Gateway 8080 | `ssh jetson 'curl -fsS http://127.0.0.1:8080/health'` and laptop `curl http://$IP:8080/health` |

### Jetson-network-change failure modes covered

| Scenario | Detection | Hint |
|---|---|---|
| Jetson Ethernet stolen for school uplink | "Jetson internet route" shows `eth0` instead of `wlan0` | "Reconnect school network via Wi-Fi; Ethernet must stay on Go2" |
| Jetson Wi-Fi unable to associate | "local → Jetson Tailscale" fails or `tailscale ping` very high latency | "Reconnect Wi-Fi or wait 60s for Tailscale reconnect" |
| Tailscale transient reconnect | All Tailscale checks fail simultaneously | "Tailscale reconnecting, retry in 60s" |
| Go2 OTA pollution from school Wi-Fi | (Operational, not detectable) | runbook: never plug Go2 into Wi-Fi |

---

## CLI Layer Breakdown

### L1 — Connectivity (must-have, ~1.5–2hr)

Extend `pawai doctor` with new checks. **No new commands** in L1.

| Check | Default | `--deep` | `--fix` writes? |
|---|---|---|---|
| Tailscale daemon present | yes | yes | — |
| Tailscale finds Jetson peer | yes | yes | — |
| `.env.local` IP vs auto-detected IP | mismatch warning | mismatch warning | yes if mismatch |
| SSH alias works (with detected IP fallback) | yes | yes | — |
| Network topology block (5 lines above) | yes | yes | — |
| `OPENROUTER_KEY` presence | yes | yes | — |
| OpenRouter live test call | **no** | yes | — |
| Studio frontend `.env.local` consistency | yes | yes | yes if mismatch |

Added flags:
- `--fix` — prompt-then-write for resolvable inconsistencies.
- `--deep` — extra live network calls.
- `--cache 30` — cache result for 30s to avoid five teammates each waiting on SSH probes.

### L2 — Coordination (must-have, ~2–2.5hr)

| Command | Change |
|---|---|
| `pawai demo start` | Pre-acquire `starting` lock under flock; only flip to `running` after `start.sh` succeeds; revert on failure. Collision → prompt (wait / `--force` / cancel). |
| `pawai demo stop` | Default refuses to clear another user's lock; `--force` overrides. Stale `running` (>4h) flagged, not auto-deleted. |
| `pawai jetson deploy` | Read lock; prompt on collision; `--force` to override. `.pawai-last-deploy` writes new fields. |
| `pawai status` | New sections: demo-lock state + age, local vs install branch mismatch warning, network topology summary line. |

### L3 — Convenience (~1hr, can defer to morning)

| Command | Behavior |
|---|---|
| `pawai docs <module>` | Print or `$EDITOR`-open `docs/pawai-brain/architecture/0511/<module>/<module>.md`. Aliases: `onboarding` → `docs/pawai_cli/team-onboarding.md`, `contract` → `docs/contracts/interaction_contract.md`. |
| `pawai contract check` | **Default: run local** (`python3 scripts/ci/check_topic_contracts.py` against current branch). `--jetson` flag runs it against the deployed copy on Jetson via SSH. Local-first is safer for branch development — Jetson copy may be a stale sync from another teammate. If script absent locally, print explicit fallback instructions (do **not** silently degrade to opening docs). |

**Dropped from earlier brainstorm**: `pawai reset` (too destructive), demo-start panel hints (low-value), `pawai doctor --fast` (out of scope tonight, `--cache` covers re-run speed).

---

## Skill

### Existing implementation (already on disk)

```
.claude/skills/pawai-cli/
├── SKILL.md                              (77 lines)
├── references/
│   ├── command-reference.md              (56 lines)
│   ├── lock-semantics.md                 (58 lines)
│   └── network-diagnosis.md              (61 lines)
└── scripts/
    └── quick-check.sh                    (16 lines, +x)
```

### Design principles encoded

1. **Self-discovery**: SKILL.md instructs AI to verify exact flags via `pawai --help` rather than assume designed-but-unimplemented behavior. Removes need to re-patch skill after every CLI layer ships.
2. **Conservative on lock takeover**: `references/lock-semantics.md` tells AI to recommend manual coordination first and only use `--force` after explicit user confirmation.
3. **Single-purpose references**: `common-errors.md` was merged into `lock-semantics.md` and `network-diagnosis.md` to avoid drift.
4. **`.gitignore` pattern**: `*` + double unignore (`!.claude/skills/<name>/` plus `!.claude/skills/<name>/**`) to bypass the directory-unignore loophole in git.

### Optional post-implementation patch

After L1/L2/L3 land, optionally patch skill references to inline the now-real flag names (`--fix` / `--deep` / `--force`). This is nice-to-have, not required.

---

## Documentation Updates (pending — ships per layer, see Implementation Order)

### `docs/pawai_cli/README.md`

Add sections (do not rewrite existing):
- Lock mechanism explainer (state machine, stale rules)
- `-y` vs `--force` table
- `doctor` new flags (`--fix` / `--deep` / `--cache 30`) and when to use each
- Branch mismatch explainer (`.pawai-last-deploy` new fields)
- Network topology output reader's guide

### `docs/pawai_cli/troubleshooting.md`

Append four chapters:
- **G. Jetson network change** — Tailscale IP stability, Ethernet hijack, reconnect window, school Wi-Fi outbound rules
- **H. Tailscale Sharing** — accepting share link, `tailscale status` verification, multi-device receivers
- **I. Go2 Ethernet direct connection** — three reasons Go2 ping fails, OTA avoidance, wrong Ethernet port
- **J. Gateway 8080 split diagnosis** — interpret combinations of local-curl vs remote-curl results

### `docs/pawai_cli/team-onboarding.md` (new file)

Six-step, 30-minute path for new teammates:
1. Install tools (`brew install tmux node tailscale` / Linux equivalent)
2. Accept Tailscale share link, verify `tailscale status` shows Jetson
3. Clone repo, install CLI in venv, copy `.env.local.example`, fill `OPENROUTER_KEY`
4. `pawai doctor` should be all green; red lights map to troubleshooting B / G / H chapters
5. Branch + `pawai jetson deploy --module <yours>` + `pawai demo start` + `pawai demo stop`
6. Team rules: one demo at a time, coordinate before `--force`, `pawai demo stop` defaults to own lock only

### `.env.local.example`

Remove hardcoded IP, add `JETSON_HOSTNAME_HINT`, comment auto-detect behavior. (Shown earlier in this spec.)

### `tools/pawai_cli/README.md`

Brief daily-flow refresh + add pointer line to `docs/pawai_cli/README.md` as canonical. Avoid duplicating content.

---

## Acceptance Criteria (per layer)

### L1

- `pawai doctor` shows Network topology block at top of output. Gateway 8080 line shows `SKIP (no demo running)` when no demo is running (not red); all other lines green on Roy's machine.
- `JETSON_HOSTNAME_HINT=not-a-real-host pawai doctor` correctly surfaces Tailscale-found-no-peer red light without touching Roy's real config.
- `JETSON_HOST=jetson-bad pawai doctor` correctly distinguishes Tailscale-working / SSH-alias-broken.
- `--fix` writes only after prompt; default never mutates `.env.local`.
- `--deep` performs one OpenRouter API call; default performs zero.
- `--cache 30` second run returns under 1s.

### L2

- Two-shell simulation via `USER=teammate1`: collision prompt appears, `--force` takes over, `-y` does not take over.
- Fake-lock injection: stale 4.5hr `running` lock surfaces `STALE` in status, requires confirmation to clear, never auto-deleted.
- Branch switch + redeploy: `pawai status` correctly reports local vs install branch and dirty flag.
- flock contention: simulated concurrent acquire shows one winner + one retry message, no corrupted lock JSON.

### L3

- `pawai docs brain` prints / opens correct architecture file.
- `pawai docs <unknown>` lists valid module names instead of crashing.
- `pawai contract check` runs script if present; emits explicit fallback message (not silent docs-open) if absent.

### Cross-cutting

- Acceptance commands never modify real network state (`tailscale down`, `~/.ssh/config`, real `.env.local` — all forbidden in test instructions).
- All acceptance scenarios use env override or fake-lock injection.

---

## Risks

| Risk | Mitigation |
|---|---|
| L2 flock implementation breaks on busy network (SSH timeout mid-acquire) | 3× retry with 2s backoff; clear error message on final failure |
| Teammate's Tailscale free tier rejects share link | `troubleshooting.md` H chapter covers; fall back to `tailscale up` and inviting into Roy's tailnet as paid option |
| OpenRouter `--deep` rate-limits during 5-person doctor run | Default doctor does not call API; only one person needs to run `--deep` per session |
| Spec scope creep mid-implementation | Each layer is its own commit; explicit "no extras" rule per L1/L2/L3 |
| Skill goes stale after CLI flags land | Skill's self-discovery pattern (`pawai --help` first) makes references resilient; optional post-implementation patch is nice-to-have |

---

## Implementation Order (deferred to writing-plans)

This spec stops at design. The implementation plan (created via `superpowers:writing-plans`) will interleave code + docs per layer, because **onboarding docs are part of L1/L2 acceptance, not post-L3 cleanup**:

| Layer | Code changes | Doc changes (ship together in same commit set) |
|---|---|---|
| **L1** | doctor flags, topology block, `.env.local.example` IP change | `troubleshooting.md` G + H chapters; `team-onboarding.md` steps 1-4; `README.md` doctor flags section |
| **L2** | demo lock, `.pawai-last-deploy` schema, status warnings | `troubleshooting.md` I + J chapters; `team-onboarding.md` step 5 + team rules; `README.md` lock + branch sections |
| **L3** | `pawai docs`, `pawai contract check` | `README.md` new command rows; `tools/pawai_cli/README.md` sync |

Each layer commits as code + docs together. Skipping L3 still leaves a usable team — but skipping L1's or L2's docs would leave teammates without onboarding paths.

---

## Open Questions

None blocking implementation. The following were resolved during brainstorm:

- ~~Should Go2 also be Tailscale-shared?~~ → No. Go2 has no Tailscale client; reached via Jetson Ethernet.
- ~~Auto-delete stale `running` locks?~~ → No. Flag only; require user action.
- ~~Default `doctor` calls OpenRouter API?~~ → No. Behind `--deep`.
- ~~Add `pawai reset`?~~ → No. Out of scope.
- ~~Skill structure: 4 references or 3?~~ → 3 (common-errors merged).
