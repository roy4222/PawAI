#!/usr/bin/env bash
# Stop Verifier Hook: hard checks + dual model review
#   Phase 1: Hard verification (py_compile, eslint) → exit 2 = BLOCK + retry
#   Phase 2: Colcon build reminder (info only)
#   Phase 3a: Codex review (advisory, never blocks)
#   Phase 3b: Haiku review (advisory, never blocks)
#
# Retry mechanism:
#   - Uses a counter file to track attempts
#   - Hard checks: block up to MAX_RETRIES times, then release
#   - Haiku review: never blocks, always advisory

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$REPO_ROOT"

# --- Retry counter ---
MAX_RETRIES=3
SESSION_COUNTER="/tmp/claude_stop_verifier_${PPID}"

ATTEMPT=1
if [[ -f "$SESSION_COUNTER" ]]; then
  ATTEMPT=$(cat "$SESSION_COUNTER")
  ATTEMPT=$((ATTEMPT + 1))
fi
echo "$ATTEMPT" > "$SESSION_COUNTER"

# --- Collect changed files (staged + unstaged vs HEAD + untracked) ---
CHANGED=$(git diff --name-only HEAD 2>/dev/null || true)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || true)
CHANGED=$(printf '%s\n%s' "$CHANGED" "$UNTRACKED" | sort -u | sed '/^$/d')

if [[ -z "$CHANGED" ]]; then
  rm -f "$SESSION_COUNTER"
  exit 0
fi

# ========================================
# Phase 1: HARD VERIFICATION (can block)
# ========================================
ERRORS=""

# 1a) Python syntax check (py_compile)
PY_FILES=$(echo "$CHANGED" | grep '\.py$' || true)
if [[ -n "$PY_FILES" ]]; then
  while IFS= read -r pyf; do
    if [[ -f "$pyf" ]]; then
      if ! python3 -m py_compile "$pyf" 2>&1; then
        ERRORS="${ERRORS}\nSYNTAX ERROR: $pyf"
      fi
    fi
  done <<< "$PY_FILES"
fi

# 1b) Frontend eslint check
FRONTEND_DIR="${REPO_ROOT}/pawai-studio/frontend"
TS_FILES=$(echo "$CHANGED" | grep -E '\.(ts|tsx|js|jsx)$' | grep '^pawai-studio/frontend/' || true)
if [[ -n "$TS_FILES" ]] && [[ -x "${FRONTEND_DIR}/node_modules/.bin/eslint" ]]; then
  while IFS= read -r tsf; do
    FULL_PATH="${REPO_ROOT}/${tsf}"
    if [[ -f "$FULL_PATH" ]]; then
      if ! (cd "$FRONTEND_DIR" && ./node_modules/.bin/eslint "$FULL_PATH" 2>&1); then
        ERRORS="${ERRORS}\nESLINT ERROR: $tsf"
      fi
    fi
  done <<< "$TS_FILES"
fi

# If hard checks failed → block (up to MAX_RETRIES)
if [[ -n "$ERRORS" ]]; then
  echo ""
  echo "=== VERIFIER FAILED (attempt ${ATTEMPT}/${MAX_RETRIES}) ==="
  echo -e "$ERRORS"
  echo "==============================="
  echo ""

  if [[ $ATTEMPT -lt $MAX_RETRIES ]]; then
    echo "Fix the errors above and try again." >&2
    exit 2  # BLOCK → Claude Code will retry
  else
    echo "Max retries reached. Releasing with warnings." >&2
    rm -f "$SESSION_COUNTER"
    exit 0  # Release to avoid infinite loop
  fi
fi

# Hard checks passed → reset counter
rm -f "$SESSION_COUNTER"

# ========================================
# Phase 2: COLCON BUILD REMINDER (info only)
# ========================================
NEED_BUILD=""
if echo "$PY_FILES" | grep -qE '^speech_processor/' 2>/dev/null; then
  NEED_BUILD="${NEED_BUILD}speech_processor "
fi
if echo "$PY_FILES" | grep -qE '^go2_robot_sdk/' 2>/dev/null; then
  NEED_BUILD="${NEED_BUILD}go2_robot_sdk "
fi

if [[ -n "$NEED_BUILD" ]]; then
  echo ""
  echo "=== REMINDER ==="
  echo "You modified .py files in: ${NEED_BUILD}"
  echo "Before testing on Jetson, run:"
  echo "  colcon build --packages-select ${NEED_BUILD}"
  echo "  source install/setup.zsh"
  echo "================"
  echo ""
fi

# ========================================
# Phase 3: DUAL MODEL REVIEW — DISABLED
# ========================================
# Codex + Haiku auto-review 已關閉，改用 /review skill 手動觸發。
# 原因：每次 Stop 都呼叫外部 LLM，最多等 50 秒，拖慢開發節奏。

exit 0
