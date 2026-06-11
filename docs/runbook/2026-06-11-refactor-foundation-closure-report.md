# Refactor Foundation Closure Report — 2026-06-11

> **目的**：確認 post-demo 重構第一批地基（Plan A-E + S0 freeze-safe + ISM Phase 0）在 **Jetson runtime + Go2 實機**上乾淨可用，**不改新功能、不改 runtime**。
> **方法**：READ-ONLY smoke，main `b2b4a4e` 部署到 Jetson，九項逐項驗證後 demo stop 清場。
> **結論**：**9/9 通過。地基封閉（closed）—— 可安全進入下一階段重構（ISM Phase 1 / Studio Evidence / S1）。**

---

## 受測 baseline

| 項 | 內容 | 來源 PR |
|---|---|---|
| Plan A | CI/CD guardrails（fast-gate 多 invocation + container + hook） | #143-#149 |
| Plan B | CLI v2 第一刀（audited deploy + healthcheck hard-gate） | #151 |
| Plan C | pawai_contracts 抽取（skill_contract/zh/llm_policy/trace_schema） | #152 |
| Plan D | Brain Router Phase 0（perception_router 雙路徑） | #153 |
| Plan E | Brain Trace v1（/brain/trace + decision_id） | #154 |
| Gap 1/2 | deploy 依賴閉包 + healthcheck full-mode pane/grace | #155 / #156 |
| S0-1 | CI/hook hardening（secret guard + permissions） | #157 |
| S0-2 | Gateway access-control 機制（env-gated，預設關） | #158 |
| ISM Phase 0 | 純 interaction_state 模組（未接 runtime） | #159 |

main = `b2b4a4e`（部署當下），全程綠、可部署。

---

## 九項驗證結果

### 1. ✅ deploy `.env` 前後不變
`pawai jetson deploy --module brain` → `.env` / `.env.local` md5 `32a6453a...` **部署前後完全一致**，LF 換行未污染。確認 Plan B audited rsync + exclude 契約生效（6/10「deploy 洗 .env」事故已封）。

### 2. ✅ build 三件套
`colcon build --packages-select go2_interfaces pawai_contracts pawai_brain interaction_executive` 全 built（CLI module 依賴閉包正確，Gap 1 修復生效）。ISM 模組 `interaction_state.py`（13497 bytes，含 review 修正版）已落 install tree。

### 3. ✅ demo start full mode → running
`pawai demo start -y` → healthcheck **8/8 全綠**（conv_graph 冷啟輪詢 ~15s）→ `✓ Demo running`，lock **starting→running**，不再卡 starting（Gap 2 pane fallback + grace window 實機生效）。

### 4. ✅ contracts / registry / brain ready
Jetson import：`SKILL_REGISTRY=30`、IE shim 與 contracts 同物件、`BANNED_API_IDS=3`、`MOTION_NAME_MAP=11`。brain ready（healthcheck [1] conv_graph + [3] persona 6 檔）。

### 5. ✅ perception_router_enabled 預設
`ros2 param get /brain_node perception_router_enabled` → **True**（Plan D 預設路徑）。

### 6. ✅ /brain/trace 有 publisher + suppressed trace
`/brain/trace` = **2 publishers**（brain_node + interaction_executive）+ 1 subscription（gateway）。14s 捕獲 4 條 trace **全 suppressed**（例：`object` 事件被 `attention_engaged` gate 擋，reason `attention:IDLE`），decision_id 串接正常。

### 7. ✅ gateway access-control default-off 不破壞 Studio/gateway
gateway 進程啟動於 deploy **之後**（21:59 > 21:38）→ 跑的是新 build（7 處 `_access_control`/`_ws_authorized`）。`.env` **無 GATEWAY_* override** → default-off。`/health` 200、`/api/plan_mode` GET/POST 200、`/api/gesture_enabled` 200、`/ws/events` WS 連線 —— **全部無 token 可用**，現有 Studio 流程零破壞。

### 8. ✅ ISM Phase 0 未接 runtime
`brain_node` 的 pub/sub **無 `state_transition`**；`/brain/trace` 訊息 **無 `state_transition` kind**；`TraceKind.STATE_TRANSITION` 在 contracts **不存在**（那是 Phase 1 才加）。三重佐證 ISM Phase 0 純觀測模組未接線、brain 行為不受影響。

### 9. ✅ demo stop 後全淨
`pawai demo stop` → tmux 0、lock none、**真實殘留 demo 進程 0**（brain/gateway/driver/conv_graph/executive 全清）、`.env` md5 不變。

---

## 結論與下一步

**地基封閉（Foundation closed）。** A-E + S0 freeze-safe + ISM Phase 0 在 Jetson+Go2 實機上乾淨可用、互不干擾、可一鍵起停。重構基礎設施（CI / contracts / router / trace / CLI healthcheck / gateway 機制 / ISM 純核心）全部就緒且零行為回歸。

**已知非阻斷項（凍結期內刻意延後，見 hardening plan + S0 報告）**：
- gateway secure-default flip（bind 127.0.0.1 + 強制 token）+ 前端/probe token wiring → 6/18 demo 凍結解除後。
- foxglove clientPublish 降權 → Roy 決策（會碰 nav initialpose 工作流 + 凍結腳本）。
- WSL→Jetson gateway:8080 Tailscale 不通（Jetson 端服務正常，僅本機 overlay 連線；不影響 demo）。

**可安全進入**：ISM Phase 1（shadow 觀測）/ Studio Evidence Center / Plan S1 / Plan V。
