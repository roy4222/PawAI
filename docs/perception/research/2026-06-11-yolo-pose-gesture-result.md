# YOLO26-pose 取代/補強 MediaPipe pose 與手勢 可行性研究結果

> **日期**：2026-06-11
> **對應 goal**：`docs/perception/research/goals/2026-06-11-yolo-pose-gesture-goal.md`（multi-goal member 4/4）
> **Verdict**：**NEEDS_TEST_HITL_CLIPS**（§5 附離線 A/B 協議 + 晉級上機的 pass gate）
> **本研究為 read-only**：未改 code、未 commit、未安裝任何東西。
> 引用格式：`file:line`（repo 相對路徑）或 URL；外推數字一律標明假設與來源世代。

---

## TL;DR

1. **「17 kpt 改寫成本」這個問題本身已經過時**：`pose_classifier.classify_pose` 的輸入**本來就是 COCO 17 kpt**（`pose_classifier.py:5,119`），MediaPipe 是經 33→17 壓縮層接進來的（`mediapipe_pose.py:18-32`），z 軸從未進過 classifier（`mediapipe_pose.py:78`）。**結構性改寫成本 ≈ 0**——真正的移植成本是 score 語意（visibility vs kpt-conf）的門檻重校，不是規則重寫。
2. **手勢的 YOLO 路線確認死路**：Ultralytics 官方只有 hand-keypoints **dataset**（標註由 MediaPipe 生成、CC BY-NC-SA 4.0 非商用），**沒有預訓練 hand 模型**；社區品全是「拿 GPU 蒸餾 MediaPipe」——品質天花板就是現任、授權鏈更糟。**「一顆換兩顆」的整併算盤砍半**：YOLO26-pose 最多換掉 pose 一顆 + 附贈 person bbox + 接管 wave（body wrist 可餵 WaveDetector），palm/fist/ok 等靜態手勢仍離不開 MediaPipe 21 點。
3. **紙面裁不了的只剩一件事**：YOLO26n-pose 的 landmark 品質在 Go2 仰角 + 居家場景下是否好到值得放棄「GPU 0% 基石」。而這件事**離線免費可測**——`classify_pose` 是 backend 無關純函數，拿 6/9-6/10 demo 錄影在 WSL 跑 YOLO26n-pose，餵同一套規則，直接和 MediaPipe 同幀對比 sitting 判定。一個下午出數字，順便把 478_SC 三方對照（Q9）一起做掉。
4. **上機名額本輪不給 pose**：下次上機日已被 object scale-up 矩陣 A-D 訂走（sibling 報告 GO_BENCH_MATRIX）；YOLO-pose 的 FPS/RAM 紙面上限/下限已夾得很窄（純推理 ~5-8ms、node 內 15-25ms、RAM +200-400MB 獨立 node），不是決策瓶頸——sitting 品質才是，而那不需要 Jetson。

---

## §1 Findings（45 條，附引用）

### A. YOLO26-pose 官方規格

- **F1** YOLO26-pose **五尺度（n/s/m/l/x）全部已發布**，inference/val/train/export 全支援，無 coming-soon 標記。（https://docs.ultralytics.com/models/yolo26/ Supported Tasks 表；與 sibling 報告 F3 一致）
- **F2** 官方數字：**YOLO26n-pose = mAP-pose 50-95(e2e) 57.2 / 2.9M params / 7.5 GFLOPs**；**YOLO26s-pose = 63.0 / 10.4M / 23.9 GFLOPs**。（https://docs.ultralytics.com/tasks/pose/ 效能表）
- **F3** T4 TensorRT 延遲：n-pose **1.8ms**、s-pose 2.7ms、l-pose 6.5ms、x-pose 12.2ms（COCO val2017@640）。（https://learnopencv.com/yolo26-pose-estimation-tutorial/）
- **F4** YOLO26 全家族 NMS-free end-to-end；官方宣稱 pose 相對 YOLO11「up to +7.2 AP」。（https://docs.ultralytics.com/models/yolo26/）
- **F5** 輸出 = **17 COCO keypoints × (x, y, conf)**；Python API `result.keypoints.xy` shape `(N, 17, 2)` + `keypoints.conf`。（https://learnopencv.com/yolo26-pose-estimation-tutorial/ 原文引述）
- **F6** ONNX e2e export 輸出形態 = **`(1, 300, 6 + K×3)`**（detect 的 `(1,300,6)` 後附 kpt）；社區 21-kpt 手部模型實測 `[1, 300, 69]`、格式 `[x1,y1,x2,y2,conf,class, kp1_x,kp1_y,kp1_vis,…]` → **COCO 17 kpt 推得 `(1,300,57)`**。與 object lane 的 `(1,300,6)` 同哲學、同 parse 模式。（https://github.com/marceloeatworld/yolo26-training；https://docs.ultralytics.com/modes/export/ `max_det=300`；確切 shape 須 WSL export 實證——官方 docs 未明文 pose e2e tensor shape）
- **F7** **多人原生**：「As a single-stage detector, YOLO26-pose handles multiple persons in one forward pass… Each person gets its own bounding box and 17-keypoint skeleton.」單次 forward 出 N 人 bbox + 17 kpt，上限 = max_det 300。（https://learnopencv.com/yolo26-pose-estimation-tutorial/ 原文）
- **F8** pose head 用 **RLE（Residual Log-Likelihood Estimation）**、移除 DFL（edge 友善）。（https://learnopencv.com/yolo26-pose-estimation-tutorial/）
- **F9** 官方自承弱點：罕見姿勢（yoga）、**全倒立**、人體重疊時骨架糾纏、背景小人漏偵——**沒有 sitting/lying/fall 的任何官方評測**。（https://learnopencv.com/yolo26-pose-estimation-tutorial/ Limitations）
- **F10** **官方 Jetson 指南沒有 pose 變體數字**：Orin Nano Super 表只有 detect n（TRT FP16 4.57ms）；pose 在 Jetson 的效能全靠外推。（https://docs.ultralytics.com/guides/nvidia-jetson/；sibling 報告 F14/F15）

### B. 現役 sitting/fallen 規則的 17 kpt 相容性（Q3/Q4 核心證據）

- **F11** **classifier 輸入本來就是 COCO 17**：docstring「Input: COCO body keypoints (17, 2) + scores (17,)」（`vision_perception/vision_perception/pose_classifier.py:5`）、shape 硬檢查 `(17,2)/(17,)`（`pose_classifier.py:119`）。YOLO26-pose 的原生輸出格式 = classifier 的原生輸入格式。
- **F12** MediaPipe 是壓縮層接入：`_MP_TO_COCO` 33→17 映射（`mediapipe_pose.py:18-32`），**只映射 13/17 點**——COCO 1-4（眼/耳）恆為 0（註解明言「Eyes and ears (COCO 1-4) are omitted — not needed」，`mediapipe_pose.py:17`）。
- **F13** 規則用到的 kpt 全集 = nose(0,僅畫圖)、shoulders(5,6)、elbows(7,8)、wrists(9,10)、hips(11,12)、knees(13,14)、ankles(15,16)（`pose_classifier.py:34-39`）——**無一超出 COCO 17，17 kpt 缺 0 個**。
- **F14** MediaPipe 33 點的專屬點（heel 29/30、foot_index 31/32）**沒有任何規則使用**：grep 全 `pose_classifier.py`/`vision_perception_node.py` 無 29-32 索引；wrapper 根本不輸出它們（`mediapipe_pose.py:18-32`）。「腳跟/腳尖」依賴不存在。
- **F15** 各規則 kpt 依賴明細（file:line）：
  - **fallen**：trunk_angle(shoulder,hip) > 60° + 0 ≤ vertical_ratio < 0.45（`pose_classifier.py:161`）；torso 四點 visibility ≥ 0.5 gate（`:168-172`）；deep-bending guard 用 hip→ankle 向量（`:179-189`）；ankle_on_floor 用 ankle.y/image_height > 0.6（`:200-203`）；bbox_ratio 只是 +0.05 confidence bonus（`:205`）。
  - **standing/akimbo**：hip_angle(shoulder-hip-knee) > 155 + knee_angle(hip-knee-ankle) > 155（`:209`）；akimbo 用 shoulders/elbows/hips ≥ 0.5 + wrists 選擇性 ≥ 0.3（`:280-282, :312-321`）。
  - **knee_kneel**：hips+knees ≥ 0.5 必要（`:352-354`）、站側 ankle ≥ 0.5 必要（`:377`）、跪側 ankle 低分視為被遮（`:389-397`）。
  - **sitting**：trunk_angle < sitting_trunk_max_deg + hip/knee/ankle y-geometry + knee_angle < 145（`:230-240`）。
  - **crouching/bending**：hip/knee/trunk 角度（`:243, :249-253`）。
  **每條規則改寫難度：0（公式層）**——全部是 2D 像素幾何。
- **F16** **Q4 直接證據：z 軸是裝飾**。`mediapipe_pose.py:78` 只取 `lm.x * w, lm.y * h`，z 在 wrapper 就被丟棄，從未到達 classifier。goal context「33 kpt 含 z」描述的是 MediaPipe 的能力，不是 PawAI 的使用事實。
- **F17** **真正的移植成本 ①：score 語意**。`body_scores` 現值是 MediaPipe **visibility**（`mediapipe_pose.py:79`）；規則裡 0.5（akimbo/kneel/fallen torso gate）、0.3（wrist）、avg ≥ 0.2 全按 visibility 分布校準。YOLO-pose 的 kpt confidence 是不同分布（OKS-trained sigmoid），**門檻需要離線重校**，否則 fallen/kneel 的 visibility gate 行為漂移。
- **F18** **真正的移植成本 ②：avg_score 隱性偏移**。MediaPipe 下眼/耳 4 點恆 0，`avg_score = np.mean(body_scores)` 被壓低 ~24%（13 點有效/17），`min_score=0.2` 實質= 有效點 avg ≥ 0.26（`pose_classifier.py:122-124`；`mediapipe_pose.py:64-65`）。YOLO-pose 17 點全有效 → 同參數實質變鬆——adapter 需補償或 sweep 重調（6/9 已把 min_score 做成注入參數 `pose_min_avg_score`，`vision_perception_node.py:110`，重調無需改 code）。
- **F19** **真正的移植成本 ③：零點慣例**。`_bbox_ratio_from_kps` 以 `(0,0)` 判 invalid（`vision_perception_node.py:66-77`）；MediaPipe 偵測失敗回全零（`mediapipe_pose.py:64-72`）。YOLO-pose 低 conf kpt 仍有座標值 → adapter 必須「conf < 門檻 → kpt 歸零」，否則幻覺點污染 bbox_ratio（fallen bonus、kneel guard、bending 排除全吃它）。
- **F20** fallen 的 COCO 躺姿通病有社區實證：AlphaPose 系 fall-detection 專案需用 **rotation-augmented COCO 重訓** 才能穩定偵測水平/變角人體（https://github.com/GajuuzZ/Human-Falling-Detect-Tracks 模型說明）；F9 的倒立/罕見姿勢弱點同向。**但對 demo 非阻斷**：two_class 模式 fallen 根本不發（`pose_classifier.py:43-53` COARSE_POSE_MAP 註解「fallen 在 two_class 模式不發」），fallen 是 future-work 級風險。
- **F21** sitting 不穩的根因未必是 landmark 品質：6/9 HITL 的修法全在**規則參數層**（min_score 注入、`sitting_trunk_max_deg` 35→45、two_class 粗分類、`gesture_min_votes`——`pose_classifier.py:112-114`、`vision_perception_node.py:108-114`）。換模型前必須先量「6/9 參數修正後的 MediaPipe baseline」，否則把參數修正的功勞誤記給新模型。

### C. Node 架構與切換成本（Q2 形態 / 切換清單）

- **F22** backend 抽象已存在且可複用：`InferenceAdapter`/`InferenceResult` 介面回傳 `body_kps(17,2) + body_scores(17,) + 左右手 21 點`（`vision_perception/vision_perception/rtmpose_inference.py:20, 98-105`）。YOLO-pose adapter = 實作 body 部分 + 手部回零（與 `_empty_result` 同型態，`rtmpose_inference.py:107-116`）。
- **F23** node 改動點收斂在三處：backend 分支（`vision_perception_node.py:164-226`）+ 新 param 值 + launch/yaml；`/event/pose_detected` contract **完全不動**（`event_builder.py:38-55`；`docs/contracts/interaction_contract.md:511`）。
- **F24** **但 node 是單人架構**：rtmpose adapter 只取 `keypoints[0]`（`rtmpose_inference.py:93-96`）、單一 `pose_buffer` 20 幀投票（`vision_perception_node.py:139, 312-315`）、`track_id` 恆 0（`event_builder.py:42-44` 註明 Phase 1 convention）。**多人優勢要吃到需要 per-track buffer + 跨幀關聯，是新工程不是 adapter**——YOLO-pose「天生多人」在現架構下會被 `[0]` 截斷成單人。
- **F25** contract 已預留 `track_id` 欄位（`event_builder.py:47-49`；`interaction_contract.md:523` schema）→ 多人化**不需改 contract schema**，只需 node 工程。
- **F26** **wave 可脫離手部模型**：`WaveDetector` 只吃 wrist 像素軌跡（`dynamic_gesture_detector.py:56-61`；閾值 px-space、tuned for 640×480@~15Hz，`:40-51`），現餵 hand KP0（`vision_perception_node.py:390-398`）。YOLO-pose 的 COCO wrist(9/10) 可直接餵 → **wave 是唯一可被 YOLO-pose 接管的手勢**。
- **F27** **靜態手勢不可被 YOLO-pose 接管**：palm/fist/index/thumb/peace 來自 MediaPipe Gesture Recognizer 內建分類（`gesture_recognizer_backend.py:1-50` `_GESTURE_MAP`），ok 來自 21 點幾何規則 `detect_ok_circle`（`vision_perception_node.py:404-415`）——全部依賴 21 點手部 keypoint，COCO 17 的 wrist 一點救不了。gesture enum v2.0 凍結（`.claude/rules/vision-perception.md`）。
- **F28** demo 主線實際組合 = `pose_backend:=mediapipe gesture_backend:=recognizer`（`scripts/start_full_demo_tmux.sh:165`）；yaml 預設仍是 rtmpose footgun（`vision_perception/config/vision_perception.yaml:22-23`；CLAUDE.md 6/4 HITL「WaveDetector config default=rtmpose 是 footgun」節）。**新增 backend 值必須同步 demo 腳本 + yaml，否則複製同款 footgun**。
- **F29** 現有 backend 互斥規則要擴：`pose_backend=mediapipe + gesture_backend=rtmpose` 被明文禁止（`vision_perception_node.py:168-172` raise ValueError）——新增 `yolopose` 值要補組合矩陣，避免無效組合 silent 跑。

### D. Jetson 效能 / RAM / GPU 預算（Q5 外推，假設標明）

- **F30** **純推理外推**（假設：① compute-linear 按 GFLOPs 縮放官方 detect n 錨點 4.57ms@5.4 GFLOPs；② T4 比例 pose/detect = 1.8/1.7 ≈ 1.06x；錨點為 Orin Nano **Super MAXN**）：**YOLO26n-pose@640 TRT FP16 ≈ 4.8-6.3ms，取區間 5-8ms**。若 Jetson 實際在舊 15W 檔，×1.4-1.7（sibling 報告 F22 nvpmodel 未驗證警告）。（錨點：https://docs.ultralytics.com/guides/nvidia-jetson/；`docs/perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md` F14/F22/F25）
- **F31** **node 內實際延遲 ≈ 3.5x 純推理**（Python/ORT 包裝開銷錨點：ultralytics issue #22479，YOLO11n Orin Nano Super 實測 16ms vs 官方 4.53ms）→ YOLO-pose node 內單幀 **15-25ms 預期 → 10-15Hz 迴圈可行**，不低於 MediaPipe 現役（L1 實測 13.5 FPS，見 F36）。（https://github.com/ultralytics/ultralytics/issues/22479；sibling F21）
- **F32** **GPU 占空比預估**：pose@10Hz × 5-8ms ≈ 5-8% engine 佔用 + object n@8Hz × 5-16ms ≈ 4-13% → **合計 <25%，遠低於 RTMPose 的 90% 前科**（`docs/pawai-brain/perception/pose/research/2026-03-21-benchmark-decision.md:33-35` GPU 85-90%）。但 **Whisper CUDA on-demand burst 的互動必須重測**——3/21 L2 錨點：rtmpose_lw + whisper_small 同跑 = -20% FPS（`2026-03-21-benchmark-decision.md:42`；archive `benchmarks/results/archive/pose_estimation/20260321/raw.jsonl` run aaa5e2cd）。
- **F33** **RAM 估算**（假設：社區 YOLO TRT context 全包 200-400MB；FP16 engine 本體 ~10MB 級）：**獨立 pose node = 新 CUDA context + ORT session ≈ +200-400MB**；**併進 object_perception 同 process 開第二 session ≈ +50-150MB**（共享 CUDA context）。0.8GB 紀律紙面可過但 full demo 13-window 邊際需 `tegrastats` 實測。（sibling F27 同方法）
- **F34** **現燒 engine 的 1GB workspace 風險同樣適用**：ORT TRT EP `trt_max_workspace_size` 預設 1GB，demo stack 同跑時現燒 = OOM 風險 → pose engine 必須沿用「前一晚預燒」SOP，TRT cache 按 model stem 分目錄機制已就位（`object_perception/object_perception/object_perception_node.py:271-274`）。（https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html；sibling F28）
- **F35** **TRT EP 整合 pattern 是現成的**：object node 的 `_init_onnx`（provider 參數 `"True"` 字串、engine cache、letterbox、`(1,300,6)` parse，`object_perception_node.py:266-303, 322-343`）可直接複製到 pose adapter，已知坑全部文件化（`docs/pawai-brain/perception/object/CLAUDE.md` 坑 #1/#6/#9）。
- **F36** **3/21 基線數字考古（兩個口徑）**：MediaPipe Pose **L1 單模實測 13.5 FPS**（`benchmarks/results/archive/pose_estimation/20260321/raw.jsonl` run e805b496：fps_mean 13.5、latency 76.7ms、GPU 0%、5.3W）；**18.5 FPS 是 3/21 晚「全 MediaPipe 三模同跑 30s」壓測口徑**（`2026-03-21-benchmark-decision.md:50-53`）。CLAUDE.md 選型表引用的 18.5 是共存口徑——對比 YOLO-pose 時要聲明口徑，否則基線虛高/虛低 37%。
- **F37** **3/21 決策沒有封死 YOLO-pose**：排除清單明列「YOLO11n-pose｜待測 P2」（`2026-03-21-benchmark-decision.md:25`）——當年是 deferred 不是 rejected。測 YOLO26-pose 與 3/21 決策**一致而非矛盾**；但 MediaPipe 勝出理由「CPU 0% + 效果等價 RTMPose」（`:60`）意味挑戰者必須拿出「多人 or 精度」的硬增益才有正當性。
- **F38** **L3「GPU 0%」基石被任何 YOLO-pose 路線正式推翻**：L3 三感知壓測 = face(CPU)+pose(CPU)+gesture(CPU) 60s → RAM 1.2GB、52°C、GPU 0%（CLAUDE.md「L3 三感知壓測（3/23）」行；`scripts/start_stress_test_tmux.sh`）。整併後的等價重測 = **face(CPU) + recognizer(CPU) + YOLO-pose(GPU) + object(GPU) + Whisper CUDA burst** 同跑 ≥60s，量 RAM/temp/GPU util/各 lane Hz——重測項清單見 Q8。

### E. 手勢三路線終裁材料（Q6/Q7）

- **F39** **Ultralytics 官方無 hand keypoint 預訓練模型**：pretrained pose 模型「include 1 pre-trained class, person」（COCO-pose 17 kpt）；hand-keypoints 是**讓你自己訓**的 dataset + 教學，官方 blog 同樣只給 train 流程。（https://docs.ultralytics.com/tasks/pose/；https://docs.ultralytics.com/datasets/pose/hand-keypoints/；https://www.ultralytics.com/blog/enhancing-hand-keypoints-estimation-with-ultralytics-yolo11）
- **F40** **hand-keypoints dataset 的兩個致命屬性**：① 「Annotations were generated using the Google MediaPipe library」——**任何在其上訓練的 YOLO hand 模型，品質天花板 ≈ MediaPipe Hands 本身（蒸餾物）**；② license = **CC BY-NC-SA 4.0（非商用）**，26,768 張、21 kpt、18,776/7,992 split。（https://docs.ultralytics.com/datasets/pose/hand-keypoints/ 原文）
- **F41** 社區最佳品 A：`marceloeatworld/yolo26-training`——yolo26**s**-pose 訓 21 kpt 手部，pose mAP50 0.942 / mAP50-95 0.843，ONNX FP16 可下載；但 **6 stars、訓練資料就是 F40 的 NC dataset、base weights AGPL-3.0、s 級 23.9 GFLOPs**（拿 GPU 重砲複製 CPU 現任）。（https://github.com/marceloeatworld/yolo26-training）
- **F42** 社區最佳品 B：`chrismuntean/YOLO11n-pose-hands`——90 stars、`best.pt` 可下載、**無公開 mAP**、自承「struggles to accurately detect keypoints for gestures like pinching and swiping」。（https://github.com/chrismuntean/YOLO11n-pose-hands）
- **F43** **手勢三路線終裁**：(a) 官方 hand-kpt 模型：**不存在**（F39）；(b) 社區 hand-kpt YOLO：**蒸餾天花板 + NC/AGPL 授權鏈 + GPU 成本，全面劣於現任**（F40-F42）；(c) **維持 MediaPipe + 防翻動後處理 = 唯一合理線**——PINTO 報告已給配方：SORT per-hand 追蹤 + `bbalg` 雙窗投票（零模型成本）、427_RTMPose_Hand 掛「零成本實驗失敗且遠距是主因」觸發條件、WHC/PGC 為條件式 verifier（`docs/perception/research/2026-06-11-pinto-model-zoo-pawai-fit-report.md:106, 137-140`）。本研究確認 (b) 不構成推翻 (c) 的證據。
- **F44** gesture 誤觸的既有防線已在 6/9 上線：`gesture_min_votes` 投票門檻 + `gesture_stable_s` 0.5s 穩定 gate（`vision_perception_node.py:105-114, 494-519`）——bbalg 配方是在這之上的增量，不是從零開始。

### F. sitting 三訊號源與整併算盤（Q8/Q9）

- **F45** **classify_pose 是 backend 無關純函數**（`pose_classifier.py:89-96` 簽名：純 numpy in/out，無 ROS2 無模型依賴）→ **離線 A/B 的邊際成本趨近零**：同一段 demo 錄影幀，MediaPipe 與 YOLO26n-pose 各產 17 kpt，餵同一套規則，逐幀比 sitting/standing 判定與 kpt visibility。這是本研究 verdict 的支點。
- **F46** **478_SC 的正交性論證**：SC 是外觀式分類（32×24 整身 crop、115KB、CPU 0.124ms），「與 landmark 幾何規則正交——建議 ensemble」（`2026-06-11-pinto-model-zoo-pawai-fit-report.md:90-95`）。**YOLO-pose 與 MediaPipe 同屬 landmark 幾何家族、互不正交** → 三選二的正解 = **一條幾何 + SC**，幾何內戰（MediaPipe vs YOLO-pose）由離線 clips 裁定，不要三線同開。
- **F47** **YOLO-pose 附贈的 person bbox 是 SC 的天然前級**：PINTO 報告本就列「YOLO26n person bbox (class 0)」為 SC 前級選項（`:93`）；若幾何線換成 YOLO-pose，SC 前級從「kps 推 bbox」升級為原生偵測 bbox，多人場景下每人一份 crop 尤其乾淨。**SC 與 YOLO-pose 是互補不是競爭**。
- **F48** **greet gate 的依賴鏈**：VIS-4 改版後 greet = known face stable + 3s 內 pose=sitting + cooldown（CLAUDE.md VIS-4 節；param `greet_sitting_window_s` 預設 3s）——sitting 事件是 `/event/pose_detected` 的 two_class 投票產物（20 幀 buffer，`vision_perception_node.py:139`）。**任何 pose 換線都直接動到 demo 主敘事的硬依賴**，這是「先離線、後上機」紀律的另一個理由。
- **F49** **「一顆換兩顆」精算結果**：可換 = pose 一顆（MediaPipe Pose CPU ~74ms/幀，F36）+ wave 動態偵測（F26）；不可換 = 靜態手勢全部（F27）。換完的帳：**省 CPU 一顆（MediaPipe Pose ~5.3W 口徑的 CPU 負載）、收 GPU +5-8% 佔空比 + RAM +50-400MB（架構依賴）+ 多人能力（需 node 工程才兌現）+ person bbox 副產品；付出 = GPU-0% 基石作廢 + L3 重測 + score 門檻重校**。淨值是否為正，完全取決於 sitting 品質增益——又回到離線 clips。
- **F50** goal context 引註漂移一處：goal :40 稱「COCO 模型對躺姿的通病——PINTO 報告 137 條目已提」，但 PINTO 報告 137 行（`:104`）只談 TFLite/TRT 路徑與對照組設計，**未提躺姿通病**。該主張實際支持來自外部證據（F9/F20）。主張本身成立，引註來源標錯——已在 §4 標注。

---

## §2 Q1-Q10 逐題回答

### Q1：YOLO26-pose 有哪些變體？n 的 GFLOPs/mAP-pose？輸出 shape？

五尺度 n/s/m/l/x 全發布（F1）。**n = 57.2 mAP-pose 50-95(e2e) / 2.9M / 7.5 GFLOPs；s = 63.0 / 10.4M / 23.9 GFLOPs**（F2；https://docs.ultralytics.com/tasks/pose/）。Python API 輸出 `(N,17,2)` xy + conf（F5）；ONNX e2e 推定 **`(1,300,57)`**（`6 + 17×3`；F6，社區 21-kpt 例 `[1,300,69]` 佐證，官方未明文 → WSL export 時驗 shape 列為必做）。

### Q2：多人輸出上限與形態？（對齊 (1,300,6) 哲學還是另一種）

**同一哲學**：one-to-one head、max_det=300、每列 `[x1,y1,x2,y2,conf,class]` 後附 17×3 kpt（F6）；單次 forward 出 N 人，無 grouping 後處理（F7）。parse 模式與 object lane 現役 `(1,300,6)` 同款，object node 的 parse/letterbox/rescale 代碼可直接複用（F35）。**注意**：模型多人 ≠ 系統多人——現役 node 單人架構會把多人截斷（F24），contract 的 track_id 已預留但 node 工程未做（F25）。

### Q3：現役 sitting/fallen 規則用到哪些 MediaPipe kpt？17 kpt 缺哪些？每條規則的改寫難度？

完整 file:line 清單見 F15。結論：**用到的 kpt = COCO 5-16（肩肘腕髖膝踝）+ nose（僅視覺化），17 kpt 缺 0 個**；MediaPipe 33 點專屬的 heel/foot_index 無任何規則使用（F14）；classifier 輸入本來就是 COCO 17（F11-F12）。**公式層改寫難度全部為 0**。非零成本在三處：score 語意門檻重校（F17）、avg_score 眼耳偏移補償（F18）、低 conf kpt 歸零慣例（F19）——全是 adapter 層工作，一個檔案內解決。

### Q4：MediaPipe 的 z 軸在現役規則裡是裝飾還是 load-bearing？

**裝飾，且連裝飾都不算——z 從未離開 wrapper**：`mediapipe_pose.py:78` 只取 `lm.x * w, lm.y * h`，classifier 收到的是 `(17,2)` 2D 像素座標（F16）。所有「3D」判斷（trunk_angle、vertical_ratio）都是 2D 投影幾何。換 17 kpt 模型**零 z 軸損失**。

### Q5：YOLO26n-pose 在 Orin Nano TRT FP16 的 FPS/RAM 估算？與 object n@640 同跑的 GPU 預算？

**純推理 ≈ 5-8ms**（外推：官方 detect n 4.57ms@Super-MAXN 錨點 × GFLOPs 比 1.39 / T4 比 1.06，F30）；**node 內 ≈ 15-25ms（10-15Hz）**（3.5x Python/ORT 開銷錨點 issue #22479，F31）；若 nvpmodel 非 Super 檔全數 ×1.4-1.7（F30）。**RAM：獨立 node +200-400MB / 併進 object process +50-150MB**（F33，假設標明）。**與 object 同跑 GPU 預算：合計佔空比 <25%**（pose 10Hz×5-8ms + object 8Hz×5-16ms，F32），數量級安全——真正要實測的是 Whisper CUDA burst 三方互動（3/21 L2 錨點 -20%，F32）與 full-demo RAM 邊際（F33/F34）。

### Q6：Ultralytics 官方有沒有 hand keypoint 模型？

**沒有**。官方 pretrained pose 只有 COCO person 17 kpt 一類；hand-keypoints 是 dataset（26,768 張、21 kpt、**MediaPipe 標註**、**CC BY-NC-SA 4.0**）+「自己訓」教學，無官方權重（F39-F40；https://docs.ultralytics.com/datasets/pose/hand-keypoints/）。

### Q7：社區 hand-kpt YOLO 的最佳品？訓練資料/精度/license 可靠嗎？

最佳兩件：`marceloeatworld/yolo26-training`（yolo26s-pose、mAP50-95 0.843、ONNX 可下載，但 6 stars + NC dataset + AGPL base + 23.9 GFLOPs，F41）與 `chrismuntean/YOLO11n-pose-hands`（90 stars、無公開 mAP、自承 pinch/swipe 不穩，F42）。**不可靠的三重理由**：訓練資料是 MediaPipe 蒸餾（品質天花板=現任）、授權鏈 NC/AGPL（與 LVFace 同級的候選池紅旗）、用 GPU 換 CPU 現任已有的東西（F43）。**終裁：手勢 YOLO 路線出局，維持 MediaPipe + bbalg 防翻動（零成本）+ 條件式 WHC/PGC**——與 PINTO 報告 §5b 完全一致，無矛盾。

### Q8：「一顆換兩顆」整併後，L3 三感知壓測的等價物變成什麼？

先修正前提：**整併上限是「一顆換一顆半」**（pose + wave；靜態手勢換不掉，F26-F27/F49）。等價重測組合 = **face YuNet(CPU) + Gesture Recognizer(CPU) + YOLO26n-pose(GPU) + YOLO26n object(GPU) [+ Whisper CUDA burst]**，必測項：① 同跑 ≥60s 的 RAM/temp/GPU util（對照舊 L3 的 1.2GB/52°C/0%，F38）；② 各 lane Hz（pose ≥ 與 MediaPipe 同口徑基線，注意 13.5 vs 18.5 口徑差異，F36）；③ Whisper warmup + 推理 burst 時的 pose/object 掉幀（3/21 L2 -20% 錨點，F32）；④ full demo 13-window 的 0.8GB 餘量（F33）；⑤ engine 預燒 SOP（F34）。

### Q9：與 478_SC ensemble 的組合建議：三條 sitting 訊號源選哪兩條？

**「一條幾何 + SC」，幾何內戰離線裁**（F46）。論證：SC（外觀）對幾何正交，是 ensemble 增益的來源；MediaPipe 與 YOLO-pose 同為 landmark 幾何，雙開是冗餘不是 ensemble。組合空間裁定：
- **預設（零風險）**：MediaPipe(幾何) + SC(外觀)——demo 主線不動、GPU 0% 保留、SC 前級用 kps 推 bbox。
- **挑戰版（離線勝出才升級）**：YOLO-pose(幾何+原生 bbox) + SC(外觀)——SC 前級更乾淨、多人就緒（F47），代價是 F49 的整套帳。
- **不做**：MediaPipe + YOLO-pose 雙幾何、或三線全開（goal :41 明令避免）。
離線 clips 實驗一次餵三方（MediaPipe/YOLO-pose 同餵 classify_pose + SC 跑同批 person crop），一個下午同時回答幾何內戰與 SC domain 疑慮（PINTO 報告 `:94` 的 Go2 視角 out-of-domain 警告）。

### Q10：上機要不要排 YOLO26-pose？排的話 pass/fail 門檻？

**本輪不排**（verdict NEEDS_TEST_HITL_CLIPS）。理由：① 唯一決策性未知（Go2 視角 sitting 品質增益）離線免費可測（F45），FPS/RAM 紙面已夾窄、非瓶頸（F30-F33）；② 下次上機日已被 object scale-up 矩陣佔用（sibling 報告 §5），pose 搶位會稀釋兩邊；③ greet gate 硬依賴 sitting（F48），demo 主線換線必須有數字背書。
**晉級上機的 gate（離線階段判）**：在 ≥2 段含 sitting 的 demo 錄影上，YOLO26n-pose 17 kpt 餵同規則的 **sitting 判定正確率 ≥ MediaPipe 基線 +10pp**，或 MediaPipe 漏偵幀（全零輸出）中 YOLO-pose 可救回 ≥30%。
**晉級後的上機配置與門檻**（屆時直接可用）：yolo26n-pose@640 TRT FP16（WSL export，e2e 預設），門檻 = ① node 內 pose 迴圈 ≥8Hz；② full-stack RAM 餘量 ≥0.8GB；③ object lane Hz 不退化（≥6Hz）；④ GPU util 增量 ≤30pp；⑤ 同場 HITL sitting 正確率 ≥ MediaPipe；⑥ 雙人入鏡時 per-person kpt 輸出正常（多人僅驗輸出、不驗 node 事件——node 多人化另案）。

---

## §3 整併算盤總表（Required investigation 核心）

| 項目 | MediaPipe 現任 | YOLO26n-pose 挑戰者 | 證據 |
|------|------|------|------|
| kpt 格式 | 33→17 壓縮（13/17 有效） | 原生 COCO 17 全有效 | F11-F12 |
| 規則改寫 | — | **0（公式層）**；adapter 層三項校準 | F15, F17-F19 |
| 單人 FPS | 13.5（L1）/18.5（共存口徑） | 估 10-15Hz node 內 | F36, F31 |
| CPU/GPU | CPU ~74ms/幀、GPU 0% | CPU ≈0、GPU +5-8% 佔空比 | F36, F32 |
| RAM | 已付 | +50-150MB（併 process）~ +200-400MB（獨立 node） | F33 |
| 多人 | 否（num_poses=1 用法） | 模型原生支援；**node 工程未做** | F7, F24 |
| person bbox | 無（kps 推） | 原生（SC 前級升級） | F47 |
| wave | hand KP0 | body wrist 可接管 | F26 |
| 靜態手勢 | Recognizer（不可替代） | **無能力** | F27 |
| fallen | 已知 viewpoint hallucination | COCO 躺姿通病，未必更好 | F20 |
| L3 基石 | GPU 0% 成立 | **作廢，需重測**（Q8 清單） | F38 |

---

## §4 與 cross-validate 文件的矛盾標注

1. **PINTO 報告（`2026-06-11-pinto-model-zoo-pawai-fit-report.md`）——無矛盾，一處互補修正**：§4.1/§5c 的 478_SC ensemble 結論本研究完全繼承（F46）；本研究新增的是「若幾何線換 YOLO-pose，SC 前級升級為原生 bbox」（F47），與其 `:93`「前級免費：YOLO26n person bbox」一致。本研究**不開第三條 sitting 線**——幾何內戰與 SC 驗證合併進同一個離線實驗，正面回答 goal :71 的衝突疑慮。
2. **goal 文件引註漂移一處**：goal :40「COCO 躺姿通病——PINTO 報告 137 條目已提」——PINTO 報告 137 行（`:104`）實際未提躺姿；主張本身由外部證據成立（F9/F20/F50）。
3. **3/21 benchmark 決策表（`2026-03-21-benchmark-decision.md`）——無矛盾**：YOLO 系 pose 當年是「YOLO11n-pose 待測 P2」（`:25`），deferred 非 rejected（F37）。但需澄清數字口徑：選型表的「18.5 FPS」是三模共存壓測口徑，L1 單模是 13.5（F36，archive raw.jsonl 為準）——未來 A/B 基線要聲明口徑。
4. **L3 三感知壓測（CLAUDE.md）——明示推翻條件**：任何 YOLO-pose 上線 = GPU 0% 基石作廢，等價重測清單已列（Q8）。本研究 verdict 把這筆成本押後到「離線數字證明值得」之後才支付。
5. **sibling 報告（`2026-06-11-yolo26-scaleup-highres-seg-result.md`）——無矛盾，共用錨點**：F14/F21/F22/F27/F28 的 Jetson 錨點與假設體系直接沿用（本報告 F30-F34）；上機日排程以其矩陣 A-D 優先，pose 不搶位（Q10）。
6. **goal context 一處能力描述 vs 使用事實**：goal :15「MediaPipe…33 kpt 含 z」——z 在 PawAI 從未被使用（F16），「失去 z」不構成換線成本。

---

## §5 Verdict：**NEEDS_TEST_HITL_CLIPS**

四選項裁決理由：
- ~~GO_BENCH_YOLOPOSE~~：FPS/RAM 不是未知數（F30-F33 已夾窄），上機名額被 object 矩陣佔用；在 sitting 品質增益未證實前花上機時段 = 用最貴的資源回答最便宜的問題。
- ~~GO_CONSOLIDATE_TEST~~：整併論的前提「一顆換兩顆」被 F27/F43 砍半——手勢換不掉，剩「一顆換一顆 + bbox 副產品」，不足以撐起以整併為主軸的上機實驗。
- ~~NO_GO_KEEP_MEDIAPIPE~~：言之過早——結構性移植成本被證實為 ~0（F11-F16），多人 + 原生 bbox + SC 協同是真實潛在收益（F47），直接判死會浪費一個幾乎免費的驗證機會。
- **NEEDS_TEST_HITL_CLIPS ✅**：紙面已裁定「17 kpt 可行、改寫成本 ~0、手勢路線死」；唯一裁不了的是 **Go2 視角下 YOLO26n-pose landmark 品質對 sitting 判定的實際增益**——而 `classify_pose` 的 backend 無關性（F45）讓這件事可以用 demo 錄影在 WSL 零硬體成本裁定。

### 對應 verdict 的下一步（一個，具體）

**立一張 ready-for-agent issue（建議標題：`spike: WSL offline 3-way sitting A/B — yolo26n-pose vs mediapipe vs 478_SC on demo clips`），內容如下，一個下午完成：**

0. **素材確認**（step 0，blocker check）：確認 6/9-6/10 demo 錄影（尤其 S2 認人坐姿段）可抽幀為影像序列；不可用則改用 `capture_baseline_round.py` 流程在下次上機日順手錄 sitting/standing clips（不佔矩陣時段）。
1. WSL venv：`uv venv && uv pip install ultralytics onnxruntime mediapipe`（ultralytics 禁令只限 Jetson）；export `yolo26n-pose.pt → onnx`（e2e 預設、imgsz=640），**驗證輸出 shape 是否 `(1,300,57)`**（F6 的未明文項）。
2. 對每段 clip 逐幀跑三方：(a) MediaPipe Pose（現役 wrapper 同款 33→17）；(b) YOLO26n-pose ONNX（adapter：conf<門檻 kpt 歸零 + min_score sweep 0.1-0.3，F17-F19）；(c) 478_SC（person crop 來源 = YOLO-pose bbox）。
3. 三方全部餵 `classify_pose`（two_class 模式同 demo 參數：`sitting_trunk_max_deg=45`）/ SC 直接出二元，產出逐幀對照表：sitting 正確率（人工標 ground truth）、漏偵幀數、分歧幀分佈。
4. 判 gate：YOLO-pose sitting 正確率 ≥ MediaPipe +10pp 或救回 ≥30% 漏偵幀 → 按 Q10 配置排入下下次上機；未達 → 幾何線維持 MediaPipe，sitting 增強全押 SC ensemble（PINTO 線），YOLO-pose 歸檔為「guardian 多人立項時重啟」。

---

## 附錄：來源清單

**官方文件**：
- https://docs.ultralytics.com/models/yolo26/ （task 變體全表、NMS-free、(N,300,6)）
- https://docs.ultralytics.com/tasks/pose/ （pose 變體 mAP/params/GFLOPs、COCO 17 kpt 格式、pretrained=person only）
- https://docs.ultralytics.com/guides/nvidia-jetson/ （Orin Nano Super detect n 錨點 4.57ms；無 pose 數字）
- https://docs.ultralytics.com/modes/export/ （max_det=300 與輸出 shape 關係）
- https://docs.ultralytics.com/datasets/pose/hand-keypoints/ （26,768 張、21 kpt、MediaPipe 標註、CC BY-NC-SA 4.0、無官方權重）
- https://www.ultralytics.com/blog/enhancing-hand-keypoints-estimation-with-ultralytics-yolo11 （官方 hand 路線=自己訓）
- https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker （33 個 3D landmarks、num_poses 參數）
- https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html （1GB workspace）

**社區 / 論文 / issue**：
- https://learnopencv.com/yolo26-pose-estimation-tutorial/ （RLE head、多人單次 forward、T4 延遲表、limitations）
- https://github.com/marceloeatworld/yolo26-training （yolo26s-pose 21 kpt 手部、mAP、ONNX、`[1,300,69]` 輸出例）
- https://github.com/chrismuntean/YOLO11n-pose-hands （YOLO11n-pose hand、pinch/swipe 弱點自承）
- https://github.com/GajuuzZ/Human-Falling-Detect-Tracks （rotation-augmented COCO 重訓才能穩定偵測水平人體）
- https://github.com/ultralytics/ultralytics/issues/22479 （官方 vs Python 實測 3.5x 差距錨點）

**本地 code / 文件**：
- `vision_perception/vision_perception/pose_classifier.py`（:5,119 COCO 17 輸入；:34-39 索引；:161-206 fallen；:209 standing；:230-240 sitting；:280-321 akimbo；:352-411 kneel；:43-53 two_class）
- `vision_perception/vision_perception/mediapipe_pose.py`（:17-32 33→17 映射、13/17 點；:78-79 z 丟棄、visibility 作 score）
- `vision_perception/vision_perception/vision_perception_node.py`（:66-77 bbox_ratio 零點慣例；:108-114 6/9 params；:139 單人 buffer；:164-226 backend 分支；:312-315 投票；:390-398 wave 餵點；:494-519 stable gate）
- `vision_perception/vision_perception/rtmpose_inference.py`（:20,93-116 InferenceAdapter 介面與單人截斷）
- `vision_perception/vision_perception/dynamic_gesture_detector.py`（:40-61 WaveDetector 介面與閾值）
- `vision_perception/vision_perception/gesture_recognizer_backend.py`（:1-50 靜態手勢來源）
- `vision_perception/vision_perception/event_builder.py`（:38-55 pose event、track_id 預留）
- `vision_perception/config/vision_perception.yaml`（:22-23 backend 預設 footgun）
- `scripts/start_full_demo_tmux.sh`（:165 demo 主線 backend 組合）
- `object_perception/object_perception/object_perception_node.py`（:266-303 TRT EP pattern、:271-274 cache per stem）
- `benchmarks/results/archive/pose_estimation/20260321/raw.jsonl`（MediaPipe L1 13.5 FPS、rtmpose L1/L2 全數據）
- `docs/pawai-brain/perception/pose/research/2026-03-21-benchmark-decision.md`（:25 YOLO11n-pose P2；:33-42 L1/L2 表；:50-60 18.5 口徑與決策）
- `docs/contracts/interaction_contract.md`（:511-523 pose event schema 含 track_id）
- `docs/perception/research/2026-06-11-pinto-model-zoo-pawai-fit-report.md`（:90-95 478_SC；:104 137 行；:137-143 §5b/§5c）
- `docs/perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md`（F14/F21/F22/F27/F28 Jetson 錨點體系；§5 上機矩陣排程）
- `CLAUDE.md`（L3 三感知壓測、VIS-4 greet gate、6/4 gesture footgun 節）
