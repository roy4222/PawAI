#!/usr/bin/env bash
set -u

echo "== pawai doctor =="
pawai doctor || true

echo
echo "== pawai status --short =="
pawai status --short || true

echo
echo "== module quick links =="
for module in brain speech face gesture pose object nav studio; do
  echo "--- $module ---"
  pawai dev info "$module" 2>/dev/null | sed -n '1,16p' || true
done
