---
name: pawai-cli
description: >
  PawAI CLI / Jetson / Go2 team-development operations. Use when the user asks
  about pawai doctor, pawai status, pawai jetson deploy, pawai demo start/stop,
  pawai logs, deploying to Jetson, starting/stopping demo, Tailscale sharing,
  Jetson IP/network changes, Go2 192.168.123.161 reachability, lock collisions,
  branch/deploy mismatch, or five-person shared Jetson workflows.
---

# pawai-cli

Use this skill for the team-facing PawAI CLI workflow. The goal is to help an AI
agent operate the repo without relying on remembered SSH/tmux/ROS2 commands.

## Source Of Truth

Before giving exact command flags, inspect the current CLI:

```bash
pawai --help
pawai doctor --help
pawai jetson deploy --help
pawai demo start --help
pawai demo stop --help
```

Then use the human docs as the canonical explanation:

- `docs/pawai_cli/README.md`
- `docs/pawai_cli/troubleshooting.md`
- `docs/pawai_cli/modules.md`
- `docs/pawai_cli/team-onboarding.md` if present

If this skill mentions a planned flag that does not exist yet, do not invent it.
Report that the CLI has not implemented it and fall back to the nearest current
command.

## Default Flow

For "how do I get started / why can't I connect":

1. Run or ask for `pawai doctor`.
2. If Jetson is unreachable, read `references/network-diagnosis.md`.
3. If Go2 is unreachable, check Jetson -> Go2 from the doctor output first.
4. If demo/deploy is blocked by another user, read `references/lock-semantics.md`.

For "deploy my module":

1. Identify the module: `face`, `speech`, `gesture`, `pose`, `object`, `nav`, `brain`, or `studio`.
2. Run `pawai dev info <module>` to confirm packages, docs, tests, and logs.
3. Run `pawai jetson deploy --module <module>`.
4. Run `pawai status --short` and inspect last deploy / branch warnings.

For "demo start/stop":

1. Run `pawai status --short`.
2. Respect any active demo/lock warning. `-y` means skip ordinary prompts; only
   `--force` may take over another user's lock if the CLI supports it.
3. Start with `pawai demo start`; stop with `pawai demo stop`.
4. Use `pawai logs <module> --lines 200` for the failing module.

## References

- Command syntax and examples: `references/command-reference.md`
- Lock ownership, `-y` vs `--force`, branch mismatch: `references/lock-semantics.md`
- Tailscale, Jetson network moves, Go2 Ethernet: `references/network-diagnosis.md`

## Helper Script

For a quick non-destructive snapshot:

```bash
bash .claude/skills/pawai-cli/scripts/quick-check.sh
```

The script only runs read-only CLI/status commands.
