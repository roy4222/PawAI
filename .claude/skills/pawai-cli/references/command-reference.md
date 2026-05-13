# PawAI CLI Command Reference

Always verify exact flags with `pawai <command> --help`; this repo's CLI is under
active development.

## Core Commands

```bash
pawai doctor
pawai doctor --cache 30                    # share probe results within team for 30s
pawai doctor --expect-demo                 # treat Gateway 8080 down as FAIL
pawai doctor --fix                         # prompt to write detected Tailscale IP into .env.local
pawai status
pawai status --short                       # skip ros2 node list (avoid daemon cache lie)
pawai dev info <module>
pawai jetson deploy --module <module>
pawai jetson deploy --all
pawai jetson deploy --module <name> --no-build   # sync only (yaml / launch / py changes)
pawai jetson deploy --module <name> --no-sync    # build only (rsync already done)
pawai demo start
pawai demo start --no-studio               # full mode, no Studio frontend
pawai demo start --brain-only              # minimal mode, brain + executive only
pawai demo start --nav capability
pawai demo stop
pawai health brain                         # Phase 1 — runs brain lane healthcheck (8 checks)
pawai net wifi list                        # Jetson Wi-Fi scan
pawai net wifi status                      # Jetson active SSID / IP / default route
pawai net wifi connect <SSID>              # connect Jetson Wi-Fi (prompts password)
pawai net wifi forget <SSID>               # delete saved Wi-Fi profile
pawai logs <module> --lines 200
pawai logs all                             # capture all demo windows at once
pawai docs <target>                        # jump to 0511 architecture doc
pawai contract check                       # topic schema validation
pawai contract check --jetson              # run on Jetson
```

Valid modules:

```text
face speech gesture pose object nav brain studio
```

Aliases may exist, such as `vision -> gesture` and `pawai-brain -> brain`.
Confirm with `pawai dev info <name>`.

## Deployment Pattern

Use this sequence after code changes:

```bash
pawai doctor
pawai dev info brain
pawai jetson deploy --module brain
pawai status --short
pawai demo start
pawai logs brain --lines 200
```

Do not deploy blindly while another person is running a demo. Check `pawai status`
and follow lock prompts if the CLI supports lock enforcement.

## Nav Capability Entry

Use this only for nav stack bringup and manual ROS2 action field tests:

```bash
pawai demo start --nav capability
```

This starts the nav capability lane through the nav-avoidance-lane scripts. It
does not mean Brain voice navigation is connected. The first movement test should
be a short manual `/nav/goto_relative` action, usually 0.3 m. For a new field,
build or verify the map before starting capability mode.

## Brain Debug Entry

For Brain runtime issues, prefer trace over guessing:

```bash
pawai health brain                         # Phase 1 — 8 checks (conv_graph ready, openrouter on, persona files, /brain/chat_candidate, /tts, tts_node, gateway, frontend)
pawai logs brain --lines 300
ssh "$JETSON_HOST" 'cd "$JETSON_REPO" && source install/setup.zsh && ros2 topic echo /brain/conversation_trace'
ssh "$JETSON_HOST" 'cd "$JETSON_REPO" && source install/setup.zsh && ros2 topic echo /brain/chat_candidate'
```

If `$JETSON_HOST` / `$JETSON_REPO` are not exported in the shell, use the values
from `.env.local` or let `pawai logs brain` handle the SSH target.

## Daily-Use Walkthrough

For scenario-based teaching with decision trees and an error-message lookup
table, see `docs/pawai_cli/usage-guide.md`.
