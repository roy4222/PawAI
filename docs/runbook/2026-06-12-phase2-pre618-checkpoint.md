# 系統 Phase 2 pre-6/18 Checkpoint Report（2026-06-12，AFK 自主執行）

> **性質**：系統 Phase 2（Core Brain / Ops Refactor）**pre-6/18 additive-only 範圍**的執行收據。
> **授權**：Roy 2026-06-12 凌晨 AFK 指令（「明天我不在，請執行 Phase 2 additive-only…開始執行吧」），
> 其中含 T2B-0 兩決策拍板（PII 保守預設 + export 即使 GET 也要 auth）。
> **上游 plan**：[`docs/archive/superpowers-legacy/plans/2026-06-11-phase2-core-brain-ops-refactor.md`](../archive/superpowers-legacy/plans/2026-06-11-phase2-core-brain-ops-refactor.md)
> **執行模式**：Fable 直接實作（Roy AFK 指令直接下給 Fable）＋ 每 lane 獨立 reviewer subagent
> Linus 審查 ＋ 小 PR ＋ CI 綠 ＋ admin rebase merge。**系統 Phase 3/4/5 未啟動**。

---

## 1. 交付總表（3 PRs，全部 merged → main）

| Lane | PR | Commits（rebase 後） | 內容 |
|---|---|---|---|
| Step 0 | — | `7f7ddea` push | 五份 v2 plan 已在 `39683e6` 入庫，本日推上 origin/main |
| 2A ISM Phase 1 shadow | [#160](https://github.com/roy4222/PawAI/pull/160) | `f9ea1af`（T2A-1）+ `6d42974`（T2A-2/3） | contracts `TraceKind.STATE_TRANSITION`（additive）；`brain_node` shadow 接線（`ism_shadow_enabled` declare 預設 **False**、runtime `ros2 param set` 可切）；11 條 parity/黑洞重演測試 |
| 2B Evidence Center first slice | [#161](https://github.com/roy4222/PawAI/pull/161) | `b209280` | gateway `trace_store.py`（JSONL 落盤 `runtime/traces/{session_id}.jsonl`、~20MB rotation、留 20 sessions、queue 寫入）；`GET /api/trace/export`（A-11 auth）；前端 suppressed-reason viewer；PII redaction 單一真相 `redact_trace_event()` |
| 2C CLI 第二刀 | [#162](https://github.com/roy4222/PawAI/pull/162) | `4143b33` | `pawai smoke brain`、`pawai evidence pull`、structured errors（`errors.py`）、T2C-0 測試隔離 conftest |

**Merge 後 main 全套本機驗證（2026-06-12）**：
contracts **11 passed** ／ interaction_executive **320 passed**（含新 11 條 shadow parity）／
gateway **93 passed + 1 skipped** ／ pawai_cli **173 passed in 2.16s** ／ 前端 vitest **16 passed** + `tsc --noEmit` 乾淨。
CI：三個 PR 的 Fast Gate + test_environment（+ #161 的 Frontend lint/build、Backend import check）全綠。

## 2. T2B-0 決策落實方式（Roy 拍板 → 工程具體化）

| Roy 拍板 | 落地 |
|---|---|
| PII 保守預設：safe summary 可顯示；name/transcript/image path/full text 預設 private | 磁碟 JSONL 存**完整**事件（僅 Jetson 本機證據）；**每一條離機路徑**（WS 廣播 + 預設 export）過 `trace_store.redact_trace_event()`：PII detail keys → `[private]`、reason 內人名段遮蔽（`cooldown:greet:Roy`→`cooldown:greet:[private]`），結構欄位（gate/kind/verdict/ism_*/demo_phase/cooldown_remaining_s）可見 |
| export 即使 GET 也要 auth（A-11 = GET＋例外 token-gate） | `auth.export_access()`：auth-on 時 GET export **不吃** S0-2 safe-method 豁免（無 token → 401）；`redact=0` 完整匯出在 token 系統關閉時一律 403（無法驗證身分 → PII 永不離機）；default-off 姿態 redacted export 開放（與 S0-2 byte-identical 原則一致） |

## 3. 對 plan 文字的三個工程修正（皆已寫進 PR 描述）

1. **2A suppressed 側用純 `InteractionPolicy.evaluate()` 而非 mutating `propose()`**：legacy 沒做的事不能推進 shadow 機——反事實 ACCEPT 會把機器帶進沒有真實訊號校正的狀態（如 SPEAKING 無 deadline），汙染 6/18 soak 數據。ACCEPT 側維持 `propose()`（被 skill_result/TTS 真實訊號持續校正）。
2. **2C smoke brain 走 `stream_remote`（SSH 上 Jetson 執行）而非本地 `shell.stream`**：`smoke_test_e2e.sh` 直接 `ros2 topic pub`，在開發機本地跑會靜默 no-op（不同 ROS 世界）。
3. **2C conftest 加 `real_repo` marker + 該模式中和 `.env/.env.local` 載入**：六條讀真 repo 檔案的既有測試需要真 root，但開發機真 `.env.local` 的 `JETSON_TAILSCALE_IP` 會悄悄蓋掉測試 monkeypatch 模擬值（#150 同類）。中和後 local==CI 決定性。

## 4. 附帶修出的既有問題（非本 plan 範圍、但被 T2C-0 結構性解掉）

- CLI 測試套件在 Jetson 關機的機器上要 **105s+**（doctor 類測試各做 ~10s 真 ssh probe：`shell.run(ssh_args("echo OK"))` + 27s topology 探測），#150 的 300s 假掛同類。conftest 攔截後 **173 passed in ~0.7-2.2s**，且未 mock 的 remote 呼叫立即以 `blocked-by-conftest` 失敗（fail loud, not hang）。
- `/runtime/traces/` 入 `.gitignore`（先前未涵蓋；JSONL 含 PII + 體積，永不入 repo）。
- `_on_set_params` 三個純 bool param 合併單分支（log 逐字不變）——避免新 elif 推爆 C901 基線。

## 5. 真機項（6/12 晚 Roy 在場，**全數完成** — 結果見 §8）

| 項 | 動作 | 備註 |
|---|---|---|
| **T2A-4 shadow 真機驗證 + 6/18 soak** | demo stack 起來後 `ros2 param set /brain_node ism_shadow_enabled true` → 跑一輪 demo 動線 → `ros2 topic echo /brain/trace \| grep state_transition` | 不碰凍結腳本；異常時 param set false 即退；驗過後 6/18 發表全程開著收 ISM Phase 2 數據 |
| 2B 真機驗證 | demo 跑過後 Jetson 端確認 `runtime/traces/*.jsonl` 增長；`curl http://<jetson>:8080/api/trace/export?since=0 \| head` 拉得回 redacted JSONL | gateway 重啟後生效（lifespan 建 store；`PAWAI_TRACE_STORE_ENABLED=0` 可關） |
| 2C 真機收尾 | `pawai smoke brain`（需 demo lane 在跑）；`pawai evidence pull` 拉回第一批真 JSONL | 兩命令的 mock 測試已綠；真機跑一次即封 |
| 前端目視 | Studio DevPanel / `/studio/dev` 看「為什麼沒反應 · Suppressed」區塊有資料、shadow badge 正確 | 需 gateway + brain 都是新版 |
| **Jetson 部署** | 三 lane 都要上 Jetson：`pawai jetson deploy --module brain` + `--module studio`（或手動 rsync + colcon build `pawai_contracts interaction_executive`；gateway/CLI 純 Python 同步即生效） | rsync 不 rebuild `install/` 的老坑——brain 改動必須 colcon build |

## 6. 紀律遵循聲明

- ✅ `ism_enabled` 不存在；19 個 `_suppressed` 早退零刪除；legacy gate 原樣
- ✅ 凍結檔案零接觸：`executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/`
- ✅ 不碰 Go2 / 無任何 HITL / 未啟動系統 Phase 3（vision benchmark / supervision / PINTO）/ Phase 4（robot control / nav hardening）/ Phase 5
- ✅ 全程 additive-only：shadow 預設關 = emit byte-identical（320 條既有測試零修改全綠佐證）；trace_store env kill-switch = 回純 bridge；CLI 新命令獨立可 revert
- ✅ 每 lane：小 PR + 紅綠 TDD + 獨立 reviewer LGTM + CI 綠 + admin rebase merge（既定標準）

## 7. 回滾點

- 全域：tag `post-demo-refactor-baseline-2026-06-10`（=`b1f0bc4`）；demo 行為：tag `demo-2026-06-snapshot`
- 本批：`ros2 param set /brain_node ism_shadow_enabled false`（2A 即時退）；`PAWAI_TRACE_STORE_ENABLED=0`（2B 落盤退回純 bridge）；三 PR 各自獨立 revert 無交叉依賴

## 8. 真機驗收結果（2026-06-12 晚，Roy 在場授權，Roy 10 步清單全過）

| # | 步驟 | 結果 |
|---|---|---|
| 1-2 | deploy + build（contracts+IE+brain+go2_interfaces） | ✅ `.env` 存活、provenance=`2e47464` |
| 3 | `pawai demo start` | ✅ healthcheck 8/8、13 windows、19 nodes |
| 4 | shadow on（runtime param set） | ✅ 不碰凍結腳本 |
| 5 | `/brain/trace` state_transition | ✅ `idle→executing:candidate:chat`→`skill_started`→`operator_reset` 完整軌跡；CANDIDATE 並排比對已收到 legacy/ISM 分歧樣本（legacy `attention_engaged` 擋、ISM accept） |
| 6 | `runtime/traces/*.jsonl` 增長 | ✅ 46→192 行持續累積 |
| 7 | `/api/trace/export` | ✅ redacted 200（27 行 `[private]`）；`redact=0` 無 auth → **403**；`since` 過濾正確 |
| 8 | `pawai smoke brain` | ✅ **5/5**（經 3 個真機修復後，見下表） |
| 9 | `pawai evidence pull` | ✅ 拉回 56 events / 27 suppressed / 34 shadow / 12 state_transition |
| 10 | Suppressed viewer 資料路徑 | ✅ WS 流驗證：trace 事件 + shadow 標記 + `[private]` redaction（畫面 Roy 目視 `:3001/studio`） |

**真機過程抓到並修掉的 4 個既有 bug（全部小 PR + CI + merge）**：

| PR | 問題 | 修法 |
|---|---|---|
| #163 | `pawai smoke brain` SSH 非互動 shell 無 ROS env → 腳本 precheck 永遠 0 nodes | stream_remote 前 source setup.zsh（仿 deploy 先例）|
| #164 | **凍結檔 `start_full_demo_tmux.sh:184`**（Roy 現場明示授權）：`.env` 的 ASR 陣列值經 bash source 剝引號 → zsh pane glob 炸 → **demo lane 的 stt_intent_node 長期靜默死亡**；+ smoke 腳本寫死 llm-e2e stack | 引號收斂到 send-keys 層；smoke precheck 接受 conversation_graph_node、播放證據接受 local playback |
| #165 | `ros2 topic pub --once` 對 `/tts` 的 discovery race（3 訂閱者，`-w 1` 不夠、`-w 3` 因 QoS 不相容訂閱永久卡）→ smoke 3/5 | `--times 2 -r 1`（第二發必落在 discovery 後），真機 5/5 |
| #166 | **deploy data-loss**：repo 無 `runtime/` → builtin rsync `--delete`（Plan B #151 起預設）每次 deploy 整棵刪 Jetson `runtime/`（吃掉第一個 trace session + **nav named_poses/routes**） | excludes 補 `runtime/` + `artifacts/`；重 deploy 後 trace 檔存活驗證 ✅ |

**⚠ Roy 待辦**：① Jetson 端 nav `named_poses`/`routes` 已被 6/11 起的 deploy 清掉，下次 nav 場測前要重錄（`/log_pose`）或從備份還原；② shadow 現在是 ON（soak 進行中）——**demo 每次重啟 param 歸 False**，重啟後要重下 `ros2 param set /brain_node ism_shadow_enabled true`（6/18 發表日記得）。
