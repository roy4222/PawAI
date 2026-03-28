#!/usr/bin/env bash
# Detect USB audio devices (microphone + speaker) and export indices.
#
# !! MUST use `source`, not `bash` !!
#   source scripts/device_detect.sh
#
# Exports:
#   DETECTED_MIC_INDEX        — ALSA card number for USB microphone (e.g. "24")
#   DETECTED_MIC_CHANNELS     — 1 (UACDemo mono) or 2 (HyperX stereo-only)
#   DETECTED_CAPTURE_RATE     — 48000 (UACDemo) or 44100 (HyperX)
#   DETECTED_SPK_DEVICE       — ALSA playback device for USB speaker (e.g. "plughw:3,0")
#
# If detection fails, exports empty string + prints WARNING.
# Does NOT exit on failure (safe to source from other scripts).

echo "=== USB Audio Device Detection ==="

# ── Microphone ──
# Primary: UACDemoV1.0 (USB mono mic, 48kHz)
# Fallback: any USB audio input
_mic_card=""
_mic_line=$(arecord -l 2>/dev/null | grep -i "UAC\|UACDemo" | head -1 || true)
if [ -n "$_mic_line" ]; then
    _mic_card=$(echo "$_mic_line" | sed 's/card \([0-9]*\):.*/\1/')
fi
if [ -z "$_mic_card" ]; then
    _mic_line=$(arecord -l 2>/dev/null | grep -i "USB" | head -1 || true)
    if [ -n "$_mic_line" ]; then
        _mic_card=$(echo "$_mic_line" | sed 's/card \([0-9]*\):.*/\1/')
    fi
fi

if [ -n "$_mic_card" ]; then
    export DETECTED_MIC_INDEX="$_mic_card"
    # Determine channels + sample rate based on device type
    if echo "$_mic_line" | grep -qi "UAC\|UACDemo"; then
        # UACDemoV1.0: mono, 48kHz
        export DETECTED_MIC_CHANNELS="1"
        export DETECTED_CAPTURE_RATE="48000"
        _mic_type="UACDemo (mono/48kHz)"
    elif echo "$_mic_line" | grep -qi "HyperX\|SoloCast"; then
        # HyperX SoloCast: stereo-only hardware, must use channels=2 + manual downmix
        export DETECTED_MIC_CHANNELS="2"
        export DETECTED_CAPTURE_RATE="44100"
        _mic_type="HyperX (stereo/44100Hz)"
    else
        # Unknown USB mic: assume mono/48kHz, safer default
        export DETECTED_MIC_CHANNELS="1"
        export DETECTED_CAPTURE_RATE="48000"
        _mic_type="Unknown USB (assuming mono/48kHz)"
    fi
    echo "  Mic: card $_mic_card — $_mic_type"
    echo "       ($_mic_line)"
else
    export DETECTED_MIC_INDEX=""
    export DETECTED_MIC_CHANNELS=""
    export DETECTED_CAPTURE_RATE=""
    echo "  [WARNING] USB microphone not found"
fi

# ── Speaker ──
# Primary: CD002-AUDIO (USB speaker)
# Fallback: any USB audio output
_spk_card=""
_spk_line=$(aplay -l 2>/dev/null | grep -i "CD002" | head -1 || true)
if [ -n "$_spk_line" ]; then
    _spk_card=$(echo "$_spk_line" | sed 's/card \([0-9]*\):.*/\1/')
fi
if [ -z "$_spk_card" ]; then
    _spk_line=$(aplay -l 2>/dev/null | grep -i "USB" | head -1 || true)
    if [ -n "$_spk_line" ]; then
        _spk_card=$(echo "$_spk_line" | sed 's/card \([0-9]*\):.*/\1/')
    fi
fi

if [ -n "$_spk_card" ]; then
    export DETECTED_SPK_DEVICE="plughw:${_spk_card},0"
    echo "  Speaker: plughw:${_spk_card},0 ($_spk_line)"
else
    export DETECTED_SPK_DEVICE=""
    echo "  [WARNING] USB speaker not found"
fi

# ── RealSense D435 ──
_d435_found="no"
if ls /dev/video* >/dev/null 2>&1; then
    _d435_count=$(ls /dev/video* 2>/dev/null | wc -l || true)
    if [ "$_d435_count" -gt 0 ]; then
        _d435_found="yes ($_d435_count video devices)"
    fi
fi
echo "  D435: $_d435_found"

echo ""
echo "=== Summary ==="
echo "  DETECTED_MIC_INDEX=$DETECTED_MIC_INDEX"
echo "  DETECTED_MIC_CHANNELS=$DETECTED_MIC_CHANNELS"
echo "  DETECTED_CAPTURE_RATE=$DETECTED_CAPTURE_RATE"
echo "  DETECTED_SPK_DEVICE=$DETECTED_SPK_DEVICE"
echo ""
echo "Usage in start_full_demo_tmux.sh:"
echo "  INPUT_DEVICE=\$DETECTED_MIC_INDEX CHANNELS=\$DETECTED_MIC_CHANNELS CAPTURE_SAMPLE_RATE=\$DETECTED_CAPTURE_RATE LOCAL_OUTPUT_DEVICE=\$DETECTED_SPK_DEVICE bash scripts/start_full_demo_tmux.sh"

# Clean up temp variables (don't pollute caller's namespace)
unset _mic_card _mic_line _mic_type _spk_card _spk_line _d435_found _d435_count
