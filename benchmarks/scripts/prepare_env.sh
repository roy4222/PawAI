#!/bin/bash
# benchmarks/scripts/prepare_env.sh
# Lock Jetson to MAXN mode for reproducible benchmarks.
# Usage: sudo bash prepare_env.sh [--drop-cache]
set -euo pipefail

echo "=== Setting MAXN power mode ==="
nvpmodel -m 0
echo "=== Locking clocks ==="
jetson_clocks

if [[ "${1:-}" == "--drop-cache" ]]; then
    echo "=== Dropping page cache ==="
    sync
    echo 3 > /proc/sys/vm/drop_caches
fi

echo "=== Environment ready ==="
nvpmodel -q
jetson_clocks --show
