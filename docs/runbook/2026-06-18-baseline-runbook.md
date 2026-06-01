# Baseline Runbook（上機跑 capability baseline，Roy 親自跑）

> **性質**：在 Jetson 上跑 capability baseline 的操作手冊。這份是「**怎麼上機量、JSONL 存哪、snapshot 怎麼 freeze、demo 當天怎麼用**」的唯一真相源。
> **不放**：架構決策（Master Plan）、門檻數字（Capability Baseline Spec）、code 結構（Implementation Plan）。
> **關係**：Master Plan `docs/pawai-brain/plans/2026-05-31-capability-baseline-scoreboard-plan.md`｜Spec `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`｜Implementation `docs/pawai-brain/plans/2026-06-01-scoreboard-implementation-plan.md`
> **既有相關 runbook**：`docs/runbook/demo_script.md`、`demo-30-case-checklist.md`、`demo-frozen-backlog.md`（demo 展示用，與本 baseline 量測 runbook 互補）。

> **鐵律：as-is baseline 必走 demo entrypoint**（`start_full_demo_tmux.sh` / 各 lane 腳本），**不裸 `ros2 run`**——裸跑會拿到錯的 mic_gain(1.0≠8.0) / gesture backend(rtmpose≠recognizer) / whisper device(cpu-int8≠cuda-fp16)。

---

## 上機流程

0. **Layer-0 Preflight**：跑填好的 `pawai`/`jetson-verify demo.yaml`；`fail → 全 insufficient_data，停`。記 `version_snapshot`（讀 `.pawai-last-deploy` + WSL commit，mismatch 警告）。
1. **環境鎖定**：`sudo bash benchmarks/scripts/prepare_env.sh`（nvpmodel -m 0 + jetson_clocks；必要時 `--drop-cache`）。
2. **資源採樣**：背景跑 `benchmarks/core/monitor.py JetsonMonitor`（reuse），aggregate 值填回 scenario 的 `cpu_pct/gpu_pct/ram_mb`。
   - 實機參考（2026-05-31 motion-safe 感知 lane face+vision+D435）：RAM ~1.17GB used / avail 6.2GB、CPU ~41%、temp ~53–54°C、`/state/perception/face` 19.97Hz、vision debug_image ~3.9–4.8Hz。
3. **逐能力跑**（深測優先 voice → face/gesture/object；nav 受跑序鐵律約束，見下）：
   - voice：走 `run_speech_test.sh` → `speech_test_observer` → 轉 JSONL（A2 轉 record：補 `capability_id=voice.command/voice.stop`）。**前置（demo-blocking，見 spec §2 設計結論）**：先確認 `mic_stop` 訊號流已接（Studio stopRecording 發 `/event/mic_boundary` → stt_intent 訂閱），baseline 走 **manual mic boundary**（`energy_vad.enabled=False`）；latency **雙記錄**（新 `e2e` 從 `mic_stop_ts` 起算、保留舊 `speech_start_ts` 欄位對照，報告標「metric v2」）。voice.stop 從 30 輪拆「停」專項 N 輪（含噪音），FN 硬性=0。
   - **gesture/object**（required baseline step——mainline 主張，必跑）：起感知 lane（demo entrypoint），跑 `perception_baseline_observer`（Task 4，event-only），operator 宣告 round_meta（每 round 標 `scenario_kind` = positive / idle）+ 人工確認 → JSONL。**object 必須先起 `object_perception`（拿 demo 杯子測 `object.cup`）；gesture 必須切 `recognizer` backend**（demo 真實 backend，非壓測 mediapipe），含 person-present idle 誤觸段。
   - **face**（required）：跑 `face_baseline_observer`（Task 4b，吃 `/state/perception/face` 連續流），operator 宣告 FaceRoundMeta（expected 註冊者名 / "unknown"(idle) / distance / window，每 round 標 `scenario_kind`）→ JSONL。**勿用 `perception_baseline_observer` 跑 face**（event-only 量不出 unknown-false-accept）。
   - **nav 跑序鐵律（§6 鎖定）**：`safe_stop` + `no_auto_resume` **pass（或明確人工安全 override）前，不允許跑 motion**。順序不可顛倒（不可先跑 motion 再補 safety）。
     - `nav.safe_stop` / `nav.no_auto_resume`：**等 recorder BD-7/BD-8**（no_auto_resume 還需 **BD-8 行為重設計**，非只接 recorder），本輪標 insufficient_data。
     - `nav.short_move`：safety 兩項未 pass 前**只做 dry-run / action-path check**（手動發 goto_relative 驗 action server 鏈路通、量 /event/nav/mission，**不讓 Go2 實際走**）；safety pass 或人工 override 後才跑真實 0.3/0.5m motion。fresh stack 先定位 F7、走 BD-7D wrapper。

> **附註（執行日誌，非主流程）**：2026-05-31 的 motion-safe 探測輪**未**測 object/gesture-recognizer（當天只驗感知 lane 可起）。正式 baseline run 必須補齊上述 object_perception + recognizer backend——它們是 mainline required step，不可停在 `insufficient_data`。
4. **產 snapshot**：`build_scoreboard.py`（Task 3b，≤30 行 CLI，讀 `baseline_result.jsonl` + `--manifest` + `--preflight artifacts/baseline/preflight_result.json` → `aggregate` → 寫 `artifacts/baseline/baseline_snapshot.json`）。**必須帶 `--preflight`**——缺 preflight → `run_trusted=False` → 全 grade 覆寫 insufficient_data（fail-closed）。
5. **判讀**：看每能力 grade + brain_allowed，決定進主線(pass+mainline) / 只顯示(degraded/studio_only) / 不宣稱(fail) / 不放行高風險(insufficient_data)。**這就是 v0.1 的成功定義達成點。**

---

## JSONL / snapshot 存放與 freeze（Demo Readiness，§9 待 grill 補細節）

- baseline 逐 round → append 同一個 `baseline_result.jsonl`（face/gesture/object/voice/nav 共用）。
- `build_scoreboard.py` 讀 jsonl + `--manifest`（Jetson `.pawai-last-deploy`）+ `--preflight artifacts/baseline/preflight_result.json` → 產 `artifacts/baseline/baseline_snapshot.json`。
- **demo 當天用 frozen snapshot**（不在 demo 中即時重算，避免 grade 抖動讓 Brain 行為跳變）。snapshot 帶 `run_id / git sha / deploy timestamp / run_trusted`。
- preflight fail → `run_trusted=False` → 全 grade 覆寫 insufficient_data（fail-closed），snapshot 不可當 demo 依據。

> §9 Demo Readiness / Frozen Snapshot 的完整規則（有效期限 / 現場 override / live vs frozen）待逐功能討論到 §9 後補。
