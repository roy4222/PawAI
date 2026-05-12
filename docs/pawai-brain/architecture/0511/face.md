# 人臉辨識（Face Perception）文件索引

這一組文件整理 PawAI 的人臉辨識模組。它不是單純「看到臉」而已，而是把 D435 的 RGB/depth 影像轉成身份、距離、事件，最後供 Brain 補語境、Executive 做打招呼和安全互動仲裁。

## 快速結論

目前已做到：
- 使用 `face_identity_node` 進行 YuNet 偵測、SFace 識別、IOU tracking、身份穩定化。
- 可辨識已註冊人，例如 `roy`、`grama`，並把穩定身份送到 `/state/perception/face`。
- 可回答「你看得到我嗎？」、「你現在看到什麼人？」這類問題，因為 Brain 會把 `current_speaker` 注入 world state。
- 已有距離估計：從 `/camera/camera/aligned_depth_to_color/image_raw` 的臉部 ROI 取中位數，輸出 `distance_m`。
- 已有打招呼事件：Executive 收 `/event/face_identity`，在穩定身份、距離/停留達到 ENGAGED、無 TTS/技能中斷風險時發 `greet_known_person`。
- 已有陌生人警報路徑，但目前應視為高誤觸風險功能，不建議 Demo 主打。
- 已有註冊腳本 `scripts/face_identity_enroll_cv.py`，但還沒有整合到 `pawai cli`。

待改進重點：
- 把註冊流程包進 `pawai cli`，包含拍攝、重訓、驗證、刪除/覆蓋既有人名。
- 改善低光、側臉、反光、多人同框造成的誤認與 track 抖動。
- 降低重複打招呼：目前 Executive 有 20 秒 name cooldown，但 track fragment、identity_changed、重啟 node 仍會重觸發。
- 把 `distance_m` 用到更完整的互動策略，現在主要供 attention/greet gating，還沒接到導航避障。
- 重新決定陌生人警報是否保留；若保留，應改成 trace-only 或需要二次確認。

## 文件地圖

| 文件 | 用途 |
|------|------|
| [face/face.md](face/face.md) | 原始完整快照，保留 5/11 freeze 全量內容 |
| [face/face-runtime-flow.md](face/face-runtime-flow.md) | Runtime 架構、topic、資料流、啟動入口 |
| [face/face-recognition-tracking.md](face/face-recognition-tracking.md) | YuNet/SFace、DB、threshold、tracking、距離估算 |
| [face/face-brain-executive-integration.md](face/face-brain-executive-integration.md) | Brain、Executive、Studio、legacy bridge 如何消費 face |
| [face/face-registration-debug-runbook.md](face/face-registration-debug-runbook.md) | 現場註冊、除錯指令、常見問題、明天開發優先順序 |

## 權威程式位置

| 主題 | 檔案 |
|------|------|
| 主節點 | `face_perception/face_perception/face_identity_node.py` |
| Jetson 參數 | `face_perception/config/face_perception.yaml` |
| Launch | `face_perception/launch/face_perception.launch.py` |
| 註冊腳本 | `scripts/face_identity_enroll_cv.py` |
| 原始推論腳本 | `scripts/face_identity_infer_cv.py` |
| Brain 語境注入 | `pawai_brain/pawai_brain/conversation_graph_node.py` |
| world state stale filter | `pawai_brain/pawai_brain/nodes/world_state_builder.py` |
| Executive face rule | `interaction_executive/interaction_executive/brain_node.py` |
| Attention state machine | `interaction_executive/interaction_executive/attention_machine.py` |
| Studio pass-through | `pawai-studio/gateway/studio_gateway.py` |
