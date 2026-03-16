#!/usr/bin/env bash
# GPU Server Health Check — 每分鐘 ping healthchecks.io
# 部署方式：在 RTX 8000 上加到 crontab
#   crontab -e
#   * * * * * HC_PING_URL="https://hc-ping.com/YOUR-UUID" /home/roy422/gpu-server-healthcheck.sh
#
# healthchecks.io 設定建議：Period=1min, Grace=5min

set -euo pipefail

HC_PING_URL="${HC_PING_URL:-}"

if [ -z "$HC_PING_URL" ]; then
  echo "ERROR: HC_PING_URL not set"
  exit 1
fi

# 收集系統資訊
LOAD=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo "N/A")
MEM_AVAIL=$(awk '/MemAvailable/{printf "%.0fG", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo "N/A")

# 檢查 GPU 狀態
GPU_STATUS=$(nvidia-smi --query-gpu=index,temperature.gpu,utilization.gpu,memory.used,memory.total \
  --format=csv,noheader,nounits 2>/dev/null)
if [ $? -ne 0 ]; then
  curl -fsS --retry 3 --max-time 10 "${HC_PING_URL}/fail" \
    --data-raw "nvidia-smi failed | load=${LOAD}" > /dev/null 2>&1
  exit 1
fi

# 檢查 vLLM API
VLLM_RESP=$(curl -s --connect-timeout 3 --max-time 5 http://localhost:8000/v1/models 2>/dev/null || true)
VLLM_MODEL=$(echo "$VLLM_RESP" | grep -oP '"id"\s*:\s*"\K[^"]+' 2>/dev/null || echo "")

# 組合報告
REPORT="load=${LOAD} mem_avail=${MEM_AVAIL}"
REPORT="${REPORT}\nGPU: ${GPU_STATUS}"

if [ -z "$VLLM_MODEL" ]; then
  REPORT="${REPORT}\nvLLM: DOWN"
  # vLLM 掛了 → /fail，這樣 healthchecks.io 會發通知
  curl -fsS --retry 3 --max-time 10 "${HC_PING_URL}/fail" \
    --data-raw "$(echo -e "$REPORT")" > /dev/null 2>&1
else
  REPORT="${REPORT}\nvLLM: ${VLLM_MODEL}"
  curl -fsS --retry 3 --max-time 10 "${HC_PING_URL}" \
    --data-raw "$(echo -e "$REPORT")" > /dev/null 2>&1
fi
