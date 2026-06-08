# PawAI 夜間研究養分 — 2026-06-08（給 6/18 demo 準備）

> 5 份 read-only 研究的決策摘要。所有 file:line 已對核心邏輯抽查驗證（greet gate `brain_node.py:1093-1110`、sitting 硬依賴、whitelist `_parse_whitelist` `object_perception_node.py:138-146`）。

---

## 1. 一頁總結

| 主題 | 一句最重要結論 |
|------|----------------|
| Object runtime 切換（VIS-2） | `ros2 param set /object_perception_node class_whitelist` 下一幀（~67ms）生效、零重啟，已有 callback + tests（commit `104b481`）；風險是切全 80 類 false positive 暴增。 |
| VIS-3 物體矩陣 | **chair（56）最穩**（大、形狀規則、無色彩依賴）→ 主物體；laptop（63）+ cup（41，已 baseline pass 0.83+）備援；bottle/bowl/book/cell_phone 不建議上台（平放/小物/光線敏感）。 |
| VIS-8 效能瓶頸 | 最大嫌犯是 **Studio video bridge 的 JPEG encode + WS**（H1），不是 GPU 競爭（感知全 CPU）；RAM 預警線 5.5GB，e2e 估 ~310-345ms，量測協議與降載順序已備好。 |
| Pose/Gesture demo-safe | **gesture 必帶 `gesture_backend:=recognizer`**（yaml 預設 rtmpose 是 wave footgun）；sitting 投票 20 幀無 hysteresis、無 trusted baseline，是最大的不確定。 |
| Greet 設計 | 採 **event-only**（unknown→known + sitting window 3s + 20s cooldown）；最大風險是 **sitting 硬依賴**（`greet_require_sitting=True`）+ **face_db sim 新鮮度老化**（Roy 舊圖 0.2 → re-enroll 0.73-0.81）。 |

### 明天最該先做的 3 件事
1. **Re-enroll Roy 的 face_db + retrain**（今晚就做，趁家裡光線固定）→ 保 6/18 baseline sim ≥ 0.7。這是 greet 整條路徑的單點故障，且 sitting 硬依賴疊在它上面。SOP 見 §6。
2. **量 sitting 可靠度**（站/坐/站各 10-20 組，看 `pose_vote_confidence`）→ 決定 `greet_require_sitting` 留 True 還是降 False。沒這個數據就不能宣稱 sitting pass，也不能保證 greet 會觸發。見 §5。
3. **跑 VIS-3 物體矩陣的 chair/laptop/cup 三主備**（先做這 3 類 × 3 距離 × 2 光線，不必先做全 7 類）→ 鎖定主物體 + 備援切換規則。見 §3。

---

## 2. Object runtime 切換（VIS-2）

### 機制
- `_parse_whitelist(raw)`（`object_perception_node.py:138-146`）：保留 id 0..79，過濾範圍外（含 -1 sentinel / 999），**結果空 set → 回退全 80 類**。set 自動去重。
- `class_whitelist` param default `[-1]`（`:166-173`，INTEGER_ARRAY descriptor）— 這是為了繞過 Humble 對 empty `[]` 推成 BYTE_ARRAY 撞 yaml `[39]` override 的 bug。
- runtime callback（`:247-258`）訂閱 param 變更 → 重算 `self.allowed_classes`；detect 迴圈（`:343-378`，line 377 `if class_id not in self.allowed_classes: continue`）下一 tick（`tick_period=0.067s`）即套用。

### 邊界（已測，`test_object_perception.py`）
| 輸入 | 結果 |
|------|------|
| `[39,41,45,56,63,67,73]` | 家用 7 類 |
| `[]` 或 `[-1]` | 全 80（等價）|
| `[99,100,-5]`（全無效） | 回退全 80 |
| `[39,999,41]`（混合） | `{39,41}` |
| `[41,56,56]`（重複） | 去重 |

### 可貼的 3 段切換指令（demo pane）
```bash
# 椅子專項（展示 filtering 效果）
ros2 param set /object_perception_node class_whitelist '[56]'
# 家用 7 類（情境一致，預設）
ros2 param set /object_perception_node class_whitelist '[39,41,45,56,63,67,73]'
# 全 COCO 80（教學用，警告 false positive↑）
ros2 param set /object_perception_node class_whitelist '[]'
```

### 風險
- **【HIGH】全 80 類 false positive 暴增**：室內 COCO 物體眾多（potted_plant/vase/clock…），養老院場景不該長跑。demo 演完即切回 7 類。
- **【MED】conf_thresh=0.35 是針對 7 類調的**，全 80 類同門檻偏鬆。留 A/B：7類@0.35 vs 80類@0.50。
- **【MED】`ros2 param set` 必須在 demo tmux 內下**（同 DDS domain）；另開 SSH terminal 要先 `source install/setup.zsh` + 確認 `ROS_DOMAIN_ID` 一致，否則找不到 node。
- **【LOW】5s per-class cooldown** 會讓動態物體看不到即時反應；demo 時口頭解釋「避免 spam」。
- **【LOW】Studio 前端硬編 6 類、YAML 7 類不同步**（`object-config.ts`）；gateway 無 HTTP endpoint 暴露 set_parameters，現場只能 tmux 手動切。

---

## 3. VIS-3 物體矩陣

### 預測最穩 + 建議選擇
- **主物體：chair（56）** — 面積大（~300×200px@1m）、form factor 規則、無色彩依賴、距離耐受最好。
- **備援 1：laptop（63）** — 矩形 + 鏡面反光 + 金屬邊框幾何特徵強。
- **備援 2：cup（41）** — 已 baseline 驗證 @1m conf 0.834-0.88、5/5 pass、0 idle false trigger（`baseline_result.jsonl:21-25`），但需正對、距離 ≤1.5m。
- **不建議上台**：bottle（39，4/6 測試失敗、細長易被過濾）、bowl（45，曲面角度敏感）、book（73，平放無 3D 特徵）、cell_phone（67，平面 + 低光極弱）。

### 完整測試矩陣（每格 n≥5，6/18 前 ≥72h 完成）
| 類別 (COCO id) | 0.7m | 1.0m | 1.5m | 正常光 ~500-800lux | 暗光 ~100-200lux | demo 角色 |
|---|---|---|---|---|---|---|
| chair (56) | ✓ | ✓ | ✓ | ✓ | ✓ | **主** |
| laptop (63) | ✓ | ✓ | ✓ | ✓ | ✓ | 備援1 |
| cup (41) | ✓ | ✓ | ✓ | ✓ | ✓ | 備援2 |
| bottle (39) | ✓ | ✓ | ✓ | ✓ | ✓ | 觀察 |
| bowl (45) | ✓ | ✓ | ✓ | ✓ | (略) | 觀察 |
| cell_phone (67) | ✓ | ✓ | ✓ | ✓ | (略) | 觀察 |
| book (73) | ✓ | ✓ | ✓ | ✓ | (略) | 觀察 |

每格記：detection_count / mean conf / std / bbox_w×h px / color + color_confidence / latency。空景 60s 驗 idle false trigger=0。
> 註：bbox 面積 ∝ 1/distance²；cup 杯口 @1m≈55px / @1.5m≈37px / @2m≈28px（YOLO anchor ≥20px 邊界差）→ demo 距離務必 ≤1.5m。

### 量測 protocol
1. 米尺從 D435 RGB 光軸量距，地貼 0.7/1.0/1.5m；物體中心與相機齊高，用 D435 depth 校驗 distance_m。
2. 手機 Light Meter / 照度計在物體位置量 lux。
3. 每格 5 筆間隔 3-5s（過 5s cooldown），讀 `/event/object_detected`（jq/rosbag）。
4. CSV 欄位：`timestamp,class_name,distance_m,lux,confidence,bbox_w_px,bbox_h_px,color,color_confidence,latency_ms,detection_count`。
5. 暗光只測 chair/laptop/cup 三距離各 3-5 筆即可。

### 備援切換規則
chair 失效（逆光/遮擋）→ 改 laptop；laptop 也失效 → 降 cup-only（`class_whitelist=[41]` + 話術改「看到桌上有物品」）。**所有切換 demo 前 1 小時由 Roy 決策，不臨場切。**

### 風險摘要
小物件 recall（nano mAP 40.9% 天花板）｜平放扁平物無解（話術補救）｜低光 HSV 色彩塌成 black（紅杯被播「黑色杯子」）｜Jetson 供電不穩（XL4015 掉電 → TRT 重編 3-10min）｜多物體 bbox overlap（擺物間距 ≥20cm）。

---

## 4. VIS-8 效能瓶頸

### 資料流圖
```
D435 RGB 640×480 @15Hz
   ├─→ YuNet face   (CPU 150-200ms) ─┐
   ├─→ MediaPipe Pose (CPU 50-80ms) ─┤→ 各發 8Hz event ─→ brain_node
   └─→ YOLO26n TRT  (CPU 30-50ms) ───┘
                                       └─→ debug_image ×3 ─→ Studio gateway
                                              FrameThrottle @5Hz
                                              JPEG encode q70 (20-40ms/src)
                                              WS broadcast ─→ frontend (10-frame buffer)
e2e 估計：~310ms（不含 render）/ ~345ms（含 render）
```
Idle baseline（13 window）：RAM 3.65/7.6GB(52%)、CPU 80% avg、GPU 0-74% bursty、58.7°C、10.2W。

### Per-stage 量測 protocol
| Stage | 指標 / 工具 | 期望 |
|---|---|---|
| 1 camera 15Hz | `ros2 topic hz /camera/.../image_raw` | 66.7ms |
| 2 face infer+pub | timestamp 比對 | 160-210ms |
| 3 vision | timestamp | 60-90ms |
| 4 object | timestamp | 40-60ms |
| 5 gateway JSON+WS | log timing | 5-45ms |
| 6 JPEG encode（若啟用） | `video_bridge.py:34-43` | 30-55ms |
| 7 frontend render | browser | 20-50ms |

輸出 CSV：`[face_latency, vision_latency, object_latency, gateway_json_latency, jpeg_encode_latency, end_to_end]`，10 輪取 mean+std。

### 瓶頸假說排序
| # | 假說 | 力度 |
|---|---|---|
| H1 | Studio video bridge JPEG encode + WS（3×60-120ms/tick @10Hz = 6-12% CPU） | **高** |
| H2 | GPU 競爭 — 當前已避免（全 CPU 推理） | 中（已緩解）|
| H3 | face YuNet 200ms 疊加 identity_stable 延遲 → 影響 greet timing | 中 |
| H4 | ROS2 JSON 反序列化 <1ms | 低 |
| H5 | D435 USB3（1.4Gbps vs 5Gbps bus） | 低 |

### 降載手段（優先序）
- **P0a 關 video bridge** — `studio_gateway.py:40 _VIDEO_AVAILABLE=False`（省 60-120ms + ~100MB）
- **P0b 降 camera fps 15→10Hz** — `start_full_demo_tmux.sh:144-145`
- **P0c 降 publish_fps 8→4Hz** — 各 launch `publish_fps:=4.0`
- **P1** YOLO 白名單 7→3 類 / 關 face compare_image / gesture 改 Recognizer
- **P2** 關 gesture/pose（有功能損失）
- 監控告警線：RAM >5.5GB(warn)、CPU >90%(warn)、GPU >80%(warn)、**TEMP >65°C(critical)**。加 Whisper CUDA(+1GB) → peak 5.35-5.85GB，逼近紅線。
> 改 code 後一律 `colcon build --packages-select <pkg>` + `source install/setup.zsh`。

---

## 5. Pose/Gesture demo-safe + **sitting 可靠度（greet 硬依賴）**

### sitting 為什麼是 demo 核心風險
- VIS-4（已驗證於 `brain_node.py:1088-1096`）把 greet gate 從「ENGAGED 距離+dwell」改為「known face stable + 最近 `greet_sitting_window_s=3s` 內坐過」，**`greet_require_sitting=True` 為預設 → sitting 成硬依賴**。
- 判定邏輯（`pose_classifier.py:194-211`）：y-geometry（hip≈knee y + ankle 明顯低於 hip）+ trunk_angle<35° + knee_angle<145°。**側向坐姿 y-geometry 會誤差**（已知問題）。
- 投票：`pose_buffer maxlen=20`（~1s@20Hz）多數決，**無 hysteresis**，standing→sitting 需 ~600ms 穩定。**本輪無 trusted baseline observer（insufficient_data）** → 6/18 不該宣稱 sitting pass。

### 怎麼讓 sitting 穩
1. **先量**：站/坐/站，看 `/event/pose_detected` 的 `pose_vote_confidence`（=投票/20）。坐 ≥18/20(~1.0)、站 ≤2/20(~0.0)；若卡 0.3-0.7 區間 >2s = jitter 誤判。誤判率 >5% 就降級。
2. **強化（有時間才做）**：決策層加 hysteresis（sitting→other 需 2 幀反面、other→sitting 需 3 幀），不動 vote buffer 本身。或 `pose_vote_frames:=30` 拉長窗口。

### gesture 最終 config（demo 啟動建議）
```
gesture_backend:=recognizer        # 強制！yaml 預設 rtmpose 會 disable WaveDetector → wave 永不觸發
thumbs_up_demo_ack:=True           # VIS-5：發 say_canned 輕量回應，不過 confirm、不觸發 wiggle
gesture_vote_frames:=10            # 5/27 demo mode（較嚴，~3-4s 反應）
gesture_stable_s:=1.5
pose_vote_frames:=20               # 保持（除非走強化方案）
greet_require_sitting:=True        # sitting 穩才留 True；否則 False
greet_sitting_window_s:=3.0
greet_cooldown_s:=20.0
enable_fallen:=False               # 5/8 demo silence
idle_enabled:=False
demo_video_cup_compound:=False     # 除非要複合句
```
> `start_full_demo_tmux.sh` 已內建 `gesture_backend:=recognizer` override；直接 `ros2 launch` 不帶 override 會中招。WaveDetector 預設 `min_amplitude_px=50 / min_reversals=2`，誤觸就調 amplitude→75 或 reversals→3，**不要動 vote_frames**（那是靜態手勢用）。

### Fallback
sitting 誤判頻繁 → `ros2 param set /brain_node greet_require_sitting false`（只看人臉 stable + cooldown），台詞改「我看到你了」（去掉「坐下來了」）。**6/18 現場若 greet 不觸發，先查 `last_sitting_seen_ts` 是否 <3s，再考慮降 False。**

---

## 6. Greet 設計後續

### event-only vs steady-state 取捨 → 建議維持 event-only
- 現況（`brain_node.py:1093-1110`，`face_identity_node.py:559-575`）：identity_stable 只在 **unknown→known 轉變**發（純 event-only，無 steady-state 路徑），符合「看到你進來」語義；20s per-person cooldown 防 spam（Roy 一直在框內不會重問，等 cd 過或 track 斷重進）。
- steady-state 補丁成本：在 `_on_face` 加「identity=known but not stable + 在 window + 不在 cooldown」約 5 行，但**增加 false positive**（網路抖動重連同一人重複問候），**不建議**。
- 明天驗證點：遮臉/低頭走開→抬頭回來，看是否觸發第二次。不想重複問候就保持現狀。

### Enrollment SOP（今晚先做）
```bash
python3 scripts/face_identity_enroll_cv.py --person-name=Roy --samples=30 --capture-interval=0.2
# 採樣 ~6s；監看 console「saved X/30」，saved <20 重採
# model_path 自動 retrain → log「Retrained and saved model」
```
拍攝條件：室內均勻光、逆光 0-30°、距 1.5m、無眼鏡/遮擋。re-enroll 時機：sim 連 3 天 <0.5，或新增眼鏡/髮型。**demo 前先 `cp -p model_sface.pkl model_sface.pkl.$(date +%s).bak`**。

### face_db 衛生
- **缺陷**：`train_model`（`face_identity_node.py:337-379`）遍歷 db_dir 所有子目錄當人名，`_backup/`、`.tmp/`、`old/` 會被當幽靈身份訓進 model.pkl，稀釋 Roy centroid → sim 掉/誤認。
- **demo 前**：`ls -la /home/jetson/face_db/` 確認只有真人；有殘留 `rm -rf .../_backup && rm .../model_sface.pkl` force retrain。
- **建議實裝**：`list_face_images`/`compute_db_counts` 前加 dirname 黑名單跳過 `.`/`..`/`_backup`/`.git`/`__pycache__`/`*.pkl`（open question，需 Roy 決策是否改 node code vs 外部 shell 清理）。

### cooldown 數值評估
| 參數 | 現值 | 評估 |
|---|---|---|
| `greet_cooldown_s` | 20s | 足夠（Roy「走開再回來」<3次/分）；dev 測試可臨時 3s |
| `greet_sitting_window_s` | 3s | 取自坐下動作捕捉延遲（pose lag 0.5-1s）+ 2s margin，合理；若 lag 大可 debug 拉到 5s |

---

## 7. 明天的 open questions（去重後）

### 需要 Roy 決策
- **greet 行為語義**：一直坐著、20s 後若 identity_stable 再觸發（重連），要「只在進場問候」還是「定期重問」？（影響是否補 steady-state）
- **face_db 黑名單實裝方式**：改 `face_identity_node.py` 加 `/^[._]` 過濾 vs 外部 shell 定期清理？
- **`greet_require_sitting` 留 True 還 False**：取決於明天 sitting 量測結果（>10% 誤判就降 False）。
- **Studio gateway 是否 6/18 前加 HTTP endpoint 暴露 class_whitelist 切換**？（目前現場只能 tmux 手動，非技術觀眾體驗差；優先級待定）
- **person(0) 為何排除白名單**：YOLO person 品質不如 face SFace，還是純避免雙層觸發？（影響 demo 話術）
- **YOLO26s 升級**：若 bottle/bowl 主線完全不過，6/18 前是否評估升級（mAP +7.7pp，FLOPs ×4，需 RAM 評估）？

### 需要實機驗證
- **sitting 投票 20 幀現場誤判率**（站/坐/站 10-20 組）— 是否需 hysteresis / 改 maxlen。
- **`last_sitting_seen_ts` 更新頻率**：若使用者抖動 <1s 一次，greet 會否觸發不到？
- **conf_thresh 7 類 vs 80 類最優值** A/B（小物件 cell_phone/remote 在 80 類 false positive）。
- **`ros2 param set` broadcasting latency <50ms?**（確保「下一幀生效」承諾，CycloneDDS 端到端）。
- **VIS-8 baseline 重測 + per-stage 10 輪 latency**（驗 H1 video bridge 成本、確認記憶體 <5GB）。
- **VIS-4 是否已 merge main + greet_sitting param 是否進 launch**（demo 要驗整條路徑已整合）。
- **暗光 lux 閾值**：是否存在某 lux（如 <150）使所有小物一致失效；白瓷杯反光是否反而暗光更易測。
- **identity_stable 欄位型態與設置時機**（`face_identity_node.py:199-210` String JSON → `brain_node.py:1021-1023` 檢查 path）。
- **wave WaveDetector `min_amplitude_px=50` 在 640×480 的 false positive 率**（需提前測定是否調參）。
- **demo_video_cup_compound timing**：cup 誤認 / sitting 抖動造成 3s 窗失效的頻率（要不要 e2e 測）。
- **GPU 0-74% bursty 來源**（object TRT 在 CPU 跑、GPU 應 0，尖峰來自哪個模組）。
- **fallen `enable_fallen=False` 時 Studio 仍顯示紅 alert chip** — 現場怎麼解釋 / 是否改 gateway 不顯示未啟用 alert。

(相關真相來源：`brain_node.py:1093-1110/1159`、`object_perception_node.py:138-146/247-258/343-378`、`object_perception.yaml:16-21`、`pose_classifier.py:194-211`、`vision_perception.yaml:22`、`face_identity_node.py:337-379/410-447/559-575`、`studio_gateway.py:40/239-248`、`video_bridge.py:34-43`、`start_full_demo_tmux.sh:144-145`、`baseline_result.jsonl:21-25`、`docs/mission/2026-06-18-demo-production-plan.md:57-76`、commit `104b481`)