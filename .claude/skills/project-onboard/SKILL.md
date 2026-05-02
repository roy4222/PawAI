---
name: project-onboard
description: >
  PawAI 專案快速上手 — 讓任何 AI 在新 session 中立即理解專案全貌、
  當前進度、功能架構與開發慣例。每次開新對話、接手不熟悉的模組、
  或需要理解專案上下文時都應觸發。觸發詞包括但不限於：
  "onboard"、"上手"、"了解專案"、"project context"、"/onboard"、
  "這個專案是做什麼的"、"幫我看一下專案"、"我是新來的"、
  "給我專案背景"。即使使用者只是問了一個看起來簡單的功能問題，
  如果你對專案缺乏上下文，也應該先觸發這個 skill 建立基礎認知。
---

# PawAI 專案快速上手

## 這個專案是什麼

以 Unitree Go2 Pro 機器狗為載體的 embodied AI 互動陪伴平台。
核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」，不是導航或尋物。
硬底線：2026/4/13 展示。

## 三層架構

```
Layer 3（中控）：Interaction Executive + AI Brain
  事件聚合、高階決策、技能分派、安全仲裁
  部署：Jetson (Executive) + RTX 8000 (Brain)

Layer 2（感知）：人臉 / 語音 / 手勢 / 姿勢模組
  各自發布 event（觸發式）+ state（持續式）到 ROS2 topics
  部署：Jetson

Layer 1（驅動）：Go2 Driver + D435 + Jetson + ROS2
  硬體抽象、WebRTC DataChannel、模型推理 runtime
  部署：Jetson + Go2 Pro
```

所有動作唯一出口在 Layer 3。大腦提建議、Executive 做決策、Runtime 安全執行。

## 硬體拓撲

- **Jetson Orin Nano 8GB**（邊緣端）：ROS2 runtime、本地推理、感知模組
- **Go2 Pro**（機器人）：運動控制、音訊播放（WebRTC DataChannel api_id 4001-4004）
- **5x RTX 8000 48GB**（雲端）：LLM 推理（vLLM）、FastAPI Gateway
- **Intel RealSense D435**：RGB-D 攝影機（人臉偵測 + 深度估計）
- **HyperX SoloCast**：USB 麥克風（stereo-only，node 內手動 downmix to mono）

## 當前進度

讀 `references/project-status.md` 取得最新進度。
那份檔案會頻繁更新，不要依賴快取。

## 功能路由

根據你的任務，讀對應的 reference 檔案。每個 reference 包含：
模組定位、權威文件指標、核心程式、已知陷阱、開發入口、驗收方式。

reference 是導覽與摘要，不是第二份真相。詳細內容在它指向的權威文件裡。
如果 reference 和權威文件衝突，以權威文件為準。

| 你的任務涉及... | 讀這個 reference |
|----------------|-----------------|
| 語音、ASR、TTS、麥克風、Whisper、喚醒、Piper、MeloTTS、intent | references/speech.md |
| 人臉、face、YuNet、SFace、D435、追蹤、identity | references/face.md |
| 手勢、姿勢、gesture、pose、DWPose、RTMPose、MediaPipe、跌倒、fallen | references/vision-perception.md |
| LLM、大腦、brain、Qwen、vLLM、Gateway、FastAPI | references/llm-brain.md |
| Studio、前端、Next.js、面板、WebSocket、Chat、UI | references/studio.md |
| 測試、驗收、30 輪、test、CI、observer、clean-start | references/validation.md |
| Jetson、部署、環境、colcon、build、網路、ROS2 setup、sync | references/environment.md |

如果任務跨多個模組，依序讀相關的 references。
如果不確定從哪開始，先讀 `references/project-status.md` 看當前焦點。

## 權威文件索引

這些是各領域的 single source of truth：

| 領域 | 真相來源 |
|------|---------|
| 專案方向、Demo 目標、八大功能 | docs/mission/README.md |
| ROS2 介面契約（v2.1 凍結） | docs/contracts/interaction_contract.md |
| 語音模組設計 | docs/pawai-brain/speech/README.md |
| 人臉辨識設計 | docs/pawai-brain/perception/face/README.md |
| 手勢辨識設計 | docs/pawai-brain/perception/gesture/README.md |
| 姿勢辨識設計 | docs/pawai-brain/perception/pose/README.md |
| PawAI Studio 設計 | docs/pawai-brain/studio/README.md |
| 環境建置 | docs/runbook/README.md |
| 3/16 交付清單 | docs/mission/handoff_316.md |

## 模組文件結構

每個模組資料夾根目錄有 3 個入口檔案：

| 檔案 | 用途 | 誰看 |
|------|------|------|
| `README.md` | 模組當前真相（狀態卡 + 核心流程 + 已知問題） | 所有人 |
| `CLAUDE.md` | Claude Code 工作規則（禁止事項 + 陷阱 + 驗證指令） | Claude Code |
| `AGENT.md` | 介面契約 + 接手摘要（topic schema + 事件流 + 確認清單） | 任何 agent / 接手者 |

子資料夾：`research/`（選型研究）、`archive/`（歷史記錄）、`specs/`（設計規格）。

## 開發慣例速記

這些是跨模組通用的規則，不管做哪個功能都要知道：

- `pip install` → 一律用 `uv pip install`
- 改 Python 後必須 `colcon build --packages-select <pkg>` + `source install/setup.zsh`
- Jetson 用 zsh，source 時用 `.zsh` 不是 `.bash`，兩者不可混用
- HyperX 麥克風是 stereo-only，必須 `channels:=2` + 手動 downmix，不要用 `channels:=1`
- TTS WAV：16kHz/16bit/mono（Megaphone 路徑），+16dB gain boost
- 同時間只允許一套 speech session（禁止多 tmux 混跑）
- Go2 Megaphone 播放：`4001`(enter) → `4003`(upload chunks, 4096 base64) → `4002`(exit)，msg type 必須 `"req"`
- `ROS_DOMAIN_ID` 必須所有 node 一致，否則互相看不到
- Launch 檔案改動不需 rebuild，重啟即可

## 給非 Claude Code 平台的 AI

如果你不是在 Claude Code 的 skill 系統中被觸發，
請改讀 repo 根目錄的 `PROJECT_MAP.md`，裡面有依序閱讀指引。
那份檔案不假設任何 skill 機制存在，純粹用檔案路徑引導你。

## 觸發邊界

不需要觸發這個 skill 的情況：
- 任務已明確限定在單一檔案且不需要專案上下文
- 純 build / lint / format 等工具類操作（CLAUDE.md 已覆蓋）
