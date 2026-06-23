# Research Result: 居家類別擴充 — open-vocabulary vs 更大 closed-set（COCO 80 不夠用）

> **日期**：2026-06-11
> **對應 goal**：[`goals/2026-06-11-open-vocab-indoor-classes-goal.md`](goals/2026-06-11-open-vocab-indoor-classes-goal.md)（multi-goal member 2/4）
> **Verdict**：**`NEEDS_TEST_VOCAB_REPLAY`**（機制面已證實可行且便宜；精度面 LVIS-rare AP ~21-23 的紙面證據不足以保證 22 個非 COCO 居家類在 D435 距離下可用，且藥瓶連 LVIS 都沒有——必須先 WSL 離線 replay 測 vocab 命中率再決定）
> **本研究為 read-only**：未改 code、未 commit、未安裝任何東西、硬體未動。

---

## TL;DR

1. **路線收斂**：open-vocab 這條路只剩一個候選 = **Ultralytics YOLOE-26（custom vocab set-then-export）**——它就是現役 YOLO26 的開放詞彙版（同架構、NMS-free e2e、export 後零 text-encoder 成本）。YOLO-World 被 YOLOE26 以 +10~11.4 AP 壓制；Grounding DINO 級 transformer 以 AGX Orin 實測 2-3 FPS 正式出局；「更大 closed-set」**在三組 WebSearch 範圍內未找到獨立供給**（搜尋紀錄 §4c；實務上 LVIS 級可部署模型就是 YOLOE 的 prompt-free 變體，精度反而更低）。
2. **但 GO 的精度證據不足**：S 尺寸 LVIS-rare AP 只有 ~22（YOLOE-v8s AP_r=22.3），整體 LVIS AP 23.7（26n）~31.0（26s）vs 現役 COCO mAP 40.9——rare 居家小物是 hit-or-miss；**藥瓶（pill_bottle）連 LVIS 1203 類裡都沒有**，零 shot 可靠度無任何可引用數字。加上既有實證「COCO 重訓類 cup 都只有 0.7m 穩」（距離/解析度是獨立瓶頸），直接上機等於重演 cup overclaim。
3. **先做一個下午的 WSL replay**：vocab 清單 v0（38 條目 / 43 類，本文 §1）+ 自拍居家物件照（0.5/1.0/1.5m）+ demo 錄影重放，量 per-class recall 與容器類混淆矩陣，過門檻才排上機。export 步驟已備好（§2.4），與 goal 1 的 s@960 候選同一顆模型可疊加（§8）。
4. **附帶修正一個前提錯誤**：goal 痛點清單裡的「遙控器、碗筷抓不到」**不是類別缺口**——`remote`(65)、`bowl`(45)、`fork/knife/spoon`(42-44) 都在 COCO 80 內（`coco_classes.py:84,64,61-63`），那是 recall/距離問題，屬 goal 1 管轄。真正的類別缺口是：藥瓶、眼鏡、鑰匙、拐杖、輪椅、馬克杯、保溫瓶、錢包、手錶、拖鞋、毛巾、衛生紙。

---

## 1. PawAI 居家目標類別清單 v0（38 條目，展開複合條目後 43 類）

從互動場景（demo S1-S5 12 步腳本、拿杯子/喝水提醒、藥瓶提醒、遙控器尋物——`project_demo_flow_0609.md`；`docs/mission/README.md:437-459` 功能 6）與 guardian 場景（拐杖/輪椅——`docs/mission/README.md:50-52` 互動 70%/守護 30%）反推。COCO 欄位依 `object_perception/object_perception/coco_classes.py:18-99`；LVIS 欄位依 `ultralytics/cfg/datasets/lvis.yaml`（1203 類，raw GitHub 逐項查證）。

### 1a. 互動主軸（尋物 / 情境回應）

| # | 類別（prompt 候選詞） | 中文 | COCO 80 | LVIS 1203 | 備註 |
|---|------|------|:---:|:---:|------|
| 1 | cup | 杯子 | ✅ (41) | ✅ | 現役 S3 主角，0.7m 穩 |
| 2 | mug | 馬克杯 | ❌ | ✅ "mug" | 與 cup 混淆風險（§6） |
| 3 | teacup | 茶杯 | ❌ | ✅ "teacup" | 同上 |
| 4 | bottle | 瓶子 | ✅ (39) | ✅ | |
| 5 | water_bottle | 水瓶 | ❌ | ✅ "water bottle" | |
| 6 | thermos | 保溫瓶 | ❌ | ✅ "thermos bottle" | |
| 7 | kettle | 水壺 | ❌ | ✅ "kettle/boiler" | |
| 8 | bowl | 碗 | ✅ (45) | ✅ | **痛點清單誤列**，本來就在 COCO |
| 9 | fork / knife / spoon | 叉/刀/匙 | ✅ (42-44) | ✅ | 同上 |
| 10 | medicine | 藥 | ❌ | ✅ "medicine" | LVIS-rare 級 |
| 11 | pill_bottle | 藥瓶 | ❌ | **❌ 不存在** | 只能靠 open-vocab text prompt，零紙面證據 |
| 12 | remote | 遙控器 | ✅ (65) | ✅ "remote control" | **痛點清單誤列**，在 COCO + brain whitelist（`zh_tables.py:19`） |
| 13 | cell_phone | 手機 | ✅ (67) | ✅ "cellular telephone" | |
| 14 | key | 鑰匙 | ❌ | ✅ "key" | 極小物，距離瓶頸比類別瓶頸大 |
| 15 | eyeglasses | 眼鏡 | ❌ | ✅ "spectacles/specs/eyeglasses/glasses" | 同上 |
| 16 | wallet | 錢包 | ❌ | ✅ "wallet/billfold" | |
| 17 | watch | 手錶 | ❌ | ✅ "watch/wristwatch" | |
| 18 | book | 書 | ✅ (73) | ✅ | |
| 19 | newspaper | 報紙 | ❌ | ✅ "newspaper" | |
| 20 | magazine | 雜誌 | ❌ | ✅ "magazine" | |
| 21 | tissue_paper | 衛生紙 | ❌ | ✅ "tissue paper" | |
| 22 | slipper | 拖鞋 | ❌ | ✅ "slipper" | |
| 23 | towel | 毛巾 | ❌ | ✅ "bath towel"/"hand towel" | |
| 24 | toothbrush | 牙刷 | ✅ (79) | ✅ | |
| 25 | toothpaste | 牙膏 | ❌ | ✅ "toothpaste" | |
| 26 | banana / apple / orange | 水果 | ✅ (46,47,49) | ✅ | brain whitelist 已收 |

### 1b. Guardian / 場景錨點

| # | 類別 | 中文 | COCO 80 | LVIS 1203 | 備註 |
|---|------|------|:---:|:---:|------|
| 27 | person | 人 | ✅ (0) | ✅ | |
| 28 | dog / cat | 狗/貓 | ✅ (16,15) | ✅ | |
| 29 | chair | 椅子 | ✅ (56) | ✅ | |
| 30 | couch | 沙發 | ✅ (57) | ✅ | |
| 31 | bed | 床 | ✅ (59) | ✅ | |
| 32 | dining_table | 餐桌 | ✅ (60) | ✅ | |
| 33 | tv | 電視 | ✅ (62) | ✅ | |
| 34 | walking_cane | 拐杖 | ❌ | ✅ "walking cane"（另有 "walking stick"） | PINTO 472 有屬性級替代（§4b） |
| 35 | crutch | 腋下拐 | ❌ | ✅ "crutch" | 同上 |
| 36 | wheelchair | 輪椅 | ❌ | ✅ "wheelchair" | 同上 |
| 37 | walker | 助行器 | ❌ | **❌ 不存在** | LVIS 無此類 |
| 38 | first_aid_kit | 急救箱 | ❌ | ✅ "first-aid kit" | |

**COCO 80 覆蓋率**（兩種計數單位並列）：38 條目中 **16 條**有 COCO ✅；展開複合條目（fork/knife/spoon=3 類、水果=3 類、dog/cat=2 類）後共 **43 類**，其中 COCO 內 **21 類**（cup/bottle/bowl/餐具×3/remote/cell_phone/book/toothbrush/水果×3/person/dog/cat/chair/couch/bed/dining_table/tv）——**覆蓋率 = 16/38 條目 ≈ 42%，或 21/43 類 ≈ 49%**；非 COCO 缺口 = 22 條目 = 22 類（複合條目全在 COCO 內，展開不增加缺口）。**LVIS 1203 覆蓋率 ≈ 95%**（36/38 條目，缺 pill_bottle、walker；另查證 6 個 v0 外相關詞不在 LVIS：pill、comb、hearing_aid、tablet_computer、electric_fan、medicine_cabinet——來源同 lvis.yaml 查證）。

---

## 2. Open-vocab 路線：YOLOE / YOLOE-26 set-classes-then-export

### 2.1 機制（已證實）

- `set_classes()` 設定 vocabulary 後 export，**類別被燒進權重**：「Classes configured with `set_classes()` (or via `refer_image` for visual prompts) are baked into the exported weights. Once exported, the model can no longer accept new prompts: calling `set_classes()` or passing `visual_prompts=...` to `predict()` on a loaded export will fail.」（[Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)）
- export 產物「behaves like a standard YOLO detector and can also be loaded with `YOLO()` instead of `YOLOE()`」——**runtime 零 text-encoder 成本**（同上）。
- 機制原理：RepRTA「refines text embeddings (e.g., from CLIP) via a small auxiliary network. At inference, this network is folded into the main model, ensuring zero overhead」（同上）。THU-MIG 上游 README 同述：「After re-parameterization, YOLOE-v8 / YOLOE-11 can be re-parameterized into the same architecture as YOLOv8 / YOLO11, with zero overhead for transferring」（[THU-MIG/yoloe README](https://github.com/THU-MIG/yoloe/blob/main/README.md)）。
- text encoder 只在 `set_classes()` 當下跑一次：YOLOE 用 **MobileCLIP-B(LT)**（WSL 需 `wget https://docs-assets.developer.apple.com/ml-research/datasets/mobileclip/mobileclip_blt.pt`，[THU-MIG/yoloe README](https://github.com/THU-MIG/yoloe) / [ultralytics text_model reference](https://docs.ultralytics.com/reference/nn/text_model/)）；YOLOE-26 升級為 **MobileCLIP2**（[arXiv 2606.03748](https://arxiv.org/html/2606.03748v1)）。

### 2.2 YOLO26 世代對應版本：有，叫 YOLOE26

- 「YOLOE26 offers all five model scales (N/S/M/L/X)」，建立在 YOLO26 的「NMS-free end-to-end design for faster inference」之上（[Ultralytics YOLOE docs — Available Models](https://docs.ultralytics.com/models/yoloe/#available-models-supported-tasks-and-operating-modes)）。
- 注意：**Ultralytics 全部 YOLOE 權重（含 YOLOE-26N/S/M/L/X 與全部 -PF 變體）任務欄都是 Instance Segmentation**（如 `yoloe-26l-seg.pt`、`yoloe-26s-seg.pt`；同上 docs）。沒有純 detect 權重——整合面影響見 §2.3。
- YOLOE-26 = YOLO26 backbone + decoupled segmentation training + MobileCLIP2 + pseudo-label data engine（teacher 用 **4585 個內建類** prompt；[arXiv 2606.03748](https://arxiv.org/html/2606.03748v1)）。

### 2.3 Export 產物 vs 現役 (1,300,6) 的整合差異

- 現役 parse：`object_perception_node.py:384` `raw = outputs[0][0]  # (300, 6): x1, y1, x2, y2, conf, class_id`。
- YOLOE-26 是 seg 模型，e2e NMS-free seg export 的同型參照是 YOLO11s-seg with NMS export：輸出 `((1, 300, 38), (1, 32, 160, 160))`——前 6 欄 = bbox+conf+class、後 32 欄 = mask 係數、第二個 tensor = mask proto（[supervision issue #1787](https://github.com/roboflow/supervision/issues/1787)）。**假設**（標注：未實際 export 驗證）：YOLOE-26-seg ONNX export 形態同款 → node 改動 = 取 `outputs[0][0][:, :6]` 切片 + 忽略 proto tensor，**一行級 parse 改動**；mask 不取用則 CPU 零額外成本。
- 換 vocab 必改類別表：`object_perception_node.py:393-404` 有 `if class_id not in COCO_CLASSES: continue` guard 與 `COCO_CLASSES[class_id]` 名稱映射——custom vocab 的 class_id 0..N-1 與 COCO id 表意不同，**必須換成 vocab 對應表**（id 碰撞風險：不換表會把 vocab id 2 講成 "car"）。
- TRT EP 角度：export 後是普通 ONNX graph（無 text branch），與現役 YOLO26n 同走 onnxruntime-gpu 1.23.0 + `trt_fp16_enable` 路徑，無已知額外 operator 風險（依據 §2.1 的 "standard YOLO detector" 宣稱；TRT engine 首次 build 3-10 分鐘照舊，`docs/architecture/perception/object/CLAUDE.md` 既有紀律）。

### 2.4 WSL export 步驟（replay/上機前置，照抄即可）

```python
# WSL only（ultralytics 禁令只限 Jetson — CLAUDE.md「不要 pip install ultralytics」條目；goal 1 spec 同認定 WSL export 合法）
from ultralytics import YOLOE
model = YOLOE("yoloe-26s-seg.pt")          # 或 yoloe-26n-seg.pt
names = [...]                               # §1 的 38 類英文 prompt
model.set_classes(names)                    # 觸發 MobileCLIP2 下載/嵌入（一次性）
model.export(format="onnx")                 # 之後可加 imgsz=960 與 goal 1 對齊
```
（code 形態出自 [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)；`set_classes` 內部走 `get_text_pe` + MobileCLIP，[ultralytics text_model reference](https://docs.ultralytics.com/reference/nn/text_model/)）

---

## 3. 精度證據：LVIS / LVIS-rare AP（GO 卡在這裡）

| 模型 | Params | LVIS minival AP（text prompt） | AP_r（rare） | 來源 |
|------|:---:|:---:|:---:|------|
| YOLOE-v8-S | 12M | 27.9 | **22.3** | [THU-MIG/yoloe README](https://github.com/THU-MIG/yoloe/blob/main/README.md) |
| YOLOE-v8-M | 27M | 32.6 | 26.9 | 同上 |
| YOLOE-v8-L | 45M | 35.9 | 33.2 | 同上 |
| YOLOE-11-S | 10M | 27.5 | 21.4 | 同上 |
| YOLOE-11-L | 26M | 35.2 | 29.1 | 同上 |
| YOLOE-26n-seg | 未公布 | ~23.7（E2E） | 未公布 | WebSearch 摘要引 Ultralytics 文檔系（二手，置信度低，replay 時以實測為準） |
| YOLOE-26s-seg | 未公布 | **29.9（E2E）/ 31.0（non-E2E）** | 未公布 | [arXiv 2606.03748 Table 12](https://arxiv.org/html/2606.03748v1) |
| YOLOE26-L | 32.3M / 88.3 GFLOPs | 36.8 | 未公布 | [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/) |

- YOLOE 對 rare 類的相對增益：「For rare categories, YOLOE-v8-S and YOLOE-v8-L obtain significant improvements of 5.2% and 7.6% AP_r」over YOLO-Worldv2（[arXiv 2503.07465](https://arxiv.org/pdf/2503.07465)）——**但絕對值 22.3 仍然低**：rare 類（≈ 藥/拐杖/急救箱這一桶）平均十次有七八次標不準或漏標。
- YOLOE26 對 YOLO-World 的代差：「YOLOE26-S achieves 29.9% mAP, surpassing YOLO-World-S by +11.4 AP, while YOLOE26-L achieves 36.8% mAP, exceeding YOLO-World-L by +10.0 AP」（[Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)）→ **YOLO-World 不必再考慮**。
- 對照現役：YOLO26n COCO mAP 40.9 / 26s 48.6（[Ultralytics YOLO26 docs](https://docs.ultralytics.com/models/yolo26/)）——LVIS AP 與 COCO mAP 不可直比（類別數 15 倍），但量級差說明 open-vocab 在長尾類上的單類可靠度遠低於 COCO 主類。
- **致命缺口**：`pill_bottle` 不在 LVIS 1203 類中（[lvis.yaml](https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/cfg/datasets/lvis.yaml) 查證；最接近的是 "medicine" 與 "bottle"）——「藥瓶」這個 goal 點名的第一痛點，**沒有任何 benchmark 可引用**，純靠 MobileCLIP2 文字嵌入泛化，可靠度只能實測。

---

## 4. 更大 closed-set 路線盤點（結論：無獨立供給）

### 4a. LVIS 級 closed-set 可部署模型

- 真正「LVIS 1203 closed-set + 可 ONNX + edge 可負擔」的現成供給**在三組 WebSearch 查詢內未找到獨立選項**（搜尋字串與前列結果否決理由見 §4c 搜尋 1-3）：mmdetection 的 Mask R-CNN ONNX export 路徑存在（[mmdetection issue #4247](https://github.com/open-mmlab/mmdetection/issues/4247)、[MMDetection 3.x deploy docs](https://mmdetection.readthedocs.io/en/3.x/user_guides/deploy.html)），但兩階段架構在 edge 的 LVIS 配置 Jetson FPS/RAM 實測**搜尋零命中**（§4c 搜尋 2）；Detic 走 CLIP head + 21k 類（[ECCV 2022 paper](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136690344.pdf)），transformer 級成本，同樣無 Jetson 供給證據浮出（§4c 搜尋 1/3 均未命中）。
- 實務上的「更大 closed-set」就是 **YOLOE 的 prompt-free 變體**：內建 4585 類 vocabulary（[arXiv 2606.03748](https://arxiv.org/html/2606.03748v1) pseudo-label engine 描述；Ultralytics docs 稱「internal embeddings trained on large vocabularies (1200+ categories from LVIS and Objects365)」）、LVIS AP 21.0-27.2（[THU-MIG README](https://github.com/THU-MIG/yoloe/blob/main/README.md)）——**比同尺寸 custom-vocab 低**，且 4585 類輸出對 30 類需求是浪費。**裁定：closed-set 不是獨立路線，是 open-vocab 的劣化版**。
- YOLO-World 的 LVIS fine-tune 路線（[AILab-CVC/YOLO-World](https://github.com/ailab-cvc/yolo-world) 支援 normal / prompt / reparameterized fine-tuning）被 YOLOE26 代差壓制（§3），不採。

### 4b. PINTO zoo 供給查證（Q5 的證據）

- `grep -ril "yolo-world\|yoloe\|open.vocab\|grounding" $HOME/newLife/PINTO_model_zoo/*/README.md` → **0 命中**（grep exit 1）。
- 目錄名掃描（world|yoloe|owl|ground|lvis|detic|glip）只有 2 個**假陽性**：`138_BackgroundMattingV2`（"ground" 撞 "Background"）、`336_PP-YOLOE-Plus`（Paddle 的閉集 COCO 偵測器，與清華 YOLOE 同名不同物；目錄內僅 demo/convert_script.txt/download.sh/LICENSE/url.txt，無 README.md）。
- **結論：PINTO 報告盤點「未被任何角度撈出」是真缺席不是漏掃**——zoo 內無 open-vocab、無 LVIS 級 closed-set 供給。
- 但 guardian 場景有**屬性級替代**：`472_DEIMv2-Wholebody34` 含 `body_with_wheelchair`（per-class mAP 0.4186→0.9288 隨尺寸）與 `body_with_crutches`（0.4764→0.9487）（`$HOME/newLife/PINTO_model_zoo/472_DEIMv2-Wholebody34/README.md` per-class mAP 表）——「坐輪椅的人/拄拐的人」用人體屬性偵測比「偵測拐杖物體」更貼 guardian 語意，**拐杖/輪椅可以不靠 open-vocab**（觸發條件照 PINTO 報告 §4.2：guardian 能力線立項才動）。

### 4c. 負面結論搜尋紀錄（2026-06-11 WebSearch，供復查）

負面結論（「未找到 X」）必須附搜尋字串與前列結果的否決理由才可復查。以下四組搜尋是 §4a「closed-set 無獨立供給」與 Q3「無居家小物實測」兩個負面裁定的證據基礎；**所有「不存在」措辭一律降級為「此搜尋範圍內未找到」**。

| # | 搜尋字串 | 前列結果（節選） | 否決理由 |
|---|---------|----------------|---------|
| 1 | `LVIS trained detector ONNX edge deployment`（goal Sources #3 原字串） | [EdgeSAM](https://github.com/chongzhou96/EdgeSAM)；[Grounding DINO 1.5 Edge (emergentmind)](https://www.emergentmind.com/topics/grounding-dino-1-5-edge)；[Replicate yolo-world](https://replicate.com/zsxkib/yolo-world/readme)；EdgeDAM（arXiv 2603.05463）；[DataCamp ONNX 通論](https://www.datacamp.com/tutorial/onnx) | EdgeSAM=SAM 蒸餾非偵測器；GDINO 1.5 Edge=API-gated（§5 已出局）；YOLO-World=已被 YOLOE26 壓制（§3）；EdgeDAM=追蹤、iPhone CoreML；其餘為通論/無關。**無一是可直接 export 的 LVIS closed-set 權重** |
| 2 | `mmdetection LVIS Mask R-CNN ONNX export Jetson deployment fps` | [mmdetection issue #4247](https://github.com/open-mmlab/mmdetection/issues/4247)（Mask R-CNN ONNX export 修障）；[MMDetection 3.x deploy docs](https://mmdetection.readthedocs.io/en/3.x/user_guides/deploy.html)；其餘為各版 changelog | torch2onnx 路徑存在，但**零筆 LVIS 配置上 Jetson 的 FPS/RAM 實測**（官方與社區皆無）——「edge 部署無實測供給」由此搜尋支撐，非絕對不存在 |
| 3 | `LVIS 1203 classes pretrained detector weights download ONNX export real-time` | [Ultralytics LVIS dataset docs](https://docs.ultralytics.com/datasets/detect/lvis)；[learnopencv YOLOE tutorial](https://learnopencv.com/yoloe-tutorial-real-time-open-vocabulary-detection/)；[OVLW-DETR (arXiv 2407.10655)](https://arxiv.org/html/2407.10655v1)；[rfdetr PyPI](https://pypi.org/project/rfdetr/1.1.0/) | 前列結果**繞回 YOLOE/Ultralytics 生態**；OVLW-DETR 是 open-vocab transformer 論文（非 closed-set、無 edge 供給）；RF-DETR 是 COCO 預訓練（非 LVIS closed-set）。佐證「實務上 LVIS 級可部署 = YOLOE prompt-free 變體」（§4a 第二點） |
| 4 | `YOLOE YOLO-World custom vocabulary household objects real-world accuracy pill bottle medicine detection` | [YOLO-World paper (arXiv 2401.17270)](https://arxiv.org/abs/2401.17270)；[Ultralytics YOLO-World docs](https://docs.ultralytics.com/models/yolo-world)；[Medium zero-shot vs custom YOLOv8 比較](https://medium.com/@sulavstha007/how-well-does-a-zero-shot-detection-model-yolo-world-perform-as-compared-to-custom-trained-yolov8-6e85a94052f6)；[open-vocab robustness under distribution shifts (arXiv 2405.14874)](https://arxiv.org/pdf/2405.14874) | 全是論文/官方文檔/通用介紹文；robustness 論文談 OOD 分佈偏移但非居家小物距離 recall。**無任何可引用的藥瓶/鑰匙/眼鏡級居家小物實測**——Q3 的「搜尋無果」限於此範圍 |

---

## 5. 反面證據固定：Grounding DINO / OWL-ViT 級正式出局

- **開源 Grounding DINO（SwinT）**：AGX Orin 上 NVIDIA 官方 JPS 宣稱 11.6 FPS，社區實測「inference was significantly slower than advertised (2-3 FPS vs 11.6 FPS advertised)」（[NVIDIA-AI-IOT/jetson-platform-services issue #3](https://github.com/NVIDIA-AI-IOT/jetson-platform-services/issues/3)）。AGX Orin（275 TOPS 級）對 Orin Nano 8GB（40 TOPS 級）約 5-7 倍算力 → **Orin Nano 外推 <1 FPS**（外推假設：算力線性比，世代同為 Orin/JetPack 6）。Hackster 實作者直言「GroundingDINO is too slow to achieve meaningful real-time interactions on edge devices such as the Jetson Orin」，換 YOLO-World 得 6x 加速（[Hackster — Realtime Language-Segment-Anything on Jetson Orin](https://www.hackster.io/lurst811/realtime-language-segment-anything-on-jetson-orin-ccf6e1)）。
- **Grounding DINO 1.5/1.6 Edge / DINO-X Edge**：Orin NX 上 TRT 優化後 >10 / 15.1 / 20.1 FPS（[arXiv 2405.10300](https://arxiv.org/pdf/2405.10300)、[arXiv 2411.14347](https://arxiv.org/pdf/2411.14347)）看似可用，**但權重不公開**——只有 API 存取，社區要權重的 issue 沒有下文（[IDEA-Research/Grounding-DINO-1.5-API issue #24](https://github.com/IDEA-Research/Grounding-DINO-1.5-API/issues/24)）。不可部署 = 出局。
- **OWL-ViT（NanoOWL TRT 優化）**：AGX Orin 95 FPS（ViT-B/32@768, mAP 28）/ 25 FPS（ViT-B/16, mAP 31.7），**Orin Nano 欄位 README 標 TBD**（[NVIDIA-AI-IOT/nanoowl](https://github.com/NVIDIA-AI-IOT/nanoowl)）。mAP 28 低於 YOLOE26-L 的 36.8，部署棧（torch2trt + 獨立 runtime）與現役 onnxruntime 主線不相容——速度不是死因，**精度+整合成本出局**。
- **裁定**：transformer 級 open-vocab 在 Orin Nano 8GB 上「可部署的太弱（OWL-ViT）、夠強的跑不動（GDINO SwinT）或拿不到（1.5 Edge）」。此節證據固定後，之後不再重提。

---

## 6. 風險面

1. **容器類 fine-grained 混淆（藥瓶 vs 水瓶 vs 杯子）**：LVIS 把 `bottle` / `water bottle` / `thermos bottle` / `mug` / `teacup` / `cup` / `pill bottle 缺席` 全列為獨立或缺失類（[lvis.yaml](https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/cfg/datasets/lvis.yaml)）——38 類 vocab 同場時，文字嵌入相近的容器類互搶是結構性風險，rare AP 22.3 的 proxy（§3）暗示混淆率不低。**replay 必須出容器類混淆矩陣**。
2. **conf threshold 連動**：現役 `confidence_threshold=0.5`（`object_perception_node.py:159`）是對 COCO 主類調的；zero-shot rare 類分數整體偏低，0.5 會把弱命中全切掉。supervision 報告已有「0.25-0.3 + ByteTrack `minimum_consecutive_frames=3` 時序確認」spike（`docs/perception/research/2026-06-11-supervision-pawai-fit-report.md:152-154,143`）——**replay 應與該 spike 合併量測**，避免兩條線各跑一次同樣的錄影。
3. **中文場景詞→英文 prompt 對應表維護**：成本低且模式已存在——`pawai_contracts/pawai_contracts/zh_tables.py:14-26` 就是 class_name→中文 的 32 類表（Plan C3 單一真相來源，`zh_tables.py:1-11`），producer 端 `coco_classes.py:8-11` docstring 明載三份鏡像（coco_classes / studio object-config.ts / brain）+ parity test 守護。新 vocab = 同模式加行，每類一行中文 + 一行英文 prompt；**真正的成本在 prompt 措辭調優**（"pill bottle" vs "medicine bottle" vs "prescription bottle" 哪個嵌入命中高——replay 可同場 A/B）。
4. **距離混淆因子**：goal 點名的新類多半比 cup 更小（鑰匙、眼鏡、手錶），而 COCO 重訓類 cup 在現役配置只有 0.7m 穩（`project_demo_flow_0609.md` S3：「cup 鎖 0.7m，1m 不穩、不演」）——**類別擴充不解距離**，新 rare 類在 1m+ 的 recall 預期比 cup 更差。這是 verdict 不能直接 GO 的第二根支柱，也是必須與 goal 1（尺寸/解析度）綁定測試的原因。

---

## 7. 類別擴充與 class_whitelist / brain gate 連動（scope 外，記錄）

- **contract 層**：`/event/object_detected` 的 `class_name` schema type 是自由字串（`docs/contracts/interaction_contract.md:674`），**type 層擴類別確實不動 contract**；但同節描述文字寫死「COCO 80 class name」與「類別範圍：COCO 80 class」（`interaction_contract.md:674,687`）→ 擴充時要做**文件級更新**（非 schema breaking change）。
- **node 層**：`class_whitelist` 參數語意是 COCO id（`object_perception_node.py:141-148`），vocab 換表後 id 表意全變——whitelist 預設值與 runtime `ros2 param set` 用法（`object_perception_node.py:251-258`）要對新表重新文件化。
- **brain 層**：目前消費者是 `zh_tables.py:14-26` 的 32 類 whitelist，不在表內的 class 靜默不講（`brain_node.py:93`）；S3 demo 實際只開 cup（`project_demo_flow_0609.md`：「object 0.35 cup-only」）。**新類別進來後誰消費、講什麼台詞（OBJECT_TTS_SPECIAL_SUFFIX 模式，`zh_tables.py:35-39`）是 brain 編排問題**——本研究標注為 scope 外，掛在「PawAI Brain 流程編排深挖」線（`project_demo_flow_0609.md` 6/9 待辦 #4）。

---

## 8. 與 goal 1（s@960 升級線）的耦合

- **YOLOE-26 與 YOLO26 同架構**（§2.2），`export(imgsz=...)` 是同一條路徑 → **goal 1 若裁定 s@960 勝出，YOLOE-26s-seg custom-vocab @960 是「同一顆模型同時解尺寸與類別」的疊加解**——不需要兩顆模型分別解兩個問題。
- 成本邊際：YOLOE26-L 88.3 GFLOPs vs YOLO26l 86.4（[docs](https://docs.ultralytics.com/models/yoloe/) / [docs](https://docs.ultralytics.com/models/yolo26/)）→ open-vocab 架構 overhead ≈ +2%；seg head 另加（det→seg 參照 YOLO11n 6.5→10.4 GFLOPs ≈ 1.6x，外推假設標注：YOLO11 世代數據）。
- **公平比較紀律**（goal 點名）：replay 時 YOLOE-26 候選必須與 goal 1 勝出配置同 imgsz 同尺寸出數字，不可拿 n@640 的 baseline 對比 s@960 的 open-vocab。

---

## 9. Jetson 成本估算（Q7）

**錨點**（實測，Orin Nano Super, JP6.1, TRT FP16, engine-only 不含前後處理）：YOLO26n **4.57ms** / YOLO26s **7.17ms**（[Ultralytics nvidia-jetson guide](https://docs.ultralytics.com/guides/nvidia-jetson/)，Ultralytics 8.4.33 實測）。注意：這是 Orin Nano **Super** 模式數字；本機 JetPack 6 可用 Super 模式則直接適用，否則按 ~0.6-0.7x 折算（外推假設標注）。

| 配置 | GFLOPs 估算 | engine 推理估算 | RAM 邊際 | 依據與假設 |
|------|:---:|:---:|:---:|------|
| 現役 YOLO26n det @640 | 5.4 | 4.57ms 實測 | 基線（ONNX 9.5MB） | [YOLO26 docs](https://docs.ultralytics.com/models/yolo26/)；`CLAUDE.md` 模型路徑條目 |
| YOLOE-26n-seg vocab38 @640 | ~8-10 | ~7-9ms | +10-30MB engine 級 | det→seg 1.6x（YOLO11 世代外推）+ open-vocab +2% |
| YOLOE-26s-seg vocab38 @640 | ~33-35 | ~11-13ms | +50-80MB 級 | s det 20.7 GFLOPs × seg 1.6x；s det 7.17ms 錨點 |
| YOLOE-26s-seg vocab38 @960 | ~74-79 | ~25-30ms | +100-150MB 級 | 上行 ×(960/640)²=2.25；goal 1 疊加配置 |

- **全部配置都不破 0.8GB RAM 紀律**（最重的 s-seg@960 估 <200MB 邊際，現役 GPU 上只有 object 一顆——`goals/2026-06-11-yolo26-scaleup-highres-seg-goal.md:16`）。
- **Hz 結論**：現役 pipeline 6-8Hz 的瓶頸不在 engine（4.57ms = 理論 200+ FPS），在 node 前後處理與 tick——換 YOLOE-26n/s @640 對 Hz 影響可忽略；@960 需 goal 1 的 D435 餵圖配套一起算。
- 以上全部為**外推估算**（標注：錨點是 YOLO26 det 世代 + YOLO11 seg 比例），上機前以 TRT engine build 後實測為準。

---

## 10. Findings（42 條，附引用）

**本地證據（file:line）**

1. 現役類別表 = COCO 80、id 0-79、含空格類名底線化 — `object_perception/object_perception/coco_classes.py:18-99`
2. `remote`(65)、`bowl`(45)、`fork/knife/spoon`(42-44)、`cell_phone`(67) 都在 COCO 80 內 — `coco_classes.py:84,64,61-63,86`；**goal 痛點清單「遙控器、碗筷全抓不到」在類別層不成立**，是 recall/距離問題
3. `remote` 甚至已在 brain TTS whitelist（「遙控器」）— `pawai_contracts/pawai_contracts/zh_tables.py:19`
4. 真正不在 COCO 80 的目標類 **22 個**（條目=類，皆單類條目）：藥/藥瓶（2）、眼鏡、鑰匙、拐杖×2（walking_cane+crutch）、輪椅、助行器、馬克杯、茶杯、水瓶、保溫瓶、水壺、錢包、手錶、報紙、雜誌、衛生紙、拖鞋、毛巾、牙膏、急救箱 — §1 表 vs `coco_classes.py:18-99`
5. v0 清單 38 條目（展開複合條目後 43 類），COCO 覆蓋 16/38 條目 ≈42%（21/43 類 ≈49%）、LVIS 覆蓋 36/38 條目 ≈95% — §1 統計
6. `/event/object_detected` schema `class_name` type=string（自由字串）— `docs/contracts/interaction_contract.md:674`
7. 但 contract 同節描述寫死「類別範圍：COCO 80 class」— `interaction_contract.md:687`；擴類別需文件級更新（非 breaking）
8. node parse 寫死 `(300,6)` 形態 — `object_perception_node.py:384`
9. node 有 `class_id not in COCO_CLASSES` guard + 名稱映射，換 vocab 必換表 — `object_perception_node.py:393-404`
10. 現役 conf threshold 0.5 — `object_perception_node.py:159`；對 zero-shot rare 類過高（§6.2）
11. `class_whitelist` 語意 = COCO id，空 list = 全開 — `object_perception_node.py:141-148`
12. brain 消費端 32 類 whitelist，表外靜默 — `zh_tables.py:14-26` + `brain_node.py:93`
13. 中文表單一真相來源 + 三鏡像 parity test 紀律已存在 — `zh_tables.py:1-11`、`coco_classes.py:8-11`
14. demo S3 實況：cup 鎖 0.7m、1m 不穩；6/9 上機 object 0.35 cup-only — `project_demo_flow_0609.md`（S3 段、6/9 晚 HITL 段）
15. Roy 6/9 已點名「發揮 COCO 更多類別、別只 cup-only」+「object 鎖 1m 內、遠距降 bonus」 — `project_demo_flow_0609.md` 待辦 #2、修法 #6
16. 互動 70% / 守護 30% 定位，類別清單對齊場景而非貪多 — `docs/mission/README.md:50-52`
17. mission 既有待辦「組員篩選適合室內場景的 COCO 類別」（COCO 內篩選）— `docs/mission/README.md:459`；本研究 v0 是其 superset
18. PINTO zoo README 全文 grep open-vocab 關鍵詞 **0 命中**（exit 1）— 本研究實測 `grep -ril` on `$HOME/newLife/PINTO_model_zoo/*/README.md`
19. 目錄名僅 2 假陽性：`138_BackgroundMattingV2`、`336_PP-YOLOE-Plus`（Paddle 閉集，無 README.md）— 本研究 `ls` + 目錄內容查證
20. PINTO `472_DEIMv2-Wholebody34` 有 `body_with_wheelchair` mAP 0.4186-0.9288 / `body_with_crutches` 0.4764-0.9487（隨尺寸）— `472_DEIMv2-Wholebody34/README.md` per-class mAP 表
21. PINTO 報告裁定「object 線此 zoo 無解」針對 cup 遠距 — `2026-06-11-pinto-model-zoo-pawai-fit-report.md:63,130-135`；本研究確認**類別擴充同樣無解**（兩結論獨立成立）
22. supervision 報告已有低 threshold + ByteTrack 時序確認 spike 計畫 — `2026-06-11-supervision-pawai-fit-report.md:143,152-154`；replay 應合併量測

**Web 證據（URL）**

23. YOLOE `set_classes()` 後 export 把類別燒進權重、export 後不可再 prompt — [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)（exact quote 見 §2.1）
24. export 產物 = 標準 YOLO detector、可用 `YOLO()` 載入、零 runtime text-encoder — 同上
25. RepRTA fold-in：inference 零 overhead — 同上
26. YOLOE26 五尺寸 N/S/M/L/X、基於 YOLO26 NMS-free e2e — [Ultralytics YOLOE docs — Available Models](https://docs.ultralytics.com/models/yoloe/#available-models-supported-tasks-and-operating-modes)
27. Ultralytics 全部 YOLOE 權重任務 = Instance Segmentation（無純 det 權重）— 同上
28. YOLOE26-L：LVIS 36.8 / 32.3M / 88.3 GFLOPs；YOLOE-L：35.2 / 26.2M / 86.9 — [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)
29. YOLOE-26s：LVIS 29.9 AP (E2E) / 31.0 (non-E2E)；MobileCLIP2 + pseudo-label engine（4585 內建類 teacher）— [arXiv 2606.03748](https://arxiv.org/html/2606.03748v1)
30. YOLOE-v8-S/M/L LVIS AP 27.9/32.6/35.9，**AP_r 22.3/26.9/33.2**；YOLOE-11-S AP_r 21.4 — [THU-MIG/yoloe README](https://github.com/THU-MIG/yoloe/blob/main/README.md)
31. YOLOE rare 類相對增益 +5.2/+7.6 AP_r over YOLO-Worldv2 — [arXiv 2503.07465](https://arxiv.org/pdf/2503.07465)
32. YOLOE26-S 超 YOLO-World-S **+11.4 AP**、L 超 +10.0 — [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/)；YOLO-World 出局
33. YOLO-World 僅 v2 可 export ONNX/TRT；set_classes+save 機制同款 — [Ultralytics YOLO-World docs](https://docs.ultralytics.com/models/yolo-world/)
34. YOLOE prompt-free = 內建大詞彙（docs 稱 1200+ 類；paper 的 teacher vocab 4585 類），AP 21.0-27.2 < 同尺寸 custom-vocab — [Ultralytics YOLOE docs](https://docs.ultralytics.com/models/yoloe/) + [THU-MIG README](https://github.com/THU-MIG/yoloe/blob/main/README.md)
35. text encoder = MobileCLIP-B(LT)（`mobileclip_blt.pt` 需下載）/ YOLOE-26 用 MobileCLIP2，只在 set_classes 時跑 — [THU-MIG/yoloe](https://github.com/THU-MIG/yoloe) + [ultralytics text_model reference](https://docs.ultralytics.com/reference/nn/text_model/)
36. LVIS 1203 類含 **36/38 個 v0 條目**（命中例：remote control / medicine / walking cane / crutch / wheelchair / spectacles-eyeglasses / key / mug / water bottle / tissue paper / slipper / first-aid kit…）；v0 條目缺 **pill_bottle、walker**；另查證 6 個 v0 外相關詞 **pill、comb、hearing_aid、tablet_computer、electric_fan、medicine_cabinet** 也不存在（合計 44 個查詢詞、36 命中，與 §1 的 36/38 ≈95% 為同一份查證）— [ultralytics lvis.yaml](https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/cfg/datasets/lvis.yaml) 逐項查證
37. e2e seg export 輸出同型參照：YOLO11s-seg with NMS → `((1,300,38),(1,32,160,160))`，前 6 欄 = bbox+conf+class — [supervision issue #1787](https://github.com/roboflow/supervision/issues/1787)
38. Grounding DINO AGX Orin 實測 2-3 FPS（vs 宣稱 11.6）— [jetson-platform-services issue #3](https://github.com/NVIDIA-AI-IOT/jetson-platform-services/issues/3)；Orin Nano 外推 <1 FPS（假設：算力線性比 ~1/5-1/7）
39. GDINO 1.5/1.6 Edge（Orin NX >10/15.1 FPS）/ DINO-X Edge（20.1 FPS）權重不公開、API-only — [arXiv 2405.10300](https://arxiv.org/pdf/2405.10300)、[arXiv 2411.14347](https://arxiv.org/pdf/2411.14347)、[Grounding-DINO-1.5-API issue #24](https://github.com/IDEA-Research/Grounding-DINO-1.5-API/issues/24)；OWL-ViT/NanoOWL AGX 95 FPS@mAP 28、Orin Nano TBD — [NVIDIA-AI-IOT/nanoowl](https://github.com/NVIDIA-AI-IOT/nanoowl)
40. Jetson 實測錨點：Orin Nano Super TRT FP16 YOLO26n 4.57ms / YOLO26s 7.17ms（JP6.1, engine-only）— [Ultralytics nvidia-jetson guide](https://docs.ultralytics.com/guides/nvidia-jetson/)；YOLO26 規格 n=2.4M/5.4 GFLOPs/40.9 mAP、s=9.5M/20.7/48.6 — [YOLO26 docs](https://docs.ultralytics.com/models/yolo26/)
41. WebSearch `LVIS trained detector ONNX edge deployment`（goal Sources #3 原字串）與 `LVIS 1203 classes pretrained detector weights download ONNX export real-time` 前列結果**無一是可直接 export 的 LVIS closed-set 權重**（EdgeSAM / GDINO 1.5 Edge API-gated / Replicate YOLO-World / Ultralytics 文檔 / [OVLW-DETR](https://arxiv.org/html/2407.10655v1) / [RF-DETR](https://pypi.org/project/rfdetr/1.1.0/) 逐筆否決理由見 §4c 搜尋 1/3）— 本研究 2026-06-11 實搜
42. WebSearch `mmdetection LVIS Mask R-CNN ONNX export Jetson deployment fps` 僅得官方 changelog / deploy docs / [ONNX export issue #4247](https://github.com/open-mmlab/mmdetection/issues/4247)，**零筆 LVIS 配置 Jetson 實測**；`YOLOE YOLO-World custom vocabulary household objects … pill bottle medicine detection` 無任何居家小物實測 recall（僅論文與通用介紹文，§4c 搜尋 2/4）— 本研究 2026-06-11 實搜

---

## 11. Q1-Q9 逐題回答

**Q1：YOLOE（YOLO26 世代等價物）的 set-classes-then-export 流程？export 產物在 TRT EP 上與普通 YOLO26 ONNX 有無差異？**
YOLO26 世代等價物存在且就叫 **YOLOE26**（N/S/M/L/X，NMS-free e2e；[docs](https://docs.ultralytics.com/models/yoloe/#available-models-supported-tasks-and-operating-modes)）。流程 = `YOLOE("yoloe-26s-seg.pt")` → `set_classes([...])`（MobileCLIP2 一次性嵌入）→ `export(format="onnx")`；類別燒進權重、export 後不可再 prompt、產物行為等同標準 YOLO（[docs](https://docs.ultralytics.com/models/yoloe/) exact quotes 見 §2.1）。**差異有二**：① 全部 YOLOE 權重是 seg 任務 → 輸出多 32 欄 mask 係數 + proto tensor（參照 (1,300,38)+(1,32,160,160)，[supervision #1787](https://github.com/roboflow/supervision/issues/1787)），node 需一行級切片改動（§2.3，export 時驗證）；② class_id 表意換新 vocab，`object_perception_node.py:393-404` 類別表必換。TRT EP 路徑本身無已知差異（標準 ONNX graph）。

**Q2：YOLOE/YOLO-World 各尺寸 LVIS AP（含 rare）與 params/GFLOPs 表？**
見 §3 表。重點：YOLOE-v8-S 27.9 AP / **AP_r 22.3** / 12M（[THU-MIG README](https://github.com/THU-MIG/yoloe/blob/main/README.md)）；YOLOE-26s 29.9-31.0 AP（[arXiv 2606.03748](https://arxiv.org/html/2606.03748v1)）；YOLOE26-L 36.8 / 32.3M / 88.3 GFLOPs（[docs](https://docs.ultralytics.com/models/yoloe/)）。YOLOE26 N/S 的 params/GFLOPs/AP_r 官方未公布（finding 29 標注）。YOLO-World 被 YOLOE26 +10~11.4 AP 壓制（[docs](https://docs.ultralytics.com/models/yoloe/)），不再列表。

**Q3：自訂 30 類居家 vocab export 後，對訓練分佈外小物（藥瓶、遙控器）可靠度的可引用證據？**
遙控器不適用此問（COCO 80 內建，finding 2）。對真 OOD 類：唯一可引用 proxy 是 LVIS-rare AP — S 尺寸 22.3（[THU-MIG README](https://github.com/THU-MIG/yoloe/blob/main/README.md)），意味 rare 類單類可靠度低；**藥瓶（pill_bottle）不在 LVIS 1203 內**（[lvis.yaml](https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/cfg/datasets/lvis.yaml)），零 benchmark 證據，純靠文字嵌入泛化。社區也**未找到**可引用的居家小物實測——搜尋字串 `YOLOE YOLO-World custom vocabulary household objects real-world accuracy pill bottle medicine detection` 前列結果僅論文/官方文檔/通用介紹文，無一筆藥瓶/鑰匙/眼鏡級實測 recall（逐筆否決理由見 §4c 搜尋 4；缺席結論限於該搜尋範圍）。**此題的證據真空直接決定 verdict = NEEDS_TEST_VOCAB_REPLAY**。

**Q4：PawAI 居家類別清單 v0？COCO 80 覆蓋率？**
§1 表，38 條目（互動 26 + guardian/錨點 12；展開複合條目後 43 類）。COCO 80 覆蓋 **16/38 條目 ≈42%（21/43 類 ≈49%）**，非 COCO 缺口 22 類；LVIS 覆蓋 36/38 ≈95%（缺 pill_bottle、walker）。附帶修正：goal 痛點清單中 remote/bowl/餐具其實在 COCO 內（`coco_classes.py:84,64,61-63`）。

**Q5：PINTO zoo 有沒有 open-vocab 或 LVIS 級供給？**
**真缺席，非漏掃**：README 全文 grep 0 命中、目錄名僅 2 假陽性（`138_BackgroundMattingV2` 撞字、`336_PP-YOLOE-Plus` 是 Paddle 閉集同名異物）——本研究實測（findings 18-19）。間接供給：`472_DEIMv2-Wholebody34` 的 wheelchair/crutches **人體屬性**類（mAP 0.42-0.95，`472/README.md`）可替代 guardian 場景的拐杖/輪椅物體偵測（finding 20）。

**Q6：Grounding DINO 在 Orin Nano 的實測 FPS？（出局證據）**
Orin Nano 直接實測不存在（沒人跑得動到值得發文）；最近錨點：**AGX Orin 實測 2-3 FPS**（官方宣稱 11.6；[jetson-platform-services #3](https://github.com/NVIDIA-AI-IOT/jetson-platform-services/issues/3)）→ Orin Nano 8GB（~1/5-1/7 算力）外推 **<1 FPS**。能跑快的變體（1.5/1.6 Edge、DINO-X Edge，Orin NX 10-20 FPS）權重全部 API-gated 不可部署（[issue #24](https://github.com/IDEA-Research/Grounding-DINO-1.5-API/issues/24)）。**正式出局，此後不再提**（§5）。

**Q7：open-vocab export 模型在 Orin Nano 的 RAM/FPS 估算 vs 現役 n@640？**
§9 表。錨點 = Orin Nano Super TRT FP16：YOLO26n 4.57ms / s 7.17ms（[nvidia-jetson guide](https://docs.ultralytics.com/guides/nvidia-jetson/)）。YOLOE-26n-seg@640 估 ~7-9ms、s-seg@640 ~11-13ms、s-seg@960 ~25-30ms（外推假設：seg=det×1.6（YOLO11 世代比例）+ open-vocab +2%）；全配置 RAM 邊際 <200MB，不破 0.8GB 紀律。pipeline Hz 瓶頸在 node 前後處理（現役 6-8Hz vs engine 200+ FPS），@640 換模型對 Hz 影響可忽略。

**Q8：若走 open-vocab，上機（前的 replay）該測什麼？**
- **Vocab 清單**：§1 v0 全 38 類一次餵（測混淆上限）+ 縮減 12 類「demo 核心組」（cup/mug/bottle/water_bottle/medicine/pill bottle/remote/key/eyeglasses/person/chair/dining_table）對照（測 vocab 大小對精度的影響）；藥瓶做 prompt A/B（"pill bottle"/"medicine bottle"/"prescription bottle"）。
- **測試物件組**：實體自拍照（D435 同視角高度 ~30cm，`docs/mission/README.md:640` 遠端模擬慣例）：藥瓶、鑰匙串、眼鏡、遙控器、馬克杯+水瓶+保溫瓶同框（混淆組）、拖鞋、毛巾、拐杖；每物 0.5/1.0/1.5m 三距離；外加 demo 既有錄影重放（cup 基線對齊）。
- **量測項與門檻**：per-class recall@conf0.25（搭 ByteTrack N=3 時序確認，與 supervision spike 合併）；**pass 門檻 = demo 核心組新類在 1.0m recall ≥0.5 且容器混淆組（藥瓶↔水瓶↔杯子）誤標率 <30%**；cup 在新模型上不得比現役 baseline 退步（recall 差 <5pp）。過門檻 → 升級 GO 排上機；不過 → fallback 評估（§12 下一步）。

**Q9：哪條路線能與 goal 1 勝出配置疊加？**
**只有 open-vocab 路線能疊加，且是完美疊加**：YOLOE-26 與 YOLO26 同架構同 export 路徑（§2.2），goal 1 若選 s@960，`yoloe-26s-seg` set_classes 後 `export(imgsz=960)` 即「同一顆模型同時解尺寸與類別」（§8）。closed-set 路線在搜尋範圍內無獨立供給（§4a，搜尋紀錄 §4c），無從疊加。replay 時兩 goal 必須同 imgsz 同尺寸出數字才公平（goal 原文要求）。

---

## 12. Verdict 與下一步

### Verdict: `NEEDS_TEST_VOCAB_REPLAY`

**機制可行性已證實**（set-then-export、零 runtime 成本、YOLOE26 同世代同架構、WSL export 合法、成本不破 RAM/Hz 紀律——§2/§9），**但精度證據不足以 GO**：① rare 類 proxy AP_r ~22（S 尺寸）；② 第一痛點藥瓶連 LVIS 都沒有、零可引用數字；③ COCO 重訓類 cup 都只有 0.7m 穩，更小的 OOD 類在實用距離的 recall 無從紙面保證（§3/§6）。也**不是 NO_GO**：沒有任何證據顯示這條路過不了門檻，只是沒人測過我們要的東西。closed-set 與 transformer 路線已分別以「搜尋範圍內無獨立供給」（§4a，搜尋紀錄 §4c）與「跑不動/拿不到」（§5）排除——**replay 只需測一條路線一顆模型家族**。

### 下一步（對應 verdict 的一個具體動作）

**WSL vocab replay spike（估一個下午 + 半天拍照）**：
1. WSL `uv pip install ultralytics`（WSL 合法），下載 `yoloe-26s-seg.pt`（goal 1 對齊尺寸）+ `yoloe-26n-seg.pt`（現役對齊尺寸），照 §2.4 set_classes(§1 v0 38 類) 後先**不 export、直接 predict** 跑 Q8 的測試照與 demo 錄影；
2. 產出三個數字表：per-class recall×距離、容器混淆矩陣、cup 基線對齊（與現役 YOLO26n@640 同照片對比）；同場驗證 export ONNX 的輸出 shape（§2.3 假設）；
3. 過 Q8 門檻 → verdict 升級 `GO_YOLOE_CUSTOM_VOCAB`，帶 export 產物排上機（與 goal 1 矩陣共日）；不過 → 縮 vocab 到 LVIS-frequent 類重測一輪，再不過則 `NO_GO_STAY_COCO80` + guardian 類改走 PINTO 472 屬性線。

### 與 cross-validate 文件的矛盾標注

| # | 文件 | 矛盾/張力 | 處置 |
|---|------|----------|------|
| 1 | goal spec 本身（Bottleneck 段） | 「藥瓶、**遙控器**、眼鏡、拐杖、鑰匙、**碗筷**…全抓不到」——remote(65)/bowl(45)/fork-knife-spoon(42-44) 其實在 COCO 80 內（`coco_classes.py:84,64,61-63`），remote 還在 brain whitelist（`zh_tables.py:19`） | **前提部分失真**：這幾類的「抓不到」是 recall/距離問題（goal 1 域），非類別缺口。v0 清單已把真缺口（22 類）與假缺口分開 |
| 2 | `2026-06-11-pinto-model-zoo-pawai-fit-report.md` §3/§5a | 「object 線此 zoo 無解」原語境是 cup 遠距 | **無矛盾，結論延伸**：本研究證實類別擴充維度 zoo 同樣無解（README grep 0 命中），兩結論獨立成立、goal 的「別混淆」提醒已遵守 |
| 3 | goal spec Hard constraints「擴類別不動 contract」 | type 層成立（`class_name` 是 string，`interaction_contract.md:674`），但同節 :687 明寫「類別範圍：COCO 80 class」 | **半成立**：schema 不 break，但 contract 描述文字與 `coco_classes.py` 引用需同步更新（文件級，非 v 版升級） |
| 4 | `docs/mission/README.md:459` | 既有待辦是「室內場景 **COCO** 類別篩選」（COCO 內挑子集） | **方向升級非矛盾**：v0 清單是其 superset（COCO 內 21 類 + COCO 外 22 類，共 43 類 / 38 條目），對齊互動 70/守護 30 的場景反推而非貪多 |
| 5 | `CLAUDE.md`「ultralytics 禁裝」條目 | replay/export 需要 WSL 裝 ultralytics | **無矛盾**：禁令明文只限 Jetson（torch wheel 破壞），goal 1 spec 與 PINTO 報告 §5a 均已認定 WSL export 合法 |

---

*研究方法備註：本研究 read-only；web 證據以官方 docs（Ultralytics）、上游 repo（THU-MIG、IDEA-Research、NVIDIA-AI-IOT）、arXiv 論文為主，二手摘要（YOLOE-26n 的 23.7 AP）已標注置信度。所有 Jetson 外推均標明錨點世代與假設倍率。所有負面結論（「未找到 X」）均附搜尋字串與前列結果否決理由（§4c），缺席結論限於記錄的搜尋範圍。2026-06-11 修訂：統一覆蓋率計數單位（條目 16/38 ≈42%、類 21/43 ≈49%）、非 COCO 缺口 19→22、Finding 36 改與 §1 同源（36/38 + 6 額外詞）、行號更正（coco_classes.py 61-63、object_perception_node.py 384）、補 §4c 搜尋紀錄。*
