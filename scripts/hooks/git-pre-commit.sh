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
# One isolated invocation per affected package.  Several test/ dirs contain
# __init__.py; a combined run collides on the top-level 'test' package and
# produces "ModuleNotFoundError: No module named 'test.test_validator'".
# Per-package isolation mirrors CI fast-gate behaviour.
#
# Format: "<staged-path-prefix>|<pythonpath-entry>|<pytest args>"
#
# Excluded by design:
#   tools/pawai_cli     — ~300s real network timeouts on dev machines;
#                         CI fast-gate invocation 4 covers it.
#   go2_robot_sdk       — CI invocation 6 covers it; keeps hook <10s budget.
#   nav_capability/test/integration — NEVER automate: test_mux_priority drives
#                         a real 0.30 m/s cmd_vel through the mux
#                         (2026-04-26 runaway incident).
#
# interaction_executive uses an explicit 6-file list: the remaining test files
# import rclpy/std_msgs transitively and fail without ROS on PATH (mirrors CI
# invocation 3).
SUITES=(
  "speech_processor/|speech_processor|speech_processor/test/"
  "vision_perception/|vision_perception|vision_perception/test/"
  "face_perception/|face_perception|face_perception/test/"
  "interaction_executive/|pawai_contracts:interaction_executive|interaction_executive/test/test_attention_machine.py interaction_executive/test/test_pending_confirm.py interaction_executive/test/test_skill_contract.py interaction_executive/test/test_skill_contract_demo_fields.py interaction_executive/test/test_skill_queue.py interaction_executive/test/test_state_machine.py"
  "pawai_brain/|pawai_contracts:pawai_brain|pawai_brain/test/"
  "nav_capability/|nav_capability|nav_capability/test/ --ignore=nav_capability/test/integration"
  "object_perception/|object_perception|object_perception/test/"
)

for spec in "${SUITES[@]}"; do
  prefix="${spec%%|*}"
  rest="${spec#*|}"
  pp="${rest%%|*}"
  args="${rest#*|}"
  if echo "$STAGED" | grep -q "^${prefix}"; then
    echo "[pre-commit] Running ${pp} tests..."
    # shellcheck disable=SC2086
    if ! PYTHONPATH="${pp}${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest $args -q --tb=line 2>&1; then
      echo "[pre-commit] BLOCKED: tests failed (${pp})." >&2
      exit 1
    fi
  fi
done

echo "[pre-commit] All checks passed."
exit 0
