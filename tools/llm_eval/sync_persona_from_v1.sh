#!/usr/bin/env bash
# sync_persona_from_v1.sh — 同步 personas/v1/*.md → tools/llm_eval/persona.txt
#
# 用途：eval runner 用 persona.txt（單檔）做 system prompt，但 source of truth
# 是 pawai_brain/personas/v1/ 5 檔（Brain Minimum 後變 6 檔含 MISSION.md）。
# 每次改 personas/v1/ 後跑這個 script 同步，避免 eval 結果跟實機不一致。
#
# 順序與 _load_persona BASE_ORDER 一致：
#   IDENTITY → MISSION → STYLE → OUTPUT → EXAMPLES
# 不含 CAPABILITIES.md（lazy injection in _build_user_message）。
#
# Usage:
#   bash tools/llm_eval/sync_persona_from_v1.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_DIR="$ROOT/pawai_brain/personas/v1"
DST_FILE="$ROOT/tools/llm_eval/persona.txt"

BASE_ORDER=(IDENTITY.md MISSION.md STYLE.md OUTPUT.md EXAMPLES.md)

for f in "${BASE_ORDER[@]}"; do
  if [[ ! -f "$SRC_DIR/$f" ]]; then
    echo "❌ missing: $SRC_DIR/$f"
    exit 1
  fi
done

{
  for i in "${!BASE_ORDER[@]}"; do
    f="${BASE_ORDER[$i]}"
    cat "$SRC_DIR/$f"
    if [[ $i -lt $((${#BASE_ORDER[@]} - 1)) ]]; then
      echo
      echo
    fi
  done
} > "$DST_FILE"

LINES=$(wc -l < "$DST_FILE")
BYTES=$(wc -c < "$DST_FILE")
echo "✅ wrote $DST_FILE  (${LINES} lines, ${BYTES} bytes)"
echo "   from: ${BASE_ORDER[*]}"
