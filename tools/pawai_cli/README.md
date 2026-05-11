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

## Troubleshooting

**`build_editable hook missing` 或 `cannot be installed in editable mode`**

系統 pip / setuptools 太舊（< 64）。`uv` 會自帶新版繞過。沒裝 uv 的話：

```bash
python3 -m pip install --upgrade pip setuptools
python3 -m pip install -e tools/pawai_cli
```

或最快：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install -e tools/pawai_cli
```

**`pawai: command not found` after install**

`$HOME/.local/bin`（user install）或 venv `bin/` 不在 PATH。檢查：

```bash
python3 -m pip show -f pawai-cli | grep pawai
```

把 `bin/` 加進 PATH 或用 `python3 -m pawai_cli.main` 替代。
