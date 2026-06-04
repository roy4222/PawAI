<!--
來源：route-paving workflow（audit×6 + Tournament 3 設計×3 評審 + synthesis）@ HEAD 885728f，2026-06-04。
贏家 = 設計 #0（按物理場景分批，最省 Roy 時間），grafted #1 大樣本 / #2 GATE-0 BLOCKING。
所有指令已對 repo source 實際驗證。

⚠️ 順帶抓到 3 個既有「文件 bug」（本 runbook 已避開，修它們不在本 runbook 範圍）：
1. baseline-runbook.md / capability-baseline-spec.md / baseline-issues-draft.md / 2026-05-31 plan 引用
   topic `/event/nav/mission` 作 short_move 觀測 —— 此 topic 全 source 不存在，echo 它會永久 hang。
   正確觀測 = `send_relative_goal.py` 的 action Result（success/message/actual_distance）。
2. spec §4 gesture idle gate 寫 count-based（≤1/10min），build_scoreboard 實作是 rate-based
   `unknown_false_accept_rate` —— 語意不一致；本 runbook 已標 rate-proxy。
3. readiness 第一個 blocker 實測是 `sha_mismatch`（非先前以為的 `schema_validator_unavailable`）；
   jsonschema 4.26.0 在 venv 可 import，schema 路徑本輪非 blocker（見 STEP 6 末）。
-->

# PawAI HITL Capability Baseline — 一次坐定 Runbook（Roy 回到 Jetson+Go2 後自己執行）

**Repo HEAD:** main @ `885728f` · **pawai 路徑：** `/home/roy422/.venv/bin/pawai`（**不在 PATH**）
**治理文件（嚴格遵守）：** `docs/mission/2026-06-18-demo-north-star.md`（North Star v2，fail-closed，誠實分級）
**涵蓋：** #80 voice、#81 face、#82 gesture+object、#83 pose、#84 nav → build_scoreboard → readiness → freeze
**估 Roy 體力時間：約 70 分鐘連續**（30 輪語音 ~12min 為最大宗；五次場景重配；idle 60s 窗 ×5；其餘 8s 窗）

---

## ⚠️ 先讀 — 誠實與安全護欄（不可違反）

- **誠實鐵律：** 不追求全 pass，追求每個 issue 有真實結論（pass / degraded / fail / insufficient_data + reason）。不誇大、不擴張 scope。
- **SSH 狀態與 brief 衝突：** brief 說 :22 timeout，但 audit 時 `ssh jetson-nano echo SSH_OK` 回 `SSH_OK`（port 22 是 UP）。**GATE-0 先實測**：通就照下面 `ssh` wrapper 跑；**若 SSH 已掛**，把 `ssh jetson-nano '...'` 外殼拿掉、直接在 Jetson `demo` tmux pane 貼內層 `zsh -lic "..."` 本體。**注意 readiness 與 scp 都吃 SSH（無離線 fallback）**，SSH 掛了 STEP 6 走不到 verdict=ready。
- **face 已 commit 的真相 = FAIL**（n=3、registered_recall=0.5、unknown_false_accept_rate=1.0）。目標是**可信的重測**，不是保證 pass。即使乾淨 6/6 + 0 誤觸，每個 scenario_kind 若 n<3 仍被 grader 壓到 **degraded floor** → 所以 positive ≥3、idle ≥3。handoff 那份 n=9「expected PASS」**從未被 build 進 commit 的 snapshot**，不可據此宣稱 face PASS。
- **voice e2e 是 VAD 時代，不是 metric-v2。** mic_stop **未接線**（`stt_intent_node.py` 只訂 vad/text/tts_playing；`energy_vad.enabled` 預設 True）。報告**不可**宣稱「mic_stop 起算」或「快 2 秒」。e2e_median 未達 ≤3.5s 是誠實的 as-is-with-VAD 結果，不是退步。mic_stop 接線（Codex，4 檔，動到語音主線）**延到 demo stop 後的另一場 session**，本輪不做。
- **nav = 純 DRY-RUN，Go2 不可走。** **不要設 `/initialpose`**。**不要跑 `send_relative_goal.py --distance 0.5/1.0`**（那是真走的 KPI 行）。`/event/nav/mission` **不存在於 source** — 不要 `echo` 它（會永久 hang）。觀測值是 `send_relative_goal.py` 印出的 action Result（`success`/`message`/`actual_distance`）。
- **pose = insufficient_data，不採集**（無 observer：`perception_baseline_observer` 只訂 gesture+object；`capture_baseline_round.py` 只有 `[face, percep]` 兩 mode，無 pose mode）。從 WSL 關閉。
- **build_scoreboard + readiness 必須在 WSL 跑**（Jetson git 壞 → version_mismatch=True → 全部被壓 insufficient_data）。`--preflight` **強制**（省略 → run_trusted=False → 全部 insufficient_data）。
- `run_speech_test.sh --nodes-running` 復用 demo 的 stt/tts/intent nodes — #80 voice 跑在**同一個正在跑的 demo** 上（perception demo 就是 speech demo，皆由 `start_full_demo_tmux.sh` 起）。**不要另起第二套 stack。**

### SSH 指令樣板（handoff 驗證 — bash ssh 不帶 RMW env 會看到 0 nodes）
```
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && <CMD>"'
```
> 所有 `===` echo 要加引號（zsh 把 `==` 當 glob）。遠端 for-loop 的 `\$i` 在遠端 zsh 展開。

---

## STEP 0 — PRECHECK GATE（BLOCKING；任何一項紅燈就停，不採集，~5 min，Roy 不用站到鏡頭前）

```bash
# 0a. SSH 連通 — 不印 SSH_OK 就 STOP（scp 與 readiness deploy-SHA 都吃 SSH，無離線 fallback）
ssh -o ConnectTimeout=5 -o BatchMode=yes jetson-nano 'echo SSH_OK'   # 期望 SSH_OK exit 0

# 0b. demo 是否還在跑（handoff：tmux session 'demo'，20 nodes）— 不要盲目重啟（會生重複 driver instance）
ssh jetson-nano 'zsh -lic "tmux ls"'   # 期望有一個 session 叫：demo
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 6 ros2 topic hz /state/perception/face"'   # ~20Hz；幾行後 Ctrl-C
# 若 demo 沒在跑，冷啟（不要用 'pawai demo start' — 它會 P0-fail 於缺 brain .env）：
# ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh"'   # 等 ~50s

# 0c-i. PRECHECK：jsonschema 是否在（run_preflight 需要）。不要在採集中途隱性裝環境。
ssh jetson-nano 'python3 -c "import jsonschema" 2>/dev/null && echo JSONSCHEMA_OK || echo JSONSCHEMA_MISSING'
#   若 JSONSCHEMA_MISSING → 在 GATE-0（採集前）補裝再繼續：
#   - Jetson：`ssh jetson-nano 'python3 -m pip install --user jsonschema'`
#     （專案慣例是 `uv pip install`，但 **Jetson 無 uv** 是已知例外，故 Jetson 端用 pip --user）
#   - WSL 端若缺：`uv pip install jsonschema`（不要用裸 pip）
# 0c-ii. 重生 PASS preflight（之後 run_trusted=True）：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/run_preflight.py --profile demo --out artifacts/baseline/preflight_result.json"'   # status 必須 pass 或 pass_with_warnings

# 0d. （建議）乾淨重起 JSONL（handoff 留了 ~9 筆 hitl-0603 face 記錄）。保留歷史、不刪除：
ssh jetson-nano 'cd ~/elder_and_dog/artifacts/baseline && [ -f baseline_result.jsonl ] && mv baseline_result.jsonl baseline_result.$(date +%Y%m%d-%H%M%S).bak.jsonl || echo no-prior-jsonl'
```
**CHECKPOINT（三項全綠才往下）：** `SSH_OK` · `demo` tmux 在 · preflight status `pass`/`pass_with_warnings`。
**若 preflight FAIL → 整條路線 STOP。** 沒有 pass preflight，build_scoreboard 會把每個能力壓成 insufficient_data。記錄：「GATE-0 preflight fail → 本輪無 trusted baseline」。

---

## SCENE 1 — Roy 坐在鏡頭+麥克風前（voice + face-positive）~18 min
Roy 全程坐著面對鏡頭/麥克風。**Grade lane：voice.command → ≥80% pass（70-80 degraded、<70 fail，且 e2e_median≤3.5s、play_ok≥80%）；voice.stop → FN=0 才 pass（success_rate==1.0，任何一輪 miss = fail）；face positive 餵 registered_recall（≥0.80 pass / 0.60-0.80 degraded / <0.60 fail）。**

```bash
# --- #80 VOICE（跑在正在跑的 demo 上；復用其 stt/tts nodes，不 rebuild、不重啟 driver）---
# 互動式：每輪提示，講出該句、按 Enter。30 輪含 6 stop 輪。
ssh -t jetson-nano 'zsh -lic "cd ~/elder_and_dog && bash scripts/run_speech_test.sh --nodes-running"'
# 輸出 CSV → ~/elder_and_dog/test_results/speech_test_<ts>.csv（+ _summary.json 含 grade/e2e median/play_ok）
# 6 個 stop 輪（停/停止/不要動/請你停下來/別動別動別動/欸等一下先停住）每輪都要 match==hit → voice.stop FN=0

# --- #81 FACE positive（Roy 不離座，只調距離）---
# roy @ ~1m（鏡頭 1.0-1.2m，面對鏡頭，整個窗保持不動）×3：
for s in 01 02 03; do
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/capture_baseline_round.py face --capability face.recognition --scenario-id roy_1m_'"$s"' --expected roy --kind positive --distance 1.0 --window 8 --run-id hitl-0604-face --out artifacts/baseline/baseline_result.jsonl"'
done
# roy @ ~2m（椅子退到 ~2.0m）×3：
for s in 01 02 03; do
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/capture_baseline_round.py face --capability face.recognition --scenario-id roy_2m_'"$s"' --expected roy --kind positive --distance 2.0 --window 8 --run-id hitl-0604-face --out artifacts/baseline/baseline_result.jsonl"'
done
```
> 提示：6/3 證據顯示 roy 實際鎖在 ~1.5-1.9m 深度；宣告 1.0m 可能 miss。1m 輪 miss 會誠實拉低 recall — **不要改模型/閾值**（#81 scope-guard 第 10 項：sim_threshold、YuNet/SFace、re-enroll 都不准動，除非零成本修正後 unknown_false_accept_rate 仍 >10%）。distance_m 只有在「命中」時才由 D435 深度覆寫；miss/idle 記的是宣告值（manual_declared），missed 輪別誇大量測距離。
> **若失敗記這個：** voice 任何 stop 輪 match≠hit → voice.stop = **FAIL**（單一 miss 即 fail）。voice e2e_median>3.5s → 標「VAD 時代延遲，mic_stop 尚未接線」，非系統退步。face 1m 鎖不到 → 記 MISS（誠實拉低 recall，lane FAIL/DEGRADED）。

---

## SCENE 2 — Roy 離開畫面，再放鬆入鏡（所有 idle 輪一次打包）~14 min
**Grade lane（全是硬性誤觸閘）：face unknown_false_accept_rate ≤0.03 pass / 0.03-0.10 degraded / >0.10 fail；gesture idle unknown_false_accept_rate ≤0.10 pass / 0.10-0.30 degraded（RATE proxy，非字面 count gate）；object idle ≤0.01 pass / 0.01-0.10 degraded。**

```bash
# 關鍵：每個 face/gesture idle 輪前，Roy 完全離開畫面並等 >=8s（tracker grace/hold ~2.5s；
# 這 8s 離框正是修掉 6/3 false_accept_rate=1.0 污染的關鍵）。發 idle 窗前先確認沒有 roy track：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 4 ros2 topic echo /state/perception/face --once"'   # tracks 空 或 stable_name!=roy

# --- #81 FACE idle = 空畫面 ×3（expected=unknown、kind=idle）---
for s in 01 02 03; do
# Roy：離框、等 8s、才發：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/capture_baseline_round.py face --capability face.recognition --scenario-id idle_empty_'"$s"' --expected unknown --kind idle --distance 1.0 --window 12 --run-id hitl-0604-face --out artifacts/baseline/baseline_result.jsonl"'
done

# --- #82 GESTURE idle ×3（Roy 入鏡 ~1.5m，手放鬆，不刻意比手勢；60s 窗）---
for s in 01 02 03; do
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/capture_baseline_round.py percep --capability gesture.wave --scenario-id wave_idle_'"$s"' --expected none --kind idle --window 60 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl"'
done

# --- #82 OBJECT idle ×2（畫面無杯子；60s 窗）---
for s in 01 02; do
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 benchmarks/scripts/capture_baseline_round.py percep --capability object.cup --scenario-id cup_idle_'"$s"' --expected none --kind idle --window 60 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl"'
done
```
> 要記的 caveat：face idle 是**空畫面**（無陌生人在場）→ 陌生人拒絕 **未驗證**。合 spec（face 是 evidence_only，無 guardian/stranger-alert 宣稱 — North Star §5），但 snapshot 要帶這個 caveat。若有第二人在場，可額外跑 `stranger_1m_01`（仍 `--expected unknown --kind idle`）作真實 false-accept 驗證。
> **若失敗記這個：** idle 輪預測出 roy → false_accept，加長離框時間重做（不改模型）。gesture idle 閘是 `unknown_false_accept_rate`（RATE），spec §4 是 count gate（≤1/10min）— 標「rate-based proxy，非字面 count gate」，grade 別過度解讀。

---

## SCENE 3 — Roy 站 ~1.5-2m 揮手（gesture-positive）~6 min
**Grade lane：gesture.wave success_rate ≥0.90 pass / 0.80-0.90 degraded / <0.80 fail。** wave confidence 硬寫死 1.0（`vision_perception_node.py:414`）→ recall 是 **100% 人工 ground-truth**；Roy 須目視確認每個窗都是真揮手。

```bash
# smoke：確認 recognizer backend 有發 wave（Roy 在 ~1.5m 揮手）：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 20 ros2 topic echo /event/gesture_detected --once"'   # 期望 "gesture":"wave"
# wave 近 ~1m ×10（手舉著、連續揮）：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && for i in 01 02 03 04 05 06 07 08 09 10; do echo wave_1m_\$i; python3 benchmarks/scripts/capture_baseline_round.py percep --capability gesture.wave --scenario-id wave_1m_\$i --expected wave --kind positive --distance 1.0 --window 8 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl 2>&1 | tail -2; sleep 3; done"'
# wave 遠 ~2m ×10：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && for i in 01 02 03 04 05 06 07 08 09 10; do echo wave_2m_\$i; python3 benchmarks/scripts/capture_baseline_round.py percep --capability gesture.wave --scenario-id wave_2m_\$i --expected wave --kind positive --distance 2.0 --window 8 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl 2>&1 | tail -2; sleep 3; done"'
```
> **若失敗記這個：** confidence 寫死 1.0 → recall/誤觸 是 100% 人工判讀；Roy 目視標每個窗 hit/miss。某窗在 recognizer 未出 wave → 記 MISS（誠實拉低 recall）。在 snapshot grade pass 前，Studio 只「顯示」手勢、**不觸發動作**（§4/§9）。

---

## SCENE 4 — 桌上放杯子 + 雜物（object-positive）~4 min
**Grade lane：object.cup success_rate ≥0.80 pass / 0.60-0.80 degraded / <0.60 fail。**

```bash
# 先 SMOKE GATE — object_perception TRT 首建 3-10 分鐘。TRT 編譯中發 cup 窗 = 假 miss。
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 15 ros2 topic hz /perception/object/debug_image"'   # 期望 ~6-8 Hz；若 0 Hz，等、再測
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 20 ros2 topic echo /event/object_detected --once"'   # 杯子在桌上 → class_name==cup
# cup 近 ~1m ×5（杯子放桌上 + 背景雜物；不在地上、不在手上）：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && for i in 01 02 03 04 05; do echo cup_1m_\$i; python3 benchmarks/scripts/capture_baseline_round.py percep --capability object.cup --scenario-id cup_1m_\$i --expected cup --kind positive --distance 1.0 --window 8 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl 2>&1 | tail -2; sleep 3; done"'
# cup 遠 ~2m ×5：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && for i in 01 02 03 04 05; do echo cup_2m_\$i; python3 benchmarks/scripts/capture_baseline_round.py percep --capability object.cup --scenario-id cup_2m_\$i --expected cup --kind positive --distance 2.0 --window 8 --run-id hitl-0604-percep --out artifacts/baseline/baseline_result.jsonl 2>&1 | tail -2; sleep 3; done"'
# 確認記錄都落地：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && grep -c gesture.wave artifacts/baseline/baseline_result.jsonl; grep -c object.cup artifacts/baseline/baseline_result.jsonl; grep -c face.recognition artifacts/baseline/baseline_result.jsonl"'
```
> **若失敗記這個：** cup 窗在 TRT 未暖前發 → 丟掉該輪（假 miss，別讓它污染 cup_recall）。debug_image 0 Hz = TRT 還在編，等。

---

## SCENE 5 — Go2 區域，nav DRY-RUN（不可走）~8 min
**Grade lane：4 個 nav 能力全 = insufficient_data（設計如此）。無 baseline record、無 motion_sign_off（無動作）。**
nav 要 **nav_capability lane**，不是 perception demo。voice/perception 採集已落 disk，現在停 demo 沒問題。

```bash
# （可選）停 perception demo 釋放 stack：
# ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && bash scripts/clean_full_demo.sh"'
# 起 nav lane（Go2 通電；Phase 10 stack）。等 ~50s：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && ROBOT_IP=192.168.123.161 MAP=/home/jetson/maps/home_living_room_v8.yaml bash scripts/start_nav_capability_demo_tmux.sh"'
# 確認 action server + 站立 topics（無動作）：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 action list | grep nav && ros2 topic hz /state/nav/heartbeat"'
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && timeout 4 ros2 topic echo /state/nav/safety --once"'
# *** DRY-RUN：不要設 /initialpose。AMCL 未定位下，goal 被 accept 後立即 abort → Go2 不動。 ***
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 scripts/send_relative_goal.py --distance 0.3"'
# 期望誠實 dry-run：success=False message='amcl_lost'（或 odom_lost_driver_disconnected / nav2_unavailable）。Go2 不動。
# 這證明 client->server->AMCL-gate 鏈路端到端接通且零動作。
# 不要 echo /event/nav/mission（不存在）。不要跑 --distance 0.5/1.0（那會走 Go2）。
```
> **若失敗記這個：** result success=True 或 Go2 動了 → 立刻 `clean_full_demo.sh`，記「/initialpose 殘留致 AMCL 已定位」。其餘照常記 insufficient_data。

---

## STEP 6 — BUILD SNAPSHOT + READINESS + FREEZE（全 WSL，Roy 在鍵盤前）~10 min
```bash
cd /home/roy422/newLife/elder_and_dog
# 6a. 轉 voice CSV → JSONL（tag voice.command / voice.stop）。先找最新 CSV：
NEWEST=$(ssh jetson-nano 'ls -t ~/elder_and_dog/test_results/*.csv | head -1')
scp "jetson-nano:$NEWEST" /tmp/voice.csv
python3 benchmarks/scripts/voice_csv_to_jsonl.py --csv /tmp/voice.csv --out /tmp/voice_baseline.jsonl --run-id hitl-0604-voice --stop-intent stop
# voice.stop FN 檢查（6 stop 輪要 ZERO 'fail'）：
grep '"capability_id": "voice.stop"' /tmp/voice_baseline.jsonl | grep '"pass_fail": "fail"'   # 期望「無輸出」= FN=0
# 6b. 拉 perception+face JSONL、manifest、preflight 下來：
scp jetson-nano:'~/elder_and_dog/artifacts/baseline/baseline_result.jsonl' /tmp/baseline_result.jsonl
scp jetson-nano:'~/elder_and_dog/artifacts/baseline/preflight_result.json' /tmp/preflight_result.json
scp jetson-nano:'~/elder_and_dog/.pawai-last-deploy' /tmp/jetson_manifest.json
# 6c. 把 voice JSONL 併進同一個 baseline（aggregator 按 capability_id+scenario_kind 分組，非時間）：
cat /tmp/voice_baseline.jsonl >> /tmp/baseline_result.jsonl
# 6d. 在 WSL build snapshot（--preflight 強制）：
python3 -m benchmarks.core.build_scoreboard /tmp/baseline_result.jsonl --manifest /tmp/jetson_manifest.json --preflight /tmp/preflight_result.json --out /tmp/baseline_snapshot.json
# 6e. 看你關心的 graded rows：
python3 -c "import json;c=json.load(open('/tmp/baseline_snapshot.json'))['capabilities'];print(json.dumps({k:c[k] for k in ['face.recognition','voice.command','voice.stop','gesture.wave','object.cup']},ensure_ascii=False,indent=2))"
# 6f. readiness verdict（需 SSH up — 經 SSH 讀 live deploy SHA）：
PAWAI_SCOREBOARD_PATH=/tmp/baseline_snapshot.json /home/roy422/.venv/bin/pawai readiness --json
# 6g. freeze 給 demo day（複製 artifacts/baseline/baseline_snapshot.json → frozen/2026-06-18/）：
cp /tmp/baseline_snapshot.json artifacts/baseline/baseline_snapshot.json
/home/roy422/.venv/bin/pawai readiness freeze --date 2026-06-18
# 6h. 把 evidence 凍進 git-tracked 資料夾（artifacts/baseline 在 gitignore）：
mkdir -p docs/runbook/baseline-evidence/2026-06-04-hitl && cp /tmp/baseline_result.jsonl /tmp/baseline_snapshot.json /tmp/preflight_result.json /tmp/jetson_manifest.json docs/runbook/baseline-evidence/2026-06-04-hitl/
```
**verdict 數學：** `ready` 只在 run_trusted=True AND preflight pass AND snapshot SHA == Jetson `.pawai-last-deploy`（WSL HEAD `885728f` 對得上）AND 15 caps 全在 AND 每個 mainline cap pass、非 pass 者帶 failure_reason。**本輪預期 NOT-ready**（face 可能轉 pass，但 nav/pose 仍 insufficient_data）— 這是正確的、誠實的 fail-closed 結果，不是失敗。

**清掉 schema_validator_unavailable：** 已驗證**本輪非 blocker** — jsonschema 4.26.0 可在 `/home/roy422/.venv` import；對 stale snapshot 跑 readiness 第一個 reason 是 `sha_mismatch` 不是 schema_validator。**在 WSL 用該 venv 跑 build+readiness 就不會觸發。** 永久鎖法（Codex follow-up，非本輪）：把 jsonschema 釘進 pawai/benchmarks runtime deps + 加 ImportError 測試。若真看到 `schema_validator_unavailable:ModuleNotFoundError`：WSL 端 `uv pip install jsonschema`（裝進 `/home/roy422/.venv`，不要用裸 pip）。

---

## STEP 7 — 關 issue + 清環境（~5 min，WSL）
```bash
# 讀 issue body 用 --json（純 gh issue view 在此環境回空）：gh issue view <n> --repo roy4222/PawAI --json number,title,body,state,labels
# #83 pose — 關 insufficient_data（無 observer、studio_only/P2）：
gh issue comment 83 --repo roy4222/PawAI --body 'pose.basic = insufficient_data (no_samples). 觀測管線未接：perception_baseline_observer 只訂 gesture+object；capture_baseline_round.py 只有 face/percep mode，無 pose mode。studio_only/P2（North Star §5/§8），scope-guard 不換模型。pose.fall 維持 insufficient_data（幻覺未解，§5 禁宣稱）。本輪不收 record、不擋 6/18 freeze。'
gh issue close 83 --repo roy4222/PawAI --reason completed
# #84 nav — 4 caps 全 insufficient_data（dry-run 完成，無動作）：
gh issue comment 84 --repo roy4222/PawAI --body 'nav 四能力全 insufficient_data。safe_stop=recorder BD-7 未接；no_auto_resume=BD-8 行為衝突待重設計；short_move=僅 dry-run（/nav/goto_relative --distance 0.3 未設 /initialpose 被 AMCL gate 以 amcl_lost abort，證明 action 鏈路通且 Go2 全程不動，安全先於移動鐵律 §7 未滿足前不跑真實 motion）；dynamic_avoidance=stop-only/future。修正：/event/nav/mission 不存在於 source，實際觀測是 action result(success/message/actual_distance)。本輪無真實 motion，無 motion_sign_off record。'
gh issue close 84 --repo roy4222/PawAI --reason completed
# 用 snapshot rows 的真實 grade + reason 關 #80、#82（face #81 視 grade 決定）；#88 tracking 最後關。
# 不要據 6/3 handoff prose 宣稱 face PASS — 只有本輪乾淨重採重 build 的 snapshot 能改 grade。
# 停一切：
ssh jetson-nano 'zsh -lic "cd ~/elder_and_dog && bash scripts/clean_full_demo.sh"'   # 若 perception demo 還在
# mic_stop 接線（Codex，4 檔）延到 demo stop 後的另一場 session — 動到語音主線，不可中途部署。本輪 voice 量 AS-IS-WITH-VAD。
```

---

## 本輪預期誠實 grade
| Cap | Lane | 備註 |
|---|---|---|
| voice.command | pass-eligible（≥80%） | VAD 時代 e2e，非 metric-v2 |
| voice.stop | pass-eligible iff FN=0 | 任一 stop miss → fail |
| face.recognition | degraded floor（每類 n≥3） | committed=FAIL；可信重測；idle=空畫面 → 陌生人拒絕未驗證 |
| gesture.wave | pass-eligible（≥90%） | recall 是人工 ground-truth；idle 閘是 rate-proxy |
| object.cup | pass-eligible（≥80%） | cup 輪前先 smoke-gate TRT |
| pose.basic / pose.fall | insufficient_data | 無 observer；從 WSL 關閉 |
| nav.*（4） | insufficient_data | dry-run、無動作、無 sign-off |

> **若 HITL 整條被 SSH 卡死**（fallback，無 Jetson）：#118 Studio evidence UI + #120 capability health gate 接線可在 WSL 純軟體做（`cd pawai-studio/frontend && npm ci && npm run lint && npm run build` 綠；`pytest pawai_brain/test/ -q` 338 + `interaction_executive/test/ -q` 221 在 gate 預設 OFF 下綠）。**#120 ENABLE（`capability_gate_enabled=True`）是 motion-safety**：保持預設 OFF，未經 Roy 明確授權不得在任何 launch script 翻開。