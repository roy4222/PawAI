# 2026-06-18 簡報 — 複雜架構圖生圖 Prompt

> 簡報（`2026-06-18-pawai-presentation.pdf`）裡**幾乎所有圖都已用原生 SVG 畫好、可直接用**。
> 這份檔案只在「想把最複雜的架構圖換成更精緻 AI 生成版」時才需要：
> - **第 9 頁（完整工程架構）**：目前是 placeholder（白話版流水線在第 7 頁，已可獨立講懂）—— 這頁建議用下面 prompt 生圖後填入。
> - **第 17 頁（雙層安全閘）**：**已用原生 SVG 畫好可直接用**，下面 prompt 只是選配升級。
>
> **怎麼用**：把下面的英文 prompt 貼到任一圖像生成工具（gpt-image-1 / Google Imagen / Gemini 2.5 Flash Image / fal.ai 等），生出 1920×1080 或 16:9 的圖 → 存成 PNG → 在 open-slide dev server 的 Assets 面板上傳 → 點該頁的對應位置 Replace（或把該頁 SVG 換成 `<img>`）。
>
> 風格已鎖：深色 navy 底 + 琥珀/青 line-art，跟簡報一致。生圖後若色調不合，可在 prompt 補 "match a dark navy #0a0c10 background with amber #f5b301 and teal #38e0c8 line-art"。

---

## 第 9 頁 — 完整工程架構圖

**用途**：工程路線總覽（完整版），給有概念的人看的端到端架構。

```
A clean friendly flat-vector technical architecture diagram, dark navy background
(#0a0c10), amber (#f5b301) and teal (#38e0c8) accent line-art, consistent stroke
width, rounded corners, no photorealism, no emoji. Horizontal left-to-right
data-flow pipeline with labeled boxes connected by amber arrows.
Stage 1 (far left): a stylized line-art quadruped robot dog box labeled in
Traditional Chinese '載體 Go2 Pro 電池'.
Stage 2: a chip box labeled '邊緣運算 Jetson Orin Nano'.
Stage 3: three small stacked sensor icons (an eye for camera, an ear for
microphone, a radar wave for LiDAR) labeled '相機 D435 / 麥克風 / 光達 RPLIDAR'.
Stage 4: a vertical column of five small chips labeled '人臉 face / 物體 object /
手勢 gesture / 姿勢 pose / 語音 speech', titled '五路 AI 感知'.
Stage 5: a prominent amber double-outlined gate box labeled
'SCOREBOARD 安全閘 (pass 才放行)' sitting at the entrance to the brain.
Stage 6: a brain icon box with three stacked inner layers labeled
'安全 Safety / 政策 Policy / 表達 Expression', titled 'PawAI Brain'.
Stage 7: a box labeled 'skills 允許清單'.
Stage 8: a box labeled 'interaction_executive 單一出口'.
Stage 9 (far right): splits into two boxes — 'Go2 控制' and 'Studio 觀察'.
Emphasize with a glowing amber highlight that the SCOREBOARD gate is locked at the
Brain entrance. 16:6 wide aspect ratio, generous spacing, large readable labels,
minimal text, editorial tech-poster aesthetic.
```

---

## 第 17 頁 — 雙層安全閘 fail-closed 流程圖

**用途**：工程挑戰③「AI 不能直接控制機器人」的核心機制圖。

```
A clean friendly flat-vector flow diagram showing a two-layer fail-closed safety
gate, dark navy background (#0a0c10), amber (#f5b301) accents with red (#ff5d5d)
for blocked/rejection points, teal (#38e0c8) for the LLM branch, consistent
line-art stroke, rounded corners, no photorealism, no emoji.
Main horizontal flow left to right with Traditional Chinese labels:
Box 1 speech bubble '語音：請翻跟斗' → arrow →
Box 2 'SafetyLayer 規則層 (關鍵字字面比對)' → arrow →
Box 3 a RED-outlined box 'validate() 攔 banned_api 1301' marked with a large red ✕ → arrow →
Box 4 a RED-outlined box 'executor 執行前再攔一次' marked with a large red ✕ → arrow →
Box 5 a bold red 'BLOCKED 雙層 fail-closed'.
Above the main flow, a separate teal branch box labeled
'LLM (受 9 項 allowlist 閘控 · 生不出 motion api)' with a dashed line dropping into
the main flow to show its proposals are gated.
A small note at the bottom: '世界狀態預設不可用 (publisher 沉默就當 fail-closed)'.
Two clearly marked red rejection points. 16:5.5 wide aspect ratio, large readable
labels, minimal text, friendly explanatory tech-diagram style for a general audience.
```

---

## 另外要你提供的「真實照片」（簡報裡是 ImagePlaceholder）

這些**不是**生圖、是你系統的真實畫面（生假的會違反簡報「誠實」主軸）：

- **第 13 頁** — Go2 背上掛 Jetson + RPLIDAR + D435 + USB 音訊的硬體疊裝實拍照（含 2464 降壓模組、3D 列印背板）
- **第 21 頁** — PawAI Studio thinking trace 截圖
- **第 22 頁** — Foxglove LiDAR `/scan_rplidar` 點雲 + D435 depth + 地圖三畫面

上傳方式同上：dev server Assets 面板上傳 → 點 placeholder → Replace。
