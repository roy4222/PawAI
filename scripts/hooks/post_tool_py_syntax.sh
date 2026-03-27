#!/usr/bin/env bash
# PostToolUse Hook: code quality checks after Edit/Write
#   - .py files: py_compile syntax check
#   - .ts/.tsx/.js/.jsx files in pawai-studio: eslint --fix
# Exit 2 = report error
# Exit 0 = all good

set -euo pipefail

INPUT="${CLAUDE_TOOL_INPUT:-}"
REPO_ROOT="/home/roy422/newLife/elder_and_dog"
FRONTEND_DIR="${REPO_ROOT}/pawai-studio/frontend"

# Extract file_path from tool input
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [[ -z "$FILE" ]] || [[ ! -f "$FILE" ]]; then
  exit 0
fi

# --- Python: py_compile + import sanity ---
if [[ "$FILE" == *.py ]]; then
  # 1. Syntax check (blocking)
  if ! python3 -m py_compile "$FILE" 2>&1; then
    echo "SYNTAX ERROR in $FILE — please fix before proceeding." >&2
    exit 2
  fi
  # 2. Quick import sanity: detect duplicate imports (warning only)
  python3 -c "
import ast, sys
with open('$FILE') as f:
    tree = ast.parse(f.read())
seen = set()
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        key = ast.dump(node)
        if key in seen:
            mod = getattr(node, 'module', '') or ''
            names = ', '.join(a.name for a in node.names)
            print(f'DUPLICATE IMPORT: {mod}.{names} (line {node.lineno})', file=sys.stderr)
        seen.add(key)
" 2>&1 || true
  exit 0
fi

# --- Frontend (ts/tsx/js/jsx): eslint --fix ---
if [[ "$FILE" == *.ts || "$FILE" == *.tsx || "$FILE" == *.js || "$FILE" == *.jsx ]]; then
  # Only run for files inside pawai-studio/frontend
  if [[ "$FILE" == "${FRONTEND_DIR}"/* ]]; then
    if [[ -x "${FRONTEND_DIR}/node_modules/.bin/eslint" ]]; then
      cd "$FRONTEND_DIR"
      # --fix auto-corrects fixable issues, non-zero exit = unfixable errors
      if ! ./node_modules/.bin/eslint --fix "$FILE" 2>&1; then
        echo "ESLINT ERRORS in $FILE — please fix before proceeding." >&2
        exit 2
      fi
    fi
  fi
  exit 0
fi

exit 0
