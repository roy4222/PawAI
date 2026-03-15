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
# Phase 3: DUAL MODEL REVIEW (advisory, never blocks)
# ========================================
CODE_CHANGED=$(echo "$CHANGED" | grep -E '\.(py|ts|tsx|js|jsx|yaml|yml|launch\.py)$' || true)

if [[ -z "$CODE_CHANGED" ]]; then
  exit 0
fi

# --- 3a) Codex review (independent reviewer, different model) ---
if command -v codex &>/dev/null; then
  echo ""
  echo "=== CODE REVIEW (Codex) ==="
  timeout 20s codex review --uncommitted "只回報 bug/security/crash，忽略風格建議。回覆限制在 5 行以內，用繁體中文。" 2>/dev/null || echo "（Codex review 跳過：超時或 CLI 呼叫失敗）"
  echo "==========================="
  echo ""
fi

# --- 3b) Haiku review (second opinion, different model) ---
# Build diff for Haiku (tracked + untracked)
TRACKED_CODE=$(echo "$CODE_CHANGED" | while IFS= read -r f; do
  git ls-files --error-unmatch "$f" &>/dev/null && echo "$f"
done 2>/dev/null || true)
UNTRACKED_CODE=$(echo "$CODE_CHANGED" | while IFS= read -r f; do
  git ls-files --error-unmatch "$f" &>/dev/null || echo "$f"
done 2>/dev/null || true)

DIFF=""
if [[ -n "$TRACKED_CODE" ]]; then
  DIFF=$(git diff HEAD -- $TRACKED_CODE 2>/dev/null | head -150)
fi
if [[ -n "$UNTRACKED_CODE" ]]; then
  for f in $UNTRACKED_CODE; do
    DIFF="${DIFF}
--- NEW FILE: $f ---
$(head -50 "$f" 2>/dev/null || true)"
  done
fi
DIFF=$(echo "$DIFF" | head -200)

if [[ -n "$DIFF" ]] && [[ $(echo "$DIFF" | wc -l) -ge 3 ]]; then
  if command -v claude &>/dev/null; then
    echo ""
    echo "=== CODE REVIEW (Haiku) ==="

    REVIEW=$(echo "$DIFF" | timeout 20s claude --model haiku -p "你是嚴格的 code reviewer（Linus Torvalds 風格）。
審查以下 git diff，只回報：
1. 明顯的 bug 或邏輯錯誤
2. 安全風險（硬編碼密碼、注入漏洞等）
3. 會導致 runtime crash 的問題

不要回報：風格問題、命名建議、缺少註解、可能的改善。
如果沒有嚴重問題，只回覆「LGTM」。
回覆限制在 5 行以內，用繁體中文。" 2>/dev/null || echo "（Haiku review 跳過：CLI 呼叫失敗）")

    echo "$REVIEW"
    echo "==========================="
    echo ""
  fi
fi

exit 0
