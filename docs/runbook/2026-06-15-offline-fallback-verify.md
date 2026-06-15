# Offline / 斷網 fallback — Roy 驗收 Runbook（無 motion）

> 日期：2026-06-15　狀態：**邏輯已驗（446 unit tests 綠）、Jetson live dry-run 待 Roy**
> 配套：`interaction_executive/interaction_executive/brain_node.py`（offline 短路 + G2 filler）、`safety_layer.py`（S5）
> 這份全程**無 Go2 motion**，可安心跑。

---

## 0. 先講結論（這次調查的事實）

- **offline_mode 端到端已接通**：ROS param `offline_mode` + topic `/brain/offline_mode` + Studio toggle 三入口共用同一個 setter，**預設 off = 與線上行為 byte-identical**。
- **S5 安全 offline 完全免疫**：rule-first 三層（`safety_layer.py`），在 phase gate / LLM / offline 短路**之前**，LLM 無法 override，brain 不直呼 LLM。
- **demo 亮點句本就 offline-immune**：問候「Roy 歡迎回來」/ 杯子補水句 / 手勢 WeGo 都是 perception **自發、rule-based**，不靠 LLM。offline canned 表只是 free-text 聊天的保底。
- **6/15 修的 G2 footgun**：offline + `demo_phase=all`（**預設值**）原本會吐「我聽不太懂」→ 改成溫和 filler `OFFLINE_GENERIC_FALLBACK`。

---

## 1. 最確定的驗證（純單元測試，連 Jetson 都不用）

```bash
# 開發機 / Jetson 皆可（需 ROS env）
bash -c 'source /opt/ros/humble/setup.bash && PYTHONPATH=pawai_contracts:interaction_executive python3 -m pytest interaction_executive/test/test_brain_node.py -q'
```
**期望**：全綠。涵蓋：offline 短路發 canned 不開 LLM timer、offline=False byte-identical、
S5 safety 不被 offline 短路、G2（phase=all 用 filler 非「我聽不太懂」）、param/topic 共用 setter。

---

## 2. Jetson live dry-run（無 motion，走 demo 真實 Studio 文字輸入路徑）

前提：`pawai demo start`（或 `--with-lidar`）已起、Studio 開著（`http://localhost:3000/studio`）。

### Step A — 開 offline + 設幕，看 canned 秒回
```bash
ros2 param set /brain_node offline_mode true
ros2 param set /brain_node demo_phase s2_greet      # 逐幕換 s3_pose_object / s4_gesture
ros2 param get /brain_node offline_mode             # 確認 = True
```
- Studio 文字輸入隨便打一句（如「在嗎」）→ **期望：秒回該幕 generic canned**（s2「哈囉，很高興見到你。」/ s3「記得多喝水、休息一下。」/ s4「你可以比個手勢跟我互動。」），**不等 LLM、無 dead-air**。
- 觀察 `ros2 topic echo /brain/proposal`：`reason` 應為 `offline_mode`。

### Step B — S5 安全在 offline 仍生效（最重要）
- 維持 `offline_mode true`，Studio 文字輸入「翻跟斗」（或「後空翻」）。
- **期望**：TTS 秒拒「這個動作不安全，我不能執行。」+ Studio 顯示 `BLOCKED_BY_SAFETY`。
- 同時 `ros2 topic echo /webrtc_req`：**應為 0 個動作命令**（Go2 完全不動）。

### Step C — G2 footgun 已修（沒切 phase 也不尷尬）
```bash
ros2 param set /brain_node demo_phase all           # 回預設值
```
- Studio 文字輸入隨便一句 → **期望：回「嗯，我在聽，我們繼續吧。」**（溫和 filler），**不是**「我聽不太懂」。

### Step D — offline=false 斷網不 dead-air（timeout fallback）
```bash
ros2 param set /brain_node offline_mode false        # 回線上
# 製造 LLM 不可用：拔 SSH tunnel 或把 LLM endpoint 指爛（看 speech README）
```
- Studio 文字輸入聊天句 → **期望：約 2s（`chat_wait_ms`）後回 canned**，遲到的 LLM reply 被 drop，**不 dead-air、不雙講**。
- ⚠️ **鐵則：別把 `chat_wait_ms` 改回 20000**（會變 20s dead-air）。現值 2000 是安全的。

---

## 3. 待 Roy 簽核（文案，非功能）

`DEMO_CANNED_TABLE` 15 格 + S5 三句 + `OFFLINE_GENERIC_FALLBACK`「嗯，我在聽，我們繼續吧。」
全標 `PENDING Roy sign-off` — 逐句確認措辭即可定稿（功能已在，純文案）。

---

## 4. 完整離線鏈（proven，發表日復驗一次）

cloud 全崩時的保底（5/12 + 3/17 已驗）：
```bash
LLM_ENDPOINT="http://127.0.0.1:1/" TTS_PROVIDER=piper \
  ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' \
  bash scripts/start_full_demo_tmux.sh
```
全鏈走本地、無 cloud 等待。這是 `offline_mode` runtime 開關之外的「啟動前 env」保底層。
