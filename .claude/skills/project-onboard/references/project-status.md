# 專案進度快照

> 最後更新：2026-05-03 evening (Stage 1 K-STATIC-AVOID-CONTROLLED PASS / Demo A 流程跑通 / Stage 2 detour 仍 fail)

## 當前階段

語音 3/17 freeze。人臉 + vision Phase 2 真推理通過（3/18）。Benchmark 框架 Batch 0+1 完成（3/19，core + face YuNet baseline，28 tests pass）。下一步：Jetson 真實 benchmark + Batch 2（pose/gesture adapter）。

## 里程碑

| 里程碑 | 日期 | 狀態 |
|--------|------|------|
| 功能閉環凍結 | 3/12 | [DONE] |
| 介面契約 v2.0 凍結 | 3/13 | [DONE] |
| 語音 30 輪驗收框架 | 3/14-15 | [DONE] 框架建好，待 Jetson 上跑第一輪 |
| 攻守交換 | 3/16 | [DONE] Roy 交出架構核心 |
| 手勢/姿勢技術選型 | 3/16 | [DONE] DWPose + TensorRT（待本機驗證） |
| 語音 E2E 基線 | 3/17 | [DONE] 10/10 對話、9/10 播放、median 5.4s |
| 人臉 Jetson smoke | 3/18 | [DONE] D435 + state/event/debug_image 全通 |
| vision_perception Phase 1 | 3/18 | [DONE] mock mode Jetson 驗證通過 |
| vision_perception Phase 2 | 3/18 | [DONE] RTMPose 真推理 Jetson 驗證通過（balanced mode, ~3.8 Hz debug_image, GPU 91-99%） |
| Benchmark 框架 Batch 0+1 | 3/19 | [DONE] core framework + face YuNet adapter，28 tests pass |
| P0 穩定化 | 4/6 | [PENDING] |
| **最終展示** | **4/13** | **[PENDING] 硬底線** |

## 各模組狀態

| 模組 | 狀態 | 說明 |
|------|------|------|
| 語音閉環 | [FROZEN] | E2E 已通（ASR→LLM→TTS→Megaphone→Go2），10/10 對話、9/10 播放。等硬體到貨做最後一輪（外接喇叭/麥克風 A/B、自激測試） |
| 人臉閉環 | [USABLE] | Jetson smoke passed（3/18）。D435 + state/event/debug_image 全通。int32 序列化 bug 已修。待驗：有人時識別準確率 |
| 姿勢辨識 | [USABLE] | **全 MediaPipe**（3/21 晚）：MediaPipe Pose (CPU) 18.5 FPS、GPU 0%、Foxglove 實測通過。RTMPose 降為備援 |
| 手勢辨識 | [USABLE] | **全 MediaPipe**（3/21 晚）：MediaPipe Hands (CPU) 16.8 FPS、GPU 0%。RTMPose 手部 keypoints 不可靠已驗證 |
| FastAPI Gateway | [PENDING] | 骨架待建 |
| Mock Event Server | [AVAILABLE] | vision_perception mock_event_publisher 可直接用，循環發 gesture+pose 假事件 |
| PawAI Studio | [PENDING] | 鄔負責，mock_event_publisher 已可接 |
| LLM Brain | [STABLE] | Qwen2.5-7B-Instruct on RTX 8000，max_tokens 120，RuleBrain fallback 5/5 |
| Benchmark 框架 | [STABLE] | L1 全模型完成（face/pose/gesture/stt），L2 共存矩陣完成。3/25 決策數據齊全 |
| 文件網站 | [PENDING] | 黃/陳負責，Astro + Starlight |
| nav_capability | [USABLE] | 5/3:capability_publisher launch default 0.40→**0.45**(對齊 nav_action_server YELLOW upper 0.50)、xy_goal_tolerance 0.15→**0.10**。Demo A 1.5m goal 流程跑通。Jetson `~/.local/.../entry_points.txt` 缺 3 個 entry 已手補 |
| D435 safety gate | [USABLE] | 5/2:`depth_safety_node` (go2_robot_sdk),fail-closed,手擋 1.03s 翻轉。5/3 demo 中觀察到 box ≤0.4m 即 depth_clear→false 觸發 auto-pause |
| Executive safety wiring | [USABLE] | 5/2:WorldState 訂三個 capability、SafetyLayer 三段 gate。92/92 unit tests 過,未接 launch |
| Capability launch wiring | [USABLE] | 5/3:8 windows + 7 nav nodes 全活、`nav_round_reset.sh` READY 流程驗證。已知坑：colcon build setuptools 不相容 → editable install 直接 source rsync 生效 |
| **Stage 1 遇障停車** | **[PASS]** | 5/3 R3 R1：box 1.5m / goal 1.8m → Go2 走 0.85m / drift 0.19m / 停 box 前 0.54m。reactive_stop + D435 + auto-pause 三鏈同步。**K-STATIC-AVOID-CONTROLLED PASS** |
| **Stage 2 自動繞行** | **[FAIL]** | 5/3 多輪嘗試（box 0.7-2.0m / goal 0.5-2.5m）DWB 都沒繞、`No valid trajectory` + BT spin recovery 失敗。當前 yaml 是「保守安全停」profile，要 detour 需獨立 profile + `robot.launch.py` 加 nav_params_file launch arg（line 77 寫死）|
| nav_round_reset.sh | [STABLE] | 5/3 新工具：emergency release / nav resume / costmap clear / 3 capability snapshot / cmd_vel quiet → READY/NOT-READY summary |

## 近期焦點(2026-05-02 更新)

**Phase A 導航底座日完成**(commits `a3bdd2e` / `9fe6046` / `e413406`):
1. ✅ `/state/nav/paused` latched topic + nav_action_server pause/resume + cancel/re-send (BUG #2)
2. ✅ `/capability/depth_clear` fail-closed(D435 ROI gate)
3. ✅ `/capability/nav_ready` v0.5(AMCL freshness + covariance)
4. ✅ WorldState 接三個 capability + SafetyLayer 三段 gate(NAV / MOTION / nav_paused)
5. ✅ 9 份外部 stack research(Odin / OM1 / NavDP / visualnav / amigo_ros2 / DimOS + 2 papers)+ synthesis 排好 P0/P2/P3 優先序
6. 🟡 Foxglove D435 點雲 TF (static_transform_publisher) 暫時頂著,正式 D435 mount 校正排到 5/13 後

**5/2 深夜試跑教訓**(動態避障 v0):
- ⚠️ **Damp (api_id=1001) 不能當移動中 emergency stop** — 馬達軟鬆弛 → Go2 摔倒。改用 `emergency_stop.py engage` (mux pri 255 + lock) + StopMove (1003,**必填 topic=rt/api/sport/request**)
- ⚠️ **detour fail 條件 ≤ 1s** — 不是等 5-6s。reactive 進 danger zone 即代表 DWB 沒在 0.6m 之外繞掉,本輪已失敗
- ⚠️ **velocity_smoother 不解此 bug** — mux pri 200 切換 bypass smoother;v1 才考慮 reactive 漸進 ramp
- ⚠️ **WebRtcReq 必填 topic** — `api_id=1003` 在不同 topic 下意義不同(sport=StopMove vs obstacles_avoid=Move)

**day 2 P0**(明天必做):
1. 場景校準 + R3:標 box 位置 / Go2 起點 / 左右淨空,跑第三輪驗證 R1 行為是否可重現
2. 第二階段 K-LOW-OBSTACLE-DETECT/GATE:D435 對低矮物 ≤1s 翻 depth_clear=false
3. 接 `interaction_executive.launch.py` — 把 capability_publisher / depth_safety / executive 串起
4. Brain rules `speech_nav_demo` + `face_wave_approach`
5. `/capability/nav_ready` 升級 v1 — lifecycle service + TF map→base_link + costmap healthy(取代 pose age)
6. Studio Trace Drawer LED 顯示 3 個 capability bool

## 近期焦點(3/21 更新)

**已完成（3/18-3/21）**：
1. ✅ Benchmark 框架 Batch 0+1（core + 6 adapters: YuNet/SCRFD/RTMPose/MediaPipe/Whisper）
2. ✅ L1 全模型基線（face 3 / pose 3 / gesture 2 / stt 2 = 10 個模型）
3. ✅ L2 共存矩陣（face+pose / scrfd+pose / whisper+pose）
4. ✅ MediaPipe ARM64 可安裝驗證（推翻先前結論）
5. ✅ face Research Brief 決策回填（YuNet=主線, SCRFD=備援）
6. ✅ Jetson 環境問題修復（onnxruntime GPU/CPU 衝突、numpy 降級、OpenCV 4.13 相容）

**下一步**：
1. 本地 LLM benchmark（Qwen2.5-0.5B 等小模型 fallback）
2. TTS benchmark（Piper vs MeloTTS）
3. L3 全模型共存（face + pose + whisper 同時 30s）
4. 外接喇叭/麥克風到貨後重測語音
5. PawAI Studio 串接（鄔負責）

## 3/16 後分工

| 人 | 3/16 → 4/6 | 4/6 → 4/13 |
|----|-------------|-------------|
| **Roy** | Brain Adapter + DWPose Jetson 部署 + 整合 | 端到端 + Demo pipeline |
| **楊** | 手勢/姿勢 x86 demo + Studio gesture/pose 互動 | 整合測試 + Demo B |
| **鄔** | 全部 Studio 面板 | Demo Showcase + 微調 |
| **黃** | 文件站內容 | 展示站首頁 |
| **陳** | 架構圖 + 環境建置文件 | 團隊介紹 + 校對 |

## 已解決的重大問題

- Go2 音訊播放三層 bug（asyncio 跨執行緒 + WAV sample rate + intent 名稱不對齊）
- CTranslate2 CUDA 加速（Whisper Small 延遲從 10s+ 降到 ~0.6s）
- HyperX stereo-only 麥克風問題（手動 downmix）
- Energy VAD 整合到 stt_intent_node
- LLM Bridge 支援本地 Ollama models（2026-03-16）
- **Megaphone「失效」誤判修正**（2026-03-17）— API 沒死，是 payload 格式/msg type 不對
- **Echo gate timing 修正**（2026-03-17）— tts_playing 提前到 TTS request 入口 + 1s cooldown
- **Qwen3.5 thinking mode 關閉**（2026-03-17）— enable_thinking=false，乾淨 JSON 輸出
- **face_identity_node int32 序列化修正**（2026-03-18）— np.int32 bbox 無法 json.dumps，轉 Python int
- **vision_perception Phase 1 骨架落地**（2026-03-18）— gesture+pose mock mode，23 unit tests，Jetson 驗證通過

## 關鍵技術決策（3/16 新增）

### 手勢/姿勢推理拓樸（3/18 統一）

- **主路徑**：rtmlib + RTMPose wholebody 單模型（一次推理同時產出 body + hand keypoints）
- **升級選項**：DWPose wholebody（精度略優，但 Jetson 上零成功記錄）
- **備援**：hand-only + body-only 雙模型（wholebody 不達標時啟用）
- MediaPipe 僅作 x86 概念驗證，不上 Jetson
- 詳見 `docs/pawai-brain/perception/gesture/README.md`、`docs/pawai-brain/perception/pose/README.md`、`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-18-vision-perception-skeleton-design.md`

### vision_perception 架構（3/18 新增）

- face_identity_node（現有）+ vision_perception_node（新建）共享 D435 camera topic
- vision_perception_node 支援 `use_camera=false`（mock mode，不需相機）
- gesture+pose 共用推理，分兩個 classifier
- 契約不變：`/event/gesture_detected`、`/event/pose_detected` 對齊 v2.0
