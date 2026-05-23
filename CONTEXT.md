# CONTEXT

PawAI 專案的領域語言與真相來源索引。完整內容散在以下文件，本檔只當入口。

## 真相來源
- 工作慣例與環境：`CLAUDE.md`
- 專案定位、Demo 目標、北極星：`docs/mission/README.md`
- 系統架構 freeze（7 模組 + Studio）：`docs/pawai-brain/architecture/0511/`
- ROS2 介面契約：`docs/contracts/interaction_contract.md`

## 核心領域語言
- **PawAI Brain**：三層決策引擎（Safety → Policy → Expression），LangGraph 12 節點
- **Interaction Executive**：Layer 3 中控，所有動作唯一出口
- **Skill**：Brain 提案、Executive 執行的高階動作單位（如 greet_known_person、wave_hello）
- **Event vs State**：event = 觸發式 JSON 訊息；state = 持續式 10Hz JSON
- **Go2 Megaphone**：Go2 內建喇叭播放走 WebRTC DataChannel api_id 4001/4003/4002
- **Lane**：開發切換上下文單位（brain-studio-lane / nav-avoidance-lane）
- **非接觸式巡檢助理**：PawAI 在 2026-06 POC/demo 的安全定位。PawAI 負責感知、提醒與回報，不主打攙扶、碰觸、推拉或替代照護人員的直接照顧。詳見 ADR-0001。
- **雙層敘事**：PawAI 對外定位結構。平台身份 = 通用居家/機構四足互動機器人；2026-06 demo 場景 = 非接觸式機構巡檢助理。詳見 ADR-0002。
- **Engagement Gate**：PawAI 互動入口的多源觸發抽象。2026-06 demo 三源 = studio_ptt / face_approach / gesture_ok，不做 wake word / VAD。詳見 ADR-0003。
- **產品化接線**：把已能獨立運作的功能接成可被 PawAI Brain、Studio、語音或情境流程穩定呼叫的工作。重點不是新增能力，而是讓能力有清楚入口、命名、狀態回報與失敗處理。
- **安全成熟度**：PawAI 在 demo 或實際場景中能穩定維持安全邊界的程度。包含感知狀態一致、危險狀態可被系統即時攔截、任務啟動前能判斷環境是否可執行，以及失敗時能保守降級。

不熟術語時先查這份 + CLAUDE.md，再決定要不要 grill。
