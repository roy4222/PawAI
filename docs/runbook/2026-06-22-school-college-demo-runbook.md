# 2026-06-22 學校招生 Demo Runbook — 輔大管理學院版

> 主軸：**語音 + 三鏡頭**。非 LiDAR 原版（不開 `--with-lidar`）。
> 流程：打招呼 → 自我介紹 → 介紹館院特色 → 三鏡頭展示 → 結尾道別。

## 這次新增了什麼（相對 5/16 資管版）

| 元件 | 變更 |
|------|------|
| `pawai_brain/.../nodes/mode_classifier.py` | 新增 `school_demo_college` mode，「管理學院/管院」+ ASR 錯字容錯觸發 |
| `pawai_brain/.../conversation_graph_node.py` | 新增 `_SCHOOL_DEMO_COLLEGE_FACTS`（管理學院 grounded facts），僅此 mode 注入 |
| Studio Gateway `studio_gateway.py` | 新增 `POST /api/farewell_action` → 發管院結尾口號 /tts + 比愛心 1036 |
| Studio 前端 `chat/farewell-button.tsx` | 主 chat 面板「道別」鈕（粉紅愛心），按下觸發結尾 |
| `scripts/school_demo_ending.py` | 加 `--college` 旗標切管院口號（SSH 備援） |

舊資管版（`school_demo_request`）**完全保留**，講「資管」仍走舊版。

## 觸發語對照（現場主持人怎麼說）

| 段落 | 對狗說 | brain mode |
|------|--------|-----------|
| 自我介紹 | 「自我介紹一下」 | `self_intro_request` |
| **介紹館院** | 「介紹一下**輔大管理學院**」/「介紹**管院**特色」 | `school_demo_college` ← 新 |
| 三鏡頭 | （操作展示，無觸發語） | 人臉/手勢/姿勢 live |
| 結尾 | 按 Studio「道別」鈕 | → /tts 口號 + 比愛心 |

口號原文：**「最後~祝各位考生面試順利！請記得，輔大管院填寫第一志願喔！」**

## 部署（到 Jetson，demo 前一天做完）

```bash
# 1. 部署 brain + studio（用 pawai CLI；deploy 會 rsync 源碼）
pawai jetson deploy --module brain
pawai jetson deploy --module studio

# 2. Jetson 上 rebuild brain（rsync 不會 rebuild install/）
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && \
  colcon build --packages-select pawai_brain && source install/setup.zsh"
```

## 啟動（demo 當天，非 LiDAR 原版）

**主線 — 一鍵 CLI（推薦）：**
```bash
pawai demo start --school
# = 全功能原版 demo（5 感知 + brain + TTS + Studio overlay，非 LiDAR）
#   + 啟動後自動印「五段流程 + 道別鈕 + SSH 備援」cheat-sheet
# 管院關鍵字已 baked 進 brain、永遠在線 —— 此 flag 不改 runtime，只多印備忘。
```

**手動等價（CLI 不可用時）：**
```bash
# Jetson 上：五感知 + brain + TTS 全功能 demo（不開 LiDAR）
ssh jetson-nano "cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh"
# Mac 操作端：開 Studio（含「道別」鈕）
bash pawai-studio/start.sh        # → http://localhost:3000/studio
# 或現場招生模式 wrapper（指向學校場地 Jetson IP）：
GATEWAY_HOST=<學校 Jetson IP> bash pawai-studio/start-school-live.sh
```

收工：`pawai demo stop`

## 結尾觸發（兩條路）

**主線 — Studio「道別」鈕**：主 chat 面板右上（粉紅愛心圖示）。按下 → confirm →
發口號 + 比愛心。

**備援 — SSH 腳本**（按鈕不靈時）：
```bash
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && \
  source install/setup.zsh && python3 scripts/school_demo_ending.py --college"
```

## 驗證（無實機時靠 unit test；到場後現場驗）

- `mode_classifier`：91 tests 綠（含管院 14 例，CI-gated）
- `user_message_builder`：管院 facts 隔離（Jetson 跑，需 rclpy）
- Gateway `test_demo_controls.py`：21 tests 綠（含 farewell 6 例）
- 前端 `farewell-button.test.tsx`：1 test 綠

**到場必驗**：
1. 對狗說「介紹一下輔大管理學院」→ 應念管院 facts（不是資管）
2. 按「道別」鈕 → 聽到管院口號 + 看到比愛心動作
3. 按鈕不靈 → 改跑 `school_demo_ending.py --college`

## 已知風險

- **道別鈕是全新 code，6/22 現場第一次實跑** → 故保留 SSH 腳本備援
- Gateway 的 `/tts` publish 繞過 brain，口號**不入對話歷史**（設計如此）
- 比愛心需 `WebRtcReq` 可用；不可用時口號照播、僅略過愛心（log 會 warn）
