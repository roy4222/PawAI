# 專案狀態

**最後更新**：2026-04-06（Sprint Day 11 — 混合模式策略轉向 + Studio Gateway E2E 通過）
**硬底線**：2026/4/13 文件繳交，5/16 省夜 Demo，5/18 正式展示，6 月口頭報告

---

## 各模組狀態

| 模組 | 狀態 | 最後驗證 | 備註 |
|------|------|----------|------|
| 語音 (speech_processor) | **網頁語音 E2E 通過（文字+錄音）** | 4/6 | Go2 機身 ASR 不可用（風扇噪音）；**Studio Gateway 錄音模式 E2E 通過**：瀏覽器說話→ASR~430ms→LLM~1.5s→TTS→USB 喇叭，E2E ~2s |
| 人臉 (face_perception) | **greeting 可靠化** | 4/6 | sim_threshold 0.35→0.30，identity_stable 21 次/2min（調前 1-3 次），Executive idle→greeting 確認通；track 抖動仍在（45 tracks/2min），Day 12 修 |
| 手勢 (vision_perception) | **上機驗收 5/5** | 4/4 | stop/thumbs_up/非白名單/距離/dedup 全 PASS |
| 姿勢 (vision_perception) | **上機驗收 4/4** | 4/4 | standing/sitting/fallen→EMERGENCY/恢復→IDLE 全 PASS |
| LLM (llm_bridge_node) | **E2E 通過** | 4/1 | Cloud 7B → RuleBrain，greet cooldown dedup 正確 |
| Studio (pawai-studio) | **Gateway 錄音+文字 E2E 通過** | 4/6 | Gateway（FastAPI+rclpy on Jetson:8080）；push-to-talk 錄音 E2E ~2s；文字輸入也通；前端 Next.js 不動 |
| CI | **17 test files, 225+ cases** | 4/1 | fast-gate + **blocking contract check** + git pre-commit hook |
| interaction_executive | **v0 + thumbs_up 擴展 + fallen 可關** | 4/6 | thumbs_up 在 GREETING/CONVERSING 也生效；`enable_fallen` 參數化（demo 關閉）；39 tests PASS |
| 物體辨識 | **Executive 整合完成** | 4/6 | cup 觸發 TTS「你要喝水嗎？」✅；book 偶爾辨識（0.3 threshold 下）；bottle 未偵測到；YOLO26n 小物件偵測率低，yolo26s 升級記錄到 Day 12+ |
| 導航避障 | **停用 + 文件化** | 4/4 | demo-scope.md 新建、contract/mission/導航避障 README 已更新、demo 腳本移除 obstacle windows |

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
- 文件繳交 Ch1-5（4/13 硬底線）
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
