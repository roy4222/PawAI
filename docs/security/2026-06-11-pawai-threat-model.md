# PawAI Threat Model

> **日期**：2026-06-11　**類型**：READ-ONLY 防禦性威脅建模（無修改、無連線、無主動掃描）
> **方法**：9 領域多代理 fan-out 審計 → 94 筆逐筆對抗驗證 → 完整性 critic 補洞，所有 `file:line` 親讀。
> **姊妹文件**：[`2026-06-11-pawai-security-findings-ledger.md`](2026-06-11-pawai-security-findings-ledger.md)（94 筆 finding + verdict）、[`2026-06-11-pawai-hardening-plan.md`](2026-06-11-pawai-hardening-plan.md)（修補順序）

---

## 0. 一句話結論

> **PawAI 的所有軟體安全閘（SafetyLayer、BANNED_API_IDS、二次確認）都建立在「只有可信節點能上 DDS bus」這個假設上——而這個假設在無 SROS2 的 ROS2 + 對 `/webrtc_req` 零驗證的 driver + 綁 `0.0.0.0` 無認證的 HTTP gateway 三重作用下，對家用 LAN / Tailscale tailnet / 甚至跨站瀏覽器全面塌陷。** 結果是：**未認證的遠端方可以讓一台 15kg、與居家老人共處的四足機器人實體移動或執行危險動作。** 這是 7 個 critical finding 的共同根因。

對抗驗證確認了 **5 條彼此獨立的「未認證 → 機器人實體動作」路徑**（任一條成立即達成上述）：① gateway nav 端點、② 直發 `/webrtc_req`、③ 直發 raw `/cmd_vel`、④ foxglove clientPublish、⑤ **nav_capability 的 4 個 action server 完全無認證**（MOT-05，驗證後由 high **升 critical**）。

本專案是學生專題（居家陪伴機器狗，2026/4 文件、5 月展示），目前所有暴露面都在「自有 LAN + 私人 tailnet + 學校 demo 網路」範圍，**沒有對公網 funnel**。因此這不是「正被攻擊」的緊急事件，而是**在 demo 對外、或任一隊員裝置/Tailscale 帳號被盜時會被直接利用**的結構性風險。修補成本低（多為 bind 位址 + 一道 token），收益高（直接消除人身安全路徑），值得在 Plan B 動工前一併納入。

---

## 1. 系統概觀

PawAI 是以 Unitree Go2 Pro 為載體的居家互動機器狗。三層架構：感知（face/vision/object/speech）→ 中控（pawai_brain + interaction_executive，含 SafetyLayer）→ 驅動（go2_robot_sdk / nav stack）。PawAI Studio（FastAPI gateway + Next.js 前端）提供操作面板；PawAI CLI 經 SSH 管理 5 人共用的 Jetson。

| 元件 | 目錄 | 機台 | 安全相關職責 |
|------|------|------|-------------|
| **go2_driver_node** | `go2_robot_sdk/` | Jetson | 訂閱 `/webrtc_req`、`cmd_vel` → WebRTC 下 sport 命令給 Go2。**最後一道實體出口，但本身不驗證 api_id** |
| **interaction_executive_node** | `interaction_executive/` | Jetson | 唯一「正規」`/webrtc_req` 出口；`/brain/proposal` 經 SafetyLayer 驗證後發動作 |
| **SafetyLayer** | `interaction_executive/safety_layer.py` | Jetson(lib) | 危險動作關鍵字拒絕 + `BANNED_API_IDS` + emergency/obstacle/nav/**depth_clear** gate。**純應用層，DDS 邊界外無效** |
| **pawai_brain** | `pawai_brain/`, `interaction_executive/brain_node.py` | Jetson | LangGraph 決策；訂閱感知 events + `/brain/text_input` + `/brain/skill_request`（皆 DDS，無認證） |
| **speech_processor** | `speech_processor/` | Jetson | ASR + intent + LLM bridge + TTS；`tts_node` 訂 `/tts`、legacy `llm_bridge` 也能發 `/webrtc_req` |
| **face_perception** | `face_perception/` | Jetson | YuNet+SFace；讀寫 `/home/jetson/face_db/`（人臉 PNG + `model_sface.pkl`） |
| **nav stack** | `nav_capability/`, `go2_robot_sdk` | Jetson | RPLIDAR + Nav2 + AMCL + reactive_stop + **4 個無認證 action server**（goto_relative/goto_named/run_route/log_pose） |
| **Studio Gateway** | `pawai-studio/gateway/studio_gateway.py` | Jetson | FastAPI ROS2↔瀏覽器橋接（HTTP 控制端點 + WS 廣播 + push-to-talk ASR） |
| **PawAI CLI** | `tools/pawai_cli/` | 隊員 Mac/WSL | 經 SSH 對 Jetson 跑 `tmux`/`colcon`/`rm`/`nmcli`/inline `python3 -c` |

---

## 2. 信任邊界

```
┌─ 公網 ────────────────────────────────────────────────────────┐
│  OpenRouter / Gemini / 雲端 vLLM+ASR (HTTPS, API key)          │
│  GitHub Actions (CI secrets, 5 人 PR)                          │
└───────────────────────────────────────────────────────────────┘
        │ HTTPS（出向）                    │ push/PR
┌─ Tailscale tailnet（5 人共用，SSH alias jetson-nano）─────────┐
│   ⚠ tailnet 任一節點/被盜帳號 → 可達 Jetson 全 port + SSH      │
│  ┌─ 家用 LAN / 學校 demo 網路 ───────────────────────────────┐ │
│  │  ⚠ 同網段主機 → 8080(gateway) / 8765(foxglove) 無認證     │ │
│  │  ┌─ DDS bus（CycloneDDS, ROS_DOMAIN_ID=0, 無 SROS2）────┐ │ │
│  │  │  ⛔ 邊界塌陷：同 domain 任意主機可無認證 pub/sub      │ │ │
│  │  │   /webrtc_req · /cmd_vel · /tts · /brain/skill_request │ │ │
│  │  │   · /nav/* action · /event/* · /brain/gesture_enabled │ │ │
│  │  │  ┌─ Go2 直連網段 192.168.123.x ───────────────────┐  │ │ │
│  │  │  │  Jetson ⇄ Go2（WebRTC, 韌體層無認證）           │  │ │ │
│  │  │  └─────────────────────────────────────────────────┘  │ │ │
│  │  └───────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

**關鍵觀察**：理論上 DDS bus 應是「Jetson 內部」邊界，但因為 (a) 無 SROS2、(b) CycloneDDS 未綁 interface（綁所有網卡含 tailnet/校園 Wi-Fi，GAP3-03 證實全 repo 無 `cyclonedds*.xml` 也無 active `CYCLONEDDS_URI`）、(c) `ROS_DOMAIN_ID=0` 只是 discovery 分區非認證，這個邊界實際上**與家用 LAN 重合**。再經 gateway(8080) 與 foxglove(8765) 兩個無認證 HTTP/WS 服務，邊界進一步外擴到**任何能用瀏覽器打到 Jetson IP 的人**，甚至（因 CORS `*` + WS 無 Origin 檢查）**外網誘導隊員瀏覽器**。

---

## 3. 資產（依價值排序）

| # | 資產 | 為何高價值 | 已驗證塌陷點 |
|---|------|-----------|-----------|
| **A1** | **人身安全**（15kg 會動的機器人 × 居家老人） | 最高。誤動作＝實體傷害 | MOT-01/02/05、GW-01/02、EXP-01/02、GAP1-01、GAP2-03 |
| **A2** | **API keys**（OPENROUTER_KEY 等付費金鑰） | 金錢損失、濫用 | 入庫面乾淨（SEC-06 驗證 1642 commit 無真 key）；但 `set -a; source .env` 灌進每個 tmux pane/ROS 節點環境，任一節點被入侵即洩漏 |
| **A3** | **人臉生物特徵 + 語音個資** | 居家住戶 PII、不可撤銷 | GEN-01/04/05、SEC-01、GW-06/07、EXP-04 |
| **A4** | **Jetson 主機控制** | 橫向移動跳板 | GEN-01(pickle RCE)、CLI-01(branch RCE)、tailnet SSH |
| **A5** | **Demo 可用性** | 5 月驗收 | demo lock `--force` 搶占、`.env` CRLF 假成功、DoS（MOT-08）、GAP3-01(reactive_stop 文件債致誤設鎖死 nav) |

---

## 4. 威脅行為者

| 行為者 | 位置 | 能力 | 動機 | 可信度 |
|--------|------|------|------|:---:|
| **T1 被盜隊員裝置 / Tailscale 帳號** | tailnet | SSH Jetson、HTTP 8080/8765、DDS pub/sub | 橫向移動、惡作劇、誤操作 | **高**（5 人共用 + 共用 Jetson 帳號） |
| **T2 同 LAN 主機**（被入侵 IoT、訪客手機、惡意 App） | 家用 LAN | 無認證 HTTP/WS、可能同 DDS domain | 實體破壞、隱私竊取 | 中 |
| **T3 跨站瀏覽器攻擊者** | 外網網頁 | CORS `*` + WS 無 Origin → 誘導隊員瀏覽器 POST | 遠端令機器狗動 | 中（需隊員開惡意頁） |
| **T4 學校 demo 網路主機** | 校園網 | demo 當天 gateway/foxglove 綁 0.0.0.0；同 `ROS_DOMAIN_ID=0` 可直上 DDS | 干擾 demo、惡作劇 | 中（demo 當天視窗） |
| **T5 Prompt injection（語音/文字）** | 對話通道 | 操縱 LLM 輸出 | 令機器人說/做壞事 | **受限**：LLM allowlist 不含 motion/nav；可達的 execute-bucket 動作另受 depth_clear gate 與 cooldown 限制（見 §6.5） |
| **T6 供應鏈 / 惡意 PR** | GitHub | vendored 套件、CI secrets、PR | 植入後門 | 低-中 |

---

## 5. 攻擊面：監聽服務一覽

| Port | 服務 | 綁定 | 機台 | 認證 | 風險 |
|:---:|------|:---:|------|:---:|------|
| **8080** | Studio Gateway（`/api/nav/*`、`/api/skill_request`、`/ws/*`） | **0.0.0.0** | Jetson | **無**, CORS `*` | 🔴 直接驅動 Go2 |
| **8765** | foxglove_bridge（預設允許 client publish） | **0.0.0.0** | Jetson | **無** | 🔴 瀏覽器可 pub `/webrtc_req` |
| **8001** | SenseVoice ASR（accept audio upload） | **0.0.0.0** | RTX8000/Jetson | **無** | 🔵 GPU 濫用、音訊外洩（EXP-06 驗證後 low：實務經 tunnel） |
| **8080** | Mock Server（dev 假後端） | **0.0.0.0** | 開發機 | 無（CORS 限 localhost） | 🔵 mock 狀態竄改 |
| **3000** | Next.js frontend dev | localhost | 隊員筆電 | 無 | 🔵 僅本機 |
| **8000** | vLLM endpoint | localhost+tunnel | RTX8000 | tunnel | 🔵 |
| **22** | SSH | tailnet | Jetson | key | — |
| **(UDP)** | CycloneDDS discovery（multicast, domain 0） | **LAN-wide** | 全節點 | **無 SROS2** | 🔴 無認證 pub/sub 任意 topic（含 nav action、skill_request） |

---

## 6. 主要攻擊鏈（STRIDE 視角，已對抗驗證）

### 6.1 🔴 未認證 HTTP → 機器人實體移動（Tampering / EoP）

```
T2/T3/T4  ──curl/fetch──►  POST http://<jetson>:8080/api/nav/start {"distance":1.0}
                              │  (GW-02: 無認證, studio_gateway.py:1146)
                              ▼
                         node.nav_start() ──► /nav/goto_relative action ──► Nav2 ──► cmd_vel ──► Go2 前進 1m
```
- **前提**：demo stack 運行、攻擊者可達 8080（同 LAN / tailnet / 跨站誘導瀏覽器）。
- **後果**：機器人朝預設方向移動，可撞向老人/家具。連發 `/api/skill_request`(GW-03)、`/api/nav/initialpose`(GW-05, 竄改 AMCL 定位) 擴大效果。
- **證據**：`studio_gateway.py:869-882`（CORS `*`）、`:1146-1150`、`:1333`（host 0.0.0.0）。**驗證 exploit_realistic=True。**

### 6.2 🔴 DDS peer → `/webrtc_req` → 任意危險動作（繞過全部安全閘）

```
T1/T2  ──ros2 topic pub──►  /webrtc_req {api_id: 1301(backflip)/...}
                              │  (MOT-01: 無 api_id 白名單, robot_control_service.py:113)
                              ▼
                         handle_webrtc_request() ──► send_webrtc_request() ──► Go2 翻滾/跳躍/倒立
```
- **關鍵**：SafetyLayer 的 `BANNED_API_IDS`（`skill_contract.py`）**只在 interaction_executive 內生效**；任何直發 `/webrtc_req` 的 DDS peer 完全不經過它。`/cmd_vel` 同理（MOT-02：driver 直訂原始 `cmd_vel`，繞過 twist_mux + reactive_stop）。
- **證據**：`robot_control_service.py:113-122`、`go2_driver_node.py:306-307,378`。**驗證 exploit_realistic=True。**
- **放大器**：foxglove_bridge 8765（EXP-02）讓**瀏覽器**就能 publish 這些 topic，不需 ROS2 環境。

### 6.3 🔴 nav_capability action server 無認證（critic 補洞，驗證升 critical）

```
T1/T2  ──ros2 action send_goal──►  /nav/goto_named {name:"door"} / /nav/run_route / /log_pose
                                     │  (MOT-05: 4 個 action server 零認證, nav_action_server_node.py:119)
                                     ▼
                                Nav2 規劃 ──► Go2 自走至任意/具名座標
```
- **驗證者升級理由**：4 個 action server（goto_relative/goto_named/run_route/log_pose）由 `nav_capability.launch.py` 在 demo 一起啟動；唯一 gate（`_accept_goal`）只擋並行 goal，AMCL covariance gate 只防定位不準，**皆不驗證呼叫者身份**。在無 SROS2 下同 LAN/tailnet 可直接 send_goal → 把機器狗驅離守護位置或撞家具。**升 critical。**
- **相鄰**：MOT-04（`/log_pose`、`run_route` 的 `route_id` 路徑穿越，驗證後 medium——`.json` 後綴限制了任意覆寫但仍可寫/讀 routes_dir 外）。

### 6.4 🟠 偽造 source / priority_class 繞過確認與 SafetyLayer（合流授權鏈，EoP）

這是 critic 補洞發現的**合流鏈**——原本被兩個領域各看一半：

```
gateway POST /api/skill_request  ──硬寫 source="studio_button"──►  /brain/skill_request (studio_gateway.py:911)
        或 T1/T2 直接 DDS pub /brain/skill_request {source:"studio_button", skill:"nav_demo_point"}
                              │  (GAP1-01 / LLM-02: source 取自 wire payload，可偽造)
                              ▼
        brain_node._on_skill_request: source=="studio_button" 且 skill∈{nav_demo_point, move_forward}
                              │  → 繞過 PendingConfirm OK 二次確認 (brain_node.py:1437-1487)
                              ▼  build_plan → _emit → IE validate → dispatch
```
- **GAP1-01**（high）：`source` 是 wire 欄位、可任意偽造，卻被當作 bypass confirm 的依據。`/brain/skill_request` 是純 DDS RELIABLE topic，無 SROS2 → 同 LAN/tailnet 可無認證直接觸發 nav skill（免 OK 確認）。
- **GAP2-03**（high）：`requires_confirmation=False` 的 MOTION skill（wave_hello/sit_along/stand/self_introduce/greet_known_person/fallen_alert）經此路徑**完全免確認**直發。
- **LLM-01**（`safety_layer.py:87-89`）：`priority_class==SAFETY` 短路放行所有檢查——defense-in-depth 破口，需有路徑讓外部控制 `priority_class` 才直接可利用。
- **重要 nuance（驗證者反覆確認）**：IE 的 `SafetyLayer.validate()` 對 MOTION step **有 `depth_clear` fail-closed gate**（`world_state.py:37` 預設 False，由 D435 depth_safety_node 餵 `/capability/depth_clear`）。**正前方有人/障礙時會擋下 stand 等動作**；但 **demo 清空地面、depth_clear=True 時則放行**——所以這條鏈在 demo 實況（地面清空）下可達實體動作。

### 6.5 🟡 Prompt injection → LLM（能力受限，多層緩解）

- LLM 的 skill allowlist（`llm_policy.py`，Plan C 已單源化為 9 skill）**不含** motion/nav，故語音/文字 injection **無法直接令機器人移動或導航**——設計邊界正確。
- execute-bucket 含 MOTION 的 skill（wave_hello/sit_along/stand，GAP2-02）可被 LLM 提案，但驗證者確認受 **depth_clear gate + per-skill cooldown + demo_guides `max_motion_per_turn:1`** 三層緩解，故由 high **降 medium**（exploit_realistic=False）。
- `ConversationMemory` 無內容淨化（GAP2-04，low），injection 可跨 5 輪存活放大上述，但終點仍受 gate 攔截。
- **仍可被濫用的面**：`/brain/text_input`(LLM-03) → LLM → TTS 無內容審核；`/tts`(LEG-02) 可被同 LAN 直接灌入跳過 LLM → 機器狗對老人說任意話。

### 6.6 🟠 model/branch 供應鏈 → Jetson RCE（EoP）

- **GEN-01**（`face_identity_node.py:164`，驗證 high）：啟動時無條件 `pickle.load(model_sface.pkl)`；`/home/jetson/face_db/` 為 5 人共用可寫、`pawai face enroll/rebuild` 例行寫入 → 能寫該檔者使 face node 下次啟動以 jetson 帳號 RCE（而該帳號掌控 Go2）。
- **CLI-01**（`main.py:674-678`，驗證 high）：git branch 名經 `json.dumps`（非 shell-safe）內插進 SSH shell 雙引號字串；branch 名含 `$(...)`/反引號 → Jetson 上命令替換執行。

### 6.7 🟡 隱私外洩（Information Disclosure）

- **GW-06/EXP-04**（`/ws/video`）：未認證即可串流 face/vision/object debug 影像（含人臉+姓名）→ 居家即時監控外洩。
- **GW-07/SEC-02**（`/ws/events`）：人臉姓名等全感知資料 broadcast 給任意未認證 client。
- **SEC-01**（`studio_gateway.py:685`）：對話逐字稿寫入 ROS log + gateway stdout。
- **GEN-04**（`face_identity_node.py:653`）：debug 影像寫死世界可讀 `/tmp/face_identity_debug.jpg`。
- 正向：**無真實 API key 入庫**（SEC-06，已驗證）。

> **被驗證推翻的一筆**：LEG-08（兩條對話引擎並存雙發）——驗證者讀訂閱端 `brain_node._on_chat_candidate:655-671` 發現 **buffer-then-pop 去重**已防止雙發，impact 主張不成立，判定**非真**。

---

## 7. 風險矩陣（驗證後 severity）

| | **後果：實體傷害** | **後果：個資外洩** | **後果：RCE/接管** | **後果：DoS/干擾** |
|---|---|---|---|---|
| **未認證遠端（LAN/tailnet）** | 🔴 GW-02, MOT-01/02/05, EXP-01/02 | 🟡 GW-06/07, EXP-04 | — | 🟠 MOT-08, GW-09 |
| **一個前提（誘導/條件）** | 🟠 GAP1-01, GAP2-03, MOT-03/04, LEG-01/02 | 🟡 SEC-01 | 🟠 GEN-01, CLI-01 | 🟡 MOT-10, CI-07, GAP3-01 |
| **本機/供應鏈** | 🔵 GAP2-02/04（多層緩解） | 🔵 GEN-05, SEC-04/05 | 🔵 GEN-03/07/08, CI-03 | 🔵 CLI-05, GAP3-03 |

---

## 8. 與 Plan B-E 的關係

| Plan | 相交 finding | 對 Plan 的意義 |
|------|-------------|---------------|
| **B**（CLI v2 第一刀） | GW-01, EXP-01, EXP-09, CLI-01, CLI-07, SEC-02 | Plan B 要在 `status` 加 gateway probe、改 demo healthcheck——會主動 curl 8080。若採納本報告把 gateway 改 bind 127.0.0.1 / 加 token，probe 的主機解析與 healthcheck 必須同步設計。**建議把 gateway auth 與 CLI-01 branch 消毒併入 Plan B**（同屬「操作安全」主題）。 |
| **C**（pawai_contracts 抽取） | LLM-01, LLM-06/07, GW-03, GAP1-01, GAP2-05 | Plan C 收斂 LLM allowlist / skill_contract 單源——正是修 LLM-01（priority_class 短路）、GAP1-01（source-trust）的好時機。GAP2-05 指出 `CAPABILITIES.md`（persona md）與 `llm_policy.py` allowlist 分歧，**Plan C 單源化須覆蓋 persona md，否則分歧仍在**。零行為變更目標下安全修法需另開 commit。 |
| **D**（Brain Router Phase 0） | LLM-05, LLM-09, LEG-03, LEG-06/07 | Plan D 抽出感知 callback 的 JSON 解析——是加「感知事件來源/範圍驗證」的天然切入點（LEG-03 偽造 `/event/*`）。但 Plan D 明令「輸出逐 byte 不變」，故驗證強化須標為 Phase 1 follow-up。 |
| **E**（Brain Trace v1） | GW-07, LEG-02, SEC-01/03, GAP1-01/02, GAP2-03 | Plan E 新增 `/brain/trace` 並經 gateway TOPIC_MAP 廣播——**trace 內容若含感知摘要/身份名/語音文字，會經無認證 `/ws/events` 外洩**（SEC-03）。**多筆 GAP finding 建議併入 Plan E**：trace 應記錄 `skill_request` 的 source 以便上機追「誰發的」。Plan E 動工前必須先決定 trace 的 PII 邊界。 |

---

## 9. 建議優先序（詳見 hardening-plan）

1. **P0（demo 對外前必做）**：gateway 加 bind 127.0.0.1 + 最小 token；foxglove_bridge 加 `address:=127.0.0.1` 或關 clientPublish。這兩道一次封掉 §6.1 與 §6.2 的瀏覽器放大器。
2. **P1**：CycloneDDS 綁 interface + `ROS_LOCALHOST_ONLY`/防火牆封 DDS 埠（縮小 §6.2/6.3 的 DDS 面）；go2_driver `/webrtc_req` 加 api_id 白名單；nav action server 加授權（MOT-05）。
3. **P2**：`source` 不可自稱（GAP1-01/LLM-02）、SafetyLayer priority_class fail-closed（LLM-01）、CLI-01 branch 消毒、face pickle 改非可執行格式（GEN-01）。
4. **P3**：隱私（trace/video/log PII 邊界）、CI hardening（permissions、pin SHA、secret guard 補洞）、reactive_stop 文件債（GAP3-01）。

> 本威脅模型為靜態分析結論，未經實機驗證（READ-ONLY 約束）。任何修補上線前請在隔離環境驗證不破壞 demo 既有行為。
