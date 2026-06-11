#!/usr/bin/env bash
# Regression tests for the Claude Code guard hooks (S0 security hardening,
# findings CI-01 / CI-02 / CI-03).  Each case feeds a crafted CLAUDE_TOOL_INPUT
# JSON to a hook and asserts its exit code / side effects.
#
# Run:  bash scripts/hooks/test_secret_guards.sh
# Exit: 0 = all pass, 1 = some fail.
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAFETY="$HOOK_DIR/pre_tool_safety.sh"
GUARD="$HOOK_DIR/pre_tool_secret_guard.sh"
PYSYN="$HOOK_DIR/post_tool_py_syntax.sh"

PASS=0
FAIL=0

# run_case <name> <expected_exit> <hook> <json_input>
run_case() {
  local name="$1" expected="$2" hook="$3" json="$4"
  CLAUDE_TOOL_INPUT="$json" bash "$hook" >/dev/null 2>&1
  local rc=$?
  if [[ "$rc" == "$expected" ]]; then
    PASS=$((PASS+1)); echo "  ✅ $name (exit $rc)"
  else
    FAIL=$((FAIL+1)); echo "  ❌ $name (got $rc, want $expected)"
  fi
}

echo "── CI-01: pre_tool_safety.sh dotted-env (Bash) ──"
run_case "block cat .env"            2 "$SAFETY" '{"command":"cat .env"}'
run_case "block cat .env.local"      2 "$SAFETY" '{"command":"cat .env.local"}'
run_case "block cat .env.production" 2 "$SAFETY" '{"command":"cat .env.production"}'
run_case "allow cat .env.example"    0 "$SAFETY" '{"command":"cat .env.example"}'
run_case "allow normal ls"           0 "$SAFETY" '{"command":"ls -la /tmp"}'
run_case "still block rm -rf"        2 "$SAFETY" '{"command":"rm -rf /tmp/x"}'

echo "── CI-02: pre_tool_secret_guard.sh used by Read ──"
run_case "block read .env"           2 "$GUARD" '{"file_path":"/repo/.env"}'
run_case "block read .env.local"     2 "$GUARD" '{"file_path":"/repo/.env.local"}'
run_case "allow read .env.example"   0 "$GUARD" '{"file_path":"/repo/.env.example"}'
run_case "allow read normal.py"      0 "$GUARD" '{"file_path":"/repo/normal.py"}'
run_case "block read id_rsa.key"     2 "$GUARD" '{"file_path":"/repo/id_rsa.key"}'

echo "── CI-03: post_tool_py_syntax.sh passes file_path via argv (no source interpolation) ──"
# The dup-import check must NOT interpolate $FILE into python source
# (`open('$FILE')`); it must receive the path as argv (sys.argv). A
# single-quote in a filename would otherwise break out of the string literal.
# Static guard: interpolation absent, argv present.
if grep -qE "open\('\\\$FILE'\)" "$PYSYN"; then
  FAIL=$((FAIL+1)); echo "  ❌ still interpolates open('\$FILE') into python -c"
else
  PASS=$((PASS+1)); echo "  ✅ no open('\$FILE') source interpolation"
fi
if grep -q "sys.argv" "$PYSYN"; then
  PASS=$((PASS+1)); echo "  ✅ passes file_path via sys.argv"
else
  FAIL=$((FAIL+1)); echo "  ❌ does not use sys.argv for file_path"
fi
# Behavioural: a .py file whose name contains a single quote must still be
# syntax-checked without the hook crashing (exit 0 on valid content).
TMPD="$(mktemp -d)"
QFILE="$TMPD/we'ird.py"
printf 'x = 1\n' > "$QFILE"
run_case "quote-in-name .py handled" 0 "$PYSYN" "{\"file_path\":\"$TMPD/we'ird.py\"}"
rm -rf "$TMPD"

echo "─────────────────────────────"
echo "PASS=$PASS FAIL=$FAIL"
[[ "$FAIL" == 0 ]]
