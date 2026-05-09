# Branch E — ElevenLabs Spike + TTS Dual Route Skeleton Plan

> **Skeleton plan** — task list 列改哪檔做什麼，不寫 TDD step 細節。實際開工前 expand。

**Goal:** 解 issue 1 音色（edge-tts 像 google 小姐 / Gemini 6-7s）。三段：(1) Spike-Mini 驗 ElevenLabs 音色 + latency；(2) Spike-Real 接 Megaphone Go2 實機；(3) 雙軌路由 fast/quality lane + audio_format/served_by 重構。

**Spec 來源:** `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` P2-2 (Mini + Real + fallback) + P2-3 (雙軌路由 + Provider format)。

**前置依賴**: 無（不動主鏈，可與 B/C/D 並行）。Branch A merged 後即可開。

**工時**: Spike-Mini 半天 + Spike-Real 半天（若 GO）+ Dual-route 半天 = 1.5 天

---

## Phase E-1: Spike-Mini (5/11 半天)

**Branch**: `spike/elevenlabs-tts-mini`（不 merge — 驗證用 spike branch）

**目標**: 純驗音色 + latency，**不上 Megaphone**，落地 WAV/MP3 → 本機 paplay。

### Task E-1.1: 設置 ElevenLabs PAYG account
- [ ] 註冊 Free account（已有跳過）
- [ ] PAYG $5 top-up
- [ ] 取得 API key → 寫 `.env.spike` (gitignore'd)
- [ ] commit `.env.example` template（不含 key）

### Task E-1.2: 跑 5 句固定文本 × 2-3 voice 候選
- [ ] 建 `tools/tts_spike/elevenlabs_mini.py`（spike script）
  - input: 5 句固定文本（短/中/長/情緒/safety 各一）
  - voice candidates: 2 個 Voice Library Mandarin / Chinese 童音或年輕女聲 + 1 個多語年輕女聲（如 Hope/Bella）
  - model: `eleven_flash_v2_5`
  - output: WAV/MP3 落地 + latency 量測（HTTP fetch time）
- [ ] 跑完 5 × 3 = 15 次 fetch
- [ ] 結果寫 `docs/pawai-brain/dev-logs/2026-05-11-elevenlabs-spike-mini.md`：
  - 主觀打分（音色雪寶感 1-5、中文自然度 1-5、破音/吞字/簡體腔 ✓/✗）
  - latency 表（短句 < 2s? 長句 < 4s?）
  - PAYG 用量

### Task E-1.3: GO/NO-GO 判定
- [ ] 5 GO 條件全達標：
  - ≥ 1 voice 音色 ≥ 4/5
  - 中文自然度 ≥ 4/5
  - 短句 < 2s AND 長句 < 4s
  - 無破音/吞字/簡體腔
  - PAYG quota 充足（**Roy review #1**：以 ElevenLabs dashboard 實際剩餘 quota 為準，spike log 記錄字數消耗 + 比例；不硬寫「50k chars」承諾）
- [ ] **Voice ID 記錄**（Roy review #2）：spike script 必須記下選中 voice 的 `voice_id`（永久 ID）+ `name` + `language`，主鏈 launch arg 用 voice_id 不靠 display name
- [ ] **GO** → 進 Phase E-2
- [ ] **NO-GO** → 5/12 改做 `spike/gemini-native-tts`（spec P2-2-fallback；半天）

---

## Phase E-2: Spike-Real (5/12 半天，僅 Mini GO 後)

**Branch**: `spike/elevenlabs-tts-real`（從 Mini branch 建）

### Task E-2.1: 啟用既有 TTSProvider_ElevenLabs
- [ ] `speech_processor/speech_processor/tts_node.py:234-285`：既有 ElevenLabs class verify wire（5/9 spec ElevenLabs 棄用 supersede）
- [ ] 檢查 model 設定：`eleven_flash_v2_5`
- [ ] voice_id 從 Spike-Mini 結果填入 launch arg

### Task E-2.2: ElevenLabs WAV → Megaphone 整合
- [ ] ElevenLabs 回 MP3 → 既有 audio_processor convert WAV 16kHz 流程
- [ ] Megaphone 4001/4003/4002 chunk upload 鏈（既有）
- [ ] 5 句 Go2 實機驗 + 5 句 USB 喇叭驗
- [ ] echo gate 確認不誤觸（tts_playing flip）

### Task E-2.3: GO/NO-GO 判定
- [ ] Mini GO 條件 + Go2 5 句 0 silent fail + echo gate 不誤觸
- [ ] **GO** → 進 Phase E-3
- [ ] **NO-GO** → fallback 到 Gemini native（重做 Phase E-3 with Gemini 主軌）

---

## Phase E-3: Dual Route + audio_format/served_by 重構（5/13 半天）

**Branch**: `feat/tts-dual-route`（從 main 建）

### Task E-3.1: Provider class 加 output_format 屬性

**Roy review #4 — 採較小改法**：保留 `synthesize() -> bytes | None`，**不**改 tuple return。fallback chain 風險最小。

- [ ] `tts_node.py` 各 provider class（ElevenLabs / OpenRouterGemini / EdgeTTS / Piper）加：
  ```python
  output_format: AudioFormat = AudioFormat.MP3  # 或 WAV (Piper)
  ```
- [ ] **不改** `synthesize()` 簽名（仍 `bytes | None`）— provider chain loop 在選中成功 provider 時記：
  ```python
  audio = provider.synthesize(text)
  if audio is not None:
      self._last_served_format = provider.output_format  # 給 _play_on_robot 用
      return audio
  ```

### Task E-3.2: `_play_on_robot` 改吃 served format
- [ ] L1185 改：`src_fmt = self._last_served_format` 而非 `self.config.provider == TTSProvider.PIPER ? WAV : MP3`
- [ ] 解 fallback chain bug（fallback 到 Piper 出 WAV 卻被當 MP3）
- [ ] backward compat：第一次呼叫前 `self._last_served_format = AudioFormat.MP3` 預設

### Task E-3.3: tts_callback 雙軌路由邏輯
- [ ] 入口判 effective_text_length:
  - safety/stop/alert/confirm keyword → 永遠 fast
  - effective_length ≤ 30 → fast lane
  - effective_length > 30 → quality lane
- [ ] effective_length 算法：去 audio tag `[playful]` + 去空白標點，中文 1 char = 1 unit + 英文 1 word = 1 unit
- [ ] safety keyword：`停|停止|不要動|先不要動|別動|小心|警告|危險|stop`

### Task E-3.4: Provider chain 配置（Roy review #3）

**ElevenLabs 進主鏈條件**：**Spike-Real GO**（不只 Mini GO）。Spike-Mini GO 但 Real NO-GO（Megaphone 整合失敗）→ ElevenLabs **不**放 quality lane 主軌。

- [ ] **Spike-Real GO 路徑**：
  - Fast lane: `edge-tts → Piper`
  - Quality lane: `ElevenLabs → OpenRouter Gemini → edge-tts → Piper`
- [ ] **Spike-Real NO-GO（即使 Mini GO）路徑**：
  - Fast lane 同上
  - Quality lane: `OpenRouter Gemini → edge-tts → Piper`（不放 ElevenLabs）
- [ ] **Mini NO-GO 路徑**（5/12 退 Gemini native spike）：
  - Fast lane 同上
  - Quality lane: `Gemini native → OpenRouter Gemini → edge-tts → Piper`
  - 不留 ElevenLabs 在鏈中

### Task E-3.5: 4 fallback 路徑單元測試
- [ ] fast lane edge fail → Piper（serve format WAV）
- [ ] quality lane ElevenLabs fail → OpenRouter Gemini
- [ ] quality lane all cloud fail → edge-tts
- [ ] quality lane all fail → Piper

### Task E-3.6: Jetson smoke
- [ ] 短句 5 個首音 < 2s（fast lane edge-tts）
- [ ] 長句 5 個首音 < 4s（quality lane ElevenLabs）
- [ ] safety keyword 短句強制 fast lane
- [ ] 長句故事 5 句連續無跳句（fallback chain 不亂）

---

## Verification

### Spike-Mini
- [ ] 5 句 latency 表（短句 < 2s、長句 < 4s）
- [ ] 主觀打分 ≥ 1 voice 過 4/5
- [ ] 中文自然度 ≥ 4/5
- [ ] PAYG quota 估算

### Spike-Real
- [ ] Go2 實機 5 句 0 silent fail
- [ ] USB 喇叭 5 句 0 silent fail
- [ ] echo gate 不誤觸

### Dual Route
- [ ] `python3 -m pytest speech_processor/test/test_tts_dual_route.py`：4 fallback 路徑全 PASS
- [ ] Jetson smoke：fast 短句 < 2s、quality 長句 < 4s
- [ ] safety keyword 強制 fast 路徑（即使 > 30 字也走 fast）
- [ ] format 重構：fallback 到 Piper 不被當 MP3 decode

---

## Risk

| Risk | Mitigation |
|---|---|
| ElevenLabs Mini 5/11 NO-GO | 5/12 退 Gemini native spike（spec P2-2-fallback 已寫） |
| ElevenLabs API quota 用爆 | 以 ElevenLabs dashboard 實際 quota 為準；spike script 記錄字數消耗；demo 期 quota 不足即 top-up |
| Megaphone 跟 ElevenLabs 整合卡關 | Spike-Real 半天若卡 → 退 Gemini native + edge-tts dual route |
| Dual-route 路由邏輯打亂既有 say_canned | 既有 say_canned 短，自然落 fast lane（< 30 字） |

---

## Out of Scope

- ElevenLabs Pro $99/mo 月費
- ElevenLabs custom voice cloning
- GPT-Realtime / GPT-Realtime-2 主鏈替換
- Megaphone DataChannel 邊收邊播 streaming（協議改動，demo 後再評估）
- Megaphone 16kHz → 24kHz upgrade
