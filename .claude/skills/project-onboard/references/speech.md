# speech 導覽

正式入口：repo 的 `docs/architecture/speech/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`speech_processor/`，依問題使用 rg 定位相關實作與測試。

分開驗證錄音、ASR、intent、TTS 與播放。曾用麥克風需要 stereo 擷取再 downmix；換裝置時重查 channels。Go2 Megaphone 路徑曾要求 16kHz／16bit／mono WAV、req 訊息及 enter→upload→exit 狀態序列，實際實作與設備仍需核對。不要把舊增益或音效卡號直接當預設。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
