#!/usr/bin/env bash
# PreToolUse Hook: block dangerous commands and secret file access
# Exit 2 = BLOCK the tool call
# Exit 0 = allow

set -euo pipefail

INPUT="${CLAUDE_TOOL_INPUT:-}"

# --- 1) Block destructive commands ---
if echo "$INPUT" | grep -qE 'rm\s+(-[a-zA-Z]*)?r[a-zA-Z]*f|rm\s+(-[a-zA-Z]*)?f[a-zA-Z]*r'; then
  echo "BLOCK: rm -rf is not allowed. Please delete files individually." >&2
  exit 2
fi

if echo "$INPUT" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCK: git reset --hard is not allowed. Use git stash or git checkout <file> instead." >&2
  exit 2
fi

if echo "$INPUT" | grep -qE 'git\s+push\s+.*--force'; then
  echo "BLOCK: git push --force / --force-with-lease is not allowed without explicit user approval." >&2
  exit 2
fi

# --- 2) Block secret file access (but allow .example / .sample / .template) ---
if echo "$INPUT" | grep -qE '\.(env|pem|key)(\s|"|$|/)'; then
  if ! echo "$INPUT" | grep -qE '\.(env|pem|key)\.(example|sample|template)'; then
    echo "BLOCK: Access to secret files (.env/.pem/.key) is not allowed. Use .env.example instead." >&2
    exit 2
  fi
fi

if echo "$INPUT" | grep -qiE 'credentials(\s|"|$|\.json|\.yaml|\.yml)'; then
  if ! echo "$INPUT" | grep -qiE 'credentials\.(example|sample|template)'; then
    echo "BLOCK: Access to credentials files is not allowed." >&2
    exit 2
  fi
fi

exit 0
