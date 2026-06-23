# Mac × 學校網路 Readiness — 5/12 移交前

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **Owner**: Roy
> **目的**：把家裡（Tailscale + 開發機 SSH tunnel + 固定 IP）→ 學校（陌生網段 + Mac 操作端 + Wi-Fi 不穩）的所有寫死 ref 抓出來、集中成 env 檔，並建 Mac wrapper。讓任何人在任何網路、有 Go2 + Jetson 都能 clone repo 跑起來。
> **基於**：subagent 寫死 ref 審計報告（27 處，3 個 P0，記在 §3）

---

## 1. 核心目標

到學校後，Roy 在 Mac 上只要這兩條命令 demo 就動：

```bash
# Mac
cd ~/elder_and_dog/pawai-studio
GATEWAY_HOST=<Jetson_IP> bash start-school-live.sh
```

```bash
# Jetson（學校）
cd ~/elder_and_dog
source config/school_demo.env
bash scripts/start_full_demo_tmux.sh
```

不能再有「現場 grep 哪裡寫死了 IP」「每個腳本手動 export」的環節。

---

## 2. 必修 P0（3 處，subagent 審計確認）

### P0-1：`speech_processor/config/speech_processor.yaml:24` ASR URL 寫死
**問題**：硬寫 `127.0.0.1:8001`，沒讀環變
**修法**：
```yaml
qwen_asr:
  base_url: "${QWEN_ASR_BASE_URL:-http://127.0.0.1:8001/v1/audio/transcriptions}"
```
ROS2 yaml 不直接支援 env 替換 → 需在 `stt_intent_node` 啟動時讀 env override，或用 launch.py 的 substitution
**工時**：5 min

### P0-2：`pawai-studio/gateway/studio_gateway.py:53` ASR_URL 寫死
**問題**：Python hardcoded `127.0.0.1:8001`
**修法**：
```python
ASR_URL = os.getenv("ASR_URL", "http://127.0.0.1:8001/v1/audio/transcriptions")
```
**工時**：3 min

### P0-3：`pawai-studio/gateway/asr_client.py:46` asr_url param
**問題**：default 寫死，caller 可能沒傳
**修法**：caller (`studio_gateway.py`) 改傳 env override 進來
**工時**：2 min

---

## 3. 集中環境檔：`config/school_demo.env`

新建檔案：

```bash
# ============================================================
# config/school_demo.env
# Demo 啟動環境設定 — 學校場地用
# Source 後再跑 start_full_demo_tmux.sh / start_nav_capability_demo_tmux.sh
# ============================================================

# --- Network: Robot ---
export ROBOT_IP="192.168.123.161"          # Go2 Ethernet 直連，這個不變
export CONN_TYPE="webrtc"
export ROS_DOMAIN_ID="0"

# --- Network: Jetson host (學校現場填) ---
export JETSON_HOST="${JETSON_HOST:-jetson-school}"   # 5/13 場勘填學校 IP
export JETSON_IP="${JETSON_IP:-}"                    # 5/13 場勘填

# --- 硬檢查：JETSON_IP 或 GATEWAY_HOST 至少要有一個 ---
# 不允許 silent default 成 http://:8080，現場會以不明確方式失敗
if [[ -z "${JETSON_IP:-}" && -z "${GATEWAY_HOST:-}" ]]; then
  echo "❌ [school_demo.env] ERROR: JETSON_IP 或 GATEWAY_HOST 至少要設一個"
  echo "   用法：JETSON_IP=192.168.x.y source config/school_demo.env"
  echo "   或：  GATEWAY_HOST=jetson-school source config/school_demo.env"
  return 1 2>/dev/null || exit 1
fi

# --- Network: Studio gateway (Mac → Jetson) ---
export GATEWAY_HOST="${GATEWAY_HOST:-${JETSON_IP}}"
export GATEWAY_PORT="${GATEWAY_PORT:-8080}"
export NEXT_PUBLIC_GATEWAY_URL="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

# --- Foxglove ---
export FOXGLOVE_PORT="${FOXGLOVE_PORT:-8765}"
export FOXGLOVE_URL="ws://${JETSON_IP}:${FOXGLOVE_PORT}"

# --- LLM / ASR endpoints ---
# 學校環境若 SSH tunnel 開好,localhost; 若直連雲端,改成雲 IP
export LLM_ENDPOINT="${LLM_ENDPOINT:-http://localhost:8000/v1/chat/completions}"
export QWEN_ASR_BASE_URL="${QWEN_ASR_BASE_URL:-http://127.0.0.1:8001/v1/audio/transcriptions}"
export ASR_URL="${ASR_URL:-${QWEN_ASR_BASE_URL}}"

# --- Map / Runtime path ---
export MAP="${MAP:-/home/jetson/maps/school_demo.yaml}"
export PBSTREAM="${PBSTREAM:-/home/jetson/maps/school_demo.pbstream}"
export MAP_DIR="${MAP_DIR:-/home/jetson/maps}"
export NAV_RUNTIME_DIR="${NAV_RUNTIME_DIR:-${HOME}/elder_and_dog/runtime/nav_capability}"
export NAV_NAMED="${NAV_NAMED:-${NAV_RUNTIME_DIR}/named_poses/main.json}"
export NAV_ROUTES="${NAV_ROUTES:-${NAV_RUNTIME_DIR}/routes/}"

# --- Models / WORKDIR ---
export WORKDIR="${WORKDIR:-${HOME}/elder_and_dog}"
export MODEL_BASE="${MODEL_BASE:-/home/jetson/models}"

# --- Modes ---
export ENABLE_LOCAL_LLM="${ENABLE_LOCAL_LLM:-false}"   # 學校網路無 tunnel 時切 true
export DEMO_MODE="${DEMO_MODE:-school}"

# --- Print summary ---
echo "[school_demo.env] ROBOT_IP=$ROBOT_IP"
echo "[school_demo.env] JETSON_IP=$JETSON_IP"
echo "[school_demo.env] GATEWAY=$NEXT_PUBLIC_GATEWAY_URL"
echo "[school_demo.env] LLM=$LLM_ENDPOINT"
echo "[school_demo.env] ASR=$ASR_URL"
echo "[school_demo.env] MAP=$MAP"
```

---

## 4. 既有腳本改造（讓所有腳本都讀 env）

### 4.1 `scripts/start_full_demo_tmux.sh`
- L18 WORKDIR 改 `${WORKDIR:-/home/jetson/elder_and_dog}`
- L41 ROBOT_IP 已環變 ✅
- L45 LLM endpoint 改 `${LLM_ENDPOINT}`
- L64 ASR 改 `${QWEN_ASR_BASE_URL}`
- L264 Foxglove port 改 `${FOXGLOVE_PORT:-8765}`

### 4.2 `scripts/start_nav_capability_demo_tmux.sh`
- L16 MAP 已環變 ✅
- 無其他寫死

### 4.3 `scripts/start_nav2_amcl_demo_tmux.sh`
- L17 MAP 已環變 ✅
- L101 ws URL 用 `hostname -I` 動態取 ✅

### 4.4 `scripts/build_map.sh`
- L13 MAP_DIR 改 `${MAP_DIR:-/home/jetson/maps}`

### 4.5 `scripts/e2e_health_check.sh`
- L2 LLM endpoint 改 `${LLM_ENDPOINT}`

### 4.6 `pawai-studio/start.sh`
- 加 `${GATEWAY_PORT:-8080}` 讀環變

### 4.7 `pawai-studio/backend/mock_server.py`
- port 8080 hardcoded → 讀環變

---

## 5. Mac wrapper：`pawai-studio/start-school-live.sh`

新建：

```bash
#!/usr/bin/env bash
# start-school-live.sh — Mac 操作端 demo 啟動 wrapper
#
# 用法：
#   GATEWAY_HOST=192.168.x.y bash start-school-live.sh
#
# 預設 GATEWAY_PORT=8080。若 GATEWAY_HOST 沒設，要求使用者手動指定。
set -euo pipefail

if [[ -z "${GATEWAY_HOST:-}" ]]; then
  echo "❌ ERROR: GATEWAY_HOST 未設定"
  echo ""
  echo "用法："
  echo "  GATEWAY_HOST=<學校 Jetson IP> bash start-school-live.sh"
  echo ""
  echo "Jetson IP 取得方式："
  echo "  ssh jetson@<JETSON_HOST> 'hostname -I'"
  exit 1
fi

export GATEWAY_PORT="${GATEWAY_PORT:-8080}"
export NEXT_PUBLIC_GATEWAY_URL="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

echo "[start-school-live] GATEWAY_HOST=$GATEWAY_HOST"
echo "[start-school-live] GATEWAY_PORT=$GATEWAY_PORT"
echo "[start-school-live] Studio URL: $NEXT_PUBLIC_GATEWAY_URL"
echo ""

# 連通性 pre-check
echo "[pre-check] ping $GATEWAY_HOST..."
ping -c 1 -W 2 "$GATEWAY_HOST" > /dev/null || {
  echo "❌ ping fail. 確認:"
  echo "   1. Jetson 開機"
  echo "   2. Mac + Jetson 在同網段"
  echo "   3. IP 正確"
  exit 1
}

echo "[pre-check] curl $NEXT_PUBLIC_GATEWAY_URL/health..."
curl -sf -m 3 "$NEXT_PUBLIC_GATEWAY_URL/health" > /dev/null || {
  echo "❌ Gateway 沒回應. 確認:"
  echo "   ssh jetson@$GATEWAY_HOST 'cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh'"
  exit 1
}

echo "[pre-check] all green ✅"
echo ""
echo "[start] launching Studio frontend..."
cd "$(dirname "$0")"
exec bash start-live.sh --live
```

`chmod +x pawai-studio/start-school-live.sh`

---

## 6. 5/12 連通性驗證 6 項（家裡用手機熱點模擬）

| # | 項 | 指令 | Pass |
|:---:|---|---|:---:|
| N1 | Mac ping Jetson | `ping -c 3 $GATEWAY_HOST` | ☐ |
| N2 | Mac → Gateway health | `curl http://$GATEWAY_HOST:8080/health` | ☐ |
| N3 | Mac → Foxglove | `wscat -c ws://$GATEWAY_HOST:8765` | ☐ |
| N4 | Mac Studio connected | browser 開 Studio 看 indicator | ☐ |
| N5 | Jetson ping Go2 | `ping -c 3 192.168.123.161` | ☐ |
| N6 | 假 GATEWAY_HOST → Studio 明確 fail | `GATEWAY_HOST=10.0.0.99 bash start-school-live.sh` 應報錯不偷連 mock | ☐ |

---

## 7. 5/12 PM 任務排程

| 時段 | 任務 |
|---|---|
| 13:00-13:15 | 建 `config/school_demo.env`（依 §3） |
| 13:15-13:45 | 修 P0-1 / P0-2 / P0-3（subagent 報告 §2） |
| 13:45-14:30 | 改造 7 個 script（§4） |
| 14:30-14:50 | 建 `pawai-studio/start-school-live.sh`（§5） |
| 14:50-15:30 | N1-N6 連通性驗證（手機熱點模擬） |
| 15:30-16:00 | git commit + push |

---

## 8. 結論表（5/12 17:00）

| 項 | 結論 |
|---|---|
| `config/school_demo.env` 落檔 | ☐ |
| P0-1/2/3 修完 | ☐ / ☐ / ☐ |
| 7 script 改成讀 env | ☐ |
| Mac wrapper `start-school-live.sh` 落檔 | ☐ |
| N1-N6 連通驗證 | ☐ x6 |
| Mac 模擬學校網段 demo 跑通 | ☐ |

---

## 9. 開源化指引（順手做）

Roy 想把這當開源專案：任何人 clone、有 Go2 + Jetson 就能跑。

### 必補文件（demo 後優先補）
- `docs/runbook/clone-and-run.md`：clone → 設環變 → 啟動 3 步驟
- `config/school_demo.env.example`：拿掉 secret，列必填欄位
- README.md 加 quick start

### demo 期最低保證（5/12 前）
- `config/school_demo.env` 在 git 內（無 secret）
- 文件提到 `cp config/school_demo.env.example config/school_demo.env` 並填入自家網段
- subagent 抓出來的 27 處寫死，至少 P0 3 項修掉、其他標記成 known stale

---

## 10. 不在這份 plan 的事

❌ Tailscale → mDNS 自動發現（demo 後）
❌ Docker compose 化（demo 後）
❌ ROS2 multi-machine 自動 sync（demo 後）

---

**End of Mac × 學校網路 Readiness**
