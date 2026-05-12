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

Expected stale policy:

- `starting` older than 10 minutes: likely failed startup; prompt before clearing.
- `running` older than 4 hours: stale warning only; do not delete automatically.

## `-y` Versus `--force`

Keep these meanings separate:

- `-y`: skip ordinary confirmations for your own operation.
- `--force`: take over or stop another user's demo lock.

If `--force` is not implemented in the current CLI, do not claim it is available.
Tell the user to coordinate manually and run `pawai demo stop` only after the
current owner agrees.

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
