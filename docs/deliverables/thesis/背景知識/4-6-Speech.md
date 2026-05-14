# 4-6 語音互動管線技術

## 兩條並存的語音輸入路徑

本系統的語音互動管線並非單一直線流程,而是由兩條並存的輸入路徑組成,以對應「Demo 主線」與「舊本地麥克風路徑」兩種不同的使用情境:

- **Demo 主線(目前實際使用)**:使用者於 PawAI Studio 網頁介面按住說話(push-to-talk),錄音音訊透過 WebSocket 經由 `/ws/speech` 端點上傳至 Gateway(`pawai-studio/gateway/studio_gateway.py`)。Gateway **在自身行程內完成 ASR 與意圖分類**——直接以 HTTP POST 將音訊送至雲端 SenseVoice server(`http://127.0.0.1:8001/v1/audio/transcriptions`,經 SSH tunnel),取得辨識結果後在 Gateway 端完成意圖分類,再將結果發布至 ROS2 的 `/event/speech_intent_recognized` Topic。**此路徑完全不經過 `stt_intent_node`**,也無前置 VAD——push-to-talk 的起訖時間由使用者按鈕動作明確界定。

- **舊本地麥克風路徑(已廢棄但保留)**:使用者直接對 Go2 機身上的 USB 麥克風說話,由 `stt_intent_node` 連續監聽音訊串流並透過 Energy VAD 自動切分語音段落,再送入 ASR。此路徑保留於 `stt_intent_node.py` 中以備未來使用者改用獨立指向性麥克風時可以快速復用,但目前 Demo 場景已全面改用 Studio push-to-talk。

之所以從機身麥克風路徑轉為 Studio push-to-talk,是因為 Go2 內建的散熱風扇在機器狗運作期間持續產生寬頻噪音,機身麥克風與風扇出風口距離過近,實測語音辨識正確率僅約 20%,低於可用門檻。團隊嘗試調高麥克風增益(mic_gain)、調整 VAD 閾值、擴充 Whisper 幻覺過濾黑名單等軟體手段,皆無法克服物理層級的 SNR 劣化,遂於 2026 年 4 月 8 日教授會議後定案改用 Studio push-to-talk。此方案雖然犧牲了「直接對機器狗說話」的直覺性,但換來穩定的辨識率與 Demo 可靠度。

## 管線七階段總覽

兩條路徑在 ASR 之後收斂為相同的後續流程。整條管線可分為七個階段:**音訊擷取 → (僅舊路徑) Energy VAD → ASR 語音辨識 → 意圖分類 → LLM 大型語言模型回覆生成 → TTS 語音合成 → 音訊播放**。其中 Demo 主線的前兩階段(音訊擷取 + ASR)在 Gateway 行程內完成,後續 LLM、TTS、播放仍由獨立 ROS2 節點處理。實測端到端延遲(從使用者停止說話到機器狗開始播放語音回覆)約為 2 秒級,於 2026 年 4 月 8 日的 Studio Chat 閉環實測中完成多句連續對話驗證,整體管線穩定性達到 Demo 可用水準。

## Energy VAD 語音活動偵測(舊路徑前處理)

在舊本地麥克風路徑下,系統需先判斷何時使用者真的在說話,避免將靜音或背景噪音送入辨識模組。本系統採用輕量的能量式語音活動偵測(Energy-based Voice Activity Detection, Energy VAD),其原理是計算連續音訊短時能量,若超過 `start_threshold` 即視為語音開始,低於 `stop_threshold` 並持續超過 `silence_duration_ms` 即視為語音結束。

**程式碼預設值與 Demo 啟動覆寫值的差異**:
- `stt_intent_node.py` 中 `declare_parameter` 的程式碼預設值為:`start_threshold=0.015`、`stop_threshold=0.010`、`silence_duration_ms=800`、`min_speech_ms=300`。
- 實際 Demo 啟動腳本 `scripts/start_full_demo_tmux.sh` 在啟動 `stt_intent_node` 時覆寫為:`start_threshold:=0.02`、`stop_threshold:=0.015`、`silence_duration_ms:=1000`、`min_speech_ms:=500`。

這組被稱為 Noisy Profile v1 的調校值是針對 Go2 伺服馬達運轉時的持續噪音環境做系統性 A/B 測試後的結果,提高 `start_threshold` 能有效避免 Go2 噪音誤觸發語音段開始。選擇 Energy VAD 而非更精準的深度學習 VAD(如 WebRTC VAD、Silero VAD)的主要理由是延遲與簡單性:Energy VAD 每幀僅需 O(1) 運算,無需載入模型,延遲極低。

需再次強調的是,**目前 Demo 主線採用 Studio push-to-talk,此路徑完全跳過 Energy VAD**;上述參數僅對舊本地麥克風路徑生效。

## ASR 三級 Fallback 機制

語音辨識是整條管線中最複雜的環節。本系統在 ASR 層存在**兩條獨立路徑**,需分開說明:

### Demo 主線:Gateway 內直打 SenseVoice Cloud

Demo 主線中,Studio Gateway(`studio_gateway.py`)的 `/ws/speech` WebSocket 端點接收到音訊後,**在 Gateway 行程內直接以 HTTP POST 呼叫 SenseVoice Cloud server**(`http://127.0.0.1:8001/v1/audio/transcriptions`,經 SSH tunnel 連線至遠端 RTX 8000),取得辨識文字後於 Gateway 端執行意圖分類,再將結果發布至 ROS2 的 `/event/speech_intent_recognized` Topic。此路徑是單條直打,**不經過 `stt_intent_node`**,也不存在多級 fallback——若雲端 server 不可用,Gateway 會直接回報錯誤。

### 舊本地麥克風路徑:stt_intent_node 三級 Fallback

舊本地麥克風路徑下,`stt_intent_node` 採用**三級自動降級(Graceful Degradation)** 策略,在網路狀況、伺服器可用性、運算資源變化時動態切換後端,確保服務不中斷。三個層級依 `stt_intent_node.py` 中 `provider_order` 參數的順序執行(注意:程式碼內部一級 provider key 仍為 legacy 名稱 `qwen_cloud`,實際後端已切換為 SenseVoice FunASR server):

**一級:SenseVoice Cloud(provider key: `qwen_cloud`)**。SenseVoice 是阿里巴巴達摩院於 2024 年開源的中文優化語音辨識模型家族,專為亞洲語言(中文、粵語、日文、韓文、英文)設計,相較於 Whisper 對中文短句與方言的辨識率更高,並額外輸出說話者的情緒與音訊事件標籤。本系統採用 SenseVoice Small 版本,透過 **FunASR 框架**(阿里巴巴達摩院維護的端到端語音工具包)部署於遠端 RTX 8000 伺服器上,以 FastAPI 封裝 HTTP 介面(`scripts/sensevoice_server.py`,port 8001)。Jetson 透過 SSH tunnel 與雲端伺服器建立連線,將錄音音訊以二進位格式 POST 至伺服器並接收 JSON 回應。實測延遲約 600 毫秒。

**二級(備援):SenseVoice Local**。當雲端伺服器不可用(SSH tunnel 斷線、伺服器未啟動、網路中斷)時,系統自動切換至 Jetson 本地執行的 SenseVoice 量化版本。此版本透過 **sherpa-onnx**(由 k2-fsa / 新一代 Kaldi 團隊維護的輕量化語音推理框架)執行 int8 量化後的 ONNX 模型(`sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17`,檔案大小約 228 MB,執行時佔用約 352 MB RAM)。此版本完全離線、僅使用 CPU,不佔用 Jetson 的 GPU 資源,實測延遲約 400 毫秒(因省去網路往返時間,甚至略快於雲端版本),辨識率維持與雲端相當的水準。

**三級(最終備援):Whisper Tiny(faster-whisper)**。若 SenseVoice Cloud 與 Local 皆不可用,系統退回至 OpenAI 於 2022 年發布的 Whisper 模型。Whisper 為多語言 Encoder-Decoder Transformer 架構,原生支援 99 種語言,在高品質錄音條件下表現優異。本專題透過 **faster-whisper** 框架(基於 CTranslate2 的 CUDA 加速實作,速度最高可達原生 Whisper 的約 4 倍)於 Jetson 上推理。

**關於 Whisper 實際部署配置的澄清**:`speech_processor/config/speech_processor.yaml` 中的**基礎預設值**為 `whisper_local.model_name: "tiny"`、`whisper_local.device: "cpu"`、`whisper_local.compute_type: "int8"`(CPU + tiny + int8 的極省資源配置,用於開發與低功耗場景)。然而 Demo 啟動腳本 `scripts/start_full_demo_tmux.sh` 在啟動 `stt_intent_node` 時**覆寫為 `whisper_local.device:=cuda`、`compute_type:=float16`**,即實際 Demo 跑的是 CUDA + float16 版本。此覆寫之必要性源於 Jetson 的 CUDA 核心不支援 int8 量化(強制指定 int8 會 silent fail 無錯誤訊息),因此 Demo 必須使用 float16 混合精度。實測 RTF(Real-Time Factor,推論時間除以音訊時長)約 0.13,即 3 秒音訊需約 390 毫秒處理,延遲約 3 秒(含模型首次載入)。**Whisper 僅為 `stt_intent_node` 三級 fallback 的最末層;Demo 主線走 Gateway 直打 SenseVoice Cloud,正常連線下 Whisper 不會被觸發**。

**三層 ASR A/B 測試結果**(25 筆,Go2 噪音環境):

| 指標 | SenseVoice Cloud | SenseVoice Local | Whisper Tiny |
|---|:---:|:---:|:---:|
| 正確 + 部分正確率 | 92% | 92% | 52% |
| Intent 正確率 | 96% | 92% | 56% |
| 幻覺 / 亂碼率 | 0% | 0% | 8% |
| 延遲 | ~600 ms | ~400 ms | ~3000 ms |
| 需要網路 | 是 | 否 | 否 |

**Whisper 幻覺問題與對策**:Whisper 模型存在一個已知的「幻覺」(Hallucination)問題——在靜音片段或低訊噪比片段會輸出假文字,最常見的是訓練資料中的字幕模板(例如「字幕 by 索兰娅」「請訂閱頻道」等)。本系統採取以下對策:啟用 `vad_filter=True` 使用 Silero VAD 預先過濾非語音段、設定 `no_speech_threshold=0.6` 拒絕低信心結果、設定 `log_prob_threshold=-1.0` 過濾低機率輸出、維持一份 **22 條幻覺黑名單字串**對輸出結果進行最終過濾、並過濾所有少於 2 字的結果。這些對策共同將 Whisper 的假陽性問題降至可接受範圍。

## 意圖分類與 Fast Path

ASR 輸出的文字接著進入意圖分類階段。本系統採用**規則式(Rule-based)分類器**而非機器學習分類器,原因是意圖類別有限(約 10 種)、規則明確、且可享受近乎零延遲的直接查表速度。分類器透過關鍵字匹配將 ASR 文字對應至以下意圖標籤:`greet`(打招呼)、`stop`(停止)、`sit`(坐下)、`stand`(站起)、`come_here`(過來)、`chat`(一般對話)等。

**Fast Path 設計**:對於高頻的動作類意圖(stop、sit、stand 等),系統繞過下游的大型語言模型處理,直接呼叫內建的 RuleBrain 規則引擎生成預設回覆,總延遲接近零。此設計讓 Demo 場景中的指令類互動能瞬間響應,優於「必須經過 LLM」的純雲端方案。僅當使用者說出一般對話(無法匹配任何已知意圖關鍵字)時才進入 LLM 流程。

## LLM 三級 Fallback 機制

大型語言模型負責處理意圖分類無法涵蓋的一般對話,生成符合情境的中文回覆。本系統同樣採用三級降級策略:

**主線:Cloud Qwen2.5-7B-Instruct**。採用阿里巴巴開源的 Qwen2.5 系列 7B 參數 Instruct 版本,透過 **vLLM** 推理框架部署於遠端 RTX 8000 伺服器。vLLM 是 UC Berkeley Sky Computing Lab 於 2023 年開源的高效能 LLM 推理引擎,核心技術為 **PagedAttention**(將 KV cache 管理對應至作業系統的虛擬記憶體分頁機制,大幅降低記憶體碎片化)與 **Prefix Caching**(重複 prompt 前綴的結果快取重用)。本系統的互動場景中,系統提示(system prompt)固定不變,Prefix Caching 帶來顯著的加速,實測 LLM 回覆延遲約 1.5 秒。模型參數 `llm_max_tokens=80`(由 `llm_bridge_node.py` declare_parameter 預設值),SYSTEM_PROMPT 內硬性要求 `reply_text` 不超過 **12 個中文字**,避免過長語音導致互動節奏拖沓。

**二級:Ollama 本地 Qwen2.5-1.5B**。當雲端不可用時(SSH tunnel 斷線、vLLM 伺服器異常、GPU OOM 等),系統自動切換至 Jetson 本地的 **Ollama**(Jetson ARM64 確認可用的輕量 LLM 推理框架)執行 Qwen2.5-1.5B-Instruct 模型(Q4_K_M GGUF 量化,檔案大小約 1.12 GB,執行時佔用約 1.2 至 1.5 GB RAM)。本地模型採用 CPU 推理模式(`CUDA_VISIBLE_DEVICES=""`)避免與其他 GPU 模組競爭資源,實測 P50 延遲約 1.0 秒、生成速度約 29 tokens/sec,25 字回覆的端到端延遲約 2 至 3 秒。值得注意的是,2026 年 4 月 8 日的教授會議上,團隊正式確認本地 LLM 的語言流暢度遠低於雲端主線,實務上只能作為「維持管線不中斷」的形式備援,無法承擔主要對話責任。先前評估的更小模型 Qwen2.5-0.5B 雖然速度更快(P50 延遲 0.8 秒、RAM 增量僅 139 MB),但中文對話品質明顯不足,已被排除。

**最終備援:RuleBrain 規則引擎**。當雲端與本地 LLM 皆不可用(或 LLM timeout 超過 2 秒)時,系統退回至完全 deterministic 的規則引擎。RuleBrain 內建一組固定的模板回覆(例如問候類回覆「你好,很高興見到你」、停止類回覆「好的,我停下」、無法理解時的通用回覆「抱歉,我聽不太懂,你可以再說一次嗎」等),根據輸入的意圖類別直接查表輸出,延遲接近零,並保證絕不輸出空字串或錯誤格式。此層級是整條管線的最後防線——即使網路完全斷線、本地模型損毀,RuleBrain 仍能讓機器狗維持基本的對話回應能力,不會完全啞掉。

## TTS 雙軌 Fallback 機制

語音合成階段採用雙軌策略:

**主線:edge-tts 微軟雲端 TTS**。edge-tts 是一個開源的 Python 客戶端,透過呼叫微軟 Edge 瀏覽器內部使用的 Neural Voice API 取得雲端合成的語音檔案。此服務不需註冊帳號或 API key,使用方式如同呼叫微軟的公開服務。本系統使用中文 Xiaoxiao 神經語音作為主線聲音,實測首句延遲約 0.3 至 0.8 秒(包含網路往返時間),音質等級評為 A 級(相較於本地備援的 Piper 音質更為自然、語調更有抑揚頓挫)。edge-tts 不佔用 Jetson 的 CPU / GPU / 記憶體資源(僅需約 50 MB 作為 HTTP 客戶端緩衝),是 Demo 場景中的理想選擇。主要限制為必須聯網,且此為微軟的非正式公開 API,若未來微軟變更介面可能失效。

**備援:Piper 本地 TTS**。Piper 是 Rhasspy 開源社群維護的離線 TTS 引擎,採用 **VITS(Variational Inference TTS)** 架構(VITS 為 2021 年論文《Conditional Variational Autoencoder with Adversarial Learning for End-to-End Text-to-Speech》提出的端到端語音合成模型),以 ONNX 格式於 CPU 上執行推理。本系統使用 `zh_CN-huayan-medium` 中文單聲道模型,模型檔案僅約 63 MB,執行時佔用約 200 MB RAM,完全不依賴網路。原生取樣率為 22050 Hz,透過 USB 外接喇叭播放時可保留此原始音質;若改走 Go2 Megaphone 路徑則會被硬體限制降採樣至 16 kHz。實測首句延遲約 2.4 秒,略慢於 edge-tts 但仍在可接受範圍。Piper 相較於其他開源 TTS 的主要優勢是其為 CPU-only 且記憶體佔用極低,不會與其他模組競爭 Jetson 的有限資源。

**已排除的 TTS 候選**:本專題曾評估過多個其他 TTS 方案並予以排除,包含:

- **MeloTTS**(音質接近 edge-tts 但速度不如 Piper,卡在尷尬定位,2026-03-26 會議決議棄用)
- **ElevenLabs**(商業服務成本高、API 整合複雜,已兩次棄用)
- **Spark-TTS-0.5B**(模型約 3.95 GB,Jetson 8 GB 記憶體不足以與其他模組共存)
- **XTTS v2**(模型約 1.8 GB、runtime 另需 2 至 3 GB,超出預算)
- **ChatTTS**(需 4 GB 以上 GPU VRAM,穩定性差)
- **Bark**(完整模型需約 12 GB VRAM,遠超 Jetson 硬體能力)

## 音訊播放:USB 外接喇叭與 Go2 Megaphone 雙路徑

合成完成的 WAV 音訊檔案接著送至播放階段。本系統支援兩條播放路徑:

**主線:USB 外接喇叭本地播放**。本專題於 2026 年 3 月採購外接 USB 音訊裝置(Jieli CD002-AUDIO,立體聲 48 kHz,對應 ALSA `plughw:3,0`)安裝於機器狗機身上,TTS 合成的音訊檔案直接透過 ALSA `aplay` 或 Python `sounddevice` 函式庫在本地播放。此路徑的優勢是:保留原生取樣率(22050 Hz 或 48 kHz)、延遲極低、穩定可靠、不依賴 Go2 韌體的 Megaphone API。

**備援:Go2 Megaphone DataChannel**。Unitree Go2 原廠提供 Megaphone API(api_id 4001 至 4003),允許外部裝置透過 WebRTC DataChannel 上傳音訊至機身內建喇叭播放。協議流程為 **ENTER(4001)→ UPLOAD(4003,分塊上傳,每塊 4096 base64 字元)× N → EXIT(4002)**,每塊間隔約 70 毫秒發送,訊息 type 必須為 `"req"`(非 `"msg"`)、payload 必須包含 `current_block_size` 欄位(文件未載明的隱性要求)。此路徑受限於 16 kHz 採樣率(Go2 硬體限制)與 mid-session 重啟後的 silent fail 問題,作為備援使用。本專題曾花費約兩週時間判定此 API「失效」,後透過逆向分析通訊封包找出正確格式,最終驗證連續播放成功。

## Echo Gate 自激防止

語音互動系統常見的一個問題是**自激回饋(Self-echo Feedback)**——機器狗播放語音時,同一組麥克風會接收到自己的聲音並誤判為新的語音輸入,造成無限迴圈。本系統透過 **Echo Gate** 機制解決此問題:當 `/state/tts_playing` flag 為 True 時(表示 TTS 正在播放),ASR 節點強制靜音不發布任何辨識結果;TTS 播放結束後,系統額外等待 `cooldown = 0.5` 秒(處理音訊管線殘留)+ `echo_cooldown = 1.0` 秒(處理喇叭延遲),共 **1.5 秒的總靜音期**,才重新開放 ASR 接收使用者語音。此機制經 Sprint 期間反覆驗證,是防止 Megaphone 播放回音造成管線失控的核心防護。

## Noisy Profile v1 噪音環境調校

為應對 Go2 伺服馬達運轉時的持續噪音,本專題於 2026 年 3 月 28 日建立 **Noisy Profile v1** 參數配置,針對 Go2 真機運作條件進行系統性的 VAD 與 ASR 調校。核心調整包括:

- **mic_gain**:`stt_intent_node` 中的 code default 為 1.0,Demo 啟動腳本覆寫為 **8.0**。A/B 實測甜蜜點——gain 10 測試後發現 Whisper 辨識率反而下降至 43%、gain 12 為 62%,證明噪音放大過度,8.0 為最佳平衡。
- **Energy VAD 閾值**:如前述「Energy VAD 語音活動偵測」段落所示,Demo 啟動腳本將 VAD 閾值覆寫為更高的值以避免 Go2 伺服噪音誤觸發。
- **Whisper 設定**:啟用 `vad_filter`、`no_speech_threshold=0.6`、幻覺黑名單從最初 6 條擴充至 22 條。

實測 Whisper Tiny(yaml 預設 `model_name: "tiny"`)在此 profile 下的 A/B 結果為 64% 正確率,確認為 Whisper 在中文短句 + 機器噪音場景下的瓶頸。此數據後來推動了從 Whisper 到 SenseVoice 的主線切換決策。

此外,Noisy Profile 亦引入 `ENABLE_ACTIONS` 環境變數作為動作執行的安全門——當設定為 `false` 時,`llm_bridge_node` 停止發布 `/webrtc_req`,Go2 即使收到錯誤的 ASR 結果或意圖分類錯誤也不會執行危險動作,用於開發與除錯階段。動作控制的仲裁主線目前由 `interaction_executive`(統一中控狀態機)負責,已取代早期的 `event_action_bridge`。

## Plan B 固定台詞備案

考量到 Demo 當天 GPU 雲端伺服器的穩定性風險(本專題 Sprint 期間實際發生過數次斷線事件),團隊於 2026 年 4 月 8 日教授會議上決定追加 **Plan B 固定台詞備案**。Plan B 的運作機制如下:ASR 辨識出意圖後直接匹配預先設計的固定回答,繞過 LLM 與 TTS 的動態生成流程(或使用 Piper 離線合成固定台詞的快取檔案),回應速度小於 1 秒。Plan B 需設計至少 15 組問答涵蓋 Demo 主要情境(自我介紹、功能說明、閒聊、指令回應),並於 PawAI Studio 顯示連線狀態燈號讓團隊能即時判斷是否切換模式。Plan B 的負責人為團隊成員陳如恩。此備案無法取代完整的 AI 對話體驗,但能在最壞情況下維持 Demo 現場的流暢度,必要時搭配預錄的 AI 對話影片作為佐證。

## ROS2 Topic 介面整合

語音模組透過以下 ROS2 Topic 與系統其他模組整合:

| Topic | 方向 | 說明 |
|---|:---:|---|
| `/event/speech_intent_recognized` | 輸出 | 意圖辨識事件(JSON 格式,含意圖類別、信心度、原始文字) |
| `/state/interaction/speech` | 輸出 | 語音管線狀態廣播(5 Hz,含目前階段:聆聽/辨識/思考/說話) |
| `/state/tts_playing` | 輸出 | TTS 播放中 flag(供 Echo Gate 使用) |
| `/tts` | 輸入 | 要合成的文字(供其他模組觸發語音輸出) |
| `/asr_result` | 輸出 | 原始 ASR 辨識文字 |

其他模組(如 Interaction Executive、PawAI Studio Gateway、物體辨識情境 TTS 觸發)透過這些 Topic 與語音模組互動,不需要知道管線內部的任何細節。

## 已知限制

本節對應第五章系統限制第 3 節,列出本模組實務上的邊界條件:

1. **機身麥克風不可用**(如前所述,已改用 Studio push-to-talk)。
2. **本地 LLM 品質不足**:Jetson 本地的 Qwen 系列小模型(1.5B)中文對話品質明顯低於雲端 7B 主線,4/8 會議確認僅能作為形式備援。
3. **LLM 回覆過短**:受限於 `llm_max_tokens=80` 與 SYSTEM_PROMPT 中的 **12 字硬截斷**要求,LLM 無法展開詳細對話或多輪推理,個性化表達空間有限。已列為下一步改進重點(prompt 放寬字數至 50+、加入 PawAI 個性設定)。
4. **無多輪對話記憶**:當前 LLM 呼叫為無狀態模式,每輪對話獨立,不記得先前的對話內容。多輪 memory 功能尚未整合,列為未來工作。
5. **Stop intent 辨識不穩**:SenseVoice 對「現在請停止動作」這類較長的句式辨識率約為 60%,簡短的「停」辨識率較高。建議使用者說簡短指令或搭配手勢 stop 作為更可靠的緊急停止機制。
6. **雲端 GPU 伺服器穩定性風險**:Sprint 期間實際發生過數次 RTX 8000 伺服器斷線事件,Plan B 固定台詞備案為 Demo 當天的必備保險。
