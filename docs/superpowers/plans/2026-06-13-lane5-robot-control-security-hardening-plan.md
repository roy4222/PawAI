# Lane 5：Robot Control / Security Hardening（機制先行版）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)、[hardening plan](../../security/2026-06-11-pawai-hardening-plan.md)（P0-P3 修法權威）、[threat model](../../security/2026-06-11-pawai-threat-model.md)（3 根因 R1/R2/R3、5 條未認證→motion 路徑）、[findings ledger](../../security/2026-06-11-pawai-security-findings-ledger.md)（94 筆，7 critical）、[系統 Phase 4 plan](2026-06-11-phase4-robot-control-nav-hardening.md)（本 plan 把其中**可機制先行**的子集提前；HITL 最重的 enforcement 仍歸 Phase 4）
> **執行哲學**：**機制先行**（S0-2 先例：env/param-gated、預設關 = byte-identical、真機雙模式驗證）→ enforcement flip 逐項 Roy 決策。最危險的（DDS / twist_mux / driver cmd_vel 收斂）整段 post-6/18。
>
> **enforcement 六步硬順序（每個安全項各自走完才能進下一步；跳步禁止）**：
> ① **default-off mechanism**（code 入庫、預設關 = byte-identical）→ ② **tests**（off parity + on 行為單測，紅綠）→ ③ **dry-run / audit mode**（如適用：只 log 不擋，觀察會擋到誰）→ ④ **CLI smoke 確認**（off 模式下既有 CLI/probe 全綠）→ ⑤ **Jetson smoke**（auth-on / filter-on 測試模式真機走查，含 demo 流程回歸）→ ⑥ **secure-default flip**（Roy 逐項拍板 + 可一鍵退）。
> **本批（pre-6/18 AFK）只做 ①-④；⑤ 在 Roy 的 HITL 時段；⑥ 最快也是 6/15 後 Roy 決策（B-5/B-6），gateway / Foxglove / DDS 一個都不准先翻。**
> **與 Lane 6 的分界**：本 lane 管「**誰可以**命令機器人」（gateway auth / webrtc whitelist / nav action 授權與消毒 / cmd_vel 邊界）；nav **能力本身**（poses/routes、短距可靠性、safe-stop、stop-resume、fusion/patrol/approach、capability ladder、claim wording）歸 [Lane 6 Navigation / Obstacle Avoidance v2](2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)。

---

## 1. Goal

在不破壞 6/18 demo 的前提下，把「未授權者能讓 Go2 動」的 5 條路徑開始收口：`/webrtc_req` whitelist **機制**入庫、gateway token **wiring** 完成（flip 只剩翻 env）、nav route_id 路徑穿越與 CLI 注入**直接修掉**（純 bugfix）、face pickle RCE 換掉序列化格式、foxglove 降權與 auth flip 變成 Roy 一句話可執行的決策。每項都有安全 smoke 驗證「擋得住」+ demo 回歸驗證「不誤殺」。

## 2. Current state（code + ledger 實證）

**7 個 critical（5 條未認證→motion 路徑）**：

| 路徑 | finding | 現狀 |
|---|---|---|
| gateway HTTP（`/api/nav/*`、`/api/skill_request`） | EXP-01 / GW-01 / GW-02 | bind 0.0.0.0 + CORS `*`；**S0-2 auth.py 機制已 ship**（bind/token/CORS/Origin env-gated **預設關**，真機雙模式驗過 401/403）；前端/probe **尚未會帶 token**（flip 會斷 Studio） |
| `/webrtc_req` 直發 | MOT-01（+MOT-08 rate） | `robot_control_service.handle_webrtc_request`（:113-122）**零過濾直接轉發**；BANNED_API_IDS（1030/1031/1301）只在 IE SafetyLayer 層生效 |
| 裸 `/cmd_vel` 直發 | MOT-02 | driver 直訂裸 `/cmd_vel`（繞 twist_mux priority 255/200/100/10 與 reactive_stop） |
| foxglove clientPublish | EXP-02 | 8765 預設可 publish；demo lane 啟動行在凍結腳本 `start_full_demo_tmux.sh:274` |
| nav action server | MOT-05（critical）+ MOT-04 | 4 個 action server 零認證（`_accept_goal` 只擋並行）；`route_id`/`name` 可路徑穿越 |

**R3（應用層信 wire 欄位）**：GAP1-01/LLM-02（`source=studio_button` 繞 confirm）→ B-2 已建議 post-6/18（Lane 1 §5）；LLM-01（SafetyLayer 信 `priority_class` 短路）→ 行為變更，本 lane 評估後排 post（見 §5）。

**其他高價值**：GEN-01 face pickle RCE（`pickle.load(model_sface.pkl)`，face_db 5 人可寫）；CLI-01 branch 名 SSH 注入；CI-01 secret guard 漏 `.env.local` 變體（S0-1 已修大半）。

**已修**：CLI-08 rsync `--delete` 防線（#166）；S0-1 CI/hook hardening（#157）；S0-2 gateway 機制層（#158）。

## 3. Problems / gaps

1. driver 對 `/webrtc_req` 是**最後一道實體出口卻零驗證**——SafetyLayer 的 banned 清單在 DDS 直發下形同虛設。
2. gateway auth 機制在了但 flip 不動：前端 13 HTTP + 4 WS、CLI probe、healthcheck 都不會帶 token → flip 即斷 demo。
3. nav action 授權在 ROS2 action 模型下**沒有便宜解**（goal 無 caller identity；加 token 欄位 = 改 `.action` interface = 全鏈 rebuild）——5 天內不該碰，但 route_id 消毒是獨立 bugfix 可先修。
4. 兩個 RCE 級（face pickle、CLI branch）是純軟體可修，拖著沒理由。
5. 「擋得住」沒有自動化驗證——滲透清單（系統 Phase 4 Tests §3）是人工散文。

## 4. Scope

- `go2_robot_sdk/.../robot_control_service.py` + `test_robot_control_service.py`（11 條權威測試擴充）。
- `pawai-studio/`（gateway auth 沿用、前端 token wiring）、`tools/pawai_cli/`（probe token）。
- `nav_capability/`（route_id/name 消毒）。
- `face_perception/face_identity_node.py`（序列化格式）。
- `tools/pawai_cli/main.py`（CLI-01）、`scripts/hooks/`（CI-01 殘項）。
- 新 `scripts/security_smoke.sh`。
- foxglove 降權：**僅在 B-5 通過後**動 `start_full_demo_tmux.sh:274` 一行（凍結腳本逐改知情程序）。

## 5. Forbidden scope

1. **DDS 收斂（cyclonedds.xml 接線 / ROS_DOMAIN_ID 改值 / SROS2）post-6/18**——動 Go2↔Jetson 通訊鏈，需專屬實機回歸 session（系統 Phase 4 T4A-3）。本 lane 至多把 `cyclonedds.xml` 範本寫好入庫**不接線**（P2）。
2. **twist_mux / cmd_vel 來源收斂、emergency clamp post-6/18**（T4A-6，hardening plan 明標「需 nav lane 實機回歸」）。
3. **nav action 授權（interface 級）post-6/18**（T4A-5①）；本 lane 只做 route_id 消毒（T4A-5②）。
4. **gateway 簽章（nonce/HMAC）與 source trust enforcement post-6/18**（T4A-1④ + hardening P2-1；B-2 已定）。
5. **SafetyLayer priority_class fail-closed（LLM-01）post-6/18**——行為變更會動 SAFETY 路徑時序，發表前不碰安全鏈本體（hardening P2-2 獨立 commit 另案）。
6. enforcement flip（auth-on / whitelist-on / foxglove 降權）**未經對應 HITL 回歸不得翻**；任何 flip 不寫死進凍結腳本（env/param 注入）。
7. 不做 Tailscale ACL / 校網政策（環境面，非 repo）。
8. **nav 能力面工作不在本 lane**：poses/routes 重建、短距重驗、stop-resume、goal rejection reason、orphan client、fusion/patrol/approach spec——全部歸 Lane 6，本 lane 在 nav 上只碰授權與消毒（T5S-2 與 post-6/18 的 interface 級 auth）。

## 6. Proposed tasks

| Task | hardening 對應 | 內容 | demo-affecting | 優先 |
|---|---|---|---|---|
| **T5S-1 `/webrtc_req` whitelist 機制** | P1-2 / MOT-01+MOT-08 | `robot_control_service` 加 `webrtc_api_filter_mode` param：`off`（**預設，byte-identical 零過濾**）/ `blacklist`（拒 BANNED_API_IDS 3 條，從 pawai_contracts 讀）/ `whitelist`（明列 demo+nav 所需 api_id：sport 基本動作 + Megaphone 4001-4004 等，StopMove 1003 **永遠放行**）；拒絕時 log + 丟棄；加每秒 rate limit param（預設 0=不限） | off=否；on 需動作回歸 | P0 |
| **T5S-2 route_id/name 消毒** | P1-3② / MOT-04 | `nav_capability` 的 `route_id`/`name`：`os.path.basename` + 白名單字元 `[A-Za-z0-9_-]`，拒 `../`；直接修（合法輸入不受影響=bugfix 非行為變更） | 否 | P0 |
| **T5S-3 gateway token wiring** | P0-1 前置 | 前端：fetch/WS 統一加 `Authorization: Bearer`（token 取 `NEXT_PUBLIC_GATEWAY_TOKEN` env / localStorage；無 token 時 header 不帶=現行為）；CLI：gateway probe / healthcheck 支援 `GATEWAY_TOKEN` env 帶 token；**全部 default-off 下 byte-identical** | off=否 | P0 |
| **T5S-4 CLI-01 + CI-01 殘項** | P2-3 / P3-2 | branch/module 名經 SSH 一律 `shlex.quote()`（或 argv 陣列）；secret guard regex 補 `.env.local`/`.env.production` 變體 | 否 | P0 |
| **T5S-5 face pickle → npz** | P2-4 / GEN-01 | `face_identity_node`：讀取改「npz 優先、pickle fallback（過渡期）」；`train_model` 寫 npz；`pawai face rebuild` 後自然轉格式；fallback 移除排 post-6/18 | 需 Jetson 驗證（重訓+辨識不退化） | P1 |
| **T5S-6 security smoke** | 滲透清單自動化 | 新 `scripts/security_smoke.sh`（auth-on 測試模式下跑）：無 token curl 狀態變更 endpoint → 401；WS 偽 Origin → 拒；`redact=0` 無 token → 403；（whitelist-on 時）pub banned api_id → 拒絕 log；route_id `../` → 拒。可選 wiring `pawai smoke security`（P2） | 否（只讀驗證） | P1 |
| **T5S-7 foxglove 降權** | P0-2 / EXP-02 / A-2→B-5 | **B-5 通過後**：demo lane foxglove 行加 `-p capabilities:='["connectionGraph"]'`（唯讀）——凍結腳本逐改知情程序（單獨 PR + demo smoke + Roy 點頭）；nav lane 腳本是否同步降權看發表是否還需 Foxglove 設 initialpose（Studio `/api/nav/initialpose` 已存在可替代） | **是**（碰凍結腳本） | Roy 決策 |
| **T5S-8 auth flip 彩排** | P0-1 / A-3→B-6 | **= 六步順序的第 ⑤ 步，只能在 Roy HITL 時段做**：Jetson 上開 auth-on（env）→ 跑 Studio 全流程（按鈕/push-to-talk/video/nav panel/Evidence 頁）+ `pawai status`/smoke + security smoke → 全綠則 B-6 **才有資格**選發表日 on（第 ⑥ 步）；任何紅 → 記錄、發表日維持 default-off | 翻 env 期間 | P1（HITL） |
| **T5S-9 cyclonedds.xml 範本** | P1-1 預備 | 寫範本 + 接線文件（`CYCLONEDDS_URI` 用法、interface 限定、AllowMulticast=false、Peers 白名單）入庫**不接線**——post-6/18 的 T4A-3 直接拿去用 | 否（純檔案） | P2 |

## 7. Pure software tasks（WSL，可 AFK）

T5S-1（含 11 條權威測試擴充：off byte-identical / blacklist 拒 3 條 / whitelist 內放行外拒絕 / StopMove 永放行 / rate limit 不擋 1Hz StopMove dedupe）、T5S-2、T5S-3（前端+CLI）、T5S-4、T5S-5 的實作與單測、T5S-6 腳本、T5S-9 範本。

## 8. Jetson / Go2 HITL tasks（Roy 在場）

| 項 | 需要 | 內容 |
|---|---|---|
| T5S-1 whitelist-on 動作回歸 | **Jetson + Go2** | param 切 `whitelist` → demo 動作全流程（wiggle/hello/sit/TTS Megaphone/nav 若在）不誤殺 → security smoke 的 banned 拒絕項過 → 切回 off（或 Roy 點頭留 blacklist 模式進發表） |
| T5S-5 face 驗證 | Jetson | rebuild 重訓 → roy sim 分數不退化（對照 6/8 的 0.73-0.81 帶）→ list/delete 流程正常 |
| T5S-8 auth-on 彩排 | Jetson（Go2 低度） | §6 表內容，併入 HITL #2（6/15 晚） |
| T5S-7 降權後驗證 | Jetson | Foxglove 仍可看 topic/影像、無法 publish；demo smoke 全綠 |

## 9. Tests

- `test_robot_control_service.py`：11 條既有零修改 + 新增 filter mode 條目（紅綠：先證明 off 模式 byte-identical、whitelist 會擋）。
- gateway/CLI/前端：token wiring 在 default-off 下既有測試零變動；auth-on 模式單測（帶 token 200 / 無 token 401）。
- nav_capability：消毒單測（惡意 route_id 全拒、合法全過）。
- face：npz round-trip 單測 + pickle fallback 單測。
- `security_smoke.sh`：本身在 CI 不跑（需活 gateway），真機 HITL 跑；腳本 `bash -n` 進 pre-commit。
- 每項 enforcement flip 的驗收 = security smoke（擋得住）+ 對應 demo 回歸（不誤殺）兩面都綠。

## 10. Rollback strategy

- T5S-1：param 切回 `off` = 秒級 byte-identical；whitelist 誤殺 = 切 `blacklist`（行為=現狀+拒 3 條 banned）。
- T5S-3/T5S-8：auth 全程 env-gated，翻回 default-off 一個 env（S0-2 已驗 byte-identical）。
- T5S-5：pickle fallback 在 → 舊 pkl 永遠可讀；出問題不 rebuild 即回原狀。
- T5S-7：拿掉 capabilities 參數一行即回原行為（PR revert）。
- T5S-2/T5S-4：bugfix 類，revert 即回（但不應需要——合法輸入無行為差）。
- 發表日預設姿態：**所有 enforcement 維持 off**，除非對應 HITL 全綠 + Roy 點頭（B-5/B-6）。

## 11. Done criteria

1. T5S-1~T5S-4 merged：機制層全部入庫、預設關、off 模式 byte-identical 有測試證明；兩個 RCE 級（pickle 待 T5S-5）注入點修掉。
2. T5S-8 彩排有明確結果：auth-on 全綠（B-6 可選 on）或紅燈清單（發表日 default-off + post-6/18 修）。
3. security smoke 腳本可重跑，真機至少跑過一輪。
4. B-5 / B-6 兩決策有結論記錄（做了/不做/post-6/18），無懸空。
5. 系統 Phase 4 的 post-6/18 範圍（DDS/mux/nav auth/簽章）邊界未被偷跨。

## 12. Execution order

T5S-4 + T5S-2（bugfix 先行，6/13）→ T5S-1 + T5S-3（機制，6/14）→ T5S-6 → T5S-5 →（HITL #2）T5S-8 彩排 + T5S-1 動作回歸 →（B-5 通過才）T5S-7 → T5S-9（餘力）。

## 13. 6/18 presentation impact

- 正面：可講「Go2 控制面收斂已開始——driver 層 whitelist 機制、gateway 認證 wiring、注入點修補，全部有測試與 smoke」；若 B-6=on，可現場展示未授權請求被 401/403。
- 風險控制：預設全 off = demo 行為與已錄影片一致；任何 flip 都先過彩排；T5S-7 是唯一碰凍結腳本的項、單獨 PR + Roy 點頭。
- 不可講：「未授權者已不能讓 Go2 動」（DDS 面未收斂，5 條路徑只封了機制不全是 enforcement）——誠實版是「控制面 hardening 機制已入庫、enforcement 分階段上線中」。

## 14. Fable review checklist

- [ ] T5S-1 預設 `off` 的 byte-identical 有逐 byte 級測試；StopMove 永放行有獨立斷言；BANNED_API_IDS 從 pawai_contracts 讀（不重抄）
- [ ] `test_robot_control_service.py` 11 條既有一條不改
- [ ] token wiring 在無 token 時 header 完全不帶（不是帶空值）；CLI probe 不假成功
- [ ] 消毒用白名單字元而非黑名單；單測含 URL-encoded 變體
- [ ] face npz 寫入原子性（temp+rename）；pickle fallback 有測試；無新 pickle 寫入路徑
- [ ] security smoke 的每一項對應一個 finding 編號（可追溯）
- [ ] 無任何 task 偷碰 DDS / twist_mux / SafetyLayer / `.action` interface
- [ ] T5S-7 若執行：單獨 PR、只動一行、demo smoke 證據附 PR

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 5 Task <T5S-x>（見 docs/superpowers/plans/2026-06-13-lane5-robot-control-security-hardening-plan.md §6；
修法細節以 docs/security/2026-06-11-pawai-hardening-plan.md 對應 P 項為權威）。
紀律：
- 機制先行：新行為一律 param/env-gated、預設關；先寫「off = byte-identical」紅綠測試再實作。
- 防禦性修補 only（不寫攻擊程式碼）；BANNED_API_IDS / 契約值從 pawai_contracts 讀取。
- 不碰：DDS 配置接線、twist_mux、SafetyLayer 本體、.action interface、凍結三檔
 （T5S-7 例外，需明確指示才執行）。
- test_robot_control_service.py 11 條既有測試一條不改，新增條目擴充。
驗證命令：
  python3 -m pytest go2_robot_sdk/test/test_robot_control_service.py -q
  cd tools/pawai_cli && python3 -m pytest tests/ -q
  cd pawai-studio/gateway && python3 -m pytest -q
完成後：單 commit、PR 描述附紅綠證據 + HITL 驗證步驟（含 rollback 指令）。不得 merge，等 Fable review。
```
