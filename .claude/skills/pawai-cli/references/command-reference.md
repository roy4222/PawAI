# PawAI CLI Command Reference

Always verify exact flags with `pawai <command> --help`; this repo's CLI is under
active development.

## Core Commands

```bash
pawai doctor
pawai status
pawai status --short
pawai dev info <module>
pawai jetson deploy --module <module>
pawai jetson deploy --all
pawai demo start
pawai demo start --nav capability
pawai demo stop
pawai logs <module> --lines 200
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
pawai logs brain --lines 300
ssh "$JETSON_HOST" 'cd "$JETSON_REPO" && source install/setup.zsh && ros2 topic echo /brain/conversation_trace'
ssh "$JETSON_HOST" 'cd "$JETSON_REPO" && source install/setup.zsh && ros2 topic echo /brain/chat_candidate'
```

If `$JETSON_HOST` / `$JETSON_REPO` are not exported in the shell, use the values
from `.env.local` or let `pawai logs brain` handle the SSH target.
