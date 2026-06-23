# Voice Interaction System

**English** | [中文](./README.zh.md)

> **Scope**: The **module-design source-of-truth layer** for the voice interaction main line — how ASR / VAD / Intent classification / LLM bridge / TTS routing fit together, which path is real, and which are historical/research.
> **Status**: active (module-design source-of-truth layer). This file is **NOT** the truth on "whether a capability currently passes" — any voice capability claim must follow the canonical claim matrix referenced in the "Capability claims" section below + the 6/04 baseline-evidence.
> **Owner lane**: brain-speech (together with [`CLAUDE.md`](CLAUDE.md) module working rules + [`AGENT.md`](AGENT.md) interface contract).
> **Source-of-truth priority** (high → low): code / topic schema ＞ [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) (measured trusted snapshot, SHA `78fbf36`, `run_trusted=true`, readiness=`not_ready`) ＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` (convergence audit) ＞ [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md) (per-capability claim canonical) ＞ [`docs/mission/2026-06-18-demo-north-star.md`](../../mission/2026-06-18-demo-north-star.md) (strategic boundary) ＞ this file (module design) ＞ [`docs/contracts/interaction_contract.md`](../../contracts/interaction_contract.md) (topic/action schema).
> **Maintained child files**: [`CLAUDE.md`](CLAUDE.md) (working rules), [`AGENT.md`](AGENT.md) (interface contract), `research/*.md` (research-only, benchmark / pipeline reports).
> **Archived / historical boundary**: `archive/jetson-MVP測試.md` and `research/*.md` are uniformly **historical / research-only** — not maintained in duplicate, and must not be taken as evidence of "what runs now"; the 5/2–5/12 sprint prose below (brain-freeze-v2 / Phase 0.5 / TTS chunking, etc.) is a **development record** describing "how the mechanism is implemented", which **does not mean e2e verified or capability pass**.
> **This README is NOT**: capability claim truth (→ [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)), an operations manual (→ [`docs/runbook/`](../../runbook/)), or a threshold definition (→ [`specs/2026-06-18-capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md)).

> Chinese voice conversation: hear → understand intent → LLM responds → speak it out.

---

## Capability claims (reference the canonical, do not duplicate the whole thing here)

> **Authoritative**: each capability's Current Claim / Claim Level / Pass-Fail / Non-Claims is canonical per the `voice.command` / `voice.stop` rows of [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md), with the baseline being [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/). The below is only an entry-point summary — **do not rewrite the levels**.

### voice.command (fixed-command intent — narrow pass)

- **Current Claim**: "intent classification" success_rate=0.875 for the **fixed command set** (a pure-Python keyword rule classifier, usable as a legitimate input to the Brain three-layer decision).
- **Claim Level**: CLAIM_WITH_CAVEAT.
- **Evidence-Provenance**: 6/04 HITL (n=24, success_rate=0.875, false-trigger=0.0; **latency all null, CSV reconstructed from the terminal, git_commit≠snapshot SHA, single speaker Roy**).
- **Pass / Degraded / Fail / Insufficient**: 🟢 **pass (narrow)** — limited to fixed-command-set intent classification.
- **Fallback**: ASR misheard → enunciate clearly and retake.
- **Non-Claims (do not say)**: voice latency / reaction time / **mic_stop emergency stop (not wired, not measured)** / free-conversation recognition rate / LLM directly controlling the robot dog / calling 0.875 an "ASR recognition rate".
- **Model Candidates**: BASELINE_NOW (rule classifier + SenseVoice / Whisper ASR, in service, no swap).
- **Next Retest**: a real person runs the full ASR→intent e2e ≥20 items against the demo mic + measure e2e latency + switch to a non-Roy speaker + add noise.

### voice.stop (voice "stop" — fail, not a safety mechanism)

- **Current Claim**: voice "stop" measured success_rate=0.667 on 6/04, the scoreboard honestly marks it **fail**, `brain_allowed=false`; it is merely a convenience interaction command, **not a safety mechanism**.
- **Claim Level**: DO_NOT_CLAIM (may only honestly disclose the fail itself).
- **Evidence-Provenance**: 6/04 HITL (n=6, 0.667, FN=2: R16 no-ack / R18 "hey wait, stop first" misclassified as come_here).
- **Pass / Degraded / Fail / Insufficient**: 🔴 **fail** (zero speech code changes since baseline, fail live).
- **Fallback**: real safety relies on `reactive_stop` + physical e-stop; voice stop is only a convenience command, do not shout stop at the robot dog on site.
- **Non-Claims (do not say)**: "say stop and it stops" / safe stopping / emergency stop / **mic_stop latency** / wired to nav / motion trigger / calling voice.stop a safety stop.
- **Model Candidates**: SPIKE_AFTER_FAIL (not a model swap; add a safety tie-break to the intent_classifier + tune VAD).
- **Next Retest**: add safety tie-break to intent_classifier + unit test → tune VAD → re-run HITL n≥15; do not wire motion before it passes.

> ⚠️ **mic_stop / latency / safety-stop are uniformly not wired and not measured**: the 6/04 voice e2e was **VAD-era**, the `mic_stop` observer was not wired, and the CSV had no latency column. **Do not claim a mic_stop emergency-stop latency, and do not treat voice.stop as a safety stop.** Any latency number in the prose below (VAD 2–10s / P50, etc.) is a **development-period proxy observation**, not a baseline-evidence trusted measurement.

> ℹ️ **brain LLM persona hallucination (6/04 operator-observed)**: TTS replies have fabricated unperceived world state (raining / "I see a cup" / posture). This is a Brain-persona follow-up and **must not be presented as real perception**; the voice module does not claim anti-hallucination has been verified.

## Status card

> ℹ️ The table below is the **5/12 brain-freeze-v2 development record** (model / routing selection + same-day smoke), describing "how the mechanism is configured", which **does not mean 6/18 capability pass**. Whether a capability passes always returns to the "Capability claims" section above + the canonical claim matrix; the latency numbers in the table are development-period proxy observations, not trusted measurements.

| Item | Value |
|------|---|
| Status | **brain-freeze-v2 (5/12)**: after an LLM 8-model A/B, switched to `openai/gpt-5.4-mini`, TTS dual-route gemini Despina; one-line revert via env override `PAWAI_LLM_MODEL=...` |
| Version/decision | **LLM primary**: `openai/gpt-5.4-mini` (OpenRouter, P50 1.16s local / 1.85s Jetson tunnel) ／ **fallback**: `google/gemini-3-flash-preview` ／ **TTS quality lane**: `google/gemini-3.1-flash-tts-preview` (Despina) — fast lane (≤12 chars / no audio tag) goes edge_tts; ASR uses SenseVoice cloud. Decision log: `docs/archive/pawai-brain-legacy/dev-logs/2026-05-12-llm-naturalness-ab-eval.md` |
| Completeness | 95% (brain-freeze-v2 landed) |
| Last verified | 2026-05-12 night Jetson smoke: 60s self-intro ×5 (4/5 captured, P50 1.85s, replies natural with follow-up); fallback env override switching to Gemini really took effect; TTS gemini Despina really played ✅ |
| Entry file | `speech_processor/speech_processor/stt_intent_node.py` |
| Test | `python3 -m pytest speech_processor/test/ -v` |

## How to launch

```bash
# One-click launch (recommended)
bash scripts/start_llm_e2e_tmux.sh

# Fully offline mode
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh
```

### 5/5 addendum: standalone tts_node launch + USB speaker fallback

When the Go2 driver is not running (e.g., a local perception-only test), the default Megaphone DataChannel path will silent-fail (no sound, no error). Switch to local ALSA:

```bash
# Standalone tts_node launch on Jetson (for demo bridge / smoke test)
ros2 run speech_processor tts_node --ros-args \
  -p provider:=edge_tts \
  -p local_playback:=true \
  -p local_output_device:=plughw:0,0
# (plughw:N,0 — find N as the USB speaker card index via `aplay -l`; it may drift after reboot)
```

After enabling `local_playback:=true`, the startup log should show `Playback: Local` (instead of `Robot`), and TTS is sent to the USB speaker. The Megaphone path is still kept as the demo main line (auto-restored when the Go2 driver is running).

## Core flow

```
Laptop microphone via PawAI Studio (demo main line)
    |  ← USB microphone deprecated (Go2 fan noise causes ~20% recognition rate)
    |  Studio WebSocket → Gateway(Jetson:8080) → ROS2
stt_intent_node (Energy VAD -> ASR three-tier fallback -> Intent classification)
    |   ASR: SenseVoice cloud -> SenseVoice local (sherpa-onnx int8) -> Whisper small
    | /event/speech_intent_recognized
llm_bridge_node (**locked main**: OpenRouter Gemini 3 Flash Preview → DeepSeek V4 Flash → Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain five-tier fallback)
    |   output_mode=legacy → publishes /tts + sport /webrtc_req (existing behavior)
    |   output_mode=brain  → publishes only /brain/chat_candidate (PawAI Brain MVS mode)
    |   OpenRouter timeout default 4.0s / overall budget 5.0s (bumped after 5/4 Jetson smoke)
    | /tts (legacy mode) or /brain/chat_candidate (brain mode)
tts_node (**5/8 evening unified routing**: when OPENROUTER_KEY is set, always go gemini → edge_tts → piper; mic + Studio same voice)
    |   `/tts` payload dual-mode: plain text OR JSON envelope `{"text", "input_origin"}`
    |   has _studio_fallback_chain (OPENROUTER_KEY set) → always use that chain
    |   none (key missing) → default chain (edge_tts → piper)
    |   audio_tag.py + tts_provider.py: provider.supports_audio_tags gatekeeps strip
    |   input_origin field reserved for future per-source policy (chunk / voice tweak); no routing branch for now
    |
USB speaker local playback (Megaphone DataChannel as backup)
    |
echo gate prevents ASR self-triggering (total 1.5s)
```

**Intent fast path**: high-frequency intents like stop/greet skip the LLM and go straight to RuleBrain (~0ms).
**LLM timeout** Jetson default 4.0s (5/4 bump from 2.0s — Python urllib3+requests overhead on Jetson pushes a 1.5s curl to the 2s boundary, causing premature fallback).
**TTS provider chain** (5/8 evening unified routing — commit `a2eefc8`):

| Path | input_origin | Chain | Notes |
|---|---|---|---|
| Studio chat panel text input | `studio_text` | `openrouter_gemini` (Despina, audio tag native, ~6.5s first audio) → `edge_tts` (strip tag, ~1.5s) → `piper` (offline) | Demo conversation main path |
| Microphone voice input + auto-perception (greet / object_remark / fall_alert / careful_remind ...) | `null` or missing field | **Same as above** (since 5/8 the mic also goes through the Gemini chain; Roy requested a unified persona voice) | Same voice as Studio chat |
| `ros2 topic pub /tts std_msgs/String "..."` | parse fail → null | Same as above | Development / debug |
| OPENROUTER_KEY missing / failed | any | `default_chain` (edge_tts → piper) | demo-safe fallback |

Key implementation:
- `tts_node.tts_callback` parses the `/tts` payload — attempts `json.loads`; if it is a dict with `"text"` → override raw_text + read `input_origin`; otherwise the plain-text path
- `_studio_fallback_chain` is lazily built at startup (reads the `OPENROUTER_KEY` env), dedup by provider name
- Since 5/8 the routing condition changed to "use it if `_studio_fallback_chain` exists", no longer branching on input_origin (commit `a2eefc8`, line 1040-1043)
- The chain iteration loop (line ~1024-1080) treats all chains identically; the per-provider cache key does not collide

See: `docs/architecture/specs/2026-05-05-tts-rewrite-result.md` (Stage 4 chain mechanism) + commit `10829ca` (per-message plumbing) + commit `a2eefc8` (5/8 unified routing).

### Why lock Gemini 3 Flash + Gemini 3.1 Flash TTS (2026-05-05)

- **Native audio tag support**: Gemini 3.1 Flash TTS receives emotional tags like `[excited]` / `[laughs]` / `[curious]` and renders them directly, no strip needed — strongest personality expression, consistent with the Brain MVS persona
- **Latency within acceptable range**: ~4.6s P50 (Despina voice), enough for demo scenarios; the `edge_tts` fallback is faster (~1.5s) but weaker in personality
- **Low single-provider maintenance cost**: both LLM + TTS go through OpenRouter, with unified management of credentials / rate limit / billing
- **Other options no longer evaluated**: candidates like Qwen3.6 Plus / DeepSeek V4 / Kimi K2.6 appeared in the MOC, but the 5/12 sprint already converged to run only the Gemini main line; keeping the fallback is an engineering reality, not an A/B candidate

### 5/8 addendum: TTS chunking refactor + ROS-free splitting module

The root cause of long-sentence tone breaks is not only Gemini's own limitation but also overly greedy chunking logic: originally `len(buf) >= CHUNK_MAX_CHARS // 2 (= 20)` would cut at a period, splitting even natural pauses within 20 chars into separate chunks → cross-chunk Gemini re-initialization → breathy / narrate tone completely disappears. The comma fallback used `max(rfind(','), rfind('，'), rfind(' '))` + a `> CHUNK_MAX_CHARS // 2` comparison, which is also ambiguous at the `-1` boundary (when nothing matches, max still returns -1, mistakenly entering the hard-cut branch with unclear semantics).

5/8 fix (commit `6d548b8`):
- Extracted a pure module `speech_processor/speech_processor/tts_split.py` (**ROS-free**) — the pre-commit hook does not need to source ROS, and unit tests import it directly; `tts_node` keeps backward compat via a class attribute + a `_split_for_tts` shim
- Added `MIN_SPLIT_CHARS = 30` (was `CHUNK_MAX_CHARS // 2 = 20`) — a period only cuts at 30 chars, so cross-chunk tone is no longer reset frequently
- Added an explicit `-1` guard to the comma fallback: `cut = max([c for c in candidates if c >= 0], default=-1)`, and only adopt it if `cut >= MIN_SPLIT_CHARS - 1`, otherwise hard-cut at `CHUNK_MAX_CHARS = 40`
- 13 new unit tests covering boundaries (short sentences / cross-sentence / all-CJK with no punctuation / audio-tag preservation / hard-cut character preservation)

### 5/11 night addendum: chunk-boundary silence + sentence-skip root cause pinned

5/11 night: three rounds of fixes + one round of instrumented diagnosis:

1. **CHUNK_MAX_CHARS 40 → 60, MIN_SPLIT_CHARS 30 → 45**: Google/community guidance for Gemini 3.1 Flash TTS is "long chunks have more consistent voice tone than short chunks"; 60 is still 30%+ away from the 80-char tail-drop danger zone. A 200-char story goes from 6 chunks → 3-4
2. **New module `pcm_trim.py`**: before returning each chunk, strip Gemini's internal 80-200ms silence padding, keeping 80ms (1920 samples @ 24kHz) of tail as a natural breathing gap. `int16 -32768` overflow is handled via `astype(np.int32)`. `ChunkTrimError` fail-loud: a non-empty input trimmed to empty → go to provider fallback, avoiding silently dropping a sentence
3. **whispers tag restored**: N6 morning normalizing `[whispers]` → `[curious]` was an overreaction; the user explicitly stated that whisper is necessary in storytelling / poem-reading scenarios. Keep only `[sighs]` in the normalize list (it breaks the demo rhythm). EXAMPLES.md bedtime stories switched back to `[whispers]`
4. **Phase 1 instrumented diagnosis** (5/11 night's last round): added a `PAWAI_TTS_DIAG=1` env-gated log, printing per chunk peak / rms / duration_ms / cut_lead_ms / cut_tail_ms

**5/11 night sentence-skip root cause = H1 parallel voice drift** (not trim / split / tail-drop):

The DIAG log shows the volume of 3 parallel chunks coming back for "the same whisper Despina character" differs by 2x:

| Chunk | text_len | peak | rms | duration_ms |
|-------|---------|------|------|-------|
| [0] | 69 | 18621 | **782** | 6360 |
| [1] | 68 | 12240 | **1139** | 6240 |
| [2] | 37 | 28874 | **1529** | 6240 |

The RMS steps up across the 3 chunks (782 → 1139 → 1529) = the "reads louder and louder, then suddenly quieter" stair-step sensation the user hears.

**P1 not done (next round)**: sequential synthesis (no more parallel) or post-synthesis RMS normalize across chunks, or a combination of both. The memory is in
`memory/project_tts_skip_diagnosis_0511_night.md` (a teammate's local `.claude` private memory path, not a file inside this repo, no link provided).

### 5/9 addendum: TTS dual-route + audio_format/served_by refactor (issue 1 partial)

On 5/8 evening Roy caught that the quality lane was never triggered — originally `tts_callback` went single-track through the OpenRouter Gemini chain, so even short / safety sentences went through the 6-7s cloud chain, and the user's perception was all "Google lady + slow". 5/9 PR #55 + #57 dual-track routing:

- **Fast lane**: `edge-tts → Piper` (<2s first audio; safety keyword + short sentence + no emotional tag)
- **Quality lane**: `OpenRouter Gemini → edge-tts → Piper` (emotion / long sentence; ElevenLabs to be added at the head once the spike is GO)
- **Routing logic** (`_should_use_fast_lane(text, threshold)`):
  1. safety keyword match (`停|停止|不要動|別動|小心|警告|危險|stop`) → **always** fast lane
  2. contains an emotional audio tag (`[playful]/[excited]/[whispers]/[worried]/[sighs]/[curious]/[laughs]/[thinking]/[gentle]/[happy]/[sad]/[shy]`) → **forced** quality lane
  3. effective_length (count of CJK chars + English words after removing audio tags + punctuation) ≤ `tts_fast_lane_threshold` (default 12) → fast lane
  4. otherwise → quality lane

**audio_format/served_by fix** (PR #55): originally `_play_on_robot` decided the format via `self.config.provider == TTSProvider.PIPER ? WAV : MP3` → when the fallback chain dropped from Gemini to Piper, the Piper WAV was decoded as MP3 → pydub error. Fix: each provider class adds `output_format: AudioFormat`, the chain loop records `_last_served_format` on the selected successful provider, and `_play_on_robot` uses the actual served format.

**ROS params**:
- `tts_dual_route_enabled` (default True)
- `tts_fast_lane_threshold` (default 12)

**ElevenLabs spike** (the P1 for the full fix of issue 1): the spike script is at `tools/tts_spike/elevenlabs_mini.py`, the dev-log template at `docs/archive/pawai-brain-legacy/dev-logs/2026-05-XX-elevenlabs-spike-mini.md`. Roy runs it himself (API key + pick voice ID + listen to 15 mp3 + score); after GO, a PR adds ElevenLabs to the head of the quality lane chain.

### 5/9 addendum: ASR Simplified→Traditional OpenCC s2twp (issue 6)

The ASR providers (SenseVoice / Whisper / Qwen Cloud) have no zh-TW option and output Simplified characters. Three entry points inject `to_traditional_tw()` (`opencc-python-reimplemented` lazy import + `s2twp` config):

| Entry | File | Trigger path |
|---|---|---|
| 1. Physical mic | `speech_processor/speech_processor/stt_intent_node.py:1100` before `_publish_asr_result` | USB mic → ASR → Traditional Chinese → publish `/event/speech_intent_recognized` |
| 2. Studio mic | `pawai-studio/gateway/studio_gateway.py` `/ws/speech` handler ~L627 | Browser mic → SenseVoice cloud → Traditional Chinese → same as above |
| 3. Studio chat | `pawai-studio/gateway/studio_gateway.py` `/api/text_input` POST handler | Studio chat panel typing → Traditional Chinese → publish `/brain/text_input` |

Two helpers (to avoid the cross-package import pitfall):
- `speech_processor/speech_processor/text_normalization.py`
- `pawai-studio/gateway/text_normalization.py`

**ROS param**: `enable_s2twp` (default True) + env `PAWAI_ENABLE_S2TWP`.

Dependency: `opencc-python-reimplemented` is already added to `speech_processor/setup.py` and `pawai-studio/gateway/requirements.txt`. On Jetson, first confirm with `pip install --user opencc-python-reimplemented` before use.

**5/9 night fixed a silent fail** (commit `756aeb0`): the original helper `OpenCC("s2twp.json")` would have the lib auto-append `.json`, becoming `s2twp.json.json` → FileNotFoundError → except falls back to the original text silently. Since PR #52 all three entries failed silently (ASR Simplified→Traditional never took effect), and this was only caught now by a Studio Simplified-input test. Changed to `OpenCC("s2twp")`.

## Input/Output

| Topic | Direction | Description |
|-------|:----:|------|
| `/event/speech_intent_recognized` | output | Intent event JSON |
| `/state/interaction/speech` | output | Voice pipeline state 5Hz |
| `/state/tts_playing` | output | TTS-playing flag |
| `/tts` | input | Text to speak |
| `/asr_result` | output | Raw ASR text |

## Noisy Profile v1 (2026-03-28)

ASR parameter tuning results for the Go2 servo-noise environment.

**How to launch:**
```bash
ENABLE_ACTIONS=false bash scripts/start_full_demo_tmux.sh
```

**Parameters (written in start_full_demo_tmux.sh launch args):**
- `mic_gain=8.0` (default, v1 sweet spot. gain 10/12 tested, noise amplification is worse)
- `energy_vad.start_threshold=0.02` (was 0.015, avoids Go2 noise false triggering)
- `energy_vad.stop_threshold=0.015`
- `energy_vad.silence_duration_ms=1000`
- `energy_vad.min_speech_ms=500`

**Whisper improvements (written in stt_intent_node.py):**
- `vad_filter=True` (enable silero VAD, filter non-speech segments)
- `no_speech_threshold=0.6` (reject low-confidence results)
- `log_prob_threshold=-1.0`
- hallucination blacklist 6→22 patterns + short text (< 2 chars) filtering

**Safety gate:** the `ENABLE_ACTIONS` environment variable
- `true` (default): llm_bridge and event_action_bridge publish `/webrtc_req` normally
- `false`: both action paths are off, so Go2 will not perform dangerous actions due to junk intents

**A/B test results (fixed audio-file controlled test):**

| Group | gain | Correct+Partial | Notes |
|:----:|:----:|:---------:|------|
| v1 | 8.0 | **64%** | sweet spot |
| v2 | 10.0 | 43% | triggers surge but quality drops |
| v5 | 12.0 | 62% | no improvement, hallucinations appear |

**Conclusion:** Whisper Small has hit its ceiling in the Chinese-short-sentence + machine-noise scenario (64%), and has been replaced by SenseVoice (92%).

## ASR three-tier fallback (verified 2026-03-29)

```
sensevoice_cloud (RTX 8000, FunASR) → sensevoice_local (Jetson, sherpa-onnx int8) → whisper_local
```

**Cloud server**: `scripts/sensevoice_server.py` (FastAPI + FunASR SenseVoiceSmall, port 8001, requires SSH tunnel)
**Local model**: `~/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx` (228MB, CPU only, 352MB RAM)

**Equal-volume three-way A/B test (25 items each, Go2 noise environment):**

| Metric | SenseVoice Cloud | SenseVoice Local | Whisper Local |
|------|:---:|:---:|:---:|
| Correct+Partial | 92% | 92% | 52% |
| Intent correct | 96% | 92% | 56% |
| Hallucination/garbage | 0 | 0 | 8% |
| Latency | ~600ms | ~400ms | ~3000ms |
| Needs network | Yes | No | No |

**Fallback behavior**: cloud down → `Connection refused` warn → auto-switch to sensevoice_local (`degraded=True`) → if the model is missing, switch again to whisper_local.

**⚠ The two voice paths have asymmetric fallback (6/14 HITL confirmed)**:
- **stt_intent_node (Jetson USB mic)** has the three-tier fallback above.
- **Studio laptop capture (`gateway/studio_gateway.py` `/ws/speech` L627) only POSTs to cloud 8001, with no local fallback** → once the cloud ASR dies, Studio voice fully breaks (gateway log: `Speech error: ConnectionResetError(104, Connection reset by peer)`, the frontend shows `processing_failed`). When the demo captures via Studio this is a single point of failure. Pre-6/18 follow-up: the gateway falls back to local sensevoice/whisper when 8001 is unreachable. Temporary fallback = the operator switches to Studio text input and re-types the same sentence.

**Cloud server restart procedure (6/14 HITL: the SSH tunnel is alive but the remote server process is dead ＝ `Connection reset`, not `Connection refused`)**:
```bash
# 1. Confirm it is the server process that died (not the tunnel): on Jetson, curl 8001 = 000/reset, but 8000 (LLM) is normal
ssh jetson-nano "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/health"   # 200=alive
# 2. Restart on RTX 8000 (YOUR_USER@YOUR_GPU_HOST) (run in tmux for persistence, use pawai_gpu env, GPU1)
ssh YOUR_USER@YOUR_GPU_HOST "tmux new-session -d -s sensevoice 'cd ~ && CUDA_VISIBLE_DEVICES=1 ~/miniconda3/envs/pawai_gpu/bin/python sensevoice_server.py --port 8001 > ~/sensevoice_restart.log 2>&1'"
# 3. After ~15-40s model loading, Jetson curl 8001/health should return 200 (the FunASR log line "Loading remote code failed: No module named 'model'" is a harmless warning)
```

## Known issues

- **Go2 body USB microphone deprecated** (decided 4/8): Go2 fan noise is extreme, recognition rate ~20%. The demo switched to the laptop microphone via Studio
- USB device index drifts after reboot → use `source scripts/device_detect.sh`
- MeloTTS and ElevenLabs deprecated (3/26 decision)
- SenseVoice is unstable at recognizing "please stop moving now" (stop intent ~60% correct)
- **Local ASR unusable**: after deployment, Whisper suffers severe noise interference and fails on long-sentence recognition
- **Local LLM unusable**: Qwen2.5-0.8B has extremely low intelligence and talks nonsense (confirmed at the 4/8 meeting)
- ~~**LLM reply quality needs improvement**: max_tokens=120/25-char limit, replies too short, no personality, no multi-turn memory~~ (addressed 5/5 evening: persona v3 + max_reply_chars=0 + 5-turn deque)
- **GPU cloud unstable**: disconnected twice yesterday; Plan B canned lines are mandatory
- **`speech_processor` uses ament_python; after code changes you must colcon build**: syncing source does not auto-update `install/`, and the stale install was the real culprit of the 5/5 evening all-night truncation. Changing a ROS param or persona file takes effect at runtime, no build needed; changing .py must be built.
- **Architecture fragmentation warning (5/5)**: the chat + tool calling path spans `llm_bridge_node` (1100 lines) + `brain_node._on_chat_candidate` + ChatPanel + Studio gateway; multiple-source paths increase hidden-bug risk (as with this stale install + truncation cap). Recorded as backlog (a LangGraph refactor proposal)

## Plan B canned-lines mode (added at the 4/8 meeting)

A backup for when the GPU disconnects. After ASR determines the intent, it matches a fixed answer directly, with a response time of ~0.x seconds.
- Two versions of the demo conversation script are needed: Plan A (cloud AI) + Plan B (canned lines)
- Studio displays a connection-status indicator so the team can decide in real time whether to switch
- If necessary, present a recording as evidence of the AI-conversation feature
- **Owner**: Chen Ruo-en (see the division-of-labor doc)

## PawAI Brain MVS integration (2026-04-28 Phase 0+1+2 complete)

### The `output_mode` parameter (Phase 0)

`llm_bridge_node` adds a new ROS2 param:

| Mode | Behavior | When to use |
|------|------|---------|
| `legacy` (default) | publishes `/tts` + sport `/webrtc_req` (controls the dog directly, existing behavior) | old demo / when brain_node is not started |
| `brain` | publishes **only** `/brain/chat_candidate`, no `/tts`, no sport `/webrtc_req` | when brain_node is started, with the Executive as the sole dog controller |

`scripts/start_pawai_brain_tmux.sh` one-click launches brain-mode:
- sets `llm_bridge_node` to `output_mode:=brain`
- sets `event_action_bridge` to `enable_event_action_bridge:=false`
- does not start `vision_perception/interaction_router`

### Source-level guard test

`speech_processor/test/test_tts_audio_api_only.py` — ensures `tts_node` only publishes audio api_id (4001-4004 Megaphone enter/upload/exit/cleanup) and never accidentally publishes a sport action api.

### Post-Brain-MVS fallback chain (Phase A)

```
/event/speech_intent_recognized
    ↓
llm_bridge_node (output_mode=brain)
    ↓
   /brain/chat_candidate ──→ brain_node (1500ms wait)
                                 ├ hit → SkillPlan(chat_reply)
                                 └ timeout → SkillPlan(say_canned)
                             ↓
                          /brain/proposal
                             ↓
                       interaction_executive_node
                             ↓
                            /tts → tts_node → Megaphone
```

For the detailed schema see [`docs/contracts/interaction_contract.md`](../../contracts/interaction_contract.md) v2.5.

## 5/5 evening — LLM personalization + conversation memory + Brain MVS full chain connected

The day's changes were unstaged, mainly connecting "Voice → Brain → Studio E2E" and upgrading the LLM's personality, length, memory, and environment awareness all at once.

### Brain MVS path enabled (prerequisite)
- `start_full_demo_tmux.sh` explicitly adds `-p output_mode:=brain` — llm_bridge switches to publishing `/brain/chat_candidate` instead of publishing `/tts` directly
- `brain_node._on_speech_intent` removed the self_introduce / show_status keyword bypass:
  - the action-type self_introduce 6-step gets blocked as `blocked_by_safety` by the SafetyLayer when the user is close (D435 ROI) → silence
  - the LLM persona can already naturally handle "who are you / current status" questions, no hard rule needed
  - the MOTION full self_introduce can still be triggered from the Studio button (not dependent on a voice keyword)
- `chat_wait_ms` in `interaction_executive/config/executive.yaml` 1500 → **20000** (cloud LLM long replies are sometimes ~10s, the old value's buffer was no longer effective)
- ChatPanel (`pawai-studio/frontend/components/chat/chat-panel.tsx`) adds a single-line skill trace bar — showing the latest `brain:skill_result`'s `selected_skill / status / detail`, no drawer, no timeline

### LLM length + token fully unlocked
- `max_reply_chars` default 40 → **0 (uncapped)**; `_post_process_reply` changed to skip truncation when `cap<=0`
- `llm_max_tokens` default 80 → **2000** (startup script explicitly 4000)
- `llm_timeout` default 5 → **20s**
- `openrouter_request_timeout_s` 4 → **30s**, `openrouter_overall_budget_s` 5 → **35s** (short timeouts were one of the culprits of long stories being cut)

### Conversation memory (5 turns / 10 messages)
- `llm_bridge_node` adds `_convo_history: deque(maxlen=10)`, user/assistant pairs
- both LLM paths (OpenRouter + vLLM/Ollama) stuff history into the `messages` array
- only writes when it is a "real chat" (intent ∈ greet/chat/status); stop/sit/stand do not pollute the context
- Fixed an old bug along the way: the `_call_llm` (vLLM/Ollama) path used to hard-code an inline `SYSTEM_PROMPT` (the 12-char version); now it uniformly uses `self._system_prompt` (the persona file)

### Taipei time + wttr.in weather context
- `_time_of_day_zh()`: morning / noon / afternoon / dusk / evening / late night
- `_get_weather_text()`: hits `https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw`, 10-minute cache, 2s timeout, fails quietly
- injected at the end of each user_message: `[環境] 台北 早上 10:23，外面 多雲 22°C 濕度 65%`
- the Persona teaches the LLM to "bring it in naturally, do not be a weather broadcaster"

### Persona v3: pet-first personality (4777 bytes, from `tools/llm_eval/persona.txt`)
- **70% puppy / 20% childlike / 10% home guardian** (Olaf-inspired but not imitation)
- Core line: "The most important thing is not completing tasks, but making people feel: there is a little fellow at home"
- The personality principles split into two columns "do these / avoid these"; explicitly forbids a customer-service tone, no flattery, do not throw a question in every sentence, do not proactively list features
- Guardian-mode override: fall / stranger / danger → immediately serious, no cuteness, no derailing
- Reply length determined by context: chit-chat 1-2 sentences / explanation 2-4 sentences / story / comfort / resonance can be long
- Added a clear distinction "short-term conversation memory vs long-term face database" — to prevent the LLM from using "I can't see your face" to refuse to answer about things remembered short-term
- `RuleBrain` `REPLY_TEMPLATES` upgraded to a more human version in sync (`[excited] 嗨！我在這裡，今天過得怎麼樣？` etc.)
- `tools/llm_eval/run_eval.py` alias `gemini` → `google/gemini-2.5-flash` (switched from `gemini-3-flash-preview` to stable)

### Truncation Bug real culprit — Stale `install/`
In the evening we repeatedly observed "reply truncated to 30-40 chars at a Chinese comma or where there is no punctuation"; the diagnose path:
1. ❌ initially suspected a `gemini-3-flash-preview` preview model bug → switched to `gemini-2.5-flash` → still truncated
2. ❌ suspected a common Gemini-series structured-output problem → switched to `deepseek/deepseek-v4-flash` → still truncated
3. ❌ suspected `temperature=0.2` was too low → changed to 0.7 → still truncated
4. ❌ suspected `openrouter_request_timeout_s=4.0` was short → changed to 30s → still truncated
5. ❌ suspected the conversation history contained truncated-sample pollution → cleared it → still truncated
6. ✅ curled OpenRouter DeepSeek directly, **got the full 138-token story** → confirmed the API layer is fine
7. ✅ compared md5: the WSL source matches the Jetson source, but the **Jetson `install/` directory is stale**!
   - Jetson source: `6f8edce4...`
   - Jetson install: `0f8952ca...` ← contains the old cap=40 truncation logic
   - All night's code changes had no effect (only the ROS param overrides + persona file worked, because they are read at runtime)
8. **Fix**: `colcon build --packages-select speech_processor --symlink-install`; future source changes still need a rebuild, but the install layout goes egg-link → build/, so drift will be more conspicuous

### To be verified
- The first full smoke test after the rebuild has not been run, to confirm the reply no longer sticks at 40 chars
- The comparison of DeepSeek V4 Flash vs Gemini 2.5 Flash under "real long-reply" conditions has not been done (previous A/Bs were all corrupted by the stale install, invalid)

## 5/6 night — Phase 0.5 Cut 1 (chat_candidate SkillProposal contract)

Full spec / plan:
- Spec: `docs/architecture/specs/2026-05-06-conversation-engine-langgraph-design.md`
- Plan: `docs/archive/pawai-brain-legacy/plans/2026-05-06-conversation-engine-phase-0-5.md` (3 cuts / 20 tasks)
- Contract: `docs/contracts/interaction_contract.md` v2.7

### `/brain/chat_candidate` schema (existing + 4 fields added in Phase 0.5)

```json
{
  "session_id": "speech-...",
  "reply_text": "汪我會看你會聽你...",
  "intent": "chat",
  "selected_skill": null,            // legacy diagnostic (4 P0 skills)
  "reasoning": "openrouter:eval_schema",
  "confidence": 0.82,
  // ── Phase 0.5 additions ──
  "proposed_skill": "show_status",   // null | "show_status" | "self_introduce" (the brain allowlist decides acceptance)
  "proposed_args": {},
  "proposal_reason": "openrouter:eval_schema",
  "engine": "legacy"                 // legacy | langgraph
}
```

`extract_proposal()` (`speech_processor/llm_contract.py`) carries `skill` / `args` directly from the persona JSON into the new fields, bypassing `adapt_eval_schema`'s 4-skill SKILL_TO_CMD filtering. `chat_reply` / `say_canned` are treated as "proposals with no side effect" and are filtered to `None` to avoid the brain trace being mistakenly judged as rejected.

### Brain-side execution policy (`interaction_executive/brain_node.py`)

```python
LLM_PROPOSABLE_SKILLS = frozenset({"show_status", "self_introduce"})
LLM_PROPOSAL_EXECUTE = {
    "show_status":    "execute",       # chat_reply + actually execute show_status
    "self_introduce": "trace_only",    # chat_reply only; the motion sequence is reserved for the Studio button
}
```

Each chat_candidate always first enqueues `chat_reply` (when reply_text is non-empty); the proposal additionally goes through allowlist + cooldown + safety gate, and all four states accepted/accepted_trace_only/blocked/rejected_not_allowed publish `/brain/conversation_trace`.

### TTS chunking (5/6 night, corresponding to Gemini 3.1 Flash Preview tail-truncation behavior)

`TTSProvider_OpenRouterGemini` adds:
- `CHUNK_MAX_CHARS = 60` (bumped from 40 on 5/11 night; MIN_SPLIT_CHARS=45): Gemini Flash TTS Preview randomly cuts the last 25% on ≥ 80-char input; below 60 chars it is stable and halves the number of chunk boundaries.
- `_AUDIO_TAG_RE`: detects a leading `[whispers]` / `[playful]` etc., prepending it to each segment to ensure voice consistency (otherwise chunk 2+ reverts to the default voice).
- `ThreadPoolExecutor` parallel synthesize: N segments hit OpenRouter `/audio/speech` simultaneously, wall ≈ single-segment time (not N × single segment).
- **5/11 night** `pcm_trim.py`: trims Gemini's internal silence padding before concatenating each chunk (keeping an 80ms tail). `ChunkTrimError` for a non-empty input → silent, fail-loud to the fallback chain.
- Full observability log: `chunks parallel sizes=[..]`, `chunk[N] ok / FAILED`, `N/N chunks ok in Xs wall, Ys audio after trim (saved Xms silence)`.
- **PAWAI_TTS_DIAG=1** (env-gated): turns on extra per-chunk text preview + peak/rms/duration_ms + per-chunk trim lead/tail ms. Off by default, zero overhead.

**5/11 night sentence-skip root cause pinned as H1 parallel voice drift** (RMS differs by 2x between chunks), not trim/split/tail-drop.
See the "5/11 night addendum: chunk-boundary silence + sentence-skip root cause pinned" section above. The next fix goes sequential synthesis or
post-synth RMS normalize.

### Persona (`tools/llm_eval/persona.txt`)

Added a list of 8 concrete features (voice chat / recognize acquaintances / read gestures / read posture / read objects / read stories and poems / OK action / safety), explicitly stating the LLM should not make up things it cannot do. When asked "what can you do" it should concretely pick 2-4 from the list.

---

## Next steps

- [x] **OpenRouter integration** (completed 5/4, B1 Plan D): both LLM/TTS go through OpenRouter, the five-tier fallback chain fully connected
- [x] **LLM prompt smartening** (5/5 evening): persona v3 pet personality / max_reply_chars=0 unlocked / conversation memory / environment context
- [x] **Phase 0.5 Cut 1** (5/6 night): chat_candidate SkillProposal contract + brain allowlist + Studio trace + Gemini 3 Flash Preview primary
- [ ] **Phase 0.5 Cut 2**: `pawai_brain` ROS2 package shadow skeleton (4 graph nodes + LangGraph dependency spike)
- [ ] **Phase 0.5 Cut 3**: extract 5 pure conversation/ modules from `llm_bridge_node` (zero behavior change)
- [ ] **Gemini TTS sentence-skip fix**: preamble + retry (plan: `~/.claude/plans/gemini-api-nifty-rain.md`)
- [ ] **Full smoke after the stale install/ rebuild**: 3 fixed prompts (bedtime story / introduce features / tired-and-chatting), confirm long replies are not cut
- [ ] **Long-term continuous model A/B**: DeepSeek V4 Flash vs Gemini 2.5 Flash, observing persona performance / latency / cost
- [ ] **LangGraph refactor evaluation (backlog)**: currently the chat + tool calling logic is scattered across `llm_bridge_node` (1100 lines) + `brain_node`; the user suggests moving it to `pawai-studio/backend/chat_agent/`, to be done after the 5/16 demo
- [ ] Plan B canned-line design: at least 15 Q&A sets (Chen Ruo-en)
- [ ] B1-4 Ollama 1.5B offline stress test (verify the fallback path)
- [ ] B1-5 Megaphone 16kHz end-to-end (Despina downsampling)

## Subfolders

| Folder | Content |
|--------|------|
| research/ | Voice pipeline analysis reports |
| archive/ | Jetson MVP test records (73K) |
