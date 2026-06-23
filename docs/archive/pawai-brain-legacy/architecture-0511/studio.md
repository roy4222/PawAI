# PawAI Studio

Studio 文件已拆到 [`studio/`](studio/) 目錄，方便按 runtime flow、前端元件、Gateway/Mock bridge、debug runbook 閱讀。

- [studio/studio.md](studio/studio.md)：Studio 主總覽 — chat-first 設計哲學、雙路徑架構、5/11 凍結快照。
- [studio/studio-runtime-flow.md](studio/studio-runtime-flow.md)：WebSocket 端點 + ROS2 ↔ Gateway 訊息流（TOPIC_MAP 10 組、/tts、capability Bool）。
- [studio/studio-frontend-components.md](studio/studio-frontend-components.md)：Next.js 16 panel 元件拆分（chat / 6 feature modal / Zustand stores）。
- [studio/studio-gateway-mock-bridge.md](studio/studio-gateway-mock-bridge.md)：Gateway vs Mock Server 雙路徑對比 + event schema 對接（PawAIEvent 信封）。
- [studio/studio-debug-runbook.md](studio/studio-debug-runbook.md)：現場症狀 → 檔案定位（DISCONNECTED / brain trace 沒進來 / TTS 泡泡不出現等）。
