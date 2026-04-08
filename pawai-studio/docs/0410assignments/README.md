# PawAI 四人分工概覽（4/9 會議）

## 總方向

六核心功能已到齊，但**互動深度淺**——每個功能只有一層反應，沒有複合場景。接下來每個人負責一個功能，做兩件事：

1. **Go2 互動設計**：決定「偵測到 → Go2 做什麼動作 + 說什麼話」
2. **Studio 前端頁面**：把你的模組監控頁做完整

**你不需要 Jetson、Go2、攝影機。** 用自己的電腦 + 鏡頭就能開發。完成後發 PR，Roy 整合到 Jetson。

---

## 四人分工表

| 負責人 | 功能 | Go2 互動設計 | Studio 前端 |
|--------|------|:----------:|:---------:|
| **鄔雨彤** | 手勢辨識 | 填 7 種手勢→動作映射表 | `/studio/gesture` |
| **楊沛蓁** | 姿勢辨識 | 填 5 種姿勢→動作映射表 | `/studio/pose` |
| **陳若恩** | 語音功能 | LLM prompt 調整 + Plan B 固定台詞 15 組 | — |
| **黃旭** | 物體辨識 | 選白名單物品 + 每個物品 TTS 回應 | `/studio/object` |

> 人臉辨識 + 導航避障 + PAI Docs 網站 + 文件修訂 + 全功能整合：[Roy 路線圖](go2-jetson/roy-roadmap.md)

---

## 文件結構

```
pawai-studio/docs/0410assignments/
│
├── README.md                         ← 你正在看的（分工概覽，明天開會用）
│
├── go2-jetson/                       ← Go2 互動設計（偵測到→做什麼動作+說什麼）
│   ├── interaction-design.md         ← 總覽：Go2 全部動作 API + 四人分工連結
│   ├── gesture-wu.md                 ← 鄔雨彤：手勢辨識（模型+測試腳本+映射表）
│   ├── pose-yang.md                  ← 楊沛蓁：姿勢辨識（模型+測試腳本+映射表）
│   ├── speech-chen.md                ← 陳若恩：語音功能（ASR/LLM/TTS 全流程+Plan B）
│   └── object-huang.md              ← 黃旭：物體辨識（YOLO26n+COCO 篩選+映射表）
│
└── pawai-studio/                     ← Studio 前端頁面開發
    ├── README.md                     ← 前端環境啟動 + Mock Server + Hook/Store 用法
    ├── gesture-assignment.md         ← 鄔雨彤：/studio/gesture 頁面
    ├── pose-assignment.md            ← 楊沛蓁：/studio/pose 頁面
    ├── object-assignment.md          ← 黃旭：/studio/object 頁面
    └── face-assignment.md            ← Roy：/studio/face 頁面（參考用）
```

---

## 每個人要做什麼

### 鄔雨彤 — 手勢辨識

| 項目 | 內容 |
|------|------|
| 模型 | MediaPipe Gesture Recognizer |
| 安裝 | `pip install mediapipe opencv-python` |
| 測試方式 | 鏡頭放 30cm 高，站在 1-2m 前比手勢 |
| 內建手勢 | Thumb_Up / Thumb_Down / Open_Palm / Closed_Fist / Victory / Pointing_Up / ILoveYou（7 種） |
| 目前映射 | 只有 3 個（stop / ok / thumbs_up），其他什麼都不做 |
| 參考程式碼 | `vision_perception/vision_perception/gesture_classifier.py`（100 行） |
|  | `vision_perception/vision_perception/gesture_recognizer_backend.py`（146 行） |
|  | `vision_perception/vision_perception/event_action_bridge.py`（動作映射） |
| 已知限制 | 有效距離 ~2m、僅單人、鏡頭需看到上半身（~1.5m 距離） |

**要交的**：
1. 每種手勢辨識率測試（10 次中幾次成功）
2. 手勢→Go2 動作 + TTS 映射表（例：Victory → Dance1 + 「耶！」）
3. Studio `/studio/gesture` 頁面 PR

**詳細文件**：[go2-jetson/gesture-wu.md](go2-jetson/gesture-wu.md)（含完整測試腳本 copy-paste 就能跑）
**前端文件**：[pawai-studio/gesture-assignment.md](pawai-studio/gesture-assignment.md)

---

### 楊沛蓁 — 姿勢辨識

| 項目 | 內容 |
|------|------|
| 模型 | MediaPipe Pose |
| 安裝 | `pip install mediapipe opencv-python numpy` |
| 測試方式 | 鏡頭放地上/桌上，站在 1.5-3m 前做站/坐/蹲/倒 |
| 支援姿勢 | standing / sitting / crouching / fallen / bending（5 種） |
| 目前映射 | 只有 1 個（fallen → TTS「偵測到跌倒」），其他什麼都不做 |
| 參考程式碼 | `vision_perception/vision_perception/pose_classifier.py`（114 行，**建議直接看**） |
|  | `vision_perception/vision_perception/event_action_bridge.py`（動作映射） |
| 已知限制 | 僅單人、幻覺問題（無人時誤判衣架為 fallen）、側面坐姿不準 |

**要交的**：
1. 每種姿勢辨識結果 + 角度截圖
2. 姿勢→Go2 動作 + TTS 映射表（例：sitting → Go2 也 Sit + 「你坐下了呢」）
3. Studio `/studio/pose` 頁面 PR

**詳細文件**：[go2-jetson/pose-yang.md](go2-jetson/pose-yang.md)（含完整測試腳本 + pose_classifier 復現）
**前端文件**：[pawai-studio/pose-assignment.md](pawai-studio/pose-assignment.md)

---

### 陳若恩 — 語音功能

| 項目 | 內容 |
|------|------|
| ASR 模型 | SenseVoice Small（FunASR），GPU server `140.136.155.5:8001` |
| LLM 模型 | Qwen2.5-7B-Instruct（vLLM），GPU server `140.136.155.5:8000`，OpenAI 相容 API |
| TTS 模型 | edge-tts（微軟雲端），`pip install edge-tts`，本機直接跑 |
| 連線方式 | `ssh -f -N -L 8001:localhost:8001 -L 8000:localhost:8000 帳號@140.136.155.5` |
| 目前問題 | 回答限 12 字太短、沒個性、沒多輪記憶 |
| 參考程式碼 | `speech_processor/speech_processor/llm_bridge_node.py`（624 行，**看 SYSTEM_PROMPT 行 68-94**） |
|  | `speech_processor/speech_processor/llm_contract.py`（P0 技能 + BANNED 動作） |
|  | `scripts/sensevoice_server.py`（ASR server） |
| 已知限制 | 本地 ASR/LLM 完全不可用，全依賴雲端，GPU 曾斷線 2 次 |

**語音架構流程**：

```
筆電麥克風 → Studio WebSocket → Gateway(Jetson:8080)
  → SenseVoice Cloud ASR(:8001) ~430ms
  → Intent 分類 → Qwen2.5-7B LLM(:8000) ~1.5s
  → edge-tts ~0.7s → USB 喇叭播放
E2E 總延遲：~2 秒
```

**要做的**：
1. 調整 LLM system prompt（放寬字數 12→50+、加入 PawAI 個性、自我介紹能力）
2. 設計 Plan B 固定台詞（GPU 斷線時備案，至少 15 組問答）
3. 測試 edge-tts 不同語音（找最適合機器狗的）

**要交的**：
1. 改好的 system prompt
2. Plan B 固定台詞表（15 組：使用者說什麼 → Go2 回什麼 + 做什麼動作）
3. LLM 回覆品質測試截圖

**詳細文件**：[go2-jetson/speech-chen.md](go2-jetson/speech-chen.md)（含 SSH tunnel + LLM/ASR/TTS 測試腳本）

---

### 黃旭 — 物體辨識

| 項目 | 內容 |
|------|------|
| 模型 | YOLO26n（Jetson）/ yolo11n（本機測試，COCO class 相同） |
| 安裝 | `pip install ultralytics opencv-python` |
| 測試方式 | 鏡頭放 30cm 高，拿物品到鏡頭前。**一定要開燈！** |
| 目前映射 | 只有 1 個（cup → 「你要喝水嗎？」），其他什麼都不說 |
| 參考程式碼 | `object_perception/object_perception/object_perception_node.py` |
|  | `object_perception/object_perception/yolo_detector.py` |
|  | `interaction_executive/interaction_executive/state_machine.py`（物體→TTS） |
| 已知限制 | 光線不足小物體不行、平放扁平物困難、Nano 版小物件偵測率低 |

**實測結果**（Roy 已驗證）：

| 物品 | 結果 | 備註 |
|------|:----:|------|
| cup 杯子 | ✅ | 穩定 |
| cell phone 手機 | ✅ | 適當光線 |
| book 書本 | ⚠️ | 翻開才行 |
| backpack 背包 | ✅ | 大物件 |
| laptop 筆電 | ✅ | 大物件 |
| bottle 水瓶 | ❌ | 已確認失敗，不展示 |

**要做的**：
1. 用自己鏡頭測試更多物品（每種 10 次，不同光線/角度）
2. 從 COCO 80 class 挑適合室內 Demo 的白名單
3. 每個物品設計 TTS 回應（例：laptop → 「那是筆電嗎？」）

**要交的**：
1. 每種物品辨識率測試報告
2. 白名單 + TTS 映射表
3. Studio `/studio/object` 頁面 PR

**詳細文件**：[go2-jetson/object-huang.md](go2-jetson/object-huang.md)（含完整測試腳本 + COCO 室內篩選表）
**前端文件**：[pawai-studio/object-assignment.md](pawai-studio/object-assignment.md)

---

## Go2 可用動作速查

| api_id | 動作 | 適合場景 |
|:------:|------|---------|
| 1003 | StopMove 停止 | stop 手勢、緊急 |
| 1004 | StandUp 站起來 | 語音「站起來」 |
| 1009 | Sit 坐下 | 語音「坐下」 |
| 1016 | Hello 打招呼 | 人臉辨識、揮手 |
| 1020 | Content 開心 | thumbs_up、正面回饋 |
| 1017 | Stretch 伸懶腰 | 可愛 |
| 1022 | Dance1 跳舞 1 | 慶祝 |
| 1023 | Dance2 跳舞 2 | 慶祝 |
| 1021 | Wallow 打滾 | 撒嬌 |
| 1033 | WiggleHips 搖屁股 | 開心 |
| 1036 | FingerHeart 比愛心 | 可愛 |
| 1029 | Scrape 刨地 | 模仿狗 |
| 1032 | FrontPounce 前撲 | 興奮 |

> 🚫 **禁止使用**：FrontFlip(1030) / FrontJump(1031) / Handstand(1301)（危險，會摔）

完整動作清單見 [go2-jetson/interaction-design.md](go2-jetson/interaction-design.md)

---

## Studio 前端開發

前端開發不需要 Jetson。一鍵啟動：

```bash
bash pawai-studio/start.sh
# → http://localhost:3000/studio（前端）
# → http://localhost:8080（Mock Server，模擬所有後端資料）
```

Mock Server 每 2 秒推送隨機事件，五大模組都有。詳見 [pawai-studio/README.md](pawai-studio/README.md)。

---

## 交付方式

| 方式 | 說明 |
|------|------|
| **最簡單** | LINE 群組貼映射表文字 |
| **建議** | 在你的 branch 編輯文件 → push → 發 PR |
| **Git branch** | `git checkout -b studio/你的名字`，只改自己的檔案 |

**deadline**：4/13 前至少交映射表。Studio 頁面持續開發到 5/18。

---

## 已知全域限制（所有人要知道）

- **鏡頭高度**：Go2 的 D435 攝影機在頭上，須保持 ~1.5m 距離才看到上半身
- **僅單人**：人臉 / 手勢 / 姿勢都只支援單人，多人會混亂
- **幻覺問題**：人臉和姿勢無人時偶爾誤判（鎖定衣架/物體）
- **光線**：物體辨識小物件需充足光線，Demo 必須開燈
- **供電不穩**：Jetson 在 Go2 上反覆斷電（8+ 次），Demo 有斷電風險
- **GPU 雲端不穩**：語音全依賴雲端，斷線就只剩 Plan B 固定台詞
