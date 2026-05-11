# PawAI CLI

Thin command-line wrapper for 5-person PawAI development. It does not replace
the existing bash/tmux/ROS2 scripts; it gives everyone one stable entry point.

## Install

```bash
cd ~/newLife/elder_and_dog
uv pip install -e tools/pawai_cli
```

If `uv` is not available:

```bash
python3 -m pip install -e tools/pawai_cli
```

## Daily Flow

```bash
pawai doctor
pawai status
pawai dev info gesture
pawai jetson deploy --module gesture
pawai demo start
pawai logs gesture --lines 500
pawai demo stop
```

## Modules

`face`, `speech`, `gesture`, `pose`, `object`, `nav`, `brain`, `studio`.

## Notes

- `deploy` syncs the whole repo, then builds only the selected module package.
- `status` is advisory; it warns about active sessions but does not enforce a lock.
- `dev info` is informational only. It does not start mock processes in MVP.
