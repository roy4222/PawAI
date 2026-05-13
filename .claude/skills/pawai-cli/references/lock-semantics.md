# Lock And Branch Semantics

The shared resource is the Jetson runtime: tmux sessions, ROS2 install space,
Gateway, and Go2 hardware. Multiple laptops can edit branches, but only one demo
should control the Jetson/Go2 at a time.

## Intended Lock Model

The team design uses a Jetson-side lock:

```text
$JETSON_REPO/.pawai-demo-lock
```

Expected states:

- `starting`: `demo start` has reserved the Jetson but startup is not complete.
- `running`: demo startup completed and this user owns the active demo session.

Expected lane metadata:

- `lane=brain`, `tmux_session=demo`: brain/full perception demo.
- `lane=nav_capability`, `tmux_session=nav-cap-demo`: navigation capability field test.

When taking over with `--force`, the old lane must be cleaned before the lock is
released and the new lane is acquired. Deleting only the lock can leave a Go2
driver, D435, teleop, or nav process alive.

Expected stale policy:

- `starting` older than 10 minutes: likely failed startup; prompt before clearing.
- `running` older than 4 hours: stale warning only; do not delete automatically.

## Owner-Aware Release (Phase 1, item 6)

`Lock.release_if_owned(user, host)` is the safe path used by `pawai demo stop`:

- Runs under a remote `flock` to avoid race with concurrent CLI invocations.
- `user` / `host` are `shlex.quote`-protected and compared inside a Python script
  that reads from `os.environ`, so a malicious lock payload cannot inject shell.
- Returns True iff the lock was your user/host AND was removed (or was already
  absent). Returns False on owner mismatch.

This means:

- **Own stale lock + `demo stop`** → no `--force` needed. CLI prints
  `Reclaiming your own stale {state} lock (started ...)` and uses
  `release_if_owned()`. **Do not coach users to add `--force` for their own
  stale lock**; that habit defeats the safety check.
- **Own non-stale lock + `demo stop`** → also uses `release_if_owned()`. Same
  safety.
- **Other user's lock + `demo stop --force`** → falls back to plain
  `Lock.release()` (no owner gate). Required for legitimate takeover, but the
  user must have coordinated first.

## `-y` Versus `--force`

Keep these meanings separate:

- `-y`: skip ordinary confirmations for your own operation. **Cannot** override
  another user's lock. Triggers exit 2 with message
  `` `-y` does not override another user's {demo,lock}. Use --force[ to take over]. ``
- `--force`: take over or stop another user's demo lock. Implies a takeover and
  should be preceded by out-of-band coordination (Slack, in-person).

`--force` is **not** required to clear your own stale lock (Phase 1 item 6).
Reserve it for the legitimate takeover case.

## Branch Awareness

`rsync` excludes `.git/`, so Jetson git state is not a reliable source for what
is installed. Use `.pawai-last-deploy` and `pawai status` to understand:

- who deployed
- which module
- local branch at deploy time
- git SHA
- dirty state
- package list

If local branch and install branch differ, do not assume the running code matches
the current checkout. Deploy the intended module again or switch branches first.

## Safe Response Patterns

If another user owns the demo:

1. Report owner, branch, and duration from `pawai status` if available.
2. Recommend coordination before deploy/start/stop.
3. Use `--force` only when the user explicitly confirms takeover and the CLI
   supports it.
