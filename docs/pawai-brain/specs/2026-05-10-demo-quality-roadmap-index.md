# Demo-Quality Roadmap — 6 Specs Index

> **Status**: draft
> **Date**: 2026-05-10
> **Demo 倒數**: 5/16（剩 6 天）
> **Owner**: Roy

---

## 一句話定位

> 把 PawAI 從「會動但講話像罐頭、能力散落、評審看不懂」升級為「**會自我展示、知道自己是誰、看懂手勢姿勢、辨識物體與導航的具身互動機器狗**」。

PawAI 不是長者陪伴專案。是**多模態感知融合的具身互動機器狗**：D435 + RPLIDAR 整合，能看懂人、理解語音、辨識物體，並安全地做出語音、動作與導航回應。核心 4 字：**看懂 / 理解 / 決策 / 行動**。

---

## 6 Spec 一覽

| # | Spec | 主題 | demo 前 | demo 後 | 風險 | 文件 |
|---|---|---|---|---|---|---|
| **1** | **LLM Naturalness A+** | 講話、自我介紹、知道自己 | ✅ 主軸 | — | 中 | [spec1](./2026-05-10-llm-naturalness-a-plus-design.md) |
| 2 | Gesture Interaction | 9 種手勢 mapping（靜態 6 + 動態 3） | 靜態 6 種（若有時間）| 動態 3 種 | 低 | [spec2](./2026-05-10-spec2-gesture-interaction-design.md) |
| 3 | Pose Interaction | 7 種姿勢 + 跌倒人臉融合 | — | ✅ 全部 | 中（誤觸）| [spec3](./2026-05-10-spec3-pose-interaction-design.md) |
| 4 | Object Perception | YOLOv8n vs YOLO26n + 顏色 | — | ✅ 全部 | 低 | [spec4](./2026-05-10-spec4-object-perception-design.md) |
| 5 | Navigation Roadmap | SLAM/Nav2/招手/尋物/巡邏/跟隨 | P0 SLAM 主軸 | P1-P3 | 高 | [spec5](./2026-05-10-spec5-navigation-roadmap.md) |
| 6 | Studio UX Polish | scroll / 五功能視角 / 操作面板 | P0 驗證（可能砍）| P1+P2 | 低 | [spec6](./2026-05-10-spec6-studio-ux-polish.md) |

---

## Demo 前焦點（剩 6 天）

### 必做（P0）
1. **Spec 1 LLM Naturalness A+**（5.5 天）
   - Persona 6 檔（含新 MISSION.md）
   - SAY 解綁機制（`source_llm_reply` ROS 透傳）
   - 4 個優先 skill：self_introduce / wave_hello / greet_known_person / object_remark
   - 10-prompt benchmark + 模型 A/B 評估

2. **Spec 5 P0 SLAM/Nav2 場地測**（5/13-14）
   - LM307 場地 goto_relative 1m
   - reactive_stop 對紙箱
   - 30 分鐘穩定運行

### 可選（若時間夠）
3. **Spec 2 P0 靜態手勢**（2 天）
   - Palm / Fist / Index 對應 skill
   - OK gesture 驗證（PendingConfirm 已用）

4. **Spec 6 P0 scroll 驗證**（0.5 天）
   - 5/9 fix 重現測試 → 無 → 砍此項

---

## Demo 後 sprint 規劃

| Sprint | 範圍 | 工時 |
|---|---|---|
| Sprint 1（demo 後 1 週）| Spec 2 動態手勢 + Spec 3 全部 | 6.5 天 |
| Sprint 2（demo 後 2-3 週）| Spec 4 全部 + Spec 5 P1 動態避障 | 8.5 天 |
| Sprint 3（demo 後 1 月）| Spec 5 P2 招手過來 + 尋物 | 12 天 |
| Sprint 4（看預算）| Spec 5 P3 巡邏 / 跟隨 + Spec 6 P1+P2 | 15+ 天 |

---

## 跨 Spec 共用機制

### 多變體 TTS 池
Spec 1 設計，Spec 3 沿用：
- `text_pool: list[str]` 取代 hardcoded template
- `_text_pool_history` deque maxlen=3 避免重複
- 時段 prefix（早安/午安/晚上）

### LLM SAY 覆蓋
Spec 1 設計，Spec 2-3 共用：
- `SkillPlan.source_llm_reply: str | None`
- ROS proposal JSON round-trip
- 第一個 SAY step 由 LLM reply 覆蓋；空 → fallback pool

### Skill 觸發路徑
- LLM 提案：reply 跟著 plan 走（Spec 1）
- Rule/perception 觸發：用變體池（Spec 1, 3）
- Gesture 觸發：直接 mapping 或 PendingConfirm（Spec 2）

---

## 答辯論述線（demo 主軸）

| 題 | 來自 Spec |
|---|---|
| 「PawAI 在做什麼」 | Spec 1 MISSION.md |
| 「為什麼不只是 ChatGPT 接機器狗」 | Spec 1 雙軌設計（個性 LLM / 動作 deterministic）|
| 「怎麼避免對話像客服」 | Spec 1 persona 6 檔 + SAY 解綁 |
| 「PawAI 怎麼知道自己能做什麼」 | Spec 1 MISSION + CAPABILITIES metadata |
| 「看得懂手勢姿勢嗎」 | Spec 2 + 3 |
| 「能在物理世界自主」 | Spec 5 P0 SLAM + reactive_stop |
| 「跌倒會做什麼」 | Spec 3 跌倒人臉融合 |

---

## 文件治理

- 本 index 更新時，6 個 spec 的 cross-link 一併確認
- 每個 spec 完成（從 draft → done）時更新本表 status
- demo 後做 retrospective，看哪些 spec 範圍真的吃下、哪些被砍

---

## End

6 spec 共 7 個 file（含本 index），全在 `docs/pawai-brain/specs/2026-05-10-*`。
進度追蹤回 `references/project-status.md` + `docs/mission/demo完成清單.md`。
