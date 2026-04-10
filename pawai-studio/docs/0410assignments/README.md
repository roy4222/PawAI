# PawAI 四人分工概覽（4/11 更新 — 居家互動機器狗版）

## 總方向

PawAI 的主軸已定案為**居家互動機器狗（兼具守護能力）**——**互動 70% / 守護 30%**。

**互動是核心**：手勢 / 姿勢 / 語音 / 物體辨識 → 觸發動作 or 移動。
**守護是輔助**：陌生人警告是 Demo 要演的，巡邏等雷達，跟隨寫進文件 future work。

每個人負責一個感知模組，做兩件事：

1. **互動設計**：設計自己模組的互動映射 + 擴充能力（細節 4/15 會議補齊）
2. **Studio 前端頁面**：把自己的模組監控頁做完整

填互動設計時的思考框架：**「你家有一隻會互動的機器狗，你希望它看到/聽到 _____ 時會怎麼回應？」**

**你不需要 Jetson、Go2、攝影機。** 用自己的電腦 + 鏡頭就能開發。完成後發 PR，盧柏宇整合到 Jetson。

> **系統設計規格（current）**：[`docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md`](../../../docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md)
> 4/10 守護犬 spec 已 superseded：[`docs/superpowers/specs/2026-04-10-guardian-dog-design.md`](../../../docs/superpowers/specs/2026-04-10-guardian-dog-design.md)

---

## 四人分工表

| 負責人 | 功能 | 互動設計（4/15 前） | Studio 前端 |
|--------|------|:----------:|:---------:|
| **黃旭** | 手勢辨識（**從物體換過來**）| 7 種手勢 + **模式切換設計** | `/studio/gesture` |
| **鄔雨彤** | 物體辨識（**從手勢換過來**）| 居家常見物測試 + 情境映射 | `/studio/object` |
| **楊沛蓁** | 姿勢辨識 | 5 種姿勢 + 久坐提醒邏輯 | `/studio/pose` |
| **陳如恩** | 語音功能 | 互動個性 prompt + 雲端 API fallback + Plan B 20 組 | — |

> 人臉辨識 + PawAI Brain + 導航避障 + 全功能整合：[盧柏宇路線圖](go2-jetson/roy-roadmap.md)

---

## 互動主軸框架（填映射前必讀）

PawAI 是一隻居家互動機器狗。你填的每個映射，都要能回答：**「你希望它看到/聽到 _____ 時會怎麼回應？」**

### Demo 結構（5/16 必演，3 分鐘）

| 段落 | 時間 | 內容 |
|------|:---:|------|
| **開場** | 0:10 | PawAI 安靜待命 |
| **Self Introduce（Wow Moment）** | 0:35 | 主持人「PawAI，介紹你自己」→ 6-step 自主 sequence |
| **互動主秀** ★ | 1:45 | 多模態觸發（手勢/姿勢/語音/物體）+ 熟人問候 |
| **陌生人警告（守護亮點）** | 25s | 未註冊進場 → 警戒 + Studio 推播 |
| **收尾** | 5s | 口頭補巡邏 / 跟隨等 future work |

### 互動主秀的四人角色（細節 4/15 會議定）

| 場景 | 手勢（黃旭） | 物體（鄔雨彤） | 姿勢（楊沛蓁） | 語音（陳如恩） |
|------|:---:|:---:|:---:|:---:|
| **多模態觸發** | **模式切換**（比 1/2/3）+ 指令手勢 | 情境觸發（杯子、書、手機）| 久坐提醒 + 狀態感知 | 自由對話 + Plan B |
| **熟人回家** | 揮手→回應 | 不主動 | 站/坐確認 | 個人化問候 |
| **陌生人警告** | **不回應**（不聽陌生人） | 輔助判斷（背包 → 警戒+） | 偵測但不主動 | 警戒語音 |

**互動細節（手勢模式切換、多模態 mapping、新 idea 收斂）在 4/15 會議後定案。** 先用這張表對齊大方向。

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

### 黃旭 — 手勢辨識（互動主軸 B：指令理解 + 模式切換）

> **從物體辨識換過來**。互動主軸的核心之一：透過手勢切換機器狗的運作模式（聊天/聽故事/跳舞等），並做即時指令觸發。

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

**要交的（4/15 會議前）**：
1. 每種手勢辨識率測試（7 種內建手勢，每種 10 次）
2. **手勢模式切換設計**（核心任務）：
   - 提出幾個運作模式（例：聊天 / 聽故事 / 跳舞 / 待機）
   - 每個模式對應什麼手勢觸發
   - 模式切換時 Go2 要說什麼、做什麼
3. **指令手勢映射表**：
   | 手勢 | 用途 | Go2 動作 | TTS | 冷卻 |
   |------|------|---------|-----|:----:|
   | stop | 任何場景立即停 | StopMove(1003) | ?（不說話?） | 無 |
   | thumbs_up | 正面回饋 | ?（Content/Dance?） | ?（「謝謝！」?） | 3s |
   | wave | 模式進入/注意 | ? | ? | ? |
   | point | ? | ? | ? | ? |
   | victory(✌️) | ? | ? | ? | ? |
   | thumbs_down | ? | ? | ? | ? |
   | **陌生人場景** | 全部不回應（安全） | — | — | — |
4. Studio `/studio/gesture` 頁面 PR

**詳細文件**：[go2-jetson/gesture-wu.md](go2-jetson/gesture-wu.md) ← **檔名待改**，內容要從鄔雨彤版切成黃旭版
**前端文件**：[pawai-studio/gesture-assignment.md](pawai-studio/gesture-assignment.md)

---

### 楊沛蓁 — 姿勢辨識（狀態感知層）

> 機器狗隨時注意人的身體狀態：站著=正常、坐著=陪伴、久坐=提醒、跌倒=次要警示。

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

**要交的（4/15 前）**：
1. 每種姿勢辨識結果 + 角度截圖
2. **姿勢擴充能力**（研究是否有可用模型替代手寫角度判定）
3. **久坐提醒邏輯設計**（核心任務）：
   - sitting 狀態持續計時邏輯
   - 幾分鐘觸發提醒？
   - 提醒的語氣與動作
4. **姿勢互動映射**：

| 姿勢 | 用途 | Go2 動作 | TTS | 冷卻 |
|------|------|---------|-----|:----:|
| standing | 日常 | ?（不做?） | ?（不說話?） | ? |
| sitting | 日常陪伴 | ?（Sit 跟著坐?） | ? | ? |
| sitting 超過 N 分鐘 | **久坐提醒（核心）** | ? | ?（「坐很久了，動一動吧」?） | ? |
| crouching | 互動中 | ?（StandDown 降低身高?） | ? | ? |
| fallen | 次要警示 | StopMove(1003) | 「偵測到異常！請注意安全」 | 10s |
| bending | ? | ? | ? | ? |

> **注意**：跌倒偵測幻覺率仍高（無人時誤判衣架），Demo 建議關閉（`enable_fallen=false`）。跌倒是**次要警示**，不是主賣點。

3. Studio `/studio/pose` 頁面 PR

**詳細文件**：[go2-jetson/pose-yang.md](go2-jetson/pose-yang.md)（含完整測試腳本 + pose_classifier 復現）
**前端文件**：[pawai-studio/pose-assignment.md](pawai-studio/pose-assignment.md)

---

### 陳如恩 — 語音功能（互動主軸 A：聲音表達）

> 互動主軸的核心之一：PawAI 會對話、會問候、會警告。互動語氣溫暖、警戒語氣嚴肅、日常輕鬆。

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

**要做的（4/15 前）**：
1. 調整 LLM system prompt — **PawAI 是居家互動機器狗**，不是聊天機器人。設計「互動 / 警戒 / 日常」三種語氣，放寬字數 12→50+ 字
2. **雲端 API fallback 測試**（新任務）：測試 Groq / Gemini 作為保險方案，比較延遲和品質
3. **記憶功能設計**：多輪對話上下文，讓 PawAI 記得「剛才講過什麼」
4. 設計 **場景化 Plan B 固定台詞**（GPU 斷線時備案，至少 20 組）
5. 測試 edge-tts 不同語音

**要交的**：
1. 改好的 system prompt（三種語氣 + 互動機器狗個性）
2. Groq / Gemini fallback 測試報告
3. 記憶功能設計
4. **場景化 Plan B 固定台詞表**（至少 20 組）：

| 場景 | 使用者說/做 | Go2 回答 | Go2 動作 |
|------|-----------|---------|---------|
| 熟人回家 | （人臉辨識觸發） | ?（「[名字]，你回來了！」） | Hello(1016) |
| 互動 | 「你好」 | ? | ? |
| 互動 | 「你叫什麼名字」 | ?（「我叫 PawAI！」） | ? |
| 互動 | 「坐下」 | ? | Sit(1009) |
| 互動 | 「站起來」 | ? | StandUp(1004) |
| 互動 | 「跳舞」 | ? | Dance1(1022) |
| 互動 | 「介紹自己」 | **觸發 self_introduce** | Queue: Hello→Sit→WiggleHips→Dance1→Stand→BalanceStand |
| 陌生人警戒 | （人臉辨識觸發） | ?（「偵測到不認識的人」） | BalanceStand(1002) |
| 異常偵測 | （跌倒觸發） | ?（「偵測到異常！已通知家人」） | StopMove(1003) |
| 日常 | 「再見」 | ? | Hello(1016) |
| 日常 | 「你幾歲」 | ? | ? |
| ...至少 20 組 | | | |

5. LLM 回覆品質測試截圖

**詳細文件**：[go2-jetson/speech-chen.md](go2-jetson/speech-chen.md)（含 SSH tunnel + LLM/ASR/TTS 測試腳本）

---

### 鄔雨彤 — 物體辨識（情境強化層）

> **從手勢辨識換過來**。機器狗注意到家裡的東西，適時提醒：看到杯子→「要喝水嗎？」、看到書→「在看書呀」。

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

**要做的（4/15 前）**：
1. 用自己鏡頭測試更多物品（每種 10 次，不同光線/角度）
2. 從 COCO 80 class 挑適合**居家互動場景**的白名單（不要選太多，5-8 個就夠）
3. 每個物品設計**情境式 TTS 回應**（不是單純辨識出來就念）
4. **顏色辨識探索**（新任務，會議提到）：可否在嘈雜環境用顏色牌替代語音（舉紅色=Yes）

**要交的**：
1. 每種物品辨識率測試報告
2. **情境化白名單 + TTS 映射表**：

| 物品 | 使用情境 | TTS 語音 | Go2 動作 |
|------|---------|---------|---------|
| cup 杯子 | 日常陪伴 | 「要喝水嗎？」 | 不動 |
| cell phone 手機 | 日常陪伴 | ?（「那是手機嗎？」?） | ? |
| book 書本 | 日常陪伴 | ?（「在看書呀」?） | ? |
| backpack 背包 | 可輔助陌生人警戒 | ?（提高警戒?） | ? |
| laptop 筆電 | 日常 | ? | ? |
| ...你認為適合的 | | | |

> **設計原則**：機器狗關心的物品應該跟家庭生活有關（喝水、吃藥、看書），不是隨便什麼都認。物品出現的情境比物品本身重要（例：人坐著 + 杯子 = 提醒喝水，沒人 + 杯子 = 不反應）。

3. Studio `/studio/object` 頁面 PR

**詳細文件**：[go2-jetson/object-huang.md](go2-jetson/object-huang.md) ← **檔名待改**，內容要從黃旭版切成鄔雨彤版
**前端文件**：[pawai-studio/object-assignment.md](pawai-studio/object-assignment.md)

---

## Go2 可用動作速查（互動/守護場景對照）

| api_id | 動作 | 使用情境 |
|:------:|------|-----------|
| 1003 | StopMove 停止 | **任何場景** — Safety 最高優先 |
| 1004 | StandUp 站起來 | 互動指令（語音「站起來」） |
| 1009 | Sit 坐下 | 日常待命 / 互動指令 |
| 1016 | Hello 打招呼 | **熟人回家** — 迎接動作 |
| 1020 | Content 開心 | 互動回饋（thumbs_up 正面回饋） |
| 1002 | BalanceStand 站穩 | **陌生人警戒** — 穩定注視 |
| 1017 | Stretch 伸懶腰 | 日常待命（像狗一樣伸懶腰） |
| 1022 | Dance1 跳舞 1 | 互動開心 |
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
