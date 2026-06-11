# PawAI Hardening Plan

> **日期**：2026-06-11　**類型**：防禦性修補計畫（依本次 READ-ONLY 審計，94 筆全對抗驗證）
> **姊妹文件**：[`2026-06-11-pawai-threat-model.md`](2026-06-11-pawai-threat-model.md)、[`2026-06-11-pawai-security-findings-ledger.md`](2026-06-11-pawai-security-findings-ledger.md)
> **重要**：本計畫只給防禦性修法，不含攻擊程式碼。所有修補上線前須在隔離環境驗證不破壞 demo 既有行為（本審計為 READ-ONLY，未實機測試）。

---

## 0. 修補哲學（先讀）

PawAI 的安全問題**不是 94 個獨立 bug，而是 3 個結構性根因 + 一堆衍生症狀**。先修根因，多數症狀自動消失或降級：

| 根因 | 一句話 | 修了它就降級的 finding |
|------|--------|----------------------|
| **R1** Gateway/Foxglove 綁 `0.0.0.0` 無認證 | HTTP/WS 把機器人控制面攤給整個 LAN/tailnet/瀏覽器 | GW-01~11、EXP-01/02/04/07、SEC-02、GAP1-02 |
| **R2** ROS2 無 SROS2、DDS 未綁 interface | DDS bus 信任邊界與 LAN 重合，任意 peer 可 pub `/webrtc_req`/`/cmd_vel`/`/tts`/`/brain/*`/`/nav/*` action | MOT-01~11、LLM-10、LEG-02/03/04、EXP-03、GEN-09、GAP1-01/02、GAP2-03、GAP3-03 |
| **R3** 安全閘只在應用層、可被自稱欄位繞過 | SafetyLayer/確認機制信任 wire 傳入的 `priority_class`/`source` | LLM-01/02/05/09、GAP1-01、GAP2-03 |

**「居家陪伴老人 + 15kg 會動的機器人」這個場景把每個『未認證 → 實體動作』路徑都頂到 critical。** 對抗驗證確認 **7 個 critical**（含 critic 補洞升級的 MOT-05 nav action server），分屬 5 條獨立路徑。修補的第一目標不是「擋住所有攻擊者」，而是**讓任何遠端方都無法在未經操作員確認下使機器人移動或執行危險動作**。

> **驗證帶來的兩個校準**：① MOT-05（nav action server 無認證）由 high **升 critical**——nav 入口必須與 gateway 一起納入授權。② 多筆 LLM/motion finding 被驗證者確認**已有 `depth_clear` fail-closed gate** 緩解（正前方有人時擋 MOTION），故 GAP2-01/02 降 medium；但該 gate 在 demo 清空地面時放行，**不能取代來源認證**。

---

## 1. P0 — Demo 對外前必做（封掉「瀏覽器/LAN → 機器人移動」）

> 目標：消除 §6.1 與 §6.2 的**瀏覽器放大器**。成本最低、收益最高——多為改 bind 位址 + 一道共享 token。**建議併入 Plan B（操作安全主題一致）。**

### P0-1　Studio Gateway 加認證 + 預設只綁本機
- **對應**：GW-01/02/03/04/05、EXP-01/05、SEC-02、GAP1-02（critical×2 + high×4）
- **檔案**：`pawai-studio/gateway/studio_gateway.py:1333`（uvicorn host）、`:869-882`（CORS）、`:911`（硬寫 source）、各 `/api/*` `/ws/*` 端點
- **防禦性修法**：
  1. `uvicorn.run(host=os.getenv("GATEWAY_BIND", "127.0.0.1"), ...)`——預設只綁 loopback；遠端存取改走 SSH tunnel 或反向代理。
  2. 對所有**會改變狀態 / 觸發動作**的端點（`/api/nav/*`、`/api/skill_request`、`/api/text_input`、`/api/gesture_enabled`、`/api/plan_mode`、`/api/*/reset`）加 FastAPI dependency 驗證 `Authorization: Bearer <token>`，token 從環境變數（不入庫）讀取。唯讀端點（`/health`）可豁免。
  3. `CORSMiddleware` 的 `allow_origins` 改白名單（隊員筆電 IP/`localhost:3000`），移除 `["*"]`。
  4. WebSocket 端點加 `Origin` header 檢查（白名單）防 CSWSH（GW-04）。
- **對 Plan B 的影響**：Plan B 的 `status` gateway probe 與 demo healthcheck 會 curl 8080。若改 bind/加 token，probe 需帶 token 或走 tunnel。**→ 建議 Plan B 動工時把「gateway probe」與「gateway auth」一起設計**，避免先做 probe 再回頭改 bind。
- **驗證**：demo 流程（Studio 面板按鈕、push-to-talk、video panel）在 token 模式下全綠；無 token 的 `curl :8080/api/nav/start` 回 401。

### P0-2　foxglove_bridge 關閉未認證 client publish
- **對應**：EXP-02（critical）
- **檔案**：`scripts/start_full_demo_tmux.sh:274` + 所有 `start_*.sh` 的 foxglove_bridge 行（nav2_amcl:73、nav_capability:130、lidar_slam:55、face_identity:78、vision_debug:32）
- **防禦性修法**：foxglove_bridge 啟動加 `-p address:=127.0.0.1`（僅本機，可視化走 tunnel）**或** `-p capabilities:='["connectionGraph"]'`（移除 clientPublish/services/parameters，降為唯讀可視化）。
- **成本**：每個腳本一行參數。**不阻擋任何 plan**（獨立 hardening）。
- **驗證**：Foxglove 仍能看 topic/影像；瀏覽器 client 無法 advertise/publish `/cmd_vel`。

---

## 2. P1 — 縮小 DDS 攻擊面 + driver/nav 縱深防禦（封掉「DDS peer → 機器人」）

> 目標：即使 P0 擋住 HTTP，仍須處理「同 LAN 直發 DDS」的路徑（R2）。

### P1-1　CycloneDDS 綁 interface + 隔離 domain
- **對應**：EXP-03、GAP3-03、MOT-01~11、LLM-10、LEG-02/03/04、GEN-09、GAP1-01/02、GAP2-03（一次降級一大批）
- **檔案**：全 `start_*.sh`、launch、`config/school_demo.env:37`（`ROS_DOMAIN_ID`）
- **防禦性修法**（GAP3-03 給了具體模板）：
  1. 新增 repo 內 `cyclonedds.xml`，`NetworkInterface` 限定為 Go2/Jetson 直連 interface（或 tailnet iface），`AllowMulticast=false` + 明列 unicast `Peers`（只含可信 Jetson 節點）。
  2. 在 `config/school_demo.env` 與各 `start_*.sh` 的 ROS_SETUP 後 `export CYCLONEDDS_URI` 指向該檔。
  3. `ROS_DOMAIN_ID` 從預設 0 改成專案專屬非預設值（如 42），school_demo.env 強制設定，避開最易被掃到的 domain 0。
  4. demo 走 Go2 Ethernet 直連時可額外設 `ROS_LOCALHOST_ONLY`/限 interface，避免上學校外網。
  5. **長期**：正式場景導入 SROS2（enclave + DDS-Security 認證加密），這是唯一真正關掉 R2 的方法。
- **成本**：中（需測 Go2↔Jetson 通訊不受影響）。**不阻擋 plan**，但 Plan E 新增 `/brain/trace` 後也走同一 bus，宜一併規劃。

### P1-2　go2_driver `/webrtc_req` 加 api_id 白名單（DDS 面縱深）
- **對應**：MOT-01（critical）、MOT-08
- **檔案**：`go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py:113`
- **防禦性修法**：`handle_webrtc_request` 在轉發前比對 api_id 與**允許清單**（從 `BANNED_API_IDS` 反向——明確拒絕 backflip/jump 等危險 sport id）；對 `/webrtc_req` 加速率限制（防 MOT-08 buffer flood）。這是「即使 SafetyLayer 被繞過，driver 仍是最後一道」的縱深防禦。
- **注意**：此檔的 routing unit test（`test_robot_control_service.py`）為權威，修改須同步測試。**不阻擋 plan**。

### P1-3　nav_capability action server 加授權（critic 升 critical）
- **對應**：MOT-05（critical）、MOT-04（medium，route_id 路徑穿越）
- **檔案**：`nav_capability/nav_capability/nav_action_server_node.py:119`、`route_runner_node.py`、`log_pose_node.py:101`
- **防禦性修法**：① nav 動作入口加授權（demo lock owner / token 檢查，或經由唯一受信任的 Brain Executive 節點轉發、禁止外部直呼 action）。② `route_id`/`name` 用 `os.path.basename` + 白名單字元過濾，拒絕 `../`（修 MOT-04 路徑穿越）。**不阻擋 plan**，但與 P1-1 同屬 nav 安全，建議一起做。

### P1-4　twist_mux emergency 速度上限 + cmd_vel 來源
- **對應**：MOT-02/03/10
- **檔案**：`go2_robot_sdk/config/twist_mux.yaml:21`、`go2_driver_node.py:305`
- **防禦性修法**：driver 改訂 mux 輸出專屬 topic（非裸 `cmd_vel`），裸 `cmd_vel` 不直連 driver；emergency lane 加速度 clamp。**需與 nav lane 協調**（會動到 reactive_stop/nav 既有行為，務必實機回歸）。

---

## 3. P2 — 應用層安全閘 fail-closed + 供應鏈 RCE

### P2-1　`source` 不可自稱（合流授權鏈）
- **對應**：GAP1-01（high）、LLM-02（high）、GAP2-03（high）、GAP1-02、LLM-09
- **檔案**：`interaction_executive/interaction_executive/brain_node.py:1437-1487`、`pawai-studio/gateway/studio_gateway.py:911`
- **防禦性修法**：`source` 是 wire 欄位、可任意偽造，**不能作為 bypass confirm 的依據**。改為：`requires_confirmation=True` 的 skill 一律走 PendingConfirm OK，移除 `_STUDIO_BUTTON_BYPASS_CONFIRM`；或改用 gateway 端帶不可由 DDS 偽造的 nonce/HMAC（gateway 已認證後簽章，brain 驗章）。這條是「未認證遠端 → 繞過確認 → motion」合流鏈的關鍵環。**可併入 Plan E**（trace 要記 skill_request source 以便追「誰發的」）。

### P2-2　SafetyLayer priority_class fail-closed
- **對應**：LLM-01（high）　**檔案**：`interaction_executive/interaction_executive/safety_layer.py:87`
- **防禦性修法**：移除「`priority_class==SAFETY` 直接放行」短路；改為 SAFETY 路徑仍跑 `BANNED_API_IDS` 與 emergency 檢查（SAFETY 應只豁免 obstacle/nav gate，不該豁免 banned 動作）。**可併入 Plan C**（收斂 skill_contract 時順帶，但需另開 commit 因 Plan C 要求零行為變更）。

### P2-3　CLI branch 名 shell 消毒
- **對應**：CLI-01（high）、CLI-04、CLI-07　**檔案**：`tools/pawai_cli/pawai_cli/main.py:674`、`network.py:207`
- **防禦性修法**：所有經 SSH 執行的遠端命令一律用 `shlex.quote()` 包裝使用者可控值（branch/module/pkg），或改用 argv 陣列避免 shell 解譯；wifi 密碼勿走 argv（用 stdin 餵 nmcli）。**直接屬 Plan B「操作安全」範疇，建議併入。**

### P2-4　face model 改非可執行序列化
- **對應**：GEN-01（high）、GEN-05　**檔案**：`face_perception/face_perception/face_identity_node.py:164,35`
- **防禦性修法**：`model_sface.pkl` 改用 `numpy.savez` / `json+base64(float32)` 存 centroid，移除 `pickle.load`；`face_db` 收緊為僅 enrollment 工具（非互動帳號）可寫；`train_model` 只認白名單 manifest 登記的身份，忽略未登記子目錄（同時修 CLAUDE.md 已記的「幽靈身份稀釋 centroid」坑）。

---

## 4. P3 — 隱私邊界 + CI hardening + 文件債

### P3-1　PII 落盤與廣播邊界
- **對應**：SEC-01/03、GW-06/07、EXP-04、GEN-04
- **防禦性修法**：對話逐字稿/人臉影像降為 debug-only 且預設關；`/ws/video`、`/ws/events` 隨 P0-1 一起加認證；debug 影像改寫 0700 目錄 + `O_NOFOLLOW`（防 symlink）；**Plan E 動工前先定義 `/brain/trace` 的 PII 欄位邊界**（trace 經無認證 `/ws/events` 廣播，含身份名/語音文字即外洩）。

### P3-2　GitHub Actions hardening
- **對應**：CI-04/05/06/07、CI-01/02/03/08
- **防禦性修法**：
  - 兩個 workflow 加 `permissions: { contents: read }`（最小化 GITHUB_TOKEN，CI-05）。
  - 第三方 action 與 ROS docker image pin 到 SHA（CI-04）。
  - secret guard hook 補 `.env.local`/`.env.production` pattern（CI-01）、涵蓋 Read 工具（CI-02）；`post_tool_py_syntax.sh` 的 `file_path` 改 argv 不內插（CI-03）。
  - pip 依賴 pin 版本（CI-06）。
- **成本**：低，**不阻擋 plan**。可獨立成一個 CI PR（接續 Plan A 的 CI 主題）。

### P3-3　服務暴露收斂
- **對應**：EXP-06/07/09、SEC-04、GEN-06
- **防禦性修法**：`sensevoice_server.py` 預設 `--host 127.0.0.1`（EXP-06）；mock_server 同（EXP-07）；移除腳本硬編個人 tailnet IP / 校內 user@host，改 env（EXP-09、GEN-06、SEC-04）；Tailscale 用 ACL/tag 限定誰可達 Jetson 8080/8765，定期審查 share 名單、離隊即撤。

### P3-4　reactive_stop 文件債（防誤設鎖死 nav）
- **對應**：GAP3-01（low，文件債）、GAP3-02（info）
- **防禦性修法**：CLAUDE.md 的「`safety_only=true` 必須用於 mux 模式」已過時且與實際腳本矛盾（腳本用 `mode:=progressive`，並無 `safety_only`）。更新為「mux 模式用 `mode:=progressive`；`safety_only=true` 會 promote 成 hold_brake 永久煞車鎖死 nav，僅供 B5 純停車驗證」，並在腳本 REACTIVE_PARAMS 旁加 inline 註解。demo-preflight 加一項「驗 reactive_stop 遮擋 LiDAR 時 `/cmd_vel_obstacle` 確實發 0」。

---

## 5. 執行順序總表

| 階段 | 動作 | 對應根因 | 阻擋 demo？ | 建議載體 |
|:---:|------|:---:|:---:|------|
| **P0-1** | Gateway bind 127.0.0.1 + token + CORS 白名單 | R1 | 否（demo 走 tunnel/token） | **併入 Plan B** |
| **P0-2** | foxglove_bridge 關 clientPublish | R1 | 否 | 獨立一行 PR |
| **P1-1** | CycloneDDS 綁 interface + domain 隔離 | R2 | 需回歸測試 | 獨立 |
| **P1-2** | driver `/webrtc_req` api_id 白名單 + rate limit | R2 | 需 test 同步 | 獨立 |
| **P1-3** | nav action server 授權 + route_id 路徑消毒 | R2 | 否 | 獨立（與 P1-1 一起） |
| **P1-4** | twist_mux/cmd_vel 來源收斂 | R2 | **需 nav lane 實機回歸** | 與 nav lane 協調 |
| **P2-1** | skill_request source 不可自稱（合流鏈） | R3 | 否 | Plan E 順帶 |
| **P2-2** | SafetyLayer priority_class fail-closed | R3 | 否 | Plan C 順帶（另 commit） |
| **P2-3** | CLI branch/wifi shell 消毒 | — | 否 | **併入 Plan B** |
| **P2-4** | face pickle → npz + face_db 權限 | — | 否 | 獨立 |
| **P3-1** | PII 落盤/廣播邊界 | — | 否 | **Plan E 前置** |
| **P3-2** | CI permissions/pin/secret guard | — | 否 | 獨立 CI PR |
| **P3-3** | 服務 bind + 硬編 IP 清理 | R1 | 否 | 獨立 |
| **P3-4** | reactive_stop 文件債 | — | 否 | 獨立（doc PR） |

---

## 6. 給 Roy 的 3 個決策點

1. **要不要把 gateway auth（P0-1）+ CLI shell 消毒（P2-3）正式併入 Plan B？** 兩者都屬「操作安全」、都會碰 `main.py`/`status.py`，分開做會重工。本報告建議併入，但 Plan B 的 forbidden scope 目前未涵蓋 auth——需你拍板擴張。
2. **demo 對外（學校展示）前，最低限度只做 P0-1 + P0-2 可接受嗎？** 這兩道封掉「瀏覽器/LAN → 機器人移動」，是投報率最高的一刀；P1（DDS + nav 授權）成本較高可排後。但注意 MOT-05（nav action 無認證）即使 gateway 鎖了，同 DDS domain 仍可直呼——學校網路 demo 建議至少同步做 P1-1 的 domain 隔離。
3. **`/brain/trace`（Plan E）的 PII 邊界 + source 記錄**：trace 要不要含身份名/語音文字？若含，必須先做 P3-1（否則經無認證 `/ws/events` 外洩）。同時 P2-1（source 不可自稱）建議併入 Plan E，讓 trace 能追「skill_request 誰發的」。建議 Plan E 動工前先定。

> 本計畫所有「修法」均為設計建議，未實作、未測試。實作時請走既有 TDD + 實機回歸流程（尤其 P1-4 動到 nav 安全鏈）。
