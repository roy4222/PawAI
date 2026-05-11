# Mac Migration Setup Runbook

> Purpose: move PawAI development from WSL to Mac without losing project skills,
> hooks, memory, or Jetson demo workflows.
>
> Scope: housekeeping only. ROS2 runtime stays on Jetson. Cobra `pawai` CLI and
> `OFFLINE_MODE=1` are post-demo follow-up projects.

## 1. Prerequisites

Install only the tools the Mac needs as a development and control machine:

```bash
brew install git gh tailscale tmux node pnpm
```

Also install Claude Code on the Mac and sign in.

Do not install ROS2 Humble natively on macOS for this migration. The runtime
remains on Jetson at `/home/jetson/elder_and_dog`; the Mac triggers work over
SSH and runs Studio/frontend tooling locally when needed. If local ROS2 testing
is required later, use Docker rather than a native macOS Humble install.

## 2. SSH And Tailscale

Connect the Mac and Jetson to the same Tailscale network, then configure SSH:

```sshconfig
Host jetson-nano
  HostName <JETSON_TAILSCALE_IP_OR_LAN_IP>
  User jetson
  ServerAliveInterval 30
  ServerAliveCountMax 3
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h:%p
  ControlPersist 10m
```

Verify:

```bash
ssh jetson-nano 'echo ok && hostname'
```

## 3. Clone Main Repo

```bash
mkdir -p ~/newLife
cd ~/newLife
git clone git@github.com:roy4222/elder_and_dog.git
cd elder_and_dog
```

Recommended shell env for Mac:

```bash
export JETSON_HOST="${JETSON_HOST:-jetson-nano}"
export JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
export JETSON_TAILSCALE_IP="${JETSON_TAILSCALE_IP:-<jetson-tailscale-ip>}"
export ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
export PAWAI_LLM_MODEL="${PAWAI_LLM_MODEL:-openai/gpt-5.4-mini}"
```

Secrets stay outside Git. Keep API keys in the Jetson repo `.env` or a local
shell profile, not in committed files.

## 4. Claude Code Project Assets

After clone, verify the project assets are present:

```bash
git ls-files .claude/skills .claude/rules .claude/commands .claude/settings.json
```

Expected project skills include:

```text
brain-studio-lane
nav-avoidance-lane
jetson-verify
project-onboard
demo-preflight
reviewer
ros2-test-suite
```

Project hooks use `$CLAUDE_PROJECT_DIR`, so they should work regardless of
whether the repo lives under `/home/...` or `/Users/...`.

## 5. Claude Memory Private Repo

Memory is intentionally not stored in the PawAI source repo because it contains
personal notes such as `user_career_goals.md` and `user_career_interest.md`.

Create a private GitHub repo:

```text
roy4222/pawai-claude-memory
```

WSL one-time push:

```bash
cd ~/.claude/projects/-home-roy422-newLife-elder-and-dog/memory/
git init
git remote add origin git@github.com:roy4222/pawai-claude-memory.git
git add .
git commit -m "init: WSL freeze before Mac migration (2026-05-12)"
git branch -M main
git push -u origin main
```

Mac setup:

```bash
# 1. Start Claude Code once inside the cloned PawAI repo, then exit.
cd ~/newLife/elder_and_dog
claude

# 2. Find the project directory Claude Code created. The name depends on the
#    actual Mac clone path, so do not hardcode it.
ls ~/.claude/projects/ | grep -i elder

# 3. Clone memory into that actual project directory.
cd ~/.claude/projects/<actual-project-dir>
git clone git@github.com:roy4222/pawai-claude-memory.git memory
```

Maintenance rule: push memory at the end of each work session and after major
decisions, otherwise Mac and WSL will diverge.

## 6. Sync And Build Flow

Source of truth remains the development machine. After editing on Mac:

```bash
~/sync once
ssh "$JETSON_HOST" "cd $JETSON_REPO && colcon build --packages-select pawai_brain"
```

If `~/sync` is not installed on the Mac yet, use the existing WSL machine as
fallback or recreate the same rsync/sshfs workflow before doing live edits.

## 7. Start Demo Lane From Mac

From the Mac clone:

```bash
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
```

Expected behavior:

- SSH to `$JETSON_HOST`
- start Jetson tmux sessions for brain/demo/studio gateway
- start local Studio frontend on `http://localhost:3001/studio`
- gateway points at Jetson `:8080`

Quick health checks:

```bash
ssh "$JETSON_HOST" 'tmux ls'
curl -s "http://${JETSON_TAILSCALE_IP}:8080/health"
```

## 8. PawAI CLI Quickstart

For 5-person campus development, install the MVP CLI:

```bash
cd ~/newLife/elder_and_dog
uv pip install -e tools/pawai_cli
# or: python3 -m pip install -e tools/pawai_cli
```

Daily workflow:

```bash
pawai doctor
pawai status
pawai dev info gesture
pawai jetson deploy --module gesture
pawai demo start
pawai logs gesture --lines 500
pawai demo stop
```

The CLI is a thin wrapper around the existing scripts. It does not replace the
brain/nav lane scripts and does not enforce a hard lock on the shared Go2.

## 9. Offline Fallback Cases

These are manual procedures for demo-day diagnosis. A one-shot `OFFLINE_MODE=1`
wrapper is intentionally out of scope for this migration pass.

### Case A: Normal Cloud

Use when network and cloud providers are healthy.

```bash
export OPENROUTER_KEY="sk-or-v1-..."
export PAWAI_LLM_MODEL="openai/gpt-5.4-mini"
export TTS_PROVIDER="openrouter_gemini"
ssh -f -N -L 8001:localhost:8001 user@rtx-server
```

Expected: best answer quality, highest dependency on network.

### Case B: Cloud LLM Down, ASR/TTS Still Available

Use when OpenRouter is failing but RTX ASR tunnel and Edge TTS still work.

```bash
grep -E 'OPENROUTER|OPENAI|ANTHROPIC' .env .env.local 2>/dev/null || true
unset OPENROUTER_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
export TTS_PROVIDER="edge_tts"
```

Also comment out matching keys in `.env` before restarting any session that
sources `.env`, otherwise the keys will return.

Expected: LLM falls through to local/vLLM/Ollama/RuleBrain depending on what is
available. Emotion/audio tags are lower priority.

### Case C: Full Offline

Use when there is no usable Wi-Fi or internet. Jetson-local assets must exist.

```bash
unset OPENROUTER_KEY OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
export TTS_PROVIDER="piper"
export PIPER_MODEL_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
export PIPER_CONFIG_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
export ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'
pkill -f "ssh.*8001:localhost" || true
pkill -f "ssh.*8000:localhost" || true
```

Required Jetson files:

```text
/home/jetson/models/piper/zh_CN-huayan-medium.onnx
/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json
/home/jetson/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx
/home/jetson/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/tokens.txt
```

Expected: perception, gestures, pose, fallen alert, and motion still work.
Conversation quality may degrade to short canned replies if RuleBrain is the
only remaining LLM layer.

## 10. Migration-Day Go/No-Go

Before leaving WSL as fallback, verify on Mac:

- `ssh jetson-nano 'echo ok'`
- `git status --short --branch` is clean
- Claude Code loads project hooks without absolute-path errors
- `uv pip install -e tools/pawai_cli && pawai doctor`
- `bash .claude/skills/brain-studio-lane/scripts/start.sh demo` starts
- Studio opens at `http://localhost:3001/studio`
- One typed chat request reaches `/brain/chat_candidate`
- Case C full-offline smoke has been tested at least once

Keep the WSL machine available until the Mac passes the list above.
