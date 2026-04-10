# PawAI 四人分工概覽（4/10 更新 — 居家守護犬版）

## 總方向

PawAI 的主軸已定案為**居家守護犬**。現在的任務不是補更多分散功能，而是讓所有分工共同服務三個 P0 Demo 場景：**熟人回家、使用者召喚、陌生人警戒**。

每個人負責一個感知模組，做兩件事：

1. **守護犬互動設計**：在上述場景下，「偵測到 → Go2 做什麼動作 + 說什麼話」
2. **Studio 前端頁面**：把你的模組監控頁做完整

填映射表時的思考框架：**「如果你家有一隻守護犬，它在這個場景下看到 _____ 會怎麼反應？」**

**你不需要 Jetson、Go2、攝影機。** 用自己的電腦 + 鏡頭就能開發。完成後發 PR，Roy 整合到 Jetson。

> 完整守護犬設計規格見 [`docs/superpowers/specs/2026-04-10-guardian-dog-design.md`](../../../docs/superpowers/specs/2026-04-10-guardian-dog-design.md)

---

## 四人分工表

| 負責人 | 功能 | Go2 互動設計 | Studio 前端 |
|--------|------|:----------:|:---------:|
| **鄔雨彤** | 手勢辨識 | 守護犬場景下 7 種手勢→動作映射 | `/studio/gesture` |
| **楊沛蓁** | 姿勢辨識 | 守護犬場景下 5 種姿勢→動作映射 | `/studio/pose` |
| **陳若恩** | 語音功能 | 守護犬個性 prompt + Plan B 固定台詞 15 組 | — |
| **黃旭** | 物體辨識 | 守護場景白名單 + 每物品 TTS 回應 | `/studio/object` |

> 人臉辨識 + Guardian Brain + 導航避障 + 全功能整合：[Roy 路線圖](go2-jetson/roy-roadmap.md)

---

## 守護犬場景框架（填映射表前必讀）

PawAI 是一隻居家守護犬。你填的每個映射，都要能回答：**「守護犬在這個場景下看到 _____ 會怎麼反應？」**

### 三個 P0 Demo 場景（5/16 必演）

| 場景 | 什麼時候發生 | 守護犬該做什麼 |
|------|------------|--------------|
| **熟人回家** | 人臉辨識到已註冊的家人 | 個人化問候 + 動作回應（像狗迎接主人） |
| **使用者召喚** | 手勢招手或語音呼叫 | 回應召喚 + 等待指令 + 互動（像狗聽到主人叫） |
| **陌生人警戒** | 人臉辨識到未註冊的人 | 保持距離 + 警戒姿態 + 語音提醒（像狗看到陌生人） |

### 你的模組在每個場景裡扮演什麼角色

| 場景 | 手勢（鄔雨彤） | 姿勢（楊沛蓁） | 語音（陳若恩） | 物體（黃旭） |
|------|:---:|:---:|:---:|:---:|
| 熟人回家 | 揮手→回應 | 確認站/坐狀態 | 個人化問候 | 不主動觸發 |
| 使用者召喚 | wave=注意我、stop=停 | 人坐→Go2 調整 | 自由對話/Plan B | 看到杯子→提醒 |
| 陌生人警戒 | **不回應**（守護犬不聽陌生人） | 偵測到則觀察 | 警戒語音 | 輔助判斷 |
| P1 異常偵測 | — | fallen=警報 | 緊急通知 | — |
| P1 日常待命 | — | 久坐提醒 | — | 日常物品互動 |

**填映射表時請對照這張表。** 你的映射在每個場景下都要合理，不是只在真空中設定「手勢 X → 動作 Y」。

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

### 鄔雨彤 — 手勢辨識（守護犬的「指令理解」）

> 主人用手勢指揮守護犬：招手=注意我、停=停、讚=乖。

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
2. **場景化映射表**（不只是手勢→動作，要標明「在哪個場景下」）：

| 手勢 | 場景 | Go2 動作 | TTS | 冷卻 |
|------|------|---------|-----|:----:|
| wave（揮手） | 使用者召喚 | ?（Hello? 朝向?） | ?（「我在！」?） | ? |
| stop | 任何場景 | StopMove(1003) | ?（不說話? 說「好的」?） | 無 |
| thumbs_up | 互動中 | ?（Content? Dance? WiggleHips?） | ?（「謝謝！」?） | 3s |
| ok | 互動中 | ? | ? | ? |
| victory(✌️) | 互動中 | ? | ? | ? |
| thumbs_down | ? | ? | ? | ? |
| point | 使用者召喚 | ?（轉頭? 不做?） | ? | ? |
| **陌生人場景** | 陌生人警戒 | **全部不回應**（守護犬不聽陌生人指令） | — | — |

3. Studio `/studio/gesture` 頁面 PR

**詳細文件**：[go2-jetson/gesture-wu.md](go2-jetson/gesture-wu.md)（含完整測試腳本 copy-paste 就能跑）
**前端文件**：[pawai-studio/gesture-assignment.md](pawai-studio/gesture-assignment.md)

---

### 楊沛蓁 — 姿勢辨識（守護犬的「狀態感知」）

> 守護犬隨時注意人的身體狀態：站著=正常、坐著=陪伴、跌倒=要小心。

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
2. **場景化映射表**：

| 姿勢 | 場景 | Go2 動作 | TTS | 冷卻 |
|------|------|---------|-----|:----:|
| standing | 熟人回家/日常 | ?（BalanceStand? 不做?） | ?（不說話?） | ? |
| sitting | 日常待命 | ?（Sit 跟著坐? 不做?） | ?（「你坐下了呢」?） | ? |
| sitting 超過 N 分鐘 | 日常待命 | ? | ?（「坐很久了，動一動吧」?） | ? |
| crouching | 互動中 | ?（StandDown 降低身高?） | ? | ? |
| fallen | P1 異常偵測 | StopMove(1003) | 「偵測到異常！請注意安全」 | 10s |
| bending | ? | ? | ? | ? |

> **注意**：跌倒偵測幻覺率仍高（無人時誤判衣架），Demo 建議關閉（`enable_fallen=false`）。不要把跌倒當主賣點，當次要警示即可。

3. Studio `/studio/pose` 頁面 PR

**詳細文件**：[go2-jetson/pose-yang.md](go2-jetson/pose-yang.md)（含完整測試腳本 + pose_classifier 復現）
**前端文件**：[pawai-studio/pose-assignment.md](pawai-studio/pose-assignment.md)

---

### 陳若恩 — 語音功能（守護犬的「聲音表達」）

> 守護犬會「叫」——打招呼用溫暖的、警戒用嚴肅的、日常用輕鬆的。

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
1. 調整 LLM system prompt — **PawAI 是守護犬**，不是聊天機器人。語氣要像一隻忠誠、有個性的狗。放寬字數 12→50+ 字
2. 設計 **場景化 Plan B 固定台詞**（GPU 斷線時備案，至少 15 組）
3. 測試 edge-tts 不同語音（找最適合守護犬的）

**要交的**：
1. 改好的 system prompt（含守護犬個性設定）
2. **場景化 Plan B 固定台詞表**：

| 場景 | 使用者說/做 | Go2 回答 | Go2 動作 |
|------|-----------|---------|---------|
| 熟人回家 | （人臉辨識觸發） | ?（「[名字]，你回來了！」） | Hello(1016) |
| 使用者召喚 | 「你好」 | ? | ? |
| 使用者召喚 | 「你叫什麼名字」 | ?（「我叫 PawAI！」） | ? |
| 使用者召喚 | 「坐下」 | ? | Sit(1009) |
| 使用者召喚 | 「站起來」 | ? | StandUp(1004) |
| 使用者召喚 | 「跳舞」 | ? | Dance1(1022) |
| 陌生人警戒 | （人臉辨識觸發） | ?（「偵測到不認識的人」） | BalanceStand(1002) |
| P1 異常偵測 | （跌倒觸發） | ?（「偵測到異常！已通知家人」） | StopMove(1003) |
| 日常 | 「再見」 | ? | Hello(1016) |
| 日常 | 「你幾歲」 | ? | ? |
| ...至少 15 組 | | | |

3. LLM 回覆品質測試截圖

**詳細文件**：[go2-jetson/speech-chen.md](go2-jetson/speech-chen.md)（含 SSH tunnel + LLM/ASR/TTS 測試腳本）

---

### 黃旭 — 物體辨識（守護犬的「環境認知」）

> 守護犬注意到家裡的東西，適時提醒：看到杯子→「要喝水嗎？」

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
2. 從 COCO 80 class 挑適合**居家守護場景**的白名單（不要選太多，5-8 個就夠）
3. 每個物品設計**守護犬風格的 TTS 回應**

**要交的**：
1. 每種物品辨識率測試報告
2. **場景化白名單 + TTS 映射表**：

| 物品 | 守護場景 | TTS 語音 | Go2 動作 |
|------|---------|---------|---------|
| cup 杯子 | 日常陪伴 | 「要喝水嗎？」 | 不動 |
| cell phone 手機 | 日常陪伴 | ?（「那是手機嗎？」?） | ? |
| book 書本 | 日常陪伴 | ?（「在看書呀」?） | ? |
| backpack 背包 | 陌生人警戒 | ?（輔助提高警戒?） | ? |
| laptop 筆電 | 日常 | ? | ? |
| ...你認為適合的 | | | |

> **設計原則**：守護犬關心的物品應該跟家庭生活有關（喝水、吃藥、看書），不是隨便什麼都認。

3. Studio `/studio/object` 頁面 PR

**詳細文件**：[go2-jetson/object-huang.md](go2-jetson/object-huang.md)（含完整測試腳本 + COCO 室內篩選表）
**前端文件**：[pawai-studio/object-assignment.md](pawai-studio/object-assignment.md)

---

## Go2 可用動作速查（守護犬場景對照）

| api_id | 動作 | 守護犬場景 |
|:------:|------|-----------|
| 1003 | StopMove 停止 | **任何場景** — Safety 最高優先 |
| 1004 | StandUp 站起來 | 使用者召喚（語音「站起來」） |
| 1009 | Sit 坐下 | 日常待命（主人坐我也坐）、使用者召喚 |
| 1016 | Hello 打招呼 | **熟人回家** — 迎接動作 |
| 1020 | Content 開心 | 使用者召喚（thumbs_up 正面回饋） |
| 1002 | BalanceStand 站穩 | **陌生人警戒** — 穩定注視 |
| 1017 | Stretch 伸懶腰 | 日常待命（像狗一樣伸懶腰） |
| 1022 | Dance1 跳舞 1 | 使用者召喚（開心互動） |
| 1023 | Dance2 跳舞 2 | 使用者召喚（開心互動） |
| 1021 | Wallow 打滾 | 使用者召喚（撒嬌） |
| 1033 | WiggleHips 搖屁股 | 熟人回家/使用者召喚（像狗搖尾巴） |
| 1036 | FingerHeart 比愛心 | 使用者召喚（可愛互動） |
| 1029 | Scrape 刨地 | 日常待命（像狗刨地） |
| 1032 | FrontPounce 前撲 | 使用者召喚（興奮迎接） |

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
