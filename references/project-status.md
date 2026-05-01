# 專案狀態

**最後更新**：2026-05-01 morning（**LiDAR mount v7 完成 ✅（脖子前方背板平台、yaw=0 物理錨定 commit `fabbf06`）/ home_living_room_v7 map 建成（XL4015 撐住未跳電）/ Phase 4 K1 仍待 KREE 到貨**）
**硬底線**：2026/4/13 文件繳交完成，**真正剩「4/30 那一週」**（5/11 那週搬 Go2 到老師辦公室、5/19 12:00-13:30 驗收），6 月口頭報告

---

## 5/1 進度

**LiDAR mount v7 完成 + v7 map 建成 — XL4015 撐住沒跳電**

### 完成事項

| 項目 | 內容 | 狀態 |
|------|------|------|
| **硬體變動** | LiDAR 從背部移到脖子前方 3D 列印背板平台（更大、更穩） | ✅ |
| **Mount 量測 v7** | x=+0.175 / y=0 / z=+0.18 / yaw=0；7 scripts + mount-measurement.md 同步 | ✅ commit `fabbf06` |
| **物理錨定驗證** | scan_health_check.py：物體 0.8m 在 angle=0° ±15° 偵測到 0.83m，PHANTOM PASS、scan 10.45 Hz | ✅ |
| **v7 map 建立** | `home_living_room_v7.{pbstream,pgm,yaml}` 客廳核心 4×4m 慢走 30-60s，10.35×4.90m / 207×98 cells | ✅ |
| **Default map 切換** | `start_nav2_amcl_demo_tmux.sh` + `start_nav_capability_demo_tmux.sh` → v7 | ✅ |
| **供電 surprise** | 整段建圖 + scan_only XL4015 全程穩定，Jetson 47°C 沒跳電 | ✅（與 4/29 紀錄不同）|

### Map QA（v7）

- ✅ 客廳區（東側 ~4×4m 正方形）：牆面單線、角落直角、loop closure 不裂 → AMCL K1 可用
- ⚠️ 西側延伸走廊：可見輕微 yaw drift（與 v2 同症狀）→ 嚴禁發 goal 到走廊
- ❌ 不擴掃走廊（pure scan-matching 在走廊 yaw drift 5-10°）

### 下一步

1. **等 KREE DL241910 到貨** — XL4015 建圖撐住，但 Nav2 動態 cmd_vel 風險級別更高
2. KREE 上機後跑 K1：`send_relative_goal.py --distance 0.5` × 5（≥ 4/5 即過）
3. K1 過則進 K2/K4/K5/K7

---

## 4/30 進度

**LiDAR yaw 物理錨定一次定案 + 供電災難 + KREE 補位**

### 完成事項

| 項目 | 內容 | 狀態 |
|------|------|------|
| **Phase 1（plan abstract-sleeping-hoare）** | scan-only stack + Go2 正前方 0.8m 放物體 → scan_health_check 量到 90° bin (0.6534m) | ✅ |
| **Phase 2** | 7 scripts + mount-measurement.md yaw 3.1416 → -1.5708 一次性更新 | ✅ commit `560ca79` |
| **TF 驗證** | `tf2_echo base_link laser` RPY [0, 0, -90°] | ✅ |
| **Foxglove 視覺驗證** | base_link +x 軸對齊 Go2 真實正前方、scan 點雲在前方 | ✅（用戶現場確認） |

### 供電災難 + 應對

| 階段 | 狀況 |
|---|---|
| 4/29 night | 2464 模組宣稱穩定 |
| **4/30 ~9:15** | Jetson SSH 連線斷 → 真因：2464 輸入上限 30V < Go2 滿電 33.6V |
| **4/30 ~10:00** | 重開後 ~10 分鐘再斷一次（過壓保護觸發或元件壓力異常） |
| **4/30 上午** | 暫退回 XL4015（4-38V/75W）撐到新模組到貨 |
| **訂購中** | KREE DL241910 (22-40V→19V/10A/190W) 鋁殼 IP68 — Go2 滿電 33.6V 在範圍內、190W 餘裕大 |

### Yaw 物理錨定的關鍵推論

物體實際在 base_link +x（Go2 正前），scan 顯示在 angle=90° bin → laser frame +y 對應 base_link +x → laser 的 0° 物理上指向 Go2 右方 → 補正 yaw = **−π/2**。

| Yaw 試過的值 | 結果 | 棄用原因 |
|---|---|---|
| 0 (v2) | ❌ | 視覺猜，map 90° 旋轉 |
| −π/2 (v3) | ❌ | 視覺猜，map 看起來反 |
| +π/2 (v4) | ❌ | 視覺猜 |
| π (v5, 4/29 night) | ❌ | 視覺猜 |
| **−π/2 (v6, 4/30 物理錨定)** | ✅ | scan_health_check 90° bin + tf2_echo + Foxglove 三重驗證 |

> 教訓：**視覺判讀不可信**（map 由錯誤 yaw 建出時也會「內部一致」）。**只有物理錨定看 raw LaserScan 角度**才是黃金標準。

### 沒做的事（避開風險）

- ❌ 不重建 map v6（XL4015 撐不住 cartographer + Go2 移動）
- ❌ 不跑 Nav2 demo（Go2 動態移動 → 馬達瞬電流尖峰 → XL4015 跳電風險）
- ❌ 不寫 scan_flipper（H1 已排除）

### 下一步（等 KREE 到貨）

1. KREE 到貨 → 萬用表驗 19V → 接 Jetson
2. 重啟 cartographer stack → 遙控 Go2 慢走客廳一圈 → 存 v6 map
3. AMCL 跑 K1：`send_relative_goal.py --distance 0.5` × 5（≥ 4/5 即過）
4. v6 過則進 K2/K4/K5/K7 連發

---

## 4/29 進度

**LiDAR roadmap Phase 1-3 — 物理層 + 建圖實機驗證 / yaw 仍待定案 / 4/30 教授會議對齊**

### 完成事項

| Phase | 內容 | 狀態 |
|-------|------|------|
| **Phase 1** | mount 量測（x=−0.035, y=0, z=0.15）+ TF 6 scripts + build_map.sh echo 同步 | ✅ |
| **Phase 2** | scan-only stack + `scan_health_check.py`（PHANTOM 4-條件 gate）+ baseline CSV + 旋轉復測 | ✅ |
| **Phase 3** | Cartographer pure scan-matching 重建 4 張 map（v2 yaw=0 / v3 yaw=−π/2 / v4 yaw=+π/2 / v5 yaw=π）| ⚠️ 全部因 yaw 錯而 deprecated |
| **AMCL 校正預備** | nav2_params.yaml `laser_min_range: 0.20` / `laser_max_range: 8.0` | ✅ commit ready |
| **教授會議** | [`docs/mission/meetings/2026-04-29.md`](../docs/mission/meetings/2026-04-29.md) | ✅ 紀錄 |

### Yaw 校正 4 次失敗的教訓

每改 yaw 就重建一張 map → cartographer 用該 yaw 建出**內部一致**的 map → Foxglove 看 scan 跟 map 永遠看起來反，因為比對基準（map）也跟著轉。**用戶 4/29 SSH 實測排除**：

- `/scan_rplidar:angle_increment = +0.008738784` → 標準 CCW，**排除 scan 鏡像 / scan_flipper 路線**
- `/scan_rplidar` publisher 唯一是 sllidar_node → 排除 topic 混用
- 雷達 motor 朝下 → 排除物理倒裝
- initialpose 拖箭頭對齊 Go2 真實前方 → 排除 initialpose 方向錯

**新路徑（user 定）**：物理錨定測試 — 在 Go2 正前方 0.8m 放物體，跑 scan_health_check.py 看物體落在哪個 angle bin，直接判讀 yaw。**完整 plan**：`/home/roy422/.claude/plans/abstract-sleeping-hoare.md`

### 供電升級（demo blocker → 已解）

| 階段 | 狀態 |
|---|---|
| XL4015 | 4/29 16:30-17:30 跳電 3 次（10 分鐘內） |
| **2464 可調自動升降壓恒壓恒流模組** | 35W 自然散熱 + 50W 加強散熱、過流/過壓/過溫多重保護、輸入防反接、輸出防倒灌 |
| 4/29 19:52 後 | 不再跳電 ✅ |

### 4/30 教授會議對齊（會議 vs 進度差異）

- ✅ 一致：北極星機器狗版 OpenClaw、Brain Phase A 完成、雷達校正本週主軸、OpenRouter 升級
- ⚠️ 落差：供電 XL4015 → 2464、OpenRouter 候選改 DeepSeek V4 / Gemini 2.5 Flash / Kimi K2、TTS 升級新需求、雷達背板平台新需求
- ❌ 時程更緊：「真正剩 4/30 那一週」= 4-5 天 code 時間，之後忙簡報 + 搬運 + 整合
- ✅ Brain 設計：會議列「指令分層架構」為次大難題，**Phase A 已 cover**（safety_layer + skill_contract + executive 單一出口）

### 文件 / 工具新增

- `scripts/scan_health_check.py` — 30 樣本 angular probe + PHANTOM 4-條件 fail gate
- `scripts/start_scan_only_tmux.sh` — 3-window scan-only（TF + sllidar + monitor）
- `docs/導航避障/research/2026-04-29-mount-measurement.md` — 量測 + yaw 修正歷史
- `docs/導航避障/research/baseline-scans/` — baseline / Pose-A / Pose-B-cw30 三 CSV
- `docs/導航避障/research/maps/` — v2/v3/v4/v5 PNG/yaml/pgm + README

### 明日（4/30）下一步

1. **早上**：物理錨定測試（plan Phase 1）→ yaw 一次定案
2. **早上**：重掃 v6 map → AMCL 跑 K1 baseline 0.5m × 5（≥ 4/5 即過）
3. **中午 12:00**：教授會議 + 簡報
4. **下午**（時間夠）：B-1 OpenRouter（DeepSeek V4 主、Gemini Flash 備）

### 不做（5/19 前 scope 控制）

- ❌ 不寫 scan_flipper_node（H1 排除）
- ❌ 不再改 yaw 第 5 次靠視覺猜
- ❌ Brain Phase B / C 留 5/19 後
- ❌ Studio UI 重做 留 freeze 後

---

## 4/28 進度

**PawAI Brain × Studio 從零做到 Phase A 完整骨架（17 commits 一日完成）**

### 完成事項

| Phase | 內容 | 狀態 | tag |
|-------|------|------|-----|
| **Phase 0** | Action Outlet Refactor — sport `/webrtc_req` 收成 Executive 單一出口 | ✅ | `pawai-brain-phase0-done` |
| **Phase 1 (A1)** | Brain MVS 後端 — brain_node + skill_contract + safety_layer + world_state + skill_queue + executive 重寫 | ✅ | `pawai-brain-phase1-done` |
| **Phase 2 (A2)** | Studio Brain Skill Console — schemas + gateway + mock + 8 React components + chat-panel 整合 | ✅ | `pawai-brain-phase2-done` |
| **Master Plan** | PawClaw Master Integration Plan v1.0（單一入口、5 條 review 修正併入） | ✅ | — |

### 驗證

- **interaction_executive**：77 tests pass
- **WebRtcReq audit**：OK（只 executive + tts_node 是合法發送者）
- **Topic contract v2.5**：5 個新 `/brain/*` + `/state/pawai_brain` 進 §2 表格
- **Studio mock smoke**：`/api/skill_request` `/api/text_input` `/mock/scenario/self_introduce` 三條全 200
- **TypeScript / ESLint**：clean（4 個 pre-existing 無關 warning）

### North Star 共識（2026-04-28 釐清）

> **PawAI Brain = 機器狗版 [OpenClaw](https://github.com/openclaw/openclaw)**
>
> 自然語言互動 + 居家互動/守護犬 + 所有能力暴露為 SkillContract + 危險動作經 deterministic safety。Phase A 是 OpenClaw-style 框架地基，不是 demo 終點；Phase B 加 Capability/BodyState；Phase C 接 LLM function calling。

### Codex 外包流程（成功 2 次）

兩次 Codex job 都採用「briefing → review feedback → v2 briefing → Codex 實作 → 5 點驗收 → merge + tag」流程，每次都在約 2-4 小時內完成數千行 PR-quality diff：

- A1 Brain backend：3 commits + 77 tests + WebRtcReq audit + 5 個 forward-compat 欄位
- A2 Studio Console：4 commits + 8 React components + REST 200 + WS envelope 一致

### 唯一文件入口

從今天起：[`docs/superpowers/plans/2026-04-28-pawclaw-master-integration.md`](../docs/superpowers/plans/2026-04-28-pawclaw-master-integration.md)（master 只管 north-star/scope/phase ordering；topic schema/API/施工細節以下游 spec/plan 為準）。

### 下一步（4/29 雙軌開發）

- **軌道 1（主軸）**：LiDAR mount STL 已印好 → 跑 roadmap Phase 1-7（量測 → SLAM → AMCL → K1/K2 → K5/K7）
- **軌道 2（背景）**：B-1 OpenRouter 接入 — 把 `llm_bridge_node` fallback chain 升級成 4 級（OpenRouter Sonnet 4.6 → 本地 Qwen2.5-7B → Ollama → RuleBrain），讓自由對話智商升級

### 4/30 教授會議後

隊員 push 過來時：宇童手勢 mapping、佩珍跌倒 TTS 文案、黃旭物體擴 whitelist、如恩語音正向表列；都是「加 brain rule + skill_contract 條目 + bubble 文案」，不是大整合。

### 不做（避免 5/16 demo 前 scope 失控）

- ❌ Studio UI 重做 — 留 5/14-5/18（freeze 後）用 ui-ux-pro-max skill 一次重做
- ❌ Phase B（Capability Validator / BodyState）— 5/19 驗收後啟動
- ❌ Phase C（LLM function calling）— Phase B 完成後
- ❌ 抄 4 個 PawAI repo PR — Phase 3 hooks，5/16 後

---

## 4/27 進度

**Phase 10 K1 撞牆 → 挖出從 4/25 上機就埋的雷**

### 觸發事件

跑 K1 warmup（`goto_relative 0.3m`）→ nav_action_server 拒收 `amcl_lost`。Go2 完全沒動 AMCL covariance 反而從 σ_y 0.52 漂大到 0.72。`/state/nav/safety` 顯示 `obstacle_distance=0.819m, zone=slow`，user 現場確認 Go2 前方根本沒東西。

### 重大發現（30 樣本 5 秒 angular probe）

Go2 右側 +15°~+100° 範圍（85° 寬）整片 0.82-0.99m reading，intensity 全部 = 15（max），jitter < 3mm。左側完全空（2-3m）。**完全不對稱、極穩、強反射** → 不是 ghost / 雜訊，是真實物體被 RPLIDAR 看到，最可能是 **Go2 自身揹包 / 拓展模組 / 電池蓋** 或 **mount yaw 偏 ~70°**（文件明寫 mount xyz yaw 從 4/25 起就沒量過）。

完整證據與三假設見 [`docs/導航避障/research/2026-04-27-rplidar-rightside-cluster-investigation.md`](../docs/導航避障/research/2026-04-27-rplidar-rightside-cluster-investigation.md)。

### 同步發現的平台 latent bug

`lifecycle_manager_localization` 自動 STARTUP **沒完成** — `map_server` 與 `amcl` 卡在 inactive（process 都活、tmux 8 window 都綠，但靜默失敗）。手動 `ros2 lifecycle set /map_server activate` + `/amcl activate` 兩次 transition 才上來。`lifecycle_manager_navigation` 卻是 active，所以表面看 stack 正常。Root cause 留作 5/13 前 todo。

### 三天 KPI 卡關真因（Linus 風格回顧）

1. **mount 從 4/25 第一天就沒量過** — `z=0.10` 估測，xyz yaw 全沒量。[4/25 log §3](../docs/導航避障/research/2026-04-25-rplidar-a2m12-integration-log.md) 寫「待精確量測」但延宕至今
2. **4/25 桌上 10.4Hz 通過 → 直接上機，沒做 scan angular audit** — 30 樣本角度分布該是 day-1 sanity，到今天才跑
3. **4/26 上午判定「lethal 是暫態 / map 髒污」 → 整下午重建地圖** — 但根因是 scan 本身有 phantom，新 map 一樣會被污染
4. **4/26 下午+晚上做 nav_capability S2 平台抽象（4 actions / 70 unit tests / 22+ commits）** — 抽象層 K9/K10 過了，但 K1 從沒成功一次。底層沒打穩，平台層蓋再多都是空中樓閣
5. **4/26 晚 covariance 0.53 紅當下沒查根因，推到 4/27** — 今天直接重啟變 0.72，更糟

### 物理 mount 升級調研

- amigo_ros2 README 連結 `pant_tilt_v2-1` 已 link rot（GrabCAD 404）
- GrabCAD 全平台 0 個 Go2+RPLIDAR mount
- MakerWorld 找到 8 個 Go2 背架候選，前 3 推薦：「宇树Go2 背部拓展板」/「Unitree GO2 Back Plate」/「Base Unitree Go 2 - T-Track 30」
- Demo 短期方案：3M VHB 雙面膠 + 手機水平儀（±3°），線材側邊綁出

### Phase 10 KPI 結果（無變化）

| KPI | 結果 | 備註 |
|-----|------|------|
| K1/K2/K4/K5/K7 | ⏳ **全部阻塞** | RPLIDAR 物理 mount + scan phantom 未解 → AMCL 無法收斂 |
| K8 | ✅ WSL 4/4 / 移出實機 | 不變 |
| K9 | ✅ heartbeat 1.001 / status 9.997 / safety ~10 Hz | 今天 rate 回到正常（4/26 是 2x 異常）— 可能 4/26 DDS ghost 已自然消失 |
| K10 | ✅ 3/5（user override 為 3 點） | 不變 |

### 工具升級

- 加 `Bash(agent-browser:*)` 到 `.claude/settings.local.json`（permission，個人不入版控）
- 全域安裝 `agent-browser` v0.26.0 + Chrome for Testing 148（用於需要 JS render 的 web 調研）

### 下次 session 接手

**優先級 P0（必做完才動 KPI）**：

1. user 用搖桿原地左轉 Go2 90°，重抓 30 樣本 angular probe → 判定 H1/H2/H3
2. 量 RPLIDAR 中心相對 Go2 base_link 實測 xyz（mm 尺）+ 雷達黑色 USB 線朝向（Slamtec 規定朝後 = 0° 朝前）
3. 判定後修法：
   - **H1/H3**：reactive_stop_node 加 `blank_angle_ranges_deg` param + `nav2_params.yaml` 改 `laser_min_range: 1.1`
   - **H2**：移 Go2 到開闊處重點 initialpose
4. 物理 mount 升級：選一個 MakerWorld 背架印 / 或 3M VHB 暫接

**P0 通過後跑**：

5. K1 warmup `goto_relative 0.3m` → covariance σ < 0.3m
6. K1（0.5m × 5）→ K2（0.8m × 5）→ K4（route × 3）→ K5⭐ → K7⭐

**Bonus**：

- root-cause `lifecycle_manager_localization` 自動 STARTUP fail
- 寫 `scripts/scan_health_check.py`（30 樣本 angular probe + intensity 異常標記）

### 新增/修改檔案

- 新增 [`docs/導航避障/research/2026-04-27-rplidar-rightside-cluster-investigation.md`](../docs/導航避障/research/2026-04-27-rplidar-rightside-cluster-investigation.md)
- 新增 [`docs/mission/meetings/2026-04-27-annie.md`](../docs/mission/meetings/2026-04-27-annie.md)
- 新增 [`docs/導航避障/lidar開發/2026-04-27-lidar-dev-roadmap.md`](../docs/導航避障/lidar開發/2026-04-27-lidar-dev-roadmap.md) — **支架印好後完整 7 階段開發路徑（v2.2）+ 歷史踩坑彙總**
- 個人 plan：`~/.claude/plans/snug-seeking-cascade.md`（plan-mode 產物，不入版控）

### LiDAR 開發藍圖（5/9 起執行）

完整 plan：[`docs/導航避障/lidar開發/2026-04-27-lidar-dev-roadmap.md`](../docs/導航避障/lidar開發/2026-04-27-lidar-dev-roadmap.md)

7 階段路徑（user 已選好 mount STL，等支架印好開工）：

```
1. Mount 量測 + TF 更新（5 scripts + build_map.sh echo）  ← 30 分鐘（裝完當天必做）
2. Scan 健康驗證（scan-only stack）         ← 1 小時
3. SLAM 重建圖                              ← 1.5 小時
4. AMCL 校正（laser range 先 → beamskip 後） ← 1.5 小時
5. Nav2 K1/K2                              ← 1 小時
6. 動態安全 K5/K7（reactive + pause + emergency）← 1.5 小時
7. 自動巡邏 K4 + Brain                      ← 2-4 小時
```

**最低限度 demo（5/13）**：1+2+3+4+5；**目標**：再加 6+7；**不做**：「人擋路自動繞」、進階導航。

Plan 修正歷程 v1 → v2 → v2.1 → v2.2，含**歷史踩坑彙總 9 大類 40+ 條**（雷達物理 / RPLIDAR scan 品質 / AMCL Nav2 設定 / Go2 driver / tmux mux 路由 / cartographer / ROS2 工具鏈 / 架構決策 / Linus 反思）。之後開發**先看那節**，避免重蹈覆轍。

### 主時程（2026-04-27 確定）

- **5/8 deadline**：PawAI Brain MVS 必須到 70%（另一份 plan）
- **5/9-5/12**：LiDAR 7 階段開發（本 plan）
- **5/11-5/12**：freeze（spec 強制）
- **5/13**：學校 demo

### 4/27 晚 Annie 外部諮詢會議（董偉峰指導 + Annie 外部教授 + Roy/若恩/黃旭）

完整紀錄：[`docs/mission/meetings/2026-04-27-annie.md`](../docs/mission/meetings/2026-04-27-annie.md)

**現場展示**（黃旭 Web Dashboard，Go2 不在現場用線上 demo）：
- 人臉打招呼（認得 Roy）/ 手勢比讚 → happy / 物件辨識 / 姿勢站立蹲下 / 語音對話（天氣 / 笑話 / 自介）

**Annie 提案 4 個方向**（**全部未承諾、不阻塞 5/13 demo 主線**）：
1. **對話延續性**：強化 ChatGPT 式主動反問 / 引導，由若恩處理
2. **Affective Computing ⭐**：audio-visual 情緒辨識 → LLM prompt 帶情緒 metadata → emotional support 回應。**未排程，需另開研究 spec**
3. **TTS 升級**：Gemini 2.5 Flash TTS 評估（語氣自然度顯著高於 edge-tts / Piper）。**5/13 demo 後排程**
4. **LiDAR 頂部支架**：魔鬼氈不夠穩，需印固定支架。**已併入 4/27 RPLIDAR 物理 mount 調查**（同方向，不重複工作）

**待議**：下次可邀 Annie 介紹同校 affect computing dataset

---

## 4/27 late night — PawAI Brain Skill-first MVS 設計收斂 + PawClaw 演進路線

**晚上轉軌：白天 LiDAR 卡關後，把時間投到 Brain 架構，避免兩線同時阻塞。**

### 決策脈絡（brainstorming）

**起點問題**：speech intent 直接進 state_machine、Executive 也直接發 `/cmd_vel`，且 `/webrtc_req` 同時被 `llm_bridge_node` / `interaction_executive_node` / `event_action_bridge` **三個 publisher 競爭**（其中兩個沒 banned_api 守衛）。直接加新 Brain 變第四個寫手，重演導航踩過的「多控制源互搶」事故。

**設計方向 5 次迭代收斂**：
1. → **Phase 0 refactor**：sport `/webrtc_req` 收成 Executive 單一出口，TTS audio `/webrtc_req`（tts_node Megaphone 4001-4004）保留不動；llm_bridge 加 `output_mode: legacy|brain` feature flag 漸進切換
2. → **Brain in interaction_executive package**（不開新 package，brain_node + executive_node 雙 entry_point，共用 safety_layer / skill_contract / world_state modules）
3. → **Brain 純規則 + llm_bridge 改發 /brain/chat_candidate**（LLM 變 proposal source，不直接控狗）
4. → **Skill-first reframe**：所有能力（聊天 / 動作 / 導航 / 警示）統一 SkillContract；Executive 只認 say/motion/nav 三個 primitive executor
5. → **Studio Chat = Brain Skill Console**（不是另開 dashboard，Chat 即決策可視化）

7 場景 MVS：你好 / 停 / 介紹自己 / wave / 陌生人 3s / 熟人問候 / 跌倒。Hybrid 路由（Safety 關鍵字硬擋 + 規則 + 1500ms LLM chat_candidate 等待）。

### Linus 風格 review 發現的 4 個 P0/P1 bug（已修）

1. **P0**：plan 只在 `_dispatch()` 加 brain mode 閘門，但 `_rule_fallback()`（fast-path + LLM-fail 都會走）仍會發 `/tts` 和 sport `/webrtc_req` → **兩個決策出口都加閘門 + plumb session_id/confidence 全鏈**
2. **P0**：plan snippet 用 `_load_parameters` 但實際是 `_read_parameters`；`_dispatch(result, source)` 只有 2 args 卻在 plan 裡塞 session_id → **signature 全部對齊**
3. **P1**：驗證 grep 是 single-line，會漏掉現有 multi-line publisher → **改用 `rg -U` + Python AST `audit_webrtc_publishers.py` 腳本**
4. **P1**：Executive 被 SAFETY/ALERT 中斷時，ABORTED 用新 plan 的 metadata 標老 plan → **`_ActiveStep` 改持 SkillPlan 完整參考；worker_tick 也改用 `_active.plan` 避免 post-preempt race**

### PawClaw 演進（5/16 demo 後 Phase B）

借鑑 [openclaw/openclaw](https://github.com/openclaw/openclaw) 的 harness engineering pattern，**派 Explore subagent 深掘** repo + docs 後產出可偷 / 不該偷對照表（4 偷 / 5 簡化 / 7 不偷）。Phase B 三大新增：

- **CapabilityRegistry**（SkillContract 加 `enabled_when: list[CapabilityPredicate]`）— 動態 enable/disable per skill，理由人類可讀
- **BodyState**（擴 WorldState 加 AMCL covariance / map_loaded / nav_stack_ready / battery / sensor liveness）— Brain 發 plan 前已知道身體可不可行
- **Nav Skill Pack** 6 條 — 對接 `nav_capability` 既有 4 actions（GotoNamed / GotoRelative / RunRoute / LogPose）+ 3 services（pause/resume/cancel）；NAV step 真正進 Executive dispatch

**MVS 已做 forward-compat patch**（不打斷明天的 Phase A execution）：
- `SkillContract` 新增 `static_enabled` / `enabled_when` / `requires_confirmation` / `risk_level` 欄位（safe defaults）
- `go_to_named_place` 從 `enabled=False` 改成 sentinel `enabled_when=[("phase_b_pending", "...")]`
- `build_plan()` 認得 sentinel 並 raise 帶 reason 的 ValueError → Studio 可顯示「我為什麼不能做」的人話訊息

### 交付物（5 個 commit）

| Commit | 內容 | 行數 |
|---|---|---|
| `43aa039` | Spec — Brain MVS Skill-first design | 769 行 |
| `31febe6` | Plan — MVS 34-task implementation | 3650 行 |
| `6c8d79d` | Overview — Brain × Studio 整合總覽（對外 / 論文用） | 466 行 |
| `59921ed` | Plan fix — 4 review corrections（P0×2 + P1×2） | +489/-86 |
| `07e0287` | PawClaw evolution spec + MVS forward-compat patch | +736 |

合計 **~5400 新行文件、0 程式碼**。明天起進 Phase A execution。

### 明天 Phase A 起手式

```
Task 0.1: llm_bridge 加 output_mode param
   ↓
Task 0.2: 雙閘門 + chat_candidate publisher（10 sub-step + 3 smoke test）
   ↓
Task 0.3: tts_node audio-api guard test
   ↓
Task 0.4: event_action_bridge launch arg
   ↓
Task 0.5: AST audit + 既有 e2e smoke + tag pawai-brain-phase0-done
   ↓
Phase 1（5-6 天）: 5 新檔 + 4 unit test + executive rewrite
   ↓
Phase 2（3-4 天）: Studio Brain Skill Console 8 components
```

### 新增/修改檔案

- 新增 [`docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md`](../docs/superpowers/specs/2026-04-27-pawai-brain-skill-first-design.md) — Brain MVS spec（Phase A）
- 新增 [`docs/superpowers/plans/2026-04-27-pawai-brain-skill-first.md`](../docs/superpowers/plans/2026-04-27-pawai-brain-skill-first.md) — 34-task implementation plan
- 新增 [`docs/superpowers/specs/2026-04-27-pawclaw-embodied-brain-evolution.md`](../docs/superpowers/specs/2026-04-27-pawclaw-embodied-brain-evolution.md) — Phase B PawClaw 演進
- 新增 [`docs/architecture/pawai-brain-studio-overview.md`](../docs/architecture/pawai-brain-studio-overview.md) — 對外整合總覽（466 行，含 Phase A/B 兩段）

---

## 4/26 進度

**P0-D Nav2 動態避障實機驗證 + reactive_stop_node fallback（雙管齊下）**

### A 線：Nav2 lethal space 翻案
- 上午 SSH 進 Jetson 跑 A0 診斷流程（不改參數）
- **0.5m goal**：amcl 14cm 移動，現場確認 ✅
- **0.8m goal × 2**：amcl 50cm（用戶現場確認 ~50cm 真實移動）✅
  - 起始位置 (1.19, 0.56) **接近昨天 lethal 區域 (1.56, -0.16)**，今天直接 plan 成功
- **重大判定**：昨天 lethal 是**暫態**（costmap 髒污 / particle filter 漂移），不是位置固有問題、不是 inflation 過大、不是 footprint padding
- **v3.7 nav2_params 不需修改**（不執行 plan v2 提的「階梯一」參數調整）
- 中途 Jetson 跳電一次（XL4015 已知），重啟後流程順利

### A 線發現的兩個 bug
1. **`/goal_pose` QoS mismatch**：bt_navigator 訂閱用 BEST_EFFORT，但 `send_relative_goal.py` publisher 預設 RELIABLE → 訊息丟失。CLAUDE.md 早警告「不要 `ros2 topic pub --once /goal_pose`」是同一原因。已修：publisher 改 BEST_EFFORT + 加 `_wait_for_subscriber()` 等 DDS discovery
2. **連發 5 個 goal preemption 太密集**：controller 0.5s 內被打斷 3 次，導致 `Reached the goal!` 在距離 goal 0.5m 時就誤觸發。已修：預設 `--repeat 1 --rate 0.5`

### A 線收尾（待用戶回家繼續）
- 用戶判定「map 髒污過多太亂」→ 啟 cartographer 重新建圖流程
- 已備份舊 map 為 `home_living_room.{yaml,pgm,pbstream}.bak.20260426-094853`
- cartographer 6-window stack 已啟動驗證 OK（scan 11.13Hz、`Inserted submap (0, 1)`），用戶出門前已停 lidar-slam tmux
- 待續：用戶回家遙控 Go2 繞客廳一圈 → 三步驟存圖 → 重啟 nav2-amcl 用新 map 重跑 0.8m goal

### B 線：reactive_stop_node 開發完成
- 純 ROS node，訂 `/scan_rplidar` → 發 `/cmd_vel` @ 10Hz
- 前方 ±30° 扇形：< 0.6m STOP / 0.6-1.0m SLOW(0.45) / ≥ 1.0m NORMAL(0.60)
- LiDAR 中斷 > 1s emergency stop，含 hysteresis（danger → 非 danger 需連 3 frame）+ warmup 第一筆 cmd_vel = 0
- **17 case 單元測試全綠**（dev + Jetson 都驗）— front arc filter / wrap-around / range_min skip / classification boundary
- Jetson dry-run（無 Go2 driver）：cmd_vel 10Hz 穩定、CSV 全 0、zone transition log 正確
- **未做**：4 場景實機驗收（Go2 + reactive 全 stack）— 用戶判斷今日先做 A 線，B 線實機留 5/13 demo 前

### 新增/修改檔案
- 新增 `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`（純 helpers）
- 新增 `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`（≈ 130 行）
- 新增 `go2_robot_sdk/test/test_reactive_stop_node.py`（17 cases）
- 新增 `scripts/send_relative_goal.py`（讀 amcl_pose 算前方相對 goal）
- 新增 `scripts/start_reactive_stop_tmux.sh`（4-window）
- 新增 `docs/導航避障/research/2026-04-26-nav2-dynamic-obstacle-log.md`（完整實機 log）
- 修改 `go2_robot_sdk/setup.py`（加 reactive_stop_node entry point）

### 下次 session 接手
1. 重新建圖（用戶遙控 Go2 繞客廳，慢速 ≤ 0.15 m/s）
2. 三步驟存圖（`/finish_trajectory` → `/write_state` → `map_saver_cli`）
3. 用新 map 重跑 0.8m / 1.0m goal 驗證首次 plan 不再失敗
4. reactive_stop_node 4 場景實機驗收
5. 動態避障 bonus（人走入路徑看 Nav2 dynamic re-plan）

---

## 4/26 晚進度

**nav_capability S2 平台化導航（Phase 0–9 完成 + Phase 10 KPI 部分驗收）**

### Phase 0–9 落地（22+ commits）

把 P0 reactive 邏輯抽象成「平台層」`nav_capability`，把 4 個 action / 3 個 service / 3 個 state topic 介面化，給 interaction_executive 與 PawAI Brain 使用：

- **Actions**：`/nav/goto_relative` / `/nav/goto_named` / `/nav/run_route` / `/log_pose`
- **Services**：`/nav/pause` / `/nav/resume` / `/nav/cancel`
- **State**：`/state/nav/heartbeat` (1Hz) / `/state/nav/status` (10Hz) / `/state/nav/safety` (10Hz)
- **Event**：`/event/nav/waypoint_reached` / `/event/nav/internal/status` / `/state/reactive_stop/status`
- **twist_mux 4 層**：emergency(255) > obstacle(200) > teleop(100) > nav2(10) + Bool `/lock/emergency`

新 nodes：`nav_action_server_node` / `route_runner_node` / `log_pose_node` / `state_broadcaster_node`。共 70 unit/integration tests pass（WSL）。

**Spec / Plan**：[`docs/superpowers/specs/2026-04-26-nav-capability-s2-design.md`](../docs/superpowers/specs/2026-04-26-nav-capability-s2-design.md) / [`docs/superpowers/plans/2026-04-26-nav-capability-s2.md`](../docs/superpowers/plans/2026-04-26-nav-capability-s2.md)

### 兩個重大修法（commit 8ec9a59 + e2b3932）

1. **`reactive_stop_node` safety_only mode** — 原設計是 standalone fallback「永遠驅動前進」，當被 repurpose 接到 mux priority 200 後，clear zone 時 0.60 m/s 永遠 shadow nav。實機 dry-run 抓到 Go2 衝出，新增 `safety_only` param：mux 模式只在 danger / emergency 發 0.0，clear / slow 不發，讓 nav 通過。`scripts/start_nav_capability_demo_tmux.sh` 已加 `-p safety_only:=true`。
2. **runtime path** — `named_poses_file` / `routes_dir` 預設指 `pkg_share/config/`，會被 colcon build 覆蓋且不在 git 之外。改用 `~/elder_and_dog/runtime/nav_capability/{named_poses,routes}/`，tmux 啟動時 `mkdir -p` 自動建。

### Phase 10 P0 KPI 結果（5/8 驗收，3/8 推遲）

| KPI | 結果 | 備註 |
|-----|------|------|
| K8 mux integration | ✅ WSL 4/4 / **移出實機** | FakePublisher `/cmd_vel_nav` = 0.30 透過真實 mux 進 go2_driver → Go2 衝出。永久規則：K8 不在 full stack 跑 |
| K9 state topic rate | ✅ heartbeat 2.02Hz / status 20.00Hz / safety 20.04Hz | 全 ≥ 門檻；rate 2x 預期（DDS ghost participant 異常，待 root cause） |
| K10 log_pose | ✅ 3/5（user override 為 3 點） | runtime path 寫入確認；alpha/beta/gamma 都 SUCCEEDED |
| K1/K2/K4/K5/K7 | ⏳ 推遲 | AMCL covariance 0.53（紅）需先收斂；用戶判定問題太多今日先收 |

### Phase 10 事故記錄
- 22:30 跑 K8 時 Go2 撞 — fake_nav publishes 0.30 m/s 走 mux→driver→馬達。原因是 plan 把 K8 排在 full stack。修正：K8 移出實機驗收（plan + 此 status 都註記）。

### 下次 session 接手
1. 重啟 stack `bash scripts/start_nav_capability_demo_tmux.sh`（含 e2b3932 runtime path）
2. Foxglove 設 initialpose → 等 AMCL covariance 收斂到 yellow（≤0.5）或 green（<0.3）
3. K1（goto_relative 0.5m × 5）→ K2（0.8m × 5）→ K4（run_route × 3）→ K5⭐（pause/resume × 3）→ K7⭐（emergency × 3）
4. （可選）量測 base_link → laser z 實際值，更新 `start_nav_capability_demo_tmux.sh` L40 `--z 0.10`
5. （bonus）K3/K6/K11 P1 KPI；root-cause state_broadcaster 2x rate

### 新增/修改檔案（commit `9ef3875`..`e2b3932`）
- 新增 `nav_capability/` 全包（4 nodes + 5 lib modules + 38+5 unit tests + 4 mux integration tests）
- 新增 `go2_interfaces/{action,srv}/`（4 actions + Cancel.srv）
- 修改 `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`（+ safety_only mode + nav pause/resume bridge）
- 修改 `go2_robot_sdk/config/twist_mux.yaml`（4-layer + Bool lock）
- 修改 `go2_robot_sdk/launch/robot.launch.py`（改用 nav_capability wrapper）
- 新增 `nav_capability/scripts/emergency_stop.py`（CLI helper）
- 新增 `scripts/start_nav_capability_demo_tmux.sh`（Phase 10 demo 8-window）
- 修改 `scripts/start_nav_capability_demo_tmux.sh`（runtime path env override）

---

## 4/24-4/25 進度

**RPLIDAR A2M12 外接雷達到貨 + 實機驗證通過**：

- Jetson 接上 RPLIDAR（兩條 USB：資料 + 輔助電源），CP2102 drive 正常 enumerate
- `sllidar_ros2` clone + colcon build + udev rule 設好（`/dev/rplidar` symlink 0777）
- 實測：`/scan` **10.57 Hz** / **1800 points/scan**（0.2° 解析度，比 datasheet 0.225° 更密）/ 60% valid / 0.20-7.94m range / 中位數 1.08m
- Foxglove bridge 可視化通過（port 8765）

**舊 LiDAR 問題全部解決**（對照 docs/導航避障/research/）：

| 歷史痛點（Go2 內建 LiDAR） | 現況（RPLIDAR A2M12 外接） |
|---------------------------|--------------------------|
| 7.3Hz 靜止 / 4-6Hz 行走 / burst+gap | **10.57Hz 穩定，無 gap** |
| 18% 覆蓋率（22/120 有效點） | **360° 完整，1600 點/圈** |
| Python LZ4 decode 單核滿載 | **純 C++ serial driver，CPU 近零** |
| 7 輪優化才達 5Hz | **開箱即 10Hz** |

**架構決策翻案**（4/1 判定的「Full SLAM 永久關閉」失效）：

- 舊判定基於 Go2 內建 LiDAR 5Hz 品質差，業界 SLAM 門檻 7Hz
- 新實測 RPLIDAR 10.5Hz 超過門檻 → **Full SLAM / Nav2 路線復活為 P0 主線**
- `docs/導航避障/README.md` 的「架構決策 2026-04-01」加 Supersedes 註記

**P0 導航避障 spec + plan 定稿**：

- Spec: `docs/superpowers/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`（803 行）
- Plan: `docs/superpowers/plans/2026-04-24-p0-nav-obstacle-avoidance.md`（17 tasks, gate-by-gate TDD）
- P0 承諾：劇本式 A→B + 停障 + 續行（不承諾一般繞障）
- P1 Stretch：單一靜態障礙繞行（5/6 P0-I KPI 4/5 通過才啟動）
- 嵌入 PawAI Brain 三層架構：Safety Layer 新增 Emergency latched FSM + Obstacle auto-recovery FSM，Policy Layer 新增 `patrol_route` skill（deterministic，不經 LLM），Expression Layer 新增 `safety_tts` 固定 6 句模板
- 10 條硬規則：LLM 不進安全鏈、locomotion 不經 LLM、固定模板 TTS、latched emergency、pause>15s abort、5/11-5/12 freeze、recovery 全關、5/13 當天重建地圖、5/1 emergency 硬截止、學校地圖不賭舊版

**關鍵 milestone**：

- **5/1 emergency latch hotkey 硬截止**（Gate P0-F 不過不上 Go2 合體）
- **5/6 家中排練 KPI**：4/5 成功 GO / 3/5 YELLOW / ≤2/5 NO-GO
- **5/11-5/12 Freeze 期**：Bugfix only，禁止新功能
- **5/13 到學校現場重建地圖**（不賭前一天地圖）

**4/25 明日繼續**：Task 1（Gate P0-B — SLAM 建圖）

---

## 4/25 晚進度同步會議 + PR Review

**4/25 21:00 會議**（教授 + Roy + 佩珍 + 如恩 + 黃旭 + 宇童 + 偉民學長線上）：

- 完整紀錄：[`docs/mission/meetings/2026-04-25.md`](../docs/mission/meetings/2026-04-25.md)
- 會議性質：週六進度同步 +「禮拜一 (4/27) UIT 訪客交流」前的成果盤點
- **4/27 19:00 線上交流**：UIT 助理教授（華人 AI 研究），非驗收性質
- **5 月驗收 + 6 月發表**：黃淮生老師（有 robot 經驗）大概率當校外評審
- **教授 demo 策略**：正向表列優先、避免跨模組 conflict、加 entertainment 元素（跳舞/伸懶腰）
- **Roy 明天衝刺**：動態避障「繞開」demo 影片（教授定義為「第二難關」），週一播

**4 個夥伴功能 PR review**（Linus 風格）：

| PR | 作者 | 模組 | 結論 |
|----|------|------|------|
| #38 | Yamikowu | 手勢前端 | REQUEST_CHANGES — port 寫 8080 但 server 是 8001 / enum 違反 contract / unbounded fan-out |
| #40 | Capybara094 (Elio) | 物件辨識 | REQUEST_CHANGES — 32MB 模型 binary 進 git / 用了禁用的 ultralytics / mock_server `/mock/yolo/start` RCE |
| #41 | GuaGua0216 (瓜瓜) | 姿勢前端 | REQUEST_CHANGES — 空殼 lockfile / useEffect deps race / `test_pose.py` 副作用 |
| #42 | katiechen128 (如恩) | 語音 | REQUEST_CHANGES — Shell injection / 雙音訊播放 / studio_api.py 繞過 ROS2 contract / CI 兩 job FAIL |

**共通系統性問題**：沒人對齊 `interaction_contract.md`、binary 檔亂入 git、port 全亂（5000/8000/8001/8080）、scope 失控

**各模組功能提取計畫**（明天實作）：

- [`docs/姿勢辨識/research/2026-04-25-pr41-extraction-plan.md`](../docs/姿勢辨識/research/2026-04-25-pr41-extraction-plan.md) — 分類細則 + pose schema
- [`docs/手勢辨識/research/2026-04-25-pr38-extraction-plan.md`](../docs/手勢辨識/research/2026-04-25-pr38-extraction-plan.md) — `_is_waving()` 算法 + UI panel
- [`docs/語音功能/research/2026-04-25-pr42-extraction-plan.md`](../docs/語音功能/research/2026-04-25-pr42-extraction-plan.md) — TTS voice + zhconv 簡轉繁 + 去重邏輯
- [`docs/辨識物體/research/2026-04-25-pr40-extraction-plan.md`](../docs/辨識物體/research/2026-04-25-pr40-extraction-plan.md) — retry 邏輯（重寫去 ultralytics）+ 雙模式 UX

---

## 4/12 今日進度

**專題文件衝刺(迎戰 4/13 繳交 deadline)**:

- **Ch3 系統範圍**擴寫完成(9,112 字),以 MeetSure 格式 3-1~3-10 逐項描述使用者操作情境 + 後端技術,含導航避障 Option C 條件式敘述、守護能力、自主展示
- **Ch4 背景知識**擴寫完成(13,492 字),並**額外拆為 10 個獨立 md 檔**存於 `docs/thesis/背景知識/` 便於分節驗收:
  - 4-1 ROS2 / 4-2 Unitree Go2 / 4-3 MediaPipe Gesture / 4-4 MediaPipe Pose / 4-5 YuNet + SFace / 4-6 Speech / 4-7 YOLO26 / 4-8 Navigation / 4-9 Jetson / 4-10 D435
- **Ch5 系統限制**擴寫完成(9,401 字),13 大類涵蓋硬體 / 運算 / 語音 / 視覺 / 多人權限 / 隱私等
- **三章合計從 ~6,400 字 → 32,005 字(約 5× 擴寫)**

**32 項 code/文件不一致修正**(經 subagent 交叉比對 + 上網查證):

- 🔴 Go2 Pro LiDAR:Hesai XT16 → **Unitree 自研 4D LiDAR L2(360°×96°)**,Hesai XT16 僅配於 EDU Plus
- 🔴 Go2 EDU 售價:$3,500-8,500 → **$14,500(EDU)/ $22,500(EDU Plus)**
- 🔴 Pose 五類:standing/sitting/crouching/**lying**/fallen → standing/sitting/crouching/fallen/**bending**(對齊 `pose_classifier.py:22`)
- 🔴 Pose 閾值全面訂正:fallen `bbox_ratio > 1.5` → `> 1.0`;standing `knee > 150` → `> 155`;sitting `hip 90-140 / trunk < 30` → `100-150 / < 35`;crouching 條件改為 `hip<145 AND knee<145 AND trunk>10`
- 🔴 `/state/perception/pose` topic **刪除**(不存在,只有 `/event/pose_detected`)
- 🔴 stop 手勢「無冷卻」宣稱訂正:仍受 `DEDUP_WINDOW=5.0s` 全域約束(`state_machine.py:60`)
- 🔴 手勢映射表:刪除 Victory / Pointing_Up 互動(Executive 未處理)
- 🔴 `gesture_vote_frames` 10 → **5(code default)/ 3(yaml 覆寫)**
- 🔴 LLM `max_tokens` 120 → **80**(`llm_bridge_node.py:165`),SYSTEM_PROMPT 硬截斷 25 字 → **12 字**
- 🔴 語音管線改為雙路徑描述:Demo 主線 Studio push-to-talk → Gateway → Cloud SenseVoice(無 VAD);舊本地路徑保留 Energy VAD
- 🔴 Whisper 敘述澄清三層關係:yaml 預設 `tiny + cpu + int8`;`start_full_demo_tmux.sh:145` 覆寫 `cuda + float16`;Whisper 僅為三級 fallback 最末層
- 🔴 D435 深度技術:「紅外線結構光」 → **Active IR Stereo(主動紅外線立體視覺)**
- 🟡 face Hysteresis 敘事澄清 code default vs yaml 覆寫分層
- 🟡 OpenCV 版本要求:4.5.4+ → **≥ 4.8**(`face_identity_node.py:142` require)

**同步修正的 code/文件不一致**(本次 update-docs 撰寫時一併處理):

- `docs/語音功能/README.md` 狀態卡「本地 ASR/LLM 不可用」與下方三級 fallback 流程矛盾 → 澄清本地 ASR 可作 fallback、本地 LLM 僅形式備援
- `docs/人臉辨識/AGENT.md` 的 `/camera/aligned_depth_to_color/image_raw` 缺 double namespace、OpenCV 4.5.4+ 過時宣稱 → 訂正為 `/camera/camera/aligned_depth_to_color/image_raw` + OpenCV ≥ 4.8
- `CLAUDE.md` 行 22、365 的 Whisper 敘述容易誤導 → 澄清 CPU int8(yaml 預設)可用、CUDA int8 不支援、Demo 啟動腳本覆寫為 CUDA float16 三層關係

**產出檔案**:

- `docs/thesis/114-thesis.md`(三章擴寫已合入)
- `docs/thesis/114-thesis.docx`(pandoc 轉檔完成)
- `docs/thesis/背景知識/4-*.md`(10 個獨立背景知識檔,待驗收後決定是否整合回 114-thesis.md)

**尚未決定**:背景知識/ 10 份獨立檔是否要整合回主文件 Ch4。等使用者驗收後再決定。

**第二輪 fact-check 修正**（使用者抽查 + Claude 復驗交叉比對程式碼）:

9 章中 7 章一次通過,2 章補修:
- 4-3:Gesture Recognizer 路徑不經 `gesture_classifier.py` 幾何特徵（端到端分類）
- 4-2:音訊播放主線改為 USB 外接喇叭,Megaphone 降為備援

主要修正項（跨 9 個檔案,+373/-32 行）:
- **4-1**:Skill Queue/Action 降級為「規劃中,尚未落地」
- **4-2**:LiDAR Hz 修正（<2Hz → 靜止 7.3Hz/行走 5-6Hz）+ Megaphone 降為備援
- **4-3**:gesture_backend 區分程式預設 rtmpose vs Demo 覆寫 recognizer；thumbs_up TTS「收到」→「謝謝」；手勢過濾改為 vision_perception 白名單；stop 依契約不受 cooldown
- **4-4**:pose_classifier 吃 COCO 17 點（經 `_MP_TO_COCO` adapter）；Lite not Full；fallen 幻覺 Demo 用 `enable_fallen:=false` 關閉
- **4-5**:`/state/perception/face` 非 8Hz（每 tick 發布）；det_score code 0.90/yaml 0.35 雙值
- **4-6**:Studio 主線 gateway 直打 ASR（不經 stt_intent_node）；Whisper Small→Tiny；event_action_bridge→interaction_executive
- **4-8**:LiDAR Hz 對齊 4-2
- **4-9**:資源表補「Demo 部署主線覆寫配置」說明
- **4-10**:align_depth 改為「相機啟動時啟用,face node 訂閱已對齊 topic」

**Ch5 系統限制獨立檔**（新增）:
- `docs/thesis/5-系統限制與可行性分析.md`（13 節,含延遲鏈分解、距離對照表、RAM 預算表、Megaphone 逆向工程、ARM 碎片化等技術深度）
- 使用者抽查後補修 5 處:光線影響降級為定性描述、供電電壓補 19.2V/20V 雙值、odom 0.3m 標示為規劃門檻、測試數量改為不精確描述、最靠近原則補語氣保留

**合併版產出**:
- `docs/thesis/Ch4-背景知識-合併版.md`（10 章按 4-1→4-10 順序拼接,Python 驗證腳本確認 523 行 0 缺失）
- `docs/thesis/Ch4-背景知識-合併版.docx`（79KB）
- `docs/thesis/5-系統限制與可行性分析.docx`（26KB）

---

## 4/11 重大方向更新

**產品定位**：居家守護犬 → **居家互動機器狗（兼具守護能力）**
**互動 / 守護比例**：互動 70% / 守護 30%
**系統核心命名**：Guardian Brain → **PawAI Brain**（守護術語保留在子域）
**Demo 結構**：開場 self_introduce Wow Moment + 互動主秀 + 陌生人警告 + 收尾

**分工調整**：
- **黃旭 ↔ 鄔雨彤 交換**：黃旭做手勢、鄔雨彤做物體
- **楊沛蓁**：專注姿勢擴充（久坐提醒邏輯）
- **陳如恩**：新增雲端 API fallback 測試（Groq / Gemini）+ 記憶功能

**守護能力收斂**：
- 陌生人警告（Demo 實演，附 anti-false-positive policy）
- 巡邏（雷達到貨後實演 or 錄影）
- 跟隨（不做實作，只寫進文件 future work）

**雷達狀態**：**確定採購**，老師跑國科會流程中，到貨時程未定

**新 spec（current）**：[`docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md`](../docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md)
**舊 spec（superseded）**：[`docs/superpowers/specs/2026-04-10-guardian-dog-design.md`](../docs/superpowers/specs/2026-04-10-guardian-dog-design.md)

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **Chat 閉環 12 句對話通過** | 4/8 | **Studio Chat 閉環實機驗證通過**：文字+語音→ROS2→LLM→/tts→AI bubble+喇叭；12 句連續對話全部正確回覆；E2E ~2s；**待改善**：LLM 回覆過短（`llm_max_tokens=80` + SYSTEM_PROMPT 硬截斷 12 字）、無多輪 memory、回覆缺乏個性 |
| 人臉 (face_perception) | **greeting 可靠化** | 4/6 | sim_threshold 0.35→0.30，identity_stable 21 次/2min（調前 1-3 次），Executive idle→greeting 確認通；track 抖動仍在（45 tracks/2min），Day 12 修 |
| 手勢 (vision_perception) | **上機驗收 5/5** | 4/4 | stop/thumbs_up/非白名單/距離/dedup 全 PASS |
| 姿勢 (vision_perception) | **上機驗收 4/4** | 4/4 | standing/sitting/fallen→EMERGENCY/恢復→IDLE 全 PASS |
| LLM (llm_bridge_node) | **E2E 通過** | 4/1 | Cloud 7B → RuleBrain，greet cooldown dedup 正確 |
| Studio (pawai-studio) | **Chat ROS2 閉環 + Live View 實機通過** | 4/7 | Chat 走 ROS2 pipeline 閉環（文字/語音→LLM→/tts→AI bubble）；錄音音量動畫（AnalyserNode 7 bars）；Live View 三欄影像；gateway-url 統一；start-live.sh 正式站；mock TTS event 修復；31 tests PASS |
| CI | **17 test files, 225+ cases** | 4/1 | fast-gate + **blocking contract check** + git pre-commit hook |
| interaction_executive | **v0 + thumbs_up 擴展 + fallen 可關** | 4/6 | thumbs_up 在 GREETING/CONVERSING 也生效；`enable_fallen` 參數化（demo 關閉）；39 tests PASS。**4/27 night**: Brain Skill-first MVS spec + 34-task plan + PawClaw 演進 spec 落地（純文件，0 程式變更），4/28 起進 Phase A execution — brain_node + executive 重寫 + 9-skill registry + Studio Brain Skill Console |
| 物體辨識 | **Executive 整合完成** | 4/6 | cup 觸發 TTS「你要喝水嗎？」✅；book 偶爾辨識（0.3 threshold 下）；bottle 未偵測到；YOLO26n 小物件偵測率低，yolo26s 升級記錄到 Day 12+ |
| 導航避障 | **Nav2 0.8m 自主前進實機驗證 + reactive_stop fallback** | 4/26 | 0.8m goal 走 50cm 用戶現場確認；昨天 lethal 判定為暫態（v3.7 nav2_params 不需改）；reactive_stop_node 完成 17 tests pass + Jetson dry-run 通過；發現並修兩 bug（goal_pose BEST_EFFORT QoS、preemption 過密）；待續：重新建圖（用戶判定 map 髒污）+ B 線 4 場景實機驗收 |

## 4/9 外部會議 + 核心方向 Brainstorm

### 與會者
盧柏宇（Roy）、董偉峰老師、Perry 老師、王瑞（矽谷創業經驗）、安卓、陳若恩、黃旭、楊培生

### 外部建議重點（Perry 老師）
- **缺核心主軸**：功能多但沒有一個故事串起來，評審會問「為什麼用機器狗不用攝影機」
- **看門狗方向**：人臉辨識→陌生人警報，不需複雜導航
- **R2-D2 互動**：用動作+聲音表達情緒，避免 LLM bias
- **跟隨功能**：YOLO 追蹤人體背面，不需正面人臉
- **推播通知**：跌倒→通知晚輩（類 Apple Watch）
- **長照審查嚴格**：面對弱勢族群評審角度完全不同

### 外部建議重點（王瑞）
- **Cerebras / Groq**：超快 LLM 推理，免費額度，值得評估
- **RAG 記憶**：記錄對話→產生報告給家屬
- **目標消費者**：青壯年買給長輩，不是長者自己買

### 方向 Brainstorm 結論（尚未定案，4/10 繼續）

**收斂方向**：
> 「PawAI — 會主動接近並理解人的居家互動守護犬」
> Demo 核心句：「它不是看著你，而是會認出你、走向你、回應你，並在異常時替家人留意。」

**敘事定位**：從「長照」退到「居家互動守護」，避免弱勢族群審查強度

**Roy 負責兩軸**：
1. **大腦升級**：Groq 免費 API（延遲 ~1.5s→<0.5s）+ function calling Skills 架構 + Mem0 記憶
2. **導航避障**：傾向購買 RPLIDAR A2M12，最壞情況 360° 避障仍值得；Day 1 驗證 odom 品質

**大腦升級工具評估**：
- **Groq API**：免費、30 RPM/1000 req/day、Llama 3.3 70B function calling ✅
- **Pydantic AI**：最適合的輕量框架，但先用零框架 function calling
- **Mem0**：per-person 長期記憶，跑在 RTX 8000 上
- **nav2_collision_monitor**：輕量避障（不需 SLAM），apt install 即用
- **ElevenLabs**：正式排除（第二次棄用）

**RPLIDAR 可行性更新**：
- 技術可行（RAM 安全、CPU 帳面可行）
- **新風險**：Go2 四足 odom 漂移（SLAM 核心依賴），Day 1 必做 bag 錄製驗證
- **最壞也值得**：即使 SLAM 失敗，360° 反應式避障比 22 點 LiDAR + D435 好太多
- **dimOS 發現**：有人用 Go2 Pro + D435 VoxelGrid 成功自主巡邏，但框架 v0.0.11 beta 不能直接整合

**待決事項（4/10 繼續）**：
1. RPLIDAR 買不買（傾向買）
2. Skills 架構做多深
3. 記憶方案選型
4. Demo 場地協調
5. 正式寫 spec

---

## 4/8 教授會議決策

### 關鍵決定
- **硬體全上機確認**：Jetson + D435 + 外接喇叭 + XL4015 已安裝至 Go2 機體
- **機身麥克風廢棄**：Go2 風扇噪音導致 ASR ~20%，改用筆電 Studio 收音
- **導航避障可能復活**：老師同意嘗試外接 LiDAR，4/14 前定案是否採購 RPLIDAR A2M12
- **文件先賭有 LiDAR**：4/13 繳交後不可修改，文件中先寫入導航功能
- **本地 ASR/LLM 正式確認不可用**：Whisper 噪音干擾嚴重、Qwen 0.8B 智商極低
- **Plan B 固定台詞**：GPU 斷線備案，需設計兩版 Demo 對話腳本
- **專題文件 46 頁**：歷屆 80-90 頁，需補強到 60+ 頁

### 四人互動設計分工（4/9 會議正式宣布）
| 負責人 | 功能 | 任務 |
|--------|------|------|
| 鄔雨彤 | 手勢辨識 | 7 種手勢→動作映射表 + Studio 頁面 |
| 楊沛蓁 | 姿勢辨識 | 5 種姿勢→動作映射表 + Studio 頁面 |
| 陳若恩 | 語音功能 | LLM prompt 調整 + Plan B 固定台詞 15 組 |
| 黃旭 | 物體辨識 | COCO 白名單篩選 + TTS 回應 + Studio 頁面 |

### 外接 LiDAR 可行性研究結論
- **RAM**：安全（SLAM+Nav2 新增 ~1GB，總計 ~4.7/8 GB）
- **CPU**：風險點（slam_toolbox ~70%，導航時建議關手勢）
- **推薦**：RPLIDAR A2M12（$7,530，16000/s，ROS 生態最豐富）
- **最大風險**：供電（LiDAR 馬達 +2-5W，XL4015 已 8+ 次斷電）
- 詳見 `docs/導航避障/research/2026-04-08-external-lidar-feasibility.md`

### 文件更新
- `docs/mission/README.md` v2.3 完成
- 四人分工文件完成（`pawai-studio/docs/0410assignments/`）
- 外接 LiDAR 可行性研究完成
- 各模組 README 同步更新

---

## 3/26 會議決策

### 關鍵決定
- **物體辨識策略調整**：改為**預設目標**辨識（指定日常物品如水杯、藥罐），非自由搜尋。參考 AI Expo 業界做法，降低複雜度、聚焦可展示性
- **LiDAR 正式放棄**：Go2 LiDAR <2Hz 不可行，下一步改用 D435 depth camera 做基礎反應式避障（尚未測試）
- **整體完成度**：約 50%（含功能開發，不含文件與網站）
- **MeloTTS 正式棄用**：卡在尷尬定位 — 音質不如 Edge TTS，速度又比 Piper 慢
- **Qwen 3/3.5 棄用**：太聰明導致回答不受控，Qwen 2.5 最符合需求
- **Go2 韌體自動更新風險**：Demo 當天禁止連外網，避免被更新

### 文件章節分工（4/13 前繳交 Ch1-5）
| 章節 | 內容 | 負責人 |
|------|------|--------|
| Ch1 | 專題介紹、背景說明 | 共同 |
| Ch2 | User Story、需求分析 | 魏宇同、黃旭 |
| Ch3 | 系統架構、技術細節 | 按功能：人臉+導航+語音（Roy）、物體+姿勢（魏宇同/黃旭）、手勢（陳若恩） |
| Ch4 | 問題與缺點、未來展望 | 簡單撰寫 |
| Ch5 | 分工貢獻表、個人心得 | 各自撰寫 |

### 外部交流
- **4/16（暫定）**：卓斯科技創辦人線上會議 — 陪伴機器人產品觀點
- **NVIDIA 交流**：老師在 GBUA 認識 NVIDIA 亞太區行銷經理，後續邀請工程師來校

### 審計修復（3/26 commit）
- #1 TTS echo gate 洩漏 → 修復（early return 補 `_publish_tts_playing(False)`）
- #6 跨執行緒 DC.send() → 修復（移除不安全 fallback）
- #7 執行緒無限增長 → 修復（ThreadPoolExecutor 取代 per-event Thread）
- #18 模型版本不一致 → 修復（script yunet_legacy → 2023mar）

---

## Sprint Day 12（4/7）

### Studio 即時觀測台

**目標**：Studio 取代 Foxglove 成為 Demo 觀測台 + 語音入口。

#### Gateway ROS2 Bridge
- 訂閱 5 個 ROS2 topic：face state / gesture event / pose event / speech intent / object detected
- `/ws/events` WebSocket 廣播，ConnectionManager 多 client
- Face 節流 10Hz → 2Hz，gesture/pose 補齊前端 dispatch 欄位
- Speech payload 5MB cap + 錯誤回傳不洩漏內部路徑
- 15/15 tests PASS（含 8 個新 transform 測試）

#### Mission Control 首頁
- 控制室風格：grid 背景 + HUD logo + 青綠色調
- 模組狀態列：5 模組即時連線狀態（綠/灰）
- 快捷按鈕升級：lucide icon + accent bar
- Topbar accent line + 點擊回首頁

#### Object Panel
- 新建 `object-panel.tsx` + `/studio/object` 頁面
- COCO 常用 class 中文對照（cup→杯子、dog→狗）
- types / state store / event dispatch 完整串接
- 預設折疊（Demo 不是主力展示）

#### Panel 佈局改善
- PanelCard 可折疊（click header toggle，ChevronDown/Right 指示）
- Sidebar 可拖寬（280-600px，左邊緣拖拉條）
- Panel header 連結到詳細頁（↗ icon）
- 移除事件洗版（感知事件不再灌入 chat）
- ws/wss 自動選擇 + runtime URL fallback

#### PR 合併
- #16 人臉辨識前端（Yamiko）— face panel vanishing track + loading 狀態
- #5 手勢 panel 重寫（syu）— emoji + event history + 三態

#### 語音錄音整合
- 新建 `useAudioRecorder` hook（MediaRecorder + `/ws/speech` WebSocket + cleanup useEffect）
- Chat composer 加 mic 按鈕（錄音→ASR→語音訊息 bubble，不二次 publish）
- Speech panel 加 VoiceRecorderSection（錄音按鈕 + ASR 結果顯示）

#### Mock Server 補全
- FaceTrack import 缺失 → 修復（之前 face 事件 crash 導致背景任務死亡）
- periodic_mock_push 加 try/except
- 新增 `/ws/speech`、`/ws/text` mock 端點（開發機可測語音）
- 新增 `mock_object_event` generator（Object panel 可收到事件）
- payload 10MB cap
- `start.sh` 改 port 8080 + `--ws wsproto`

#### Codex Review（2 輪）
- 第 1 輪：object normalize、object auto-show、speech payload cap、ws/wss fallback
- 第 2 輪：useAudioRecorder cleanup、mic isProcessing disabled、voiceError 顯示、mock payload cap

### Live View 三欄即時影像（下午）

**目標**：`/studio/live` 取代 Foxglove，三欄即時影像展示牆。

#### Gateway Video Streaming
- `video_bridge.py`：JPEG encode（q70）+ FrameThrottle（5fps）+ VideoClients（threading.Lock）
- `studio_gateway.py`：3 路 `WS /ws/video/{face,vision,object}` binary endpoint
- cv2 lazy import — 開發機無 cv2 不影響既有 speech/events 功能
- cv_bridge 不可用時 video endpoint disabled（NO SIGNAL），不做手寫 Image decode
- 13 video bridge tests + Codex review P2 修復

#### Live View 前端
- `useVideoStream` hook：WS binary → createObjectURL，revokeObjectURL 防 leak，FPS 計算，10s NO SIGNAL
- `LiveFeedCard`：監控鏡頭風格（topic 名 + FPS badge + status overlay）
- `EventTicker`：底部事件滾動條（standalone component）
- `/studio/live` 三欄頁面：Face / Vision / Object overlay + status bar + Jetson 溫度
- Topbar 加 LIVE 入口按鈕

#### 連線統一 + 正式站腳本
- `gateway-url.ts`：統一 `NEXT_PUBLIC_GATEWAY_HOST/URL`，所有 WS/HTTP 走同一出口
- `start-live.sh`：正式站啟動腳本（直連 Jetson Gateway，不啟 mock）
- `.env.development` 指向 Jetson Tailscale IP

#### 實機 Demo 驗證
- `start_full_demo_tmux.sh` 加入 object_perception window（五功能 Demo）
- **Demo 錄製通過**：
  - face greeting（grama 2 次 + roy 3 次）✅
  - thumbs_up → TTS「謝謝!」✅
  - stop 手勢 → api_id=1003 ✅
  - TTS USB 喇叭 5/5 播放 ✅
  - Live View 三欄影像即時串流 ✅
- **已知問題**：精準度不足（face 重複 greet、object 偵測率低）、Jetson 斷電（XL4015）

---

## Sprint Day 11（4/6）

### 策略轉向：混合模式

**根因**：Go2 風扇噪音導致機身 ASR 完全不可用（~25%），語音互動 = Demo 核心，不能沒有。
**決策**：Demo 改為「視覺互動為主 + 網頁語音輔助」。語音入口從 Go2 麥克風移到瀏覽器。
**實作**：Studio Gateway（FastAPI + rclpy on Jetson:8080），瀏覽器 push-to-talk → ASR → intent → ROS2 → LLM → TTS。

### Face 調參 — greeting 可靠化
- `sim_threshold_upper`: 0.35 → 0.30，`sim_threshold_lower`: 0.25 → 0.22
- `track_iou_threshold`: 0.15，`track_max_misses`: 20，`stable_hits`: 2
- 2 分鐘 smoke test：`identity_stable: roy` 21 次（調前 1-3 次），零誤認
- Executive `idle → greeting` 確認通了（之前一直卡 idle）

### Object 上機驗證
- cup 觸發 TTS「你要喝水嗎？」✅（threshold 0.5）
- book 偶爾辨識（0.3 threshold 下 2 次，0.79/0.56）
- bottle 未偵測到 → Demo 不展示
- 非白名單（chair/person/cell_phone）靜默 ✅
- **結論**：管線通，限制在 YOLO26n 偵測率。cup 當主力展示物

### Studio Gateway — 文字模式 E2E 通過
- `pawai-studio/gateway/` 從零建立（server + asr_client + web page + 8 tests）
- WebSocket 400 修復：websockets 16→13 + wsproto backend
- 文字輸入 E2E：「今天天氣如何」→ LLM「我還好，你在哪裡?」→ TTS USB 喇叭播放 ✅
- **錄音模式 E2E 通過**：瀏覽器說「你好」→ ASR「你好。」→ LLM「哈囉，我在這裡。」→ TTS 播放 ✅
- 延遲：ASR ~430ms + LLM ~1.5s = **E2E ~2s**（比 Go2 機身 5-14s 大幅改善）

### Executive 改善
- thumbs_up 在 GREETING/CONVERSING 狀態也能路由（之前只有 IDLE 才生效）
- `enable_fallen` 參數化：全域預設 true，demo 腳本帶 `enable_fallen:=false`
- 39 tests PASS

### 整合場景驗收（部分）
- #15 走近/問候/比讚：face greeting ✅，speech 靠網頁文字模式 ✅
- #16 stop 手勢：event 有抓到 ✅
- #17 跌倒：EMERGENCY 觸發 ✅，TTS「偵測到跌倒」✅
- #18 自由互動：中途 Jetson 斷電中斷

### 供電問題量化
- Jetson 穩態功耗：~10W（VDD_IN 4.93V / 2.0A），DC jack 端 ~12W / 0.6A@20V
- 功耗 spike：3.04A（~15W），電壓瞬降 4888mV → 斷電
- 4/6 單日斷電 3+ 次（累計 8+ 次）
- XL4015 19.8V 已是 Jetson 上限（規格 9-20V），不能再升
- 獨立電源測試穩定，確認問題在 Go2 BAT → XL4015 鏈路

### 未完成
- [x] ~~Web Audio 錄音修復~~ → **已通過**（Chrome 麥克風設定問題，非程式碼）
- [ ] 混合模式 demo flow 3 輪驗收（視覺+語音完整流程）
- [ ] Face tracking 抖動深度修復（≤5 tracks/5min）
- [ ] 供電方案定案
- [ ] thumbs_up in GREETING 真機驗證

---

## Sprint Day 10（4/5）

### Phase C — object_perception ROS2 node 完成

**新建 package**：`object_perception/`
- `object_perception_node.py`：D435 RGB → letterbox → YOLO26n ONNX → dedup → event + debug_image
- `config/object_perception.yaml` + `launch/object_perception.launch.py`
- `test/test_object_perception.py`：**21/21 PASS**（P0_CLASSES / letterbox / rescale_bbox / roundtrip / dedup / event schema）

**關鍵設計**：
- 不裝 ultralytics，ONNX Runtime 直接推理
- Event schema 用 `objects` 陣列（多物件）
- Per-class cooldown 5s 去重
- `dining_table` 底線命名（統一契約與 consumer）
- bbox 強轉 Python int（避免 np.int32 JSON 陷阱）

**Contract 更新到 v2.3**：
- 新增 `/event/object_detected`（Reliable, Volatile, depth=10, active）
- `/perception/object/debug_image` 加入 INTERNAL_TOPICS whitelist
- CI `check_topic_contracts.py` 新增 scan dir
- CI 通過：14 OK, 2 WARN, 0 FAIL

**Jetson 驗證**：
- colcon build 成功
- 21/21 tests PASS
- **TRT 陷阱**：`trt_engine_cache_enable` / `trt_fp16_enable` 值必須是 `"True"`/`"False"` 字串，不是 `"1"`/`"0"`。用錯會 fallback 到 CPU。修正後 TensorRT + CUDA provider 成功啟用

**5 分鐘穩定性測試 PASS**：
| 指標 | 結果 |
|------|------|
| Node 存活 | 10+ 分鐘無 crash |
| RAM | 2312 → 2319 MB（+7MB，無 leak） |
| 溫度 | 48.1 → 47.9°C（持平略降） |
| Debug image Hz | 6.3-6.8 Hz（目標 8.0） |
| Event 去重 | 正確（15s 發 2 筆，cooldown 生效） |
| Providers | TensorRT + CUDA + CPU |

### 14:XX — COCO 80 class 擴充（Phase C+）

原本 `P0_CLASSES` 白名單只認 6 類（Foxglove 只看得到 chair）。擴充為完整 COCO 80 class：

- **新增** `object_perception/object_perception/coco_classes.py`：COCO 80 dict + `class_color()` HSV 生成器
- **新增** ROS2 參數 `class_whitelist`：`[]`=全開，`[0,16,39,41,56,60]`=原 P0
- **改 node filter** 從 `P0_CLASSES` → `self.allowed_classes`
- **Debug overlay 顏色** 改用 `class_color(class_id)`，80 class 各自獨特色
- **契約 v2.3 → v2.4**：`class_name` enum → reference `coco_classes.py`

**Tests 21 → 28 PASS**（+COCO 80 subset + class_color 測試 +命名規則驗證）。

### 未做（留給 Day 11）
- Executive 整合（訂閱 `/event/object_detected`）
- `start_full_demo_tmux.sh` 加 object window
- 4 核心整合場景驗收（Day 9 遺留 0/4）
- Jetson 供電排查

---

## Sprint Day 9（4/4）

### 四核心上機驗收 — 14/18 PASS
- **人臉** 3/5：identity_stable <3s ✅、已註冊辨識+TTS ✅、離開再回來 ✅、未註冊/兩人 SKIP（缺第二人）
- **手勢** 5/5：stop ✅、thumbs_up ✅、非白名單 ✅、距離 1-3m ✅、dedup ✅
- **姿勢** 4/4：standing ✅、sitting ✅、fallen→EMERGENCY ✅、恢復→IDLE(30s) ✅
- **整合場景** 0/4：未測（Jetson 供電斷電 3 次）
- 人臉追蹤抖動嚴重（30s 內 40+ tracks），但辨識本身正確

### 文件化
- **新建** `docs/mission/demo-scope.md`（Demo 啟用/停用功能 + 已知限制 + 安全措施）
- **更新** mission/README.md、interaction_contract.md、導航避障/README.md — obstacle 標記 disabled
- **更新** `start_full_demo_tmux.sh` — 移除 d435obs/lidarobs windows，enable_lidar=false，10 window 重編號

### 物體辨識 Go/No-Go — GO ✅

**環境事故與修復**：
- `pip install ultralytics` 拉升 torch 2.11.0+cu130 + numpy 2.2.6，破壞 CUDA 環境
- **環境修復**：移除 ultralytics/polars → numpy 降回 1.26.4 → Jetson 官方 torch wheel（2.5.0a0+nv24.08）→ symlink libcusparseLt.so.0
- **教訓**：Jetson 上不要用 `pip install` 裝有 torch 依賴的套件，會覆蓋 Jetson 專用 wheel

**部署路徑轉向**：不裝 ultralytics，改用 ONNX Runtime 直接推理
- WSL 上用 ultralytics 匯出 `yolo26n.pt` → `yolo26n.onnx`（9.5MB，output shape 1×300×6，NMS-free）
- Jetson 上用已有的 `onnxruntime-gpu 1.23.0`（TensorRT EP + FP16）直接載入推理

**Phase A — 安裝 + import gate**：PASS
- ORT providers: TensorRT + CUDA + CPU
- ONNX 推理 output shape (1,300,6) 正確
- TRT cache 建立成功

**Phase B — 真實 D435 feed 60 秒共存壓測**：PASS
- **15.0 FPS 穩定**（70 秒零掉幀）
- RAM: 3667/7620 MB（+1GB，available 3.8GB）
- GPU: 0%（TensorRT 推理太快或走 DLA）
- 溫度: 56°C、功耗: 8.9W
- 四核心模組 16 nodes 全正常
- chair 偵測 confidence 0.91-0.93 穩定

**Phase C — 最小 ROS2 node**：待做（明天）

### Jetson 供電問題 — 升級為最大硬體風險
- 4/4 單日 Jetson 強制關機 3 次（非網路斷連，是直接斷電）
- 根因：Go2 BAT → XL4015 降壓 19V → Jetson，高負載時電壓不穩
- Demo 前必須解決（獨立電源或更好的降壓模組）

---

## Sprint Day 7 完成（4/3）

### Fallen 誤判修復 — Jetson 真機驗證 PASS
- **根因**：`pose_classifier.py` 的 fallen 條件 `bbox_ratio > 1.0 AND trunk_angle > 60` 在正面站姿時誤觸發（肩膀展開 → bbox 寬 > 高）
- **修復**：新增 `vertical_ratio = (hip_y - shoulder_y) / torso_length` guard，閾值 0.4（相對尺度，不受距離影響）
- **驗證**：Jetson 上 D435 前站立，bbox_r=1.14 時 raw=None（不再判 fallen），vote 持續 standing
- **測試**：14/14 pose classifier tests PASS（+3 新增：近距正面站立、遠距正面站立、躺平確認）
- 91/91 vision tests 全 PASS

### 導航避障 — 停用決策
- **測試過程**：threshold 從 0.8m → 1.2m → 1.5m → 2.0m，三輪 come_here 測試全部撞上
- **根因**：D435 裝在 Go2 頭上偏上方，低於鏡頭高度的障礙物在遠處看不到，只有 ~0.4m 才進入 FOV
- **延遲鏈分析**：debounce 100ms + rate limiter 200ms + WebRTC 300ms + Go2 減速 500-1000ms ≈ 1-1.5s
- **結論**：硬體鏡頭角度問題，軟體無法克服。Demo 不啟用導航避障
- **產出**：`obstacle_debug_overlay.py` — depth debug overlay node（Foxglove 可視化 ROI + min_depth + zone）
- **Jetson 供電問題**：Go2 行走時 Jetson 兩次斷電，疑似 XL4015 電壓波動

### 參數變更記錄
- `obstacle_avoidance_node.py`：threshold 0.8→2.0, warning 1.2→2.5, publish_rate 5→15
- `pose_classifier.py`：fallen 條件加 vertical_ratio < 0.4 guard

---

## Sprint Day 6 完成（4/2）

### Foxglove 3D Dashboard 診斷 + 修復

**問題**：Day 7 完成的 Foxglove 3D dashboard 程式碼從未在真機上驗證。上機後 3D panel 只顯示 TF frame 名稱，沒有 URDF 模型、LiDAR 點雲或 D435 depth。

**根因診斷（3 個）**：
1. **URDF parameter 名稱錯誤**：foxglove_bridge 在 ROS2 用 `節點名.參數名` 格式暴露參數，layout 寫 `/robot_description` 應為 `/go2_robot_state_publisher.robot_description`
2. **TF tree 斷裂**：Go2 tree（odom→base_link）和 D435 tree（camera_link→camera_color_optical_frame）是兩棵獨立的樹，缺少 `base_link → camera_link` static transform
3. **foxglove_bridge QoS 衝突**：`best_effort_qos_topic_whitelist:='[".*"]'` 把 `/tf_static`（RELIABLE+TRANSIENT_LOCAL）也強制成 BEST_EFFORT → static TF 收不到。改為只匹配 sensor topics：`["/(point_cloud2|scan|camera/.*/image_raw)"]`

**修復**：
- `foxglove/go2-3d-dashboard.json`：URDF parameter 名稱修正
- `scripts/start_full_demo_tmux.sh`：新增 `camtf` window（static TF publisher base_link→camera_link）+ foxglove bridge 改用 `ros2 run` 帶 QoS whitelist
- Day 7 程式碼 rsync 到 Jetson + colcon build（obstacle nodes 部署）

**額外修復（layout visibility tuning）**：
- Display frame 必須手動設成 `base_link`（import layout 不會自動套用）
- pointSize 4→10、decayTime 0→3.0（LiDAR ~2-4Hz 太慢，舊值會讓點瞬間消失）
- colorMode 改 flat（排障期用高對比色，不依賴 intensity）

**最終狀態**：
- URDF 模型：✅
- D435 depth：✅
- LiDAR /scan：✅（稀疏但真實，~25/120 有效點，硬體限制）
- LiDAR /point_cloud2：✅（117K 點，稀疏分佈）
- RawMessages (obstacle/status/heartbeat)：✅（executive idle + d435_alive heartbeat 確認）

**Foxglove 3D Dashboard 結論**：可視化工具達到 Day 8 Hardening 的 debug 需求。LiDAR 覆蓋率 ~21% 是硬體事實，不是軟體問題。

### Sensor Guard 驗證 — PASS
- 殺 d435obs → 發 come_here → "D435 obstacle chain stale >1s — stopping forward for safety"
- Go2 幾乎沒動（一瞬間微動即停）
- TTS「好的，我過來了」正常播放

### 10x 防撞測試 — 1/10 PASS（Go2 沒電中斷）
- Round 1：Go2 前進 → D435 偵測障礙物 → OBSTACLE_STOP → 自動停 ✅
- Round 2+：姿勢辨識 fallen 誤判反覆觸發 EMERGENCY，擋住 come_here
- WebRTC DataChannel 在 Jetson 休眠後斷連 → 重啟 driver 修復
- Go2 電量耗盡，測試中斷

### 排查修復
- **WebRTC 斷連**：Jetson 休眠導致 WebRTC DataChannel 靜默斷開，driver 不知道。重啟 driver 後 AUDIO STATE 回傳恢復，cmd_vel 恢復正常
- **USB 喇叭 device drift**：plughw:3,0 → plughw:CD002AUDIO,0（ALSA by-name 避免漂移）
- **LiDAR 可視化定性**：D435 是導航避障主力，LiDAR 是 360° safety net，不追 SLAM

### 已知問題（明天必修）
- **fallen 誤判**：站在 D435 前方被 pose 誤判為 fallen → EMERGENCY 擋住所有指令
- **WebRTC 斷連偵測**：driver 不知道 DataChannel 已斷，需要 heartbeat 機制

### Commits
- `da356ef` fix(foxglove): URDF param name + static TF + QoS whitelist
- `0759aa7` fix(foxglove): layout visibility tuning for sparse LiDAR

**工具產出**：
- `/tmp/fox_doctor.py` — Foxglove CLI 診斷腳本（6 項檢查 + topic rate）
- foxglove_bridge WebSocket 研究：`best_effort_qos_topic_whitelist` 會影響 `/tf_static` 的 TRANSIENT_LOCAL 訂閱

---

## Sprint Day 7 完成（4/1）

### LiDAR 360° Reactive Stop — 13 tests + Jetson PASS
- **LidarObstacleDetector**：純 Python，subscribe `/scan`，360° 任意方向 < 0.5m → danger
- **lidar_obstacle_node**：ROS2 node，frame debounce 3 幀，rate limit 5Hz
- **TDD**：13 unit tests GREEN
- **上機發現 & 修正**：`pcl2ls_min_height` -0.2 → -0.7（Go2 LiDAR z=-0.575m 被全部過濾）
- **LiDAR 覆蓋率分析**：22/120 有效點（18%），前方僅 4 點 — 硬體限制，LiDAR 為補充感知

### D435 + LiDAR 雙層安全 — 雙 publisher Jetson PASS
- 兩個 node 同時發布到 `/event/obstacle_detected`
- Executive source-agnostic，收到任一來源就進 OBSTACLE_STOP
- **修正**：OBSTACLE_STOP 改用 StopMove(1003)，Damp(1001) 會讓 Go2 癱軟摔倒

### come_here 受控前進 + 遇障自動停 — Jetson PASS
- 語音 `come_here` intent → cmd_vel x=0.3 持續前進 + TTS「好的，我過來了」
- 10Hz forward timer，OBSTACLE_STOP 或 IDLE 時自動停
- 2 新 tests（come_here_starts_forward, come_here_interrupted_by_obstacle）

### Safety Guard — 三道防線防撞牆
- **根因**：Go2 撞牆兩次 — D435 obstacle node 沒開 + 無感測器看門狗
- **obstacle_avoidance_node**：新增 `/state/obstacle/d435_alive` heartbeat 2Hz
- **lidar_obstacle_node**：新增 `/state/obstacle/lidar_alive` heartbeat 2Hz
- **Executive sensor guard**（_send_forward 每 tick 檢查）：
  1. state check：OBSTACLE_STOP / IDLE → 停
  2. never-seen guard：從未收到 D435 heartbeat → 拒絕前進
  3. stale guard：heartbeat > 1s → 緊急停止
- **Jetson 驗證**：不開 D435 → come_here 被拒（"refusing forward"）

### Foxglove 3D Dashboard
- **新增** `foxglove/go2-3d-dashboard.json`：
  - 3D panel：URDF 模型 + LiDAR PointCloud2 + LaserScan + D435 depth
  - Image panels：RGB + depth
  - Raw Messages：obstacle event + executive status + heartbeat
- **啟動腳本**：`start_full_demo_tmux.sh` 新增 d435obs + lidarobs windows + enable_lidar

### 數據
- **Commits**：6（b0812f5, 623d821, ac292ab, 8fda23f + docs）
- **Tests**：88 vision + 31 executive = 119 total, all GREEN
- **新增程式碼**：~500 行（4 新檔 + 4 修改檔）

---

## Sprint Day 6 完成（4/1）

### Gate A — 安靜環境 ASR E2E：PASS (4/5)
- **Cloud ASR 恢復**：sensevoice_server.py async fix 生效，不再全 timeout
- **ASR timeout**：3s → 5s（tunnel latency 餘裕）
- **sensevoice_server.py**：加 `disable_update=True`（離線模型載入，避免重啟時 modelscope API 失敗）
- **E2E 流程通**：ASR → LLM → TTS → 喇叭播放，完整鏈路驗證
- **已知缺口**：單字「停」被 VAD 吞掉（min_speech_ms 斷句不穩定），Demo 改用「停下來」
- **SSH tunnel 永久化**：Jetson systemd user service，開機自動起、斷線重連
- **USB speaker 穩定化**：改用 `plughw:CD002AUDIO,0`（by ALSA name，不受 device drift 影響）

### Gate B — Executive 邊界測試：PASS (6/6)
- **Face welcome → TTS**：executive 收到 identity_stable → TTS「roy 你好」 ✅
- **Speech chat → LLM**：intent → LLM 回覆 → TTS 播放 ✅
- **Stop gesture → StopMove**：executive api_id=1003 priority=1 ✅
- **Face + Speech 同時**：llm_bridge greet cooldown dedup 正確 ✅
- **Gesture stop + Speech 同時**：stop 優先序正確 ✅
- **Crash recovery**：殺 executive → 重啟 → 7 秒恢復 ✅

### Gate C — Go2 上機語音驗收：拆分判定

#### Gate C-command（語音命令控制）：FAIL
- **stop 語音指令不可靠** — 被 VAD 截斷或 ASR 辨識錯誤，安全關鍵指令不能依賴語音
- **transcript 準確率 ~25%** — Go2 風扇噪音壓過語音（mic_gain 8.0/12.0 均無效）
- **Demo 對策**：stop 改靠手勢 stop（Gate B 已驗證 100%），不用語音

#### Gate C-conversation（聊天陪伴互動）：PASS with caveat
- **使用者體驗**：講話後機器人幾乎都有合理回應
- **come_here / take_photo**：完全正確辨識 + 正確回覆
- **greet**：ASR 文字糊但 LLM chat fallback 回覆自然（「你好呀」「哈囉，我在這裡」）
- **status**：未被正確辨識為 status intent，但 LLM 回覆仍合理（「好的，有需要再叫我」）
- **結論**：聊天可用，命令控制未達標。Demo 詞庫應偏向容錯高的句子

#### 噪音調查結論
- **主噪音源**：Go2 內建散熱風扇（非 LiDAR），無法軟體關閉
- **adaptive VAD**（noise floor EMA + 動態 threshold）已實作並部署，改善觸發穩定性但不改善 ASR 準確率
- **根因**：硬體 SNR — 全向麥克風收到的語音被風扇噪音蓋住
- **Day 7+ 方向**：軟體降噪（noisereduce）或物理隔離麥克風

### 導航避障 — D435 反應式避障實作 + 桌測通過
- **ObstacleDetector**：純 Python/numpy，ROI depth 分析，三段式判定（clear/warning/danger）
- **obstacle_avoidance_node**：ROS2 node，D435 depth 訂閱，幀級 debounce 3 幀，rate-limited 5Hz
- **Launch file**：全參數暴露（ROI 四邊、threshold、debounce、depth_topic）
- **TDD**：7 unit tests GREEN，全 CI 225 tests PASS
- **Jetson 桌測**：椅子 41cm → OBSTACLE ratio 65% → executive Damp → 移除後 debounce 2s → idle 恢復 ✅
- **待做**：Go2 上機 10x 防撞測試、`start_full_demo_tmux.sh` 加 obstacle window

### LiDAR 重測 — 舊結論推翻 + 最終架構決策

**舊結論（2026-02/03）**：LiDAR 0.03-2Hz burst+gap → 判死
**新測量（2026-04-01）**：

| 條件 | /point_cloud2 Hz | Gap > 1s |
|------|:----------------:|:--------:|
| 靜止 + 純 driver | 7.3 | 0 |
| 靜止 + 16 nodes | 7.3 | 0 |
| 行走 0.3 m/s | 4-6 | 0（1 次 1.09s 在轉換期） |

**LiDAR 復活為 reactive safety 主線**，但 SLAM/Nav2 永久關閉：
- CycloneDDS：Go2 Pro 韌體不支援，永久關閉
- LiDAR 頻率天花板：~7.35Hz（韌體硬限），我們的 fork 已有 6 項獨有優化，超過上游
- Full SLAM：5Hz 品質差，jitter 高，業界最低門檻 7Hz
- Nav2：controller_frequency=3.0 只是「能跑就好」，動態避障不可能

**最終避障架構**：
- **D435 depth**：前方 87° 精確防撞（30fps，桌測通過）
- **LiDAR**：360° 安全防護（5-7Hz，行走測試通過）
- **Go2 移動**：api_id 預設動作 + cmd_vel，MAX_LINEAR_X 調高到 0.5 m/s（行走測試 0.3 m/s 正常）

### Go2 行走測試
- **0.20 m/s**：走得不甘不願（「被拖著的小狗」），太慢
- **0.30 m/s**：正常行走，3 輪測試通過
- **MAX_LINEAR_X**：0.22 → 0.5 m/s（Go2 官方最高 5.0 m/s）
- **已知問題**：行走中 Jetson 曾斷電一次（供電波動），重開後正常

### 基礎設施改善
- **interaction_contract.md v2.2**：新增 `/executive/status`(v0)、`/event/obstacle_detected`(實作完成)、deprecate router+bridge
- **Jetson GPU tunnel systemd**：`gpu-tunnel.service`（SSH key + auto-reconnect）
- **USB speaker by name**：`plughw:CD002AUDIO,0` 取代 `plughw:N,0`
- **Adaptive VAD**：noise floor EMA + 動態 threshold（stt_intent_node，`energy_vad.adaptive` 參數）

---

## Sprint Day 4+5 完成（3/31）

### Day 4：硬體穩定性驗證 — GATE C 通過
- **3x 冷開機** bring-up 全部成功，USB index 穩定（mic=0, spk=plughw:1,0）
- **Go2 行走 2 分鐘**：硬體不鬆脫（熱熔膠固定 USB 接頭後）
- **30 分鐘連續運行**：peak 56.2°C < 75°C，16 node 全程無掉，喇叭全程在線
- **XL4015 電壓調整**：18.8V → 19.2V（原值偏低導致 Go2 行走時 Jetson 斷電）
- **USB 喇叭反覆斷連**：根因是振動 + 接觸不良，熱熔膠固定後解決
- **啟動腳本同步**：Jetson 舊版只有 whisper_local，已推新版含 SenseVoice 三級 fallback

### Day 5：Executive v0 State Machine
- **Package scaffold**：interaction_executive ROS2 package（setup.py/cfg/package.xml）
- **TDD**：27 tests GREEN（19 state machine + 6 api_id alignment + 2 obstacle edge cases）
- **State machine**：純 Python，6 狀態（IDLE/GREETING/CONVERSING/EXECUTING/EMERGENCY/OBSTACLE_STOP）
- **ROS2 node**：訂閱 5 event topics → /tts + /webrtc_req + /executive/status(2Hz)
- **api_id 修正**：計畫裡 Damp/Sit/Stand 寫錯，已對齊 robot_commands.py 權威來源
- **Jetson 部署驗證**：`/executive/status` → `{"state": "idle"}` 確認

### Bug Fixes（審查報告 3 個 critical）
- **llm_bridge_node lock race**：acquire(False) fail 時 finally release 未持有的 lock → crash
- **sensevoice_server model null check**：model 未載入時直接 crash → 503
- **sensevoice_server blocking generate()**：async handler 裡跑 blocking call → run_in_executor

---

## Sprint Day 3 完成（3/30）

### 四核心桌測 + Go2 動作補驗
- **Phase 1 桌測**：10/10 PASS（face + speech + gesture + pose）
- **Phase 2 動作**：stop→stop_move 3x、thumbs_up→content 3x、PASS
- **驗證工具**：Foxglove layout（4-panel）+ verification_observer.py（5 topic → JSONL 882 筆）
- **模型策略收斂**：
  - ASR：SenseVoice cloud → SenseVoice local → Whisper local（三級 fallback）
  - LLM：Cloud Qwen2.5-7B → RuleBrain（**砍掉 Ollama 1.5B**，展示期要可預測不要半智能）
  - TTS：edge-tts + USB 喇叭 plughw:3,0
- **排查修復**：USB 喇叭未插、麥克風 device drift 24→0、LLM endpoint 直連→localhost tunnel、observer QoS import

### 硬體上機（3/30 晚完成）
- **供電**：Go2 BAT (XT30, 28.8V) → XL4015 DC-DC 降壓 → 19V → Jetson DC jack
- **固定**：Jetson + D435 + USB 麥克風 + USB 喇叭全部上 Go2
- **Bring-up**：full demo 10 window 啟動成功，ASR/LLM/TTS 鏈路通
- **已知問題**：
  - 喇叭 USB 間歇斷開（已束帶固定，待觀察）
  - 麥克風 device drift（啟動腳本 device=24 但實際=0，每次需確認）
  - LLM SSH tunnel 需手動開

### 結論
- Day 3 超進度：桌測 + 硬體上機一天完成（原定兩天）
- 明天 Day 4 只剩穩定性驗證（3x 重開機 + 行走 + 熱測試）

---

## Sprint Day 2 完成（3/29）

### ASR 替換：SenseVoice 三級 Fallback
- **SenseVoice cloud**（FunASR on RTX 8000）：92% correct+partial，0 幻覺，~600ms
- **SenseVoice local**（sherpa-onnx int8 on Jetson CPU）：92% correct+partial，0 幻覺，~400ms，352MB RAM
- **Whisper local**（最後防線）：52% correct+partial，8% 幻覺
- **Qwen3-ASR-1.7B** 也測了（96%），但延遲 2x、模型 8.5x，SenseVoice 更適合
- Fallback 鏈驗證通過：cloud 斷 → local SenseVoice → Whisper 全自動
- `sensevoice_server.py` 部署在 RTX 8000 GPU 1（1.1GB VRAM）
- 審計 #5 #6 #7 #9 安全修復

### 驗收標準
- [x] 固定音檔正確+部分 >= 80%（實測 92%）
- [x] 高風險 intent 誤判 = 0
- [x] Cloud → Local fallback 自動切換
- [ ] `ENABLE_ACTIONS` 尚未改回 true（等等量 A/B 補測再開）

---

## Sprint Day 1 完成（3/28）

### Baseline Contract
- **3/3 cold start PASS** + **1/1 crash recovery PASS**（1m26s < 3min）
- Topic graph 快照：51 topics, 16 nodes
- QoS runtime 驗證：全部符合靜態推導，`/state/tts_playing` TRANSIENT_LOCAL 確認
- Device mapping：mic card 24→0（device drift 確認），speaker plughw:3,0
- 新增 `scripts/clean_full_demo.sh`（全環境清理）
- 新增 `scripts/device_detect.sh`（USB 音訊裝置自動偵測，source 介面）
- 新增 `docs/operations/baseline-contract.md`（啟動順序 + QoS + SOP + 驗收記錄）

### 語音 Noisy Profile v1
- **問題：** Go2 伺服噪音下 Whisper 產生幻覺，垃圾 intent 觸發 Go2 危險動作
- **安全門：** `ENABLE_ACTIONS=false` 封鎖 llm_bridge + event_action_bridge 的 `/webrtc_req`
- **ASR 調校：** 3 組 A/B 測試（gain 8/10/12），固定音檔 controlled test
- **結果：** gain=8.0 + VAD start=0.02 是甜蜜點（64% 正確+部分），gain 更高反而噪音放大
- **Whisper 改善：** vad_filter=True + no_speech_threshold=0.6 + 擴充幻覺黑名單（6→22）
- **結論：** Whisper Small 在中文短句+噪音場景的上限已到，**明天優先研究替代 ASR（SenseVoice）**

---

## 最近完成（3/25）

### Jetson 四模組整合測試（3/25 晚）
- **四模組同跑**：face + speech + gesture + pose，不 OOM、不互卡 ✅
- **人臉→LLM 問候**：偵測 roy → WELCOME → TTS「roy 你好」✅
- **手勢→Go2 動作**：stop/thumbs_up 正確觸發 ✅
- **語音 TTS**：edge-tts + USB 喇叭播放正常 ✅
- **語音 ASR**：Whisper CUDA float16 warmup 5.9s OK，但 USB mic 收音弱，需靠近或加 gain ⚠️
- **已修問題**：Whisper compute_type int8→float16、LD_LIBRARY_PATH 帶入 ROS_SETUP、silent exception 加 log
- **已知問題**：USB device index 重開機後會飄（mic 24→0, speaker hw:3,0→hw:1,0）、debug_image 需 resize 降頻寬

### 深度審計
- 7 軸並行掃描 + 4 類 web research = 99 findings
- Decision Packet（Keep/Fix/Explore 路線圖）
- Pre-flight Checklist（3/26 整合日逐項驗證）
- Demo Gap Analysis（A ~70% / B ~75% / C ~25%）

### Code 修復（4 commits）
- **event_action_bridge rewiring**：改訂閱 interaction_router 輸出，消除雙重消費
- **TTS guard**：stop/fall_alert 永遠通過，其他 gesture TTS 播放中 skip
- **vision_perception setup.cfg**：修正 executable 安裝路徑
- **Full demo 啟動腳本全面對齊**：USB mic/speaker、edge-tts、router required、Ollama fallback、sleep 15s（Whisper warmup）
- **tts_node**：11 個 silent exception 補 log + destroy_node()
- **YuNet default**：legacy → 2023mar

### Repo 瘦身
- 206 files 刪除，~24K lines，~144MB
- go2_omniverse、ros-mcp-server、camera、coco_detector、docker、src 等
- 過時腳本清理（18 個 speech/nav2/一次性腳本）
- .gitignore 完善

### 文件更新
- interaction_contract.md v2.1（3 新 topic、gesture enum、發布者名稱、LLM 型號）
- 4 份模組 README 全部對齊實作（語音/人臉/手勢/姿勢）
- mission/README.md 選型對齊
- CLAUDE.md 日期 + hook install + 腳本引用

### CI 強化
- test_event_action_bridge.py 加入 fast-gate（15 tests）
- Topic contract check 改 blocking（FAIL → exit 1）
- Git pre-commit hook（py_compile + contract + smart-scope tests）
- 三層品質閘門：Claude hooks → git pre-commit → GitHub Actions

### 依賴管理
- 3 個 setup.py install_requires 補齊
- requirements-jetson.txt 新建

### 研究文件
- `docs/research/2026-03-25-object-detection-feasibility.md`（YOLO26n，32KB）
- `docs/research/2026-03-25-reactive-obstacle-avoidance.md`（D435 避障，34KB）
- `docs/research/2026-03-25-go2-sdk-capability-and-architecture.md`（SDK 能力 + Clean Architecture 藍圖，41KB）

## Sprint B-prime（3/28-4/7，一人衝刺）

> 完整每日任務見 [`docs/mission/sprint-b-prime.md`](../docs/mission/sprint-b-prime.md)

| Day | 日期 | 主題 | 驗收標準 |
|:---:|------|------|---------|
| 1 | 3/28 | Baseline Contract | 3x cold start + 1x crash recovery ✅ |
| 2 | 3/29 | ASR 替換：可順暢溝通 | 正確+部分 >= 80%，高風險誤判 = 0 ✅ |
| **3** | **3/30** | **四核心桌測 + 動作補驗** | **10/10 PASS + Go2 動作 PASS ✅** |
| **4** | **3/31** | **硬體穩定性 GATE C** | **3x 重開機 + 行走 + 30min 56°C + USB 穩定 ✅** |
| **5** | **3/31** | **Executive v0 State Machine** | **27 tests + ROS2 node + Jetson 部署 ✅** |
| **6** | **4/1** | **ASR 修復 + Executive 整合 + 上機驗收** | **Gate A 4/5 ✅ Gate B 6/6 ✅ Gate C FAIL（噪音）** |
| **7** | **4/1** | **導航避障：LiDAR+D435+Safety+Foxglove** | **20 tests + 雙層避障 + safety guard + 3D dashboard ✅** |
| 8 | 4/4 | 導航避障：Hardening | 10x 防撞 + 三段速度 + Foxglove 微調 |
| 9 | 4/5 | 物體辨識 Hard Gate | Go/No-Go → Phase 0（4-6h timebox）|
| 10 | 4/6 | Freeze + Hardening | Demo A 30 輪 + Demo B 5 輪 + crash drill |
| 11 | 4/7 | Handoff Day | docs 重組 + Starlight scaffold + 分工文件 |

### 砍刀順序（時程爆炸時）
1. 物體辨識 → 2. 硬體擴張 → 3. Executive 完整版 → 4. 導航避障

## 待辦（Sprint 後 / 4/9 團隊接手）

- Demo A 30 輪持續監控
- Studio 後端開發（FastAPI + WebSocket bridge）
- Starlight 文件站 + 展示站
- 文件繳交 Ch1-5（4/13 硬底線）— **114-thesis.md + .docx 初稿已產出（4/7 晚）**
- Flake8 改 blocking
- Jetson 硬編碼路徑清理

## 里程碑

| 日期 | 事項 |
|------|------|
| **3/26** | **四模組整合日 + 教授會議** ✅ |
| **3/27** | **Sprint B-prime 規劃完成** ✅ |
| **3/28** | **Sprint Day 1 — Baseline Contract PASS** ✅ |
| 3/29-30 | 硬體上機（可跑→可用） |
| 3/31-4/1 | Executive v0 開發 + 整合 |
| 4/2-3 | 導航避障開發 + 30 次防撞 |
| 4/4 | 物體辨識 Hard Gate |
| 4/5-6 | Freeze + Hardening |
| **4/7** | **Handoff Day** |
| **4/9** | **教授會議 + 團隊分工啟動** |
| **4/13** | **文件繳交（硬底線）** |
| **4/16** | **卓斯科技線上會議（暫定）** |
| **5/16** | **省夜 Demo（暖身展示）** |
| **5/18** | **正式展示／驗收** |
| **6 月** | **口頭報告** |
