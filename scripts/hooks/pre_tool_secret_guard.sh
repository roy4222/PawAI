#!/usr/bin/env bash
# PreToolUse Hook for Edit/Write: block access to secret files
# Exit 2 = BLOCK the tool call
# Exit 0 = allow

set -euo pipefail

INPUT="${CLAUDE_TOOL_INPUT:-}"

# Extract file_path from tool input
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if [[ -z "$FILE" ]]; then
  exit 0
fi

BASENAME=$(basename "$FILE")

# Allow safe patterns: .env.example, .env.sample, .env.template, etc.
if echo "$BASENAME" | grep -qE '\.(example|sample|template)$'; then
  exit 0
fi

# Block real secret files
if echo "$BASENAME" | grep -qE '^\.env$|^\.env\.' ; then
  echo "BLOCK: Edit/Write to secret file '$BASENAME' is not allowed. Use .env.example instead." >&2
  exit 2
fi

if echo "$BASENAME" | grep -qiE '\.(pem|key)$'; then
  echo "BLOCK: Edit/Write to key file '$BASENAME' is not allowed." >&2
  exit 2
fi

if echo "$BASENAME" | grep -qiE '^credentials\.(json|yaml|yml)$'; then
  echo "BLOCK: Edit/Write to credentials file '$BASENAME' is not allowed." >&2
  exit 2
fi

exit 0
