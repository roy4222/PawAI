# Jetson MVP 語音功能測試手冊

> 適用對象：PawAI 語音模組、整合測試、展示前驗收  
> 適用平台：NVIDIA Jetson Orin Nano 8GB + ROS2 Humble + Unitree Go2  
> 目標期限：2026/4/13 Demo 前完成 Jetson 端 MVP 驗證  
> 測試主線（2026-03-11 決策凍結）：`no-VAD -> ASR -> Intent -> (Template/LLM) -> TTS`

---

## 1. 文件目的

本文件用於 Jetson Orin Nano 8GB 上之語音互動 MVP 測試與展示前驗收，重點在於以最小可行鏈路驗證 PawAI 語音模組是否可在實機整合情境下穩定運作。

測試範圍涵蓋 ASR、Intent、TTS、LLM 與端到端閉環；VAD 目前列為次要實驗路徑，不列入展示主線必要條件。驗收以可重複執行穩定性、可展示延遲與資源壓力可控為優先。

**逐階段驗證目標：**

1. no-VAD 主線可穩定接收語音輸入並產生可用文字
2. ASR 能將中文短句轉為文字
3. Intent Rule 能將固定語句映射成可執行意圖
4. TTS 能將回覆文字轉成語音並經 Go2 播放
5. LLM 能在 Jetson 上完成簡短回覆生成並接上 TTS（非主路徑必要）
6. 端到端流程延遲控制在展示可接受範圍內

### 1.1 Phase 0（今日凍結項）

本輪先凍結三件事，作為後續 Phase 1-6 的唯一基準：

- 主用事件 topic：`/event/speech_intent_recognized`
- `session_id` 串流規範：VAD -> ASR -> Intent -> TTS 全鏈路可追蹤
- Foxglove 觀測策略：只看低頻關鍵 topic，先不開高流量影像/點雲

> 若實作與本節不一致，先回到本節修正契約，再進行下一個 Phase。

### 1.2 路徑決策凍結（2026-03-11）

本專案目前採用 **no-VAD-first** 策略，目標是先確保 4/13 前展示主線穩定可重現。

- 主路徑（預設）
  - `no-VAD -> ASR -> Intent -> (Template/LLM) -> TTS`
  - 啟動腳本：`scripts/start_asr_tts_no_vad_tmux.sh`
- 次路徑（僅受控驗證）
  - `VAD -> ASR -> Intent -> TTS`
  - 僅用於實驗與診斷，不作為展示成敗關鍵入口

**非協商操作規則：**

1. 同時間只允許一套 speech session（禁止混跑）
2. 每輪測試前必須 clean-start（tmux + process 全清）
3. 每輪測試後必須做 snapshot（無 snapshot 不算有效結果）

**VAD 升格回主路徑門檻（未達成前不得升格）：**

- 連續 50 輪無 `PaErrorCode -9998/-9985/-9997`
- 無 session contamination（上一輪狀態不污染下一輪）
- VAD 失敗可在同輪回退 no-VAD，且主流程可完成
- `speech_start/speech_end` 在一般室內噪音下可穩定成對

---

## 2. 系統總覽

### 2.1 硬體與執行環境

- Jetson：NVIDIA Jetson Orin Nano 8GB
- 麥克風：USB microphone
- 機器人：Unitree Go2
- 視覺感測：Intel RealSense D435
- 人臉偵測：YuNet
- ROS2：Humble
- 語音流程：主線採 no-VAD sequential pipeline（VAD 為次路徑）

### 2.2 MVP 模型配置

| 模組 | 選型 | 預估記憶體占用 | 備註 |
|------|------|------------------|------|
| VAD | Silero VAD | CPU 為主，極低 | 常駐輕量 |
| ASR | Whisper Tiny | 約 0.4 GB | 中文短句、離線降級 |
| Intent | Rule-based | 可忽略 | 固定指令映射 |
| LLM | Qwen3.5-0.8B INT4 | 約 1.0 GB | 短回覆、輕量推理 |
| TTS | MeloTTS | 約 0.8 GB | 中文自然度佳 |

> **注意**：Jetson 為統一記憶體架構（Unified Memory），CPU 與 GPU 共享同一記憶體池。本文件所述「記憶體占用」皆指此共享池之總占用，非獨立 VRAM。

### 2.3 記憶體預算建議

> Jetson 8GB 需同時承載系統、ROS2、D435、YuNet 與語音模組，建議保留安全餘量，避免在展示現場因記憶體壓力導致節點被殺或延遲暴增。

| 項目 | 預估占用 |
|------|----------|
| Ubuntu + ROS2 基礎系統 | 1.5 - 2.0 GB |
| RealSense D435 + 影像串流 | 0.6 - 1.0 GB |
| YuNet / 視覺節點 | 0.3 - 0.8 GB |
| Whisper Tiny | ~0.4 GB |
| Qwen3.5-0.8B INT4 | ~1.0 GB |
| MeloTTS | ~0.8 GB |
| 其他 ROS2 節點與緩衝 | 0.5 - 1.0 GB |

### 2.4 記憶體控制原則

- 建議展示模式總記憶體使用量不要長時間逼近 8GB 上限
- 若同時啟用 D435、YuNet、ASR、LLM、TTS，應保留至少 0.8 - 1.2 GB 餘量
- 展示模式原則上不允許 swap 長時間活躍
- 若 `tegrastats` 顯示長時間高壓（>90%）且延遲抖動，視為不通過
- 若出現 OOM、推理抖動或節點無回應，優先關閉非必要視覺/除錯節點

### 2.5 Sequential Pipeline 執行原則

本系統採 **單輪串行處理** 架構，嚴格限制如下：

| 規則 | 說明 |
|------|------|
| **單階段執行** | 同一時間只允許一個主推理階段進行：ASR、LLM、TTS 不應重疊執行 |
| **輪次隔離** | 新的語音輸入在上一輪 TTS 完成前，預設不觸發下一輪完整互動 |
| **打斷機制** | 若需支援打斷（barge-in），應另外定義 interrupt 機制，MVP 階段不納入主線 |
| **狀態管理** | 各階段應明確標示狀態（IDLE → LISTENING → ASR → LLM → TTS → IDLE），避免狀態混亂 |

> **設計理由**：Jetson 8GB 統一記憶體架構下，並行執行多個 AI 模型極易導致記憶體碎片與延遲抖動。串行處理可確保資源集中，提升展示穩定性。

---

## 3. ROS2 Topic 命名約定

### 3.1 本文件採用的語音 Topic

| Topic | 用途 | 備註 |
|-------|------|------|
| `/tts` | TTS 輸入文字 | 已存在於 repo |
| `/webrtc_req` | 傳送語音或動作命令到 Go2 | 已存在於 repo |
| `/asr_result` | ASR 文字輸出 | MVP 測試建議 topic |
| `/intent` | Rule-based intent 輸出 | MVP 測試建議 topic |
| `/state/interaction/speech` | 語音狀態 | 架構文件已定義 |
| `/state/executive/brain` | 大腦狀態 | 架構文件已定義 |

### 3.2 語音事件 Topic 對照

本專案目前存在兩種命名，測試文件統一說明如下：

| Topic | 狀態 | 說明 |
|-------|------|------|
| `/event/speech_intent_recognized` | 主要採用 | 與 `README.md` 一致，MVP 測試主用 |
| `/event/speech_intent` | 契約版名稱 | 與 `docs/architecture/interaction_contract.md` 一致 |

### 3.3 建議做法

- 測試時優先觀察 `/event/speech_intent_recognized`
- 若後續模組統一契約命名，可同步對應 `/event/speech_intent`
- 測試報告中建議明寫「目前執行用 topic 名稱」避免整合誤解

### 3.4 MVP 測試 Topic 定案

**本文件 MVP 測試正式採用：**

| Topic | 用途 | 優先順序 |
|-------|------|----------|
| `/event/speech_intent_recognized` | 語音意圖識別事件 | **主要採用（P0）** |
| `/tts` | TTS 輸入文字 | **主要採用（P0）** |
| `/asr_result` | ASR 文字輸出 | **主要採用（P0）** |
| `/intent` | Rule-based intent 輸出 | **主要採用（P0）** |

**契約對照保留（相容用途）：**

| Topic | 用途 | 狀態 |
|-------|------|------|
| `/event/speech_intent` | 語音意圖事件（契約版） | 若模組統一後採用，本文件同步更新 |

> **整合注意**：測試時若發現程式實際發布 topic 與上表不一致，應以「程式實際行為」為準，並記錄於測試報告備註欄。

### 3.5 `session_id` 串流契約（Phase 0 凍結）

為了讓單輪語音請求在 Foxglove 與測試報告可追蹤，定義以下規則：

- 一次語音互動（從 `speech_start` 到 TTS 完成）只使用一個 `session_id`
- 同一輪中的 ASR、Intent、TTS 狀態都必須帶上相同 `session_id`
- 若某節點無法在 payload 直接帶欄位，至少要在 log 帶出 `session_id`（含時間戳）
- `session_id` 建議格式：`sp-YYYYMMDD-HHMMSS-<4hex>`，例如 `sp-20260309-164530-a1f9`

建議串流對照：

| 階段 | 建議 topic | 最低要求 |
|------|------------|----------|
| VAD | `/state/interaction/speech` | `speech_start/speech_end` 可對應同一輪 |
| ASR | `/asr_result` | 可對應本輪 `session_id` |
| Intent | `/intent`、`/event/speech_intent_recognized` | 可對應本輪 `session_id` |
| TTS | `/tts`、`/webrtc_req` | 可對應本輪 `session_id` 或同時序關聯 |

### 3.6 Foxglove 觀測範圍（Phase 0 凍結）

Foxglove 在開發期用於觀測，不納入主流程依賴。為避免 Jetson 資源抖動，先凍結以下規則：

- 只觀測低頻關鍵 topic：`/state/interaction/speech`、`/asr_result`、`/intent`、`/event/speech_intent_recognized`、`/tts`
- 不在語音測試同時監看高流量 topic：影像（`/camera/*`）、點雲（`/point_cloud*`）
- 開發/除錯可 `foxglove:=true`；Demo 基線預設 `foxglove:=false`
- 若出現延遲飆升或掉訊，第一優先動作是關閉 Foxglove 或縮減觀測 topic

建議最小面板：

| 面板 | Topic | 用途 |
|------|-------|------|
| Raw Messages | `/state/interaction/speech` | 看 VAD 狀態流轉 |
| Raw Messages | `/asr_result` | 看轉寫結果與時間差 |
| Raw Messages | `/event/speech_intent_recognized` | 看意圖事件是否發布 |
| Raw Messages | `/tts` | 看回覆是否進入語音輸出 |
| Raw Messages | `/webrtc_req` | 看 Go2 播放請求是否送出 |

---

## 4. 測試環境準備

### 4.1 Jetson 基本連線確認

```bash
ssh jetson-nano "hostname && uname -a"
```

```bash
ssh jetson-nano "free -h"
```

```bash
ssh jetson-nano "python3 --version"
```

```bash
ssh jetson-nano "source /opt/ros/humble/setup.bash && ros2 --help >/dev/null && echo ROS2_OK"
```

### 4.2 專案同步確認

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && git status --short"
```

### 4.3 Jetson 建置指令

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && colcon build --packages-select speech_processor go2_robot_sdk"
```

若後續已補上 ASR / Intent / LLM 相關套件，可改用：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && colcon build --packages-select speech_processor go2_robot_sdk go2_interfaces"
```

若要完整驗證語音與現場整合，可在 Jetson 做完整 build：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && colcon build"
```

### 4.4 ROS2 環境載入模板

以下指令格式應在本文件各階段統一使用：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && <your command>"
```

---

## 5. 硬體檢查清單

### 5.1 Jetson 本體

- [ ] Jetson 已正常開機
- [ ] 電源供應穩定
- [ ] 散熱風扇正常運作
- [ ] 網路可正常 ssh 連線

### 5.2 USB 麥克風

- [ ] 麥克風已插入 Jetson
- [ ] `arecord -l` 可看到裝置
- [ ] ALSA 可錄到音
- [ ] 在一般環境音與人聲下可穩定輸入

檢查指令：

```bash
ssh jetson-nano "arecord -l"
```

簡單錄音測試：

```bash
ssh jetson-nano "timeout 5 arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 /tmp/test_mic.wav && ls -lh /tmp/test_mic.wav"
```

### 5.3 Go2

- [ ] Go2 已開機
- [ ] `ROBOT_IP` 正確
- [ ] Jetson 可與 Go2 通訊
- [ ] WebRTC 模式正常

### 5.4 RealSense D435

- [ ] D435 已接上
- [ ] 視覺串流可啟動
- [ ] 與語音流程同時運作時不會造成系統過載

---

## 6. Phase 1: VAD + 麥克風輸入測試

### 6.1 目標

驗證 USB 麥克風輸入正常，且 VAD 能穩定區分「有人說話」與「環境噪音」，避免誤觸發或漏觸發。

### 6.2 前置條件

- USB 麥克風已接妥
- Jetson 可錄音
- VAD node 或測試腳本已可執行
- ROS2 環境已 source

### 6.3 啟動指令

若已有 VAD ROS2 node：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run speech_processor vad_node"
```

若目前尚未有正式 node，至少先做錄音裝置確認：

```bash
ssh jetson-nano "arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/vad_check.wav && ls -lh /tmp/vad_check.wav"
```

建議同步開一個觀察視窗：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list"
```

若 VAD 有輸出狀態 topic，建議觀察：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /state/interaction/speech"
```

### 6.4 測試步驟

1. 在安靜環境下啟動 VAD，觀察是否持續誤判為 speaking
2. 在正常音量下說出 2 到 3 秒短句，觀察是否有 speech start / end
3. 播放背景雜音，確認是否出現大量誤觸發
4. 測試不同距離（30cm、60cm、100cm）的人聲輸入
5. 記錄每次輸入是否能穩定切出語音片段

建議測試句：

- 「哈囉，小狗」
- 「請坐下」
- 「請轉一圈」
- 「你現在在做什麼」

### 6.5 觀察指標

- VAD 是否能偵測 speech start
- VAD 是否能偵測 speech end
- 安靜環境是否誤觸發
- 背景噪音下是否仍可偵測人聲
- 語音切段是否過早或過晚

### 6.6 成功標準

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 安靜環境誤觸發 | 30 秒內 0 次 | ≤ 1 次 | > 1 次 |
| 正確切段率 | 10/10 | ≥ 9/10 | < 9/10 |
| 背景雜音誤觸發 | 10 次中 0 次 | ≤ 2 次 | > 2 次 |
| speech end 延遲 | < 0.3s | ≤ 0.5s | > 0.5s |
| 語音截斷 | 無明顯截斷 | 輕微截斷可接受 | 嚴重截斷 |

**驗收準則：**
- 所有指標達到「可接受值」即視為該 Phase 通過
- 達到「理想值」標註為優秀，但不影響通過與否
- 任一指標落入「不通過」欄位，該 Phase 視為失敗

### 6.7 失敗排查

- 用 `arecord -l` 確認麥克風卡號是否正確
- 降低背景噪音，確認是否為現場環境造成
- 檢查錄音採樣率是否為 16kHz mono
- 若過度敏感，調整 VAD threshold 或最小語音長度
- 若完全無法觸發，先確認 ALSA 音源是否真的有輸入

### 6.8 2026-03-09 實測補充（Jetson + USB MIC V1）

本日實測已確認 Phase 1 可跑通，關鍵問題與解法如下。

#### 問題與根因

| 問題 | 根因 | 解法 |
|------|------|------|
| `ros2` 指令不存在 | 在 `zsh` 使用 `.bash` 環境腳本，導致 ROS 環境未正確載入 | 使用 `setup.zsh` 而非 `setup.bash` |
| VAD 無事件觸發 | `sounddevice` default 裝置不是 USB 麥克風 | 明確指定 `input_device:=0`（USB MIC V1） |
| 麥克風 44.1k 與 VAD 16k 不相容 | Silero VAD 僅支援 8k/16k | 在 `vad_node` 內做即時重取樣（44100 -> 16000） |

#### 實測可用啟動方式（baseline）

```bash
source /opt/ros/humble/setup.zsh
source /home/jetson/elder_and_dog/install/setup.zsh
ros2 run speech_processor vad_node --ros-args \
  -p input_device:=0 \
  -p sample_rate:=16000 \
  -p capture_sample_rate:=44100 \
  -p frame_samples:=512 \
  -p vad_threshold:=0.25 \
  -p min_silence_ms:=150
```

#### 驗收結果（已確認）

- `/event/speech_activity` 持續出現成對的 `speech_start` / `speech_end`
- 每輪事件都有 `session_id`（可追蹤單輪互動）
- `/state/interaction/speech` 狀態流正常更新

#### 裝置檢查指令（必要時）

```bash
python3 - <<'PY'
import sounddevice as sd
print("default:", sd.default.device)
for i, d in enumerate(sd.query_devices()):
    if d['max_input_channels'] > 0:
        print(i, d['name'], "default_sr=", d['default_samplerate'])
PY
```

> 若 `default` 不是 USB 麥克風，務必在啟動參數指定 `input_device`。

---

## 7. Phase 2: ASR Node 測試 (Whisper Tiny)

### 7.1 目標

驗證 Whisper Tiny 能在 Jetson 上將短句中文語音轉為文字，並輸出到 `/asr_result` 供後續 Intent 使用。

### 7.2 前置條件

- Phase 1 已通過
- Whisper Tiny 已部署於 Jetson
- ASR node 可啟動
- 音訊輸入可從 VAD 或測試 wav 提供

### 7.3 啟動指令

目前 Phase 2 已提供獨立 ASR node（`asr_node`）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor asr_node --ros-args -p model_name:=tiny -p language:=zh"
```

若要確認 VAD 到 ASR 的音訊片段串流：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /audio/speech_segment"
```

觀察 ASR 輸出：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /asr_result"
```

必要依賴（至少擇一 ASR backend）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && uv pip install faster-whisper"
```

若 `faster-whisper` 不可用，可改用：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && uv pip install openai-whisper"
```

### 7.4 測試步驟

1. 啟動 ASR node
2. 用 5 句固定中文指令做測試
3. 每句重複 3 次，觀察辨識穩定度
4. 記錄辨識結果是否可被人類直接理解
5. 若支援時間戳，記錄從 speech end 到 `/asr_result` 發布所需時間

建議測試句：

- 「請站起來」
- 「請坐下」
- 「請跟我打招呼」
- 「你叫什麼名字」
- 「今天天氣怎麼樣」

### 7.5 觀察指標

- `/asr_result` 是否有輸出
- 輸出內容是否接近原句
- 重複測試時是否穩定
- ASR 延遲是否可接受
- 是否因背景噪音嚴重誤辨

### 7.6 成功標準

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 固定指令辨識率 | 15/15 | ≥ 12/15 | < 12/15 |
| 辨識延遲 | 0.2 - 0.8s | ≤ 1.2s | > 1.2s |
| 結果可用性 | 全部可直接使用 |  intent 可解析 | 無法供 Intent 使用 |
| 卡住情況 | 無 | 偶發（< 2次）| 頻繁卡住 |

**測試句建議（15次分配）：**
- 「請站起來」× 3
- 「請坐下」× 3
- 「請跟我打招呼」× 3
- 「你叫什麼名字」× 3
- 「今天天氣怎麼樣」× 3

### 7.7 失敗排查

- 確認輸入音訊格式與模型需求一致
- 確認音檔長度沒有被 VAD 截過短
- 若中文辨識品質差，優先確認語音音量與麥克風距離
- 觀察記憶體是否不足導致推理速度異常
- 若節點未輸出，檢查 node log 與 `/asr_result` topic 是否一致

### 7.8 2026-03-09 實測進度（Phase 2）

本日已完成 VAD -> ASR 串流打通，重點如下。

#### 已完成項目

- `faster-whisper` 安裝成功（Jetson 以 `pip3 --user` 路線）
- `asr_node` 可正常啟動，backend 顯示 `faster_whisper`
- `/audio/speech_segment`、`/state/interaction/asr`、`/asr_result` 三條 topic 均存在
- `/state/interaction/asr` 可穩定看到 `processing -> done`
- `/asr_result` 已有實際中文轉寫內容（非全空）

#### 實測觀察

- 已確認不是串流故障，屬於可用狀態
- 仍有少量空字串結果（常見於語音片段過短或切段偏碎）
- 當前階段建議：先往 Phase 3（Intent）推進，精度/延遲調優可在整鏈打通後集中處理

#### 當前 baseline（可重現）

VAD 參數：

- `input_device:=0`
- `sample_rate:=16000`
- `capture_sample_rate:=44100`
- `frame_samples:=512`
- `vad_threshold:=0.25`
- `min_silence_ms:=150`

ASR 參數：

- `model_name:=tiny`
- `language:=zh`

> 備註：若後續空字串比例偏高，可優先試 `vad_threshold=0.28~0.32`、`min_silence_ms=220~300`。

---

## 8. Phase 3: Intent Rule 測試

### 8.1 目標

驗證規則式 Intent 能將 ASR 輸出文字穩定映射到固定意圖，並發布到 `/intent` 或 `/event/speech_intent_recognized`。

### 8.2 前置條件

- Phase 2 已可穩定輸出 `/asr_result`
- 已定義 MVP 固定指令集
- Intent 規則已建立關鍵字映射

### 8.3 啟動指令

目前 Phase 3 建議使用獨立 `intent_node`（訂閱 `/asr_result`）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor intent_node"
```

若要觀察 intent 狀態：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /state/interaction/intent"
```

觀察建議 topic：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /intent"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /event/speech_intent_recognized"
```

若契約版名稱已採用，也可確認：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /event/speech_intent"
```

### 8.4 測試步驟

1. 使用固定指令集逐句測試
2. 檢查每句文字是否映射到正確 intent label
3. 測試同義詞或口語句型是否仍能落到同一 intent
4. 檢查未知語句是否回傳 fallback
5. 對照 ASR 結果，確認是 ASR 問題還是 Intent 規則問題

建議 intent 集：

| 測試句 | 預期 intent |
|--------|-------------|
| 請站起來 | `stand` |
| 請坐下 | `sit` |
| 跟我打招呼 | `hello` |
| 停止 | `stop` |
| 你是誰 | `chat` 或 `qa` |

### 8.5 觀察指標

- `/intent` 是否穩定輸出
- `/event/speech_intent_recognized` 是否有事件發布
- 未知語句是否進入 fallback
- 是否出現錯誤映射
- 事件延遲是否足夠短

### 8.6 成功標準

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 固定指令映射率 | 10/10 | ≥ 9/10 | < 9/10 |
| 同義詞誤判率 | 0/10 | ≤ 2/10 | > 2/10 |
| 危險動作誤觸發 | 0 次 | 0 次 | > 0 次 |
| Intent 延遲 | < 50ms | ≤ 100ms | > 100ms |
| Fallback 機制 | 全部正確落入 | 大部分正確 | 無法正確 fallback |

**危險動作定義**：`move`、`navigate`、`dance` 等可能造成機器人位移或劇烈動作的 intent。此類 intent 必須設為高門檻匹配，MVP 階段建議暫不開放。

### 8.7 失敗排查

- 先確認 `/asr_result` 內容是否正確
- 檢查規則字典是否漏掉常見口語詞
- 將危險動作 intent 設為高門檻匹配
- 若 topic 沒有輸出，確認 node 內實際發布名稱是 `/intent`、`/event/speech_intent_recognized` 或 `/event/speech_intent`
- 若規則與 ASR 互相干擾，先固定輸入文字做單元測試

### 8.8 2026-03-09 實測進度（Phase 3）

本日已完成 ASR -> Intent 串流打通，重點如下。

#### 已完成項目

- `intent_node` 可正常啟動（訂閱 `/asr_result`）
- `/intent` 與 `/event/speech_intent_recognized` 均有持續輸出
- 已確認 intent label 可命中：`sit`、`stand`、`hello`、`stop`、`chat`
- `session_id` 在 ASR 與 Intent 事件中可對應同一輪

#### tmux 觀察補充

- `speech-mvp` 目前採 6 pane 監看（VAD/ASR/Intent + 3 個 topic echo）
- 畫面看起來像 4 pane 通常是 tiled 佈局下部分 pane 過窄，不代表程式退出
- 實際判斷請以 `tmux list-panes -t speech-mvp -F '#{pane_index} dead=#{pane_dead}'` 為準（本次為 `0~5` 且 `dead=0`）

#### 實測結果摘要

- Phase 3 已達成「可用閉環」：`VAD -> ASR -> Intent`
- 目前仍有 `unknown` 比例偏高情況（主要受 ASR 誤辨與規則覆蓋率影響）
- 這屬於命中率調優問題，非串流故障

#### 下一步建議（調優）

1. 先用固定 5 句標準句反覆測試（hello/sit/stand/stop/chat）
2. 依誤辨詞擴充 `intent_node` 關鍵字規則
3. 視情況將 `min_confidence` 由 `0.55` 下修至 `0.45` 做 A/B 比較

> 建議策略：先穩定通鏈路，再集中做命中率優化，避免每個 Phase 重複調參。

---

## 9. Phase 4: TTS Provider 測試 (MeloTTS)

### 9.1 目標

驗證 TTS 能接收文字、生成語音，並透過 `/tts` -> `/webrtc_req` 讓 Go2 播放出來。

### 9.2 前置條件

- TTS provider 已可在 Jetson 執行
- Go2 可正常接收 WebRTC 音訊請求
- `/tts` topic 已存在
- Go2 與 Jetson 網路連線正常

### 9.3 啟動指令

若用現有 launch 啟動 TTS：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && unset COLCON_CURRENT_PREFIX && source /opt/ros/humble/setup.zsh && source install/setup.zsh && export ROBOT_IP=<GO2_IP> && export CONN_TYPE=webrtc && ros2 launch go2_robot_sdk robot.launch.py enable_tts:=true nav2:=false slam:=false rviz2:=false foxglove:=false"
```

若未走 launch，也可直接啟動：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor tts_node --ros-args -p api_key:=<ELEVENLABS_API_KEY>"
```

接上 Intent 到 TTS 的模板回覆橋接（無 LLM 版本）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor intent_tts_bridge_node"
```

發布測試文字：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic pub --once /tts std_msgs/msg/String '{data: "哈囉，語音模組測試成功"}'"
```

觀察 Go2 命令流：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /webrtc_req"
```

### 9.3.1 本地音訊生成驗證（優先執行）

在驗證 Go2 播放鏈路前，先確認 TTS 本身可獨立生成音訊：

```bash
# 啟動 TTS node 並監聽 log
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor tts_node --ros-args -p api_key:=<ELEVENLABS_API_KEY> 2>&1 | tee /tmp/tts_test.log"
```

```bash
# 發布測試文字
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic pub --once /tts std_msgs/msg/String '{data: "哈囉，測試"}'"
```

**本地驗證檢查點：**
- [ ] TTS node log 顯示收到文字
- [ ] log 顯示音訊生成成功（如 `TTS completed`）
- [ ] 若支援本地輸出，確認 `/tmp/tts_test.wav` 或類似檔案存在
- [ ] 音訊時長合理（5字約 1-2 秒）

只有本地驗證通過後，再進入 Go2 播放鏈路測試。

### 9.3.2 Phase 4 最小回應鏈（推薦）

在不接 LLM 的前提下，先驗證模板回應可播報：

1. `intent_node` 產生 `/event/speech_intent_recognized`
2. `intent_tts_bridge_node` 將 intent 轉為回覆模板並發布 `/tts`
3. `tts_node` 接收 `/tts` 並轉發 `/webrtc_req`

建議模板（目前預設）：

- `hello` -> 「哈囉，我在這裡。」
- `sit` -> 「收到，請坐下。」
- `stand` -> 「收到，請站起來。」
- `stop` -> 「好的，停止動作。」
- `chat` -> 「我正在進行語音互動測試。」
- `unknown` -> 「我沒聽清楚，請再說一次。」

### 9.4 Go2 播放鏈路測試步驟

1. 確認本地驗證已通過
2. 啟動完整 TTS 與 Go2 連線
3. 送出固定短句到 `/tts`
4. 確認 `/webrtc_req` 有音訊封包送出
5. 確認 Go2 實際播放音訊
6. 測試長句與短句各 3 次

建議測試句：

- 「哈囉，語音模組測試成功」（短句，~10字）
- 「請注意，現在開始播放中文語音」（中句，~15字）
- 「我是 PawAI 的語音展示模式，很高興見到你」（長句，~20字）

### 9.5 觀察指標

- `/tts` 是否成功被訂閱
- node log 是否顯示 TTS completed successfully
- 本地音訊生成是否成功
- `/webrtc_req` 是否有封包
- Go2 是否實際播音
- MeloTTS 延遲是否可接受

### 9.6 成功標準

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 本地生成成功率 | 10/10 | ≥ 9/10 | < 9/10 |
| Go2 播放成功率 | 10/10 | ≥ 9/10 | < 9/10 |
| TTS 啟動延遲 | 0.3 - 0.8s | ≤ 1.0s | > 1.0s |
| 音質評估 | 清晰無破音 | 輕微雜訊可接受 | 嚴重破音或中斷 |
| `/webrtc_req` 資料流 | 穩定輸出 | 偶有間斷 | 無資料或嚴重掉包 |

### 9.7 失敗排查

- 確認 `ROBOT_IP`、`CONN_TYPE` 是否正確
- 確認 Go2 是否在線
- 確認 TTS node 實際訂閱的是 `/tts`
- 若無聲音但有 `/webrtc_req`，優先查 WebRTC 與 Go2 播放端
- 若音訊有生成但播放失敗，檢查音訊格式轉換流程
- 若使用本地 provider 取代現有 provider，確認 provider 初始化是否成功

### 9.8 2026-03-09 實測進度（Phase 4）

本日已完成 `/tts -> /webrtc_req -> go2_driver_node` 播放鏈路驗證。

#### 已確認成功

- `go2_driver_node` 正常啟動且 WebRTC 狀態為 connected
- `/webrtc_req` 的訂閱端包含 `go2_driver_node`（不是只有 `_ros2cli_*`）
- `tts_node` log 顯示音訊分塊送出（`api_id 4001/4003/4002`）
- `tts_node` 顯示 `Robot playback completed` 與 `TTS completed successfully`

#### 關鍵踩坑與修復

1. **API key 空值導致 tts_node 無法啟動**
   - 錯誤型態：`-p api_key:=`（等號後為空）
   - 修法：先 `source .env.local`，並用雙引號帶參數
   - 正確指令：

   ```bash
   source /opt/ros/humble/setup.zsh
   source /home/jetson/elder_and_dog/install/setup.zsh
   ros2 run speech_processor tts_node --ros-args -p api_key:="$ELEVENLABS_API_KEY"
   ```

2. **NumPy 2.x 破壞 ROS cv_bridge/cv2（go2_driver_node 啟動失敗）**
   - 症狀：`_ARRAY_API not found`、`numpy.core.multiarray failed to import`
   - 修法：Jetson 環境固定 `numpy<2`，再驗證 `cv2` 與 `cv_bridge`

   ```bash
   python3 -m pip install --user --force-reinstall "numpy<2"
   python3 -c "import cv2; print('cv2 ok')"
   python3 -c "from cv_bridge import CvBridge; print('cv_bridge ok')"
   ```

3. **`/webrtc_req` 有資料但沒聲音時，先看真訂閱者**
   - 確認指令：

   ```bash
   ros2 topic info /webrtc_req -v
   ```

   - 必須看到 `go2_driver_node` 在 Subscription 清單內。

#### 一次成功的最小流程（建議）

```bash
cd /home/jetson/elder_and_dog
set -a; source .env.local; set +a
source /opt/ros/humble/setup.zsh
source install/setup.zsh

# 終端 A
ros2 launch go2_robot_sdk robot.launch.py enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false

# 終端 B
ros2 run speech_processor tts_node --ros-args -p api_key:="$ELEVENLABS_API_KEY"

# 終端 C
ros2 topic pub --once /tts std_msgs/msg/String '{data: "哈囉，Go2，請播放測試音"}'
```

> 備註：本階段已先用 ElevenLabs 路線打通。MeloTTS 改造可在此基準上替換 provider。

### 9.9 2026-03-09 夜間補充（Piper 遷移進度）

本日已將 TTS provider 由「僅 ElevenLabs/MeloTTS」擴充為可切換 `piper`，並完成腳本與文件同步。

#### 已完成

- 程式：`speech_processor/speech_processor/tts_node.py` 新增 `piper` provider
  - 支援參數：`piper_model_path`、`piper_config_path`、`piper_speaker_id`、`piper_length_scale`、`piper_noise_scale`、`piper_noise_w`、`piper_use_cuda`
  - 修正 Piper CLI 參數相容性（`--noise-w-scale`）與 `~/.local/bin/piper` fallback
- 腳本：`scripts/start_speech_phase4_tmux.sh`、`scripts/start_speech_e2e_tmux.sh` 新增 Piper 參數透傳
- 環境範本：`.env.example` 已新增 Piper 預設欄位
- 驗證：`lsp_diagnostics`、`py_compile`、`colcon build --packages-select speech_processor` 均通過

#### Jetson 實測結果

- `piper-tts` 安裝成功（`pip install --user piper-tts`）
- 中文模型下載成功（`zh_CN-huayan-medium.onnx` + `.onnx.json`）
- `python3 -m piper --help` 可執行
- E2E tmux 觀察到：
  - `/tts` 有資料
  - `/webrtc_req` 有 4001/4003/4002 且分塊送出
  - `tts_node` 顯示 `TTS completed successfully`

#### 尚未解決（留待明日）

- 目前仍有「封包送出成功但現場無聲音」情況
- 優先排查順序：
  1. 確認實際使用 `TTS_PROVIDER=piper`（避免被舊 `.env.local` 覆蓋回 elevenlabs）
  2. 確認 Go2 端音量與播放狀態（`audiohub`）
  3. 以最短路徑重測：單獨 `tts_node(provider=piper)` + 單次 `ros2 topic pub /tts`
  4. 再回到 `start_speech_e2e_tmux.sh` 全鏈路

#### 明日接續建議

- 先完成「Piper 單點播放（無 ASR/Intent）」再回測 E2E
- 若仍無聲，先以 ElevenLabs 保底 demo，再平行調 Piper 音量/裝置
- 完成後補充 15.1 測試紀錄表（Phase 4 與 End-to-End）

### 9.10 2026-03-11 凌晨補充（無聲音問題當日紀錄）

本輪已完成並行調查（explore/librarian/oracle/Sisyphus-Junior）與 Jetson 現場重現；結論是：

- ROS 指令鏈路目前可重現送出 `4004 -> 4001 -> 4003... -> 4002`
- 但現場仍可能「封包正常、實體無聲」，代表還需再做 robot 端播放狀態鑑別

#### 今天踩到的坑（已確認）

1. **tmux 腳本內 PATH 展開錯誤，造成 `tts_node` 偶發未啟動**
   - 症狀：pane 顯示 `ros2: command not found` 或 pane dead。
   - 根因：腳本裡 `export PATH="$HOME/.local/bin:$PATH"` 在外層先展開，破壞內層 shell。
   - 修正：改為 `export PATH="$HOME/.local/bin:\$PATH"`。

2. **Jetson 程式碼已更新但未重 build，導致新參數看不到**
   - 症狀：`ros2 param list /tts_node` 沒有 `robot_volume`。
   - 修正：`colcon build --packages-select speech_processor` 後重啟 session。

3. **多套 tmux/session 同時存在，造成 topic 計數與行為混淆**
   - 症狀：`/tts`、`/webrtc_req` publisher/subscriber 數量異常。
   - 修正：先 kill 舊 session 與舊 process，再只保留一套 `asr-tts-no-vad`。

4. **遠端 SSH 非互動終端，`tmux attach` 會出現 `open terminal failed`**
   - 說明：此訊息不等於流程失敗；需用 `tmux list-sessions`、`tmux capture-pane` 驗證。

5. **麥克風裝置與取樣率不一致，導致 ASR/VAD 不穩或空字串**
   - 典型症狀：
     - PortAudio 錯誤 `-9985`（device unavailable）
     - PortAudio 錯誤 `-9997`（invalid sample rate）
     - `stt_intent_node` 出現 `whisper_local: empty transcript`
   - 根因：
     - `input_device=-1`（default）在換 USB 麥克風後可能漂移到錯誤裝置
     - `sample_rate` 與裝置原生 rate 不一致（例如 node 用 16k，但裝置只穩定在 44.1k）
   - 實務修正：
     - 先固定 `capture_sample_rate=44100`，由 node 內做重採樣到 `sample_rate=16000`
    - 必要時改用具體 `input_device` index，不依賴 default
    - 若當天先求可展示，先走「無 VAD 路徑」避免 VAD 邊界切段干擾

6. **`stt_intent_node` 參數名誤用會直接失效**
   - 正確參數：`provider_order`
   - 常見誤用：`asr_provider_order`（不會被節點吃到）

7. **zsh 對 `[]` 的 glob 會炸掉 provider 陣列參數**
   - 典型錯誤寫法：`-p provider_order:=[whisper_local]`
   - 建議寫法：`-p provider_order:='["whisper_local"]'`
   - 或在啟動前加：`setopt nonomatch`

8. **空參數覆寫會把預設值清掉，造成 crash 或異常行為**
   - 高風險例子：`-p api_key:=`、`-p alsa_device:=`
   - 原則：不要傳遞空值；需要可選參數時，應在腳本中條件組裝參數字串。

9. **`setup.bash` / `setup.zsh` 混用容易造成環境不完整**
   - 現象：同一套指令在不同 shell 結果不一致（找不到 command 或 package）。
   - 原則：bash 就全程 `setup.bash`，zsh 就全程 `setup.zsh`，不要混搭。

10. **多流程混跑會讓診斷信號失真**
   - 典型衝突：`speech-e2e`、`speech-e2e-noenv`、`asr-tts-no-vad` 同時跑。
   - 影響：topic publisher/subscriber 計數失真，容易誤判「有送出/有訂閱」。
   - 原則：同時間只保留一條測試路徑，其他 session 全部關閉。

#### 麥克風排查最短指令（明天可直接用）

```bash
# 1) 看 ALSA 硬體清單（卡號/裝置號）
arecord -l

# 2) 看可用 PCM 名稱（含 plughw）
arecord -L | head -n 40

# 3) 直接錄 3 秒驗證麥克風是否有波形
arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 3 /tmp/mic_test.wav
aplay /tmp/mic_test.wav

# 4) 若 default 不穩，改成明確裝置 index 啟動 stt_intent_node
source /opt/ros/humble/setup.zsh
source /home/jetson/elder_and_dog/install/setup.zsh
ros2 run speech_processor stt_intent_node --ros-args \
  -p provider_order:='["whisper_local"]' \
  -p input_device:=<你的裝置index> \
  -p sample_rate:=16000 \
  -p capture_sample_rate:=44100
```

> 註：`<你的裝置index>` 建議先用 Python/sounddevice 或 node 啟動 log 確認，不要盲猜。

#### 今日已驗證可重現設定（明天從這裡接）

- 啟動腳本：`scripts/start_asr_tts_no_vad_tmux.sh`
- 關鍵 TTS 參數：
  - `provider=piper`
  - `robot_chunk_interval_sec=0.06`
  - `robot_playback_tail_sec=0.5`
  - `robot_volume=80`
- 觀察到的 `webrtc_req` 序列：
  - `api_id=4004`（volume）
  - `api_id=4001`（start）
  - `api_id=4003`（多 chunk）
  - `api_id=4002`（stop）

#### 明天接續的單一路徑（避免再分叉）

1. **先固定單一路徑重現（只跑一套）**

```bash
tmux kill-session -t speech-e2e 2>/dev/null || true
tmux kill-session -t speech-e2e-noenv 2>/dev/null || true
tmux kill-session -t speech-phase4 2>/dev/null || true
tmux kill-session -t asr-tts-no-vad 2>/dev/null || true

pkill -f go2_driver_node 2>/dev/null || true
pkill -f stt_intent_node 2>/dev/null || true
pkill -f intent_tts_bridge_node 2>/dev/null || true
pkill -f tts_node 2>/dev/null || true

cd /home/jetson/elder_and_dog
source /opt/ros/humble/setup.bash
colcon build --packages-select speech_processor
./scripts/start_asr_tts_no_vad_tmux.sh
```

2. **用最小測試句驗證命令有送到 audiohub**

```bash
source /opt/ros/humble/setup.bash
source /home/jetson/elder_and_dog/install/setup.bash

{ (sleep 2; ros2 topic pub --once /tts std_msgs/msg/String "data: tomorrow_probe") \
  & timeout 12s ros2 topic echo /webrtc_req; }
```

3. **若仍無聲，直接做「ROS 路徑 vs 直送路徑」二分鑑別**
   - Oracle 建議：同一份短音訊、同一台 Jetson，先做 ROS 路徑，再做直送 robot audiohub，快速切分是 ROS chunk/時序問題或 robot 端播放狀態問題。

4. **驗收口徑（避免主觀）**
   - 至少要同時滿足：
     - `/webrtc_req` 出現 `4004 -> 4001 -> 4003... -> 4002`
     - 現場聽到實體播音
   - 若只有第一項成立，不可宣告完成。

### 9.3.3 Piper 測試（本地低延遲模式）

若要測本地 Piper（降低雲端往返延遲）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && python3 -m pip install --user piper-tts"
```

下載中文 voice model（`.onnx` + `.onnx.json` 必須成對）：

```bash
ssh jetson-nano "mkdir -p /home/jetson/models/piper && cd /home/jetson/models/piper && wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx && wget -nc https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json"
```

直接啟動 tts_node（Piper provider）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor tts_node --ros-args -p provider:=piper -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx -p piper_config_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json -p piper_speaker_id:=0 -p piper_length_scale:=1.05 -p piper_noise_scale:=0.667 -p piper_noise_w:=0.8 -p piper_use_cuda:=false"
```

或用一鍵腳本切換 provider：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && set -a && source .env.local && set +a && TTS_PROVIDER=piper ./scripts/start_speech_phase4_tmux.sh"
```

Piper 調整建議（先求清晰）：

- `piper_length_scale=1.00~1.12`（值越大語速越慢）
- 優先短句模板（降低尾音含糊）
- 若 CPU 延遲偏高，再測 `piper_use_cuda=true`

直接啟動 tts_node（Melo provider）：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 run speech_processor tts_node --ros-args -p provider:=melotts -p melo_language:=ZH -p melo_speaker:=ZH -p melo_speed:=0.92 -p melo_device:=auto"
```

或用一鍵腳本切換 provider：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && set -a && source .env.local && set +a && TTS_PROVIDER=melotts ./scripts/start_speech_phase4_tmux.sh"
```

MeloTTS 調整建議（先求清晰）：

- `melo_speed=0.90~0.95`（放慢語速）
- 優先短句模板（減少含糊與尾音吃字）
- 先固定 `ZH` speaker，再做音色比較

---

## 10. Phase 5: LLM 整合測試 (Qwen3.5-0.8B)

### 10.1 目標

驗證 Qwen3.5-0.8B INT4 可在 Jetson 上接收 Intent 或 ASR 文字，生成簡短中文回覆，再轉交 TTS 播放。

**MVP 階段範圍限定：**
- LLM 主要用於簡短中文回覆生成與展示互動補充
- **不以自由多輪對話能力作為主要驗收目標**
- 限制條件：
  - 最大輸出長度：20-30 個中文字（約 1-2 句）
  - 固定 system prompt，不做動態角色切換
  - 不做多輪上下文記憶（每輪獨立）
  - 不開放長上下文（context length ≤ 2048）

### 10.2 前置條件

- Phase 3 與 Phase 4 已通過
- Qwen3.5-0.8B INT4 已可在 Jetson 載入
- LLM node 或推理服務已啟動
- 已限制最大輸出長度，避免延遲過高

### 10.3 啟動指令

若已有 LLM node：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run speech_processor llm_node"
```

觀察大腦狀態：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /state/executive/brain"
```

觀察最終 TTS：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /tts"
```

### 10.4 測試步驟

1. 送入簡單問句或 `chat` 類 intent
2. 限制 LLM 只生成 1 到 2 句短回覆
3. 確認 LLM 輸出內容可交由 TTS 播放
4. 測試 5 次不同問題，觀察延遲與穩定性
5. 測試記憶體在連續 5 次問答下是否持續升高

建議測試句：

- 「你是誰」
- 「你現在在做什麼」
- 「請用一句話介紹你自己」
- 「今天要展示什麼」
- 「跟我打個招呼」

### 10.5 觀察指標

- LLM 是否可回覆
- 首 token 是否過慢
- 回覆長度是否受控
- `/tts` 是否接到 LLM 生成文字
- 記憶體是否持續上升不回收

### 10.6 成功標準

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 回覆合理率 | 5/5 | ≥ 4/5 | < 4/5 |
| 生成延遲 | 0.5 - 1.2s | ≤ 1.8s | > 1.8s |
| 回覆長度 | ≤ 20 字 | ≤ 30 字 | > 30 字 |
| TTS 轉換成功率 | 5/5 | ≥ 4/5 | < 4/5 |
| 記憶體穩定性 | 無上升 | 輕微上升可回收 | 持續上升不回收 |

**限制條件驗證：**
- [ ] System prompt 已固定
- [ ] 最大 token 限制已設定（建議 max_tokens ≤ 50）
- [ ] 無多輪記憶機制（或已關閉）
- [ ] Context length 限制已設定（≤ 2048）

### 10.7 失敗排查

- 若回覆很慢，先限制輸出 token 數
- 若記憶體吃緊，先關閉非必要視覺節點
- 若回覆亂答，先改成 intent-template 方式驗證
- 若 `/tts` 沒收到資料，檢查 LLM 到 TTS 的 topic 串接
- 若多輪後速度下降，觀察是否有記憶體碎片或 cache 累積

---

## 11. 端到端整合測試

### 11.1 目標

完整驗證 `VAD -> ASR -> Intent -> LLM -> TTS` 閉環，確保展示模式下可從人說話一路走到 Go2 播放回應。

### 11.2 前置條件

- 前 5 個 Phase 已各自通過
- Jetson、Go2、USB 麥克風、D435 全部在線
- ROS2 topic 名稱已確認
- 測試環境噪音可控

### 11.3 啟動指令

先啟動語音相關節點，再視需要啟動整合 launch。

若採最小展示模式：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && unset COLCON_CURRENT_PREFIX && source /opt/ros/humble/setup.bash && source install/setup.bash && export ROBOT_IP=<GO2_IP> && export CONN_TYPE=webrtc && ros2 launch go2_robot_sdk robot.launch.py enable_tts:=true nav2:=false slam:=false rviz2:=false foxglove:=false"
```

同步觀察所有主要 topic：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /state/interaction/speech"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /asr_result"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /event/speech_intent_recognized"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /state/executive/brain"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /tts"
```

### 11.4 測試步驟

1. 使用者對著麥克風說固定指令或問句
2. 確認 VAD 成功切段
3. 確認 ASR 在 `/asr_result` 發布文字
4. 確認 Intent 事件被發布到 `/event/speech_intent_recognized`
5. 確認 LLM 或規則回覆進入 `/tts`
6. 確認 Go2 最終播出中文語音

建議端到端測試句：

- 「請跟我打招呼」
- 「請坐下」
- 「你是誰」
- 「你現在在做什麼」

### 11.5 觀察指標

- 每一段 topic 是否都有資料
- 是否存在某一段卡住不前進
- Go2 是否最終播音
- 是否出現延遲暴增
- 多次重複測試是否穩定

### 11.6 成功標準

**計時定義：**
- **起點**：VAD 判定 `speech_end` 的時間點（非使用者實際停嘴時刻）
- **終點**：`/tts` topic 發布最終回覆文字的時間點

| 指標 | 理想值 | 可接受值 | 不通過 |
|------|--------|----------|--------|
| 完整跑通率 | 10/10 | ≥ 8/10 | < 8/10 |
| 端到端延遲 | ≤ 2.0s | ≤ 2.5s | > 2.5s |
| TTS 到播音延遲 | < 0.3s | ≤ 0.5s | > 0.5s |
| 流程可重複性 | 無需介入 | 偶需重試 | 頻繁需要人工介入 |

**測試情境：**
- 安靜環境：8 次
- 輕度背景噪音：2 次

### 11.7 失敗排查

- 若流程卡在前段，先看 VAD 與 ASR
- 若流程卡在中段，先看 `/asr_result` 到 `/intent`
- 若流程卡在後段，先看 `/tts` 到 `/webrtc_req`
- 若只有 LLM 問答慢，先縮短 prompt 與輸出長度
- 若只有展示現場失敗，優先檢查網路、供電與噪音環境

---

## 12. 性能監控與記憶體管理

### 12.1 Jetson 監控指令

#### 系統記憶體

```bash
ssh jetson-nano "free -h"
```

#### Jetson 即時資源監控

```bash
ssh jetson-nano "tegrastats"
```

#### ROS2 節點列表

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list"
```

#### Topic 列表

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list"
```

#### Topic 頻率

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic hz /state/interaction/speech"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic hz /state/executive/brain"
```

#### Topic 內容

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /tts"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /webrtc_req"
```

### 12.2 延遲預算建議

| 階段 | 理想值 | 可接受值 | 危險值 |
|------|--------|----------|--------|
| VAD 切段 | < 0.2 s | ≤ 0.3 s | > 0.3 s |
| ASR | 0.2 - 0.8 s | ≤ 1.2 s | > 1.2 s |
| Intent Rule | < 0.05 s | ≤ 0.1 s | > 0.1 s |
| LLM | 0.5 - 1.2 s | ≤ 1.8 s | > 1.8 s |
| TTS | 0.3 - 0.8 s | ≤ 1.0 s | > 1.0 s |
| **端到端** | **≤ 2.0 s** | **≤ 2.5 s** | **> 2.5 s** |

**定義說明：**
- **理想值**：展示品質最佳的目標
- **可接受值**：Demo 現場可容忍的上限
- **危險值**：超過此值將明顯影響使用者體驗，需啟動降級策略

### 12.3 記憶體管理建議

- 展示模式關閉不必要的 RViz、Foxglove、Nav2、SLAM
- 若語音為優先測試項，先關閉高負載視覺節點
- 連續測試時每完成一輪可記錄一次 `free -h`
- 長時間監控建議另開視窗跑 `tegrastats`
- 若 RAM 持續下降不回升，需懷疑 memory leak 或模型緩存策略
- 若 GPU 記憶體吃緊，先降低並行度或縮短 LLM 回覆

---

## 13. 常見問題排解

### 13.1 麥克風沒聲音

可能原因：

- USB 麥克風未被 Jetson 正確辨識
- ALSA 裝置編號錯誤
- 錄音格式不符

先查：

```bash
ssh jetson-nano "arecord -l"
```

### 13.2 VAD 一直誤觸發

可能原因：

- 環境噪音太大
- threshold 過低
- 麥克風增益過高

處理建議：

- 降低麥克風增益
- 提高 VAD threshold
- 增加最短語音長度限制

### 13.3 ASR 沒有輸出 `/asr_result`

可能原因：

- VAD 沒有切出有效語音
- ASR node 未啟動
- topic 名稱與程式實作不一致

先查：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list"
```

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list"
```

### 13.4 Intent 沒有輸出

可能原因：

- ASR 文字內容錯誤
- intent 規則未覆蓋該句型
- 發布的 topic 名稱不是預期的 `/intent` 或 `/event/speech_intent_recognized`

建議：

- 先固定輸入文字做規則測試
- 對照 `/event/speech_intent` 與 `/event/speech_intent_recognized`

### 13.5 TTS 有收到文字但 Go2 沒有播音

可能原因：

- `/tts` 到 `/webrtc_req` 之間失敗
- Go2 WebRTC 連線異常
- 音訊格式轉換失敗

先查：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /webrtc_req"
```

### 13.6 整體延遲超過 2 秒

可能原因：

- LLM 回覆過長
- 系統記憶體不足造成 swap 或抖動
- 同時啟用太多視覺節點
- TTS 或 ASR 模型載入策略不佳

建議：

- 限制 LLM 最大輸出長度
- 關閉不必要視覺節點
- 測試時先採固定 intent 模板回覆
- 觀察 `tegrastats` 與 `free -h`

### 13.7 節點啟動了但 topic 看不到

可能原因：

- 尚未 `source install/setup.bash`
- 啟動 shell 與觀察 shell 環境不同
- namespace 或 topic 名稱不同

建議所有指令統一使用：

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && source /opt/ros/humble/setup.bash && source install/setup.bash && <command>"
```

---

## 14. 最終驗收建議

### 14.1 展示前最低通過門檻（主路徑：no-VAD）

- [ ] 主路徑啟動通過：`start_asr_tts_no_vad_tmux.sh` 可重複啟動
- [ ] Phase 2 通過：Whisper Tiny 可輸出可用中文文字
- [ ] Phase 3 通過：固定指令 intent 正確率足夠
- [ ] Phase 4 通過：Go2 可穩定播音
- [ ] Phase 5 通過：Qwen3.5-0.8B 可生成短回覆
- [ ] 端到端延遲符合「中位數 ≤ 3.5 s，最差 ≤ 6 s」
- [ ] `tegrastats` 顯示系統未長時間貼近極限
- [ ] 與 D435、YuNet 同時執行時仍可接受

### 14.2 Demo 前建議保底模式

若 Phase 5 不穩定，可先採：

- `no-VAD -> ASR -> Intent Rule -> Template Reply -> TTS`

此模式雖非完整 LLM 對話，但在目前 Jetson 音訊條件下更有利於 4/13 展示穩定性。

### 14.3 展示模式降級順序

若展示前系統不穩或資源不足，依以下順序逐步降級：

| 順序 | 降級項目 | 具體操作 | 預期效果 |
|------|----------|----------|----------|
| 1 | 關閉除錯工具 | 關閉 RViz、Foxglove、SLAM、Nav2 | 釋放 ~0.5-1.0 GB |
| 2 | 關閉視覺除錯 | 關閉非必要視覺節點（影像顯示等） | 釋放 ~0.3-0.5 GB |
| 3 | 簡化 LLM | 關閉 LLM，改用 Template Reply | 釋放 ~1.0 GB |
| 4 | 限制對話範圍 | 僅保留固定指令集，不開放自由問答 | 降低 intent 複雜度 |
| 5 | 關閉 VAD | 切回 no-VAD 主線（手動/固定窗口錄音） | 避免 `-9998` 入口崩潰 |
| 6 | 最簡模式 | 僅保留 `no-VAD -> ASR -> 固定指令 -> TTS` | 最小風險可展示鏈路 |

**降級決策建議：**
- 若在測試階段發現記憶體長時間 > 7GB，執行順序 1-2
- 若 LLM 延遲不穩定或回覆品質差，執行順序 3
- 若展示現場噪音過大或 VAD 啟動異常，直接執行順序 5
- 順序 6 為最終保底，確保至少能展示「語音控制機器人」基礎功能

### 14.4 VAD 次路徑啟用條件（僅受控測試）

只有在以下條件全部滿足時，才允許在測試場次啟用 VAD：

- 已完成當天 no-VAD 主路徑通關（ASR/Intent/TTS 全綠）
- 當前環境為單 session、乾淨啟動、可回收 snapshot
- 失敗時可在 30 秒內切回 no-VAD，不做現場長時間 debug

若任一條件不滿足，當場禁用 VAD，回主路徑。

---

## 15. 測試紀錄模板

### 15.1 測試結果紀錄

| 日期 | 測試階段 | 測試者 | 結果 | 延遲 | 啟動前記憶體 | 峰值記憶體 | 問題 | 備註 |
|------|----------|--------|------|------|--------------|------------|------|------|
| 2026-__-__ | Phase 1 |  | Pass / Fail |  |  |  |  |  |
| 2026-__-__ | Phase 2 |  | Pass / Fail |  |  |  |  |  |
| 2026-__-__ | Phase 3 |  | Pass / Fail |  |  |  |  |  |
| 2026-__-__ | Phase 4 |  | Pass / Fail |  |  |  |  |  |
| 2026-__-__ | Phase 5 |  | Pass / Fail |  |  |  |  |  |
| 2026-__-__ | End-to-End |  | Pass / Fail |  |  |  |  |  |

### 15.2 記憶體監控紀錄格式

每次測試至少記錄以下數據：

```bash
# 啟動前
ssh jetson-nano "free -h" >> /tmp/test_mem_$(date +%Y%m%d_%H%M%S).log

# 測試中（另開視窗持續監控）
ssh jetson-nano "tegrastats" | tee /tmp/test_tegra_$(date +%Y%m%d_%H%M%S).log

# 測試後
ssh jetson-nano "free -h" >> /tmp/test_mem_$(date +%Y%m%d_%H%M%S).log
```

**紀錄欄位說明：**
- **啟動前記憶體**：`free -h` 的 available 欄位
- **峰值記憶體**：測試過程中觀察到的最高記憶體占用
- **失敗時資源狀態**：若測試失敗，需記錄當時的 `tegrastats` 輸出

### 15.3 2026-03-12 進度更新（Jetson 實測）

#### 今日完成

- ASR 推理路徑切到 `whisper_local + small + cuda + float16`，已能在 Jetson 跑通。
- `stt_intent_node` 以 ALSA 裝置啟動成功：`-p alsa_device:=plughw:0,0`（避開動態 `input_device` 漂移）。
- `go2_driver_node` 與 `tts_node` 在 `ROS_DOMAIN_ID=0` 下可互通；`/webrtc_req` 已確認 `Publisher=1 (tts_node)`、`Subscription=1 (go2_driver_node)`。
- Go2 已可聽到 TTS 播放聲音（非完全無聲）。
- Intent 規則已補強常見誤辨詞（含簡體/口語變體），`take_photo / stop / status / come_here / greet` 命中率有提升。

#### 今日主要問題

- 英文 TTS 聽感差（中文音色講英文可懂度低）。
- 語音播放偶發「加速感 / 被切斷感」。
- STT/Bridge/Driver 曾出現殘留進程與重複節點（多次手動啟停造成 graph 污染）。
- `go2_driver_node` 有間歇重連：`Consent to send expired -> reconnecting`。

#### 今日已解問題

- `ssh jetson-nano` 解析失敗：已用 Tailscale IP 建立 `~/.ssh/config` 映射恢復連線。
- `Invalid number of channels [PaErrorCode -9998]`：改用 `alsa_device:=plughw:0,0` 後可穩定啟動 STT。
- `/tts` 發布卡在 `Waiting for at least 1 matching subscription(s)`：確認為「發送端環境/路徑錯誤或 subscriber 未啟」，非 topic 本身故障。
- Go2 無聲根因已縮小為「播放參數與音訊格式/連線穩定度」而非 ROS topic 斷線。

#### 今日代辦（下一輪）

1. ~~Jetson 套用並重啟最新 `tts_node`（16kHz/16bit/mono 重採樣版本）後，重測 20 輪播音穩定度。~~ ✅ 已完成
2. 英文語音改英文 Piper 模型（例如 `en_US-lessac-medium`），與中文模型分開 profile 啟動。
3. 固化單一路徑啟動腳本（clean-start -> driver -> stt -> bridge -> tts），避免手動多開造成重複節點。
4. 針對 `Consent to send expired` 做網路與 Go2 端連線穩定化檢查（同網段、單連線、減少高流量負載）。
5. 補 30 輪統計（命中率、unknown、empty、busy）並回填本文件 15.1 表格。
6. RTX 8000 架 vLLM + Qwen3.5-27B，寫 `llm_bridge_node` 取代模板回覆。

### 15.4 2026-03-12 踩坑總記錄與根因分析

> **目的**：記錄本輪除錯中遇到的所有陷阱，供後續開發者避坑。

#### 根因一：asyncio.Queue 跨執行緒丟包（最難定位的 bug）

**現象**：`/webrtc_req` 封包序列完整（4004→4001→4003→4002），WebRTC log 顯示「sent」，但 Go2 完全沒聲音。

**根因**：`webrtc_adapter.py` 的 `send_webrtc_request()` 用 `asyncio.Queue.put_nowait()` 從 ROS2 callback 執行緒塞資料，再由 asyncio event loop 執行緒的 `process_webrtc_commands()` 每 100ms 輪詢消費。但 Python 的 `asyncio.Queue` **明確不是執行緒安全的**（官方文件有寫），跨執行緒操作會靜默丟失資料。

**為什麼難發現**：
- 不會報錯、不會 crash，只是偶發丟資料
- 同一個 class 裡的動作指令（stand/sit/walk）直接呼叫 `send_command()` 走 `run_coroutine_threadsafe`，一直都正常
- 只有音訊指令走 queue 路徑，所以「動作正常但音訊無聲」

**修復**：`webrtc_adapter.py:173` — `send_webrtc_request()` 改為直接呼叫 `send_command(robot_id, payload)`，繞過 queue。

**教訓**：
- `asyncio.Queue` 只能在同一個 event loop 內使用，跨執行緒請用 `queue.Queue` 或 `run_coroutine_threadsafe`
- 其他指令正常不代表所有路徑都正常，每條路徑都要獨立驗證

---

#### 根因二：WAV sample rate 不匹配（Go2 音訊加速）

**現象**：Go2 有聲音了，但語速明顯加速、講不清楚。

**根因**：Piper 中文模型 `zh_CN-huayan-medium` 原生輸出 **22050Hz** WAV。`tts_node` 做了 WAV→MP3→WAV 雙重轉換但沒有重取樣，Go2 的 audiohub 內部以不同 sample rate（推測 16kHz）播放，導致聲音被加速。

**修復**：`tts_node.py` 的 `convert_to_wav()` 加入強制重取樣：

```python
audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
```

**教訓**：
- Go2 audiohub **沒有官方文件**說明支援的音訊格式，16kHz/16bit/mono 是根據嵌入式慣例推測
- 發送前一律標準化格式，不要假設下游能處理任意 sample rate
- Piper 不同模型的 sample rate 不同（英文模型可能是 16kHz 或 22050Hz），統一重取樣可避免問題

---

#### 根因三：開發/執行環境分離導致的同步問題

**現象**：改了 code 但行為沒變、build 產物被刪、多個同名 node 互相干擾。

**子問題與對策**：

| 子問題 | 原因 | 對策 |
|--------|------|------|
| build 後行為沒變 | `colcon build` 只更新 `install/`，正在跑的 node 是舊版 | **build 後必須重啟 node**（kill → source → run） |
| `install/` 被刪 | `rsync --delete` 把 Jetson 的 build 產物清掉 | rsync 加 `--exclude='build/' --exclude='install/' --exclude='log/'` 或 `--filter=':- .gitignore'` |
| 重複節點互相干擾 | 手動開多個 terminal、tmux 殘留進程 | 每次啟動前 `pkill -9 -f "node_name"` + `tmux kill-server` |
| `ROS_DOMAIN_ID` 不一致 | 部分 terminal 手動設了 `ROS_DOMAIN_ID=123`，其他沒設 | **所有 node 必須在同一個 domain**（預設 0，除非有明確理由） |
| `go2_driver_node` 不在 node graph | ROS2 spin 執行緒被 `asyncio.wait(FIRST_COMPLETED)` cancel | 需注意 `main.py` 的 task 生命週期管理 |

---

#### 根因四：Jetson CUDA 環境未啟用（GPU 閒置）

**現象**：Whisper Small 在 CPU 上跑 10 秒+，`ASR processing busy` 大量出現。

**根因**：
- Jetson Orin Nano 有完整 CUDA 12.6 + cuDNN 9.3
- 但 `torch` 是 pip 裝的 CPU 版（`2.10.0+cpu`）
- `ctranslate2` 也是 CPU-only（沒有 CUDA 支援）
- GPU 完全閒置，所有推理都在 CPU 上

**修復**：
- 編譯安裝 CUDA 版 CTranslate2 到 `~/.local/ctranslate2-cuda/`
- 啟動時 `export LD_LIBRARY_PATH=$HOME/.local/ctranslate2-cuda/lib:${LD_LIBRARY_PATH:-}`
- Whisper Small + CUDA float16 延遲從 10s+ 降到 **0.6s**

**教訓**：
- Jetson 上用 `pip install torch` 裝的是 x86 CPU 版，不會自動用 GPU
- Jetson 需要 NVIDIA 官方提供的 aarch64 CUDA wheel（JetPack 對應版本）
- 確認方式：`python3 -c "import torch; print(torch.cuda.is_available())"` — 如果是 False 就是 CPU 版

---

#### 根因五：麥克風裝置漂移

**現象**：`stt_intent_node` 啟動後 log 顯示 `Opening STT audio stream: default`，但完全收不到語音。

**根因**：
- `input_device=-1` 讓 sounddevice 使用 ALSA「default」裝置（device 33）
- Jetson 上 default 可能指向 NVIDIA APE 而非 HyperX SoloCast
- HyperX SoloCast 是 device 0（`hw:0,0`），原生 sample rate 44100Hz

**修復**：
- 明確指定 `input_device:=0` 或 `alsa_device:=plughw:0,0`
- 改良 `_start_audio_stream()` 的 log，顯示實際使用的裝置名稱而非 "default"

**教訓**：
- Jetson 插拔 USB 或重開機後，裝置索引可能漂移
- 用 `alsa_device:=plughw:0,0` 比 `input_device:=0` 更穩定（ALSA 名稱不隨 sounddevice 索引漂移）
- 測試前先用 `arecord -l` 或 `python3 scripts/mic_check.py` 確認實際裝置

---

#### 根因六：Intent 名稱不匹配與簡繁不一致

**現象**：說「你好」被辨識為 `unknown`，所有 intent 都不命中。

**子問題**：

1. **名稱不匹配**：`stt_intent_node` 發布 `greet`，但 `intent_tts_bridge_node` 的 template key 是 `hello` — 只有 `stop` 對得上
2. **空格問題**：Whisper 輸出 `"你 好"`（有空格），但 keyword `"你好"` 做 substring match 找不到
3. **簡繁問題**：Whisper Small 訓練資料以簡體為主，常輸出 `"请过来"` 而非 `"請過來"`

**修復**：
- `intent_tts_bridge_node.py` 的 template keys 改為與 `SUPPORTED_INTENTS` 一致（greet/come_here/stop/take_photo/status）
- `IntentClassifier._normalize()` 改為 `re.sub(r"\s+", "", text)` 移除所有空格
- 每個 intent 加入繁體+簡體+常見 Whisper 誤辨詞

**教訓**：
- 兩個 node 之間的契約（intent 名稱）必須明確定義在一個地方，不能各寫各的
- Whisper 的中文輸出不穩定（繁簡混用、字間插空格），keyword 比對前必須正規化
- 容錯詞需要從實測 log 中收集，不能只靠猜測

---

#### 安全啟動 SOP（避免再犯）

```bash
# 1. 全清（每次測試前必做）
tmux kill-server 2>/dev/null
pkill -9 -f "stt_intent_node|intent_tts_bridge|tts_node|go2_driver_node|robot.launch.py" 2>/dev/null
sleep 2
ps aux | grep -E "stt_intent|tts_node|go2_driver|intent_tts" | grep -v grep && echo "WARNING: 還有殘留!" || echo "clean"

# 2. 確認環境
cd ~/elder_and_dog
unset COLCON_CURRENT_PREFIX
source /opt/ros/humble/setup.zsh
source install/setup.zsh
export LD_LIBRARY_PATH=$HOME/.local/ctranslate2-cuda/lib:${LD_LIBRARY_PATH:-}
# 不要設 ROS_DOMAIN_ID（用預設 0）

# 3. 確認麥克風
python3 scripts/mic_check.py --device 0 --sample-rate 44100

# 4. 依序啟動（每個一個 terminal）
# Terminal A: go2_driver（最小負載）
ros2 run go2_robot_sdk go2_driver_node

# Terminal B: stt_intent_node
ros2 run speech_processor stt_intent_node --ros-args \
  -p provider_order:='["whisper_local"]' \
  -p whisper_local.model_name:=small \
  -p whisper_local.device:=cuda \
  -p whisper_local.compute_type:=float16 \
  -p alsa_device:=plughw:0,0

# Terminal C: intent_tts_bridge_node
ros2 run speech_processor intent_tts_bridge_node

# Terminal D: tts_node
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx \
  -p piper_config_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json

# 5. 驗證
ros2 node list  # 應有 4 個 node，無重複
ros2 topic info /webrtc_req -v  # Subscription count 應為 1
ros2 topic pub --once /tts std_msgs/msg/String '{data: "系統就緒"}'
# Go2 應播出清晰中文
```

---

### 15.5 2026-03-14 進度更新（30 輪驗收框架建立）

#### 今日完成

- 建立 `speech_test_observer` ROS2 node，訂閱語音主線 topic 並自動聚合每輪時間戳（20 unit tests pass）
- 建立 `test_scripts/speech_30round.yaml`（15 固定句 + 15 自由句測試定義）
- 建立 `scripts/clean_speech_env.sh`（獨立環境清理，取代各啟動腳本的手動 kill）
- 建立 `scripts/run_speech_test.sh`（一鍵 orchestration：clean → build → launch → warmup → 30 輪測試 → 報告生成）
- Observer 輸出 CSV（逐輪原始紀錄）+ Summary JSON（含 PASS/MARGINAL/FAIL 評分）
- Warmup 輪不進統計（observer 在 warmup 結束後才啟動）

#### 設計決策

- Observer 用 `/state/interaction/speech` 的 state 欄位變化偵測 round 邊界（`LISTENING→RECORDING` = speech_start，`RECORDING→TRANSCRIBING` = speech_end），因 no-VAD 主線不發布 `/event/speech_activity`
- TTS / webrtc_req 用時序關聯（`tts_correlation_window_s` 預設 3.0s），因這些 topic 不帶 `session_id`
- 控制面用 topic-based req/ack（不用 ROS2 service，避免自訂 .srv）

#### Jetson 實測結果（同日晚間）

**text_input downstream validation: PASS**

使用 `/speech/text_input` 繞過麥克風，驗證 Intent → TTS → Go2 播放 → Observer 記錄全鏈：

| 指標 | 結果 | 門檻 | 狀態 |
|------|------|------|------|
| Fixed accuracy | 100%（5/5 hit） | ≥80% | PASS |
| E2E median | 378ms | ≤3500ms | PASS |
| E2E max | 386ms | ≤6000ms | PASS |
| Play OK rate | 100% | ≥80% | PASS |
| TTS OK rate | 100% | — | PASS |

- 5 輪全部 `complete`，零 partial/timeout/orphan
- greet/come_here/stop/take_photo/status 全命中
- Round meta 綁定正確，CSV + Summary JSON 正常生成

**live mic capture on Jetson: BLOCKED**

| 問題 | 根因 | 狀態 |
|------|------|------|
| `input_device:=0` crash | PortAudio `PaErrorCode -9985`，ALSA backend 無法開 device 0 | 未解 |
| `alsa_device:=plughw:0,0` 靜默失敗 | `stt_intent_node` 只設 `ALSA_DEFAULT` 環境變數，不影響 PortAudio 的 device 選擇，stream 實際開在 default device 30（NVIDIA APE） | 未解 |
| default device 收音弱 | RMS ~0.016 剛好在 VAD threshold 0.015 邊界，觸發不穩定 | 未解 |

> **結論**：驗收工具本身已驗通。麥克風輸入層是獨立的底層 bug，需另開 debugging session 處理。

#### 今日修正的 bug

- **warmup 污染統計**：改為 observer 在 warmup 結束後才啟動
- **`--skip-driver` 未生效**：加 `SKIP_DRIVER` 條件包裹 go2 launch
- **correlation window 太短**：`tts_correlation_window_s` 從 3.0s 改為 5.0s
- **text_input 路徑 observer 不記錄**：observer 在 `on_intent_event` 無 active round 時自動建立新 round
- **match 全判 empty**：`on_intent_event` 補填 `asr_text` from intent event 的 `text` 欄位
- **report 最後一輪截斷**：`generate_report` 前加 8s drain wait

#### 下一步

- **獨立處理 Jetson PortAudio/ALSA 麥克風問題**（不與驗收工具混合）
- 麥克風問題解決後，跑完整 30 輪 live mic 測試
- 根據 30 輪數據決定是否需要調整 energy VAD 參數或 intent 規則

#### 待辦：Jetson live mic capture stabilization

> 獨立 debugging task，不阻擋驗收工具或 downstream 開發。

需調查：
1. 為什麼 PortAudio 在 ROS2 process 中無法開 device 0（獨立 python3 可以）
2. `stt_intent_node` 的 `alsa_device` 參數實際上沒有讓 sounddevice 用指定裝置
3. 是否應改用 pyaudio 或 subprocess `arecord` 替代 sounddevice/PortAudio

*最後更新：2026-03-14（Jetson 實測 + 麥克風問題定位）*
*適用專案：PawAI / elder_and_dog*
*維護用途：Jetson MVP 語音功能測試與展示前驗收*
