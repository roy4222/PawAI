#!/usr/bin/env bash
# Git pre-commit hook: local quality gate before every commit.
#
# Three checks, fast to slow:
#   1. py_compile on staged .py files (<1s)
#   2. Topic contract check (<2s)
#   3. Affected package tests (<3s, smart scope)
#
# Install:
#   ln -sf ../../scripts/hooks/git-pre-commit.sh .git/hooks/pre-commit
#
# Skip (escape hatch):
#   git commit --no-verify

set -uo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$REPO_ROOT"

STAGED=$(git diff --cached --name-only --diff-filter=ACM)
if [[ -z "$STAGED" ]]; then
  exit 0
fi

ERRORS=0

# ════════════════════════════════════════
# 1. Python syntax check (py_compile)
# ════════════════════════════════════════
PY_STAGED=$(echo "$STAGED" | grep '\.py$' || true)
if [[ -n "$PY_STAGED" ]]; then
  echo "[pre-commit] Checking Python syntax..."
  while IFS= read -r pyf; do
    if [[ -f "$pyf" ]]; then
      if ! python3 -m py_compile "$pyf" 2>&1; then
        echo "  SYNTAX ERROR: $pyf" >&2
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done <<< "$PY_STAGED"
fi

if [[ $ERRORS -gt 0 ]]; then
  echo "[pre-commit] BLOCKED: $ERRORS syntax error(s). Fix and re-stage." >&2
  exit 1
fi

# ════════════════════════════════════════
# 2. Topic contract check
# ════════════════════════════════════════
if [[ -f "$REPO_ROOT/scripts/ci/check_topic_contracts.py" ]]; then
  echo "[pre-commit] Checking topic contracts..."
  if ! python3 "$REPO_ROOT/scripts/ci/check_topic_contracts.py" > /dev/null 2>&1; then
    echo "[pre-commit] BLOCKED: topic contract check failed." >&2
    echo "  Run: python3 scripts/ci/check_topic_contracts.py" >&2
    exit 1
  fi
fi

# ════════════════════════════════════════
# 3. Smart-scope package tests
# ════════════════════════════════════════
TEST_ARGS=""
PYTHONPATH_EXTRA=""

if echo "$STAGED" | grep -q '^speech_processor/'; then
  TEST_ARGS="$TEST_ARGS speech_processor/test/"
  PYTHONPATH_EXTRA="speech_processor"
fi

if echo "$STAGED" | grep -q '^vision_perception/'; then
  TEST_ARGS="$TEST_ARGS vision_perception/test/"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}vision_perception"
fi

if echo "$STAGED" | grep -q '^face_perception/'; then
  TEST_ARGS="$TEST_ARGS face_perception/test/"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}face_perception"
fi

if [[ -n "$TEST_ARGS" ]]; then
  echo "[pre-commit] Running tests for affected packages..."
  if ! PYTHONPATH="${PYTHONPATH_EXTRA}:${PYTHONPATH:-}" python3 -m pytest $TEST_ARGS -q --tb=line 2>&1; then
    echo "[pre-commit] BLOCKED: tests failed." >&2
    exit 1
  fi
fi

echo "[pre-commit] All checks passed."
exit 0
