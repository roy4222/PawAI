# 人臉辨識

[English](./README.md) | **中文**

> **Scope**：face_perception 模組設計真相（YuNet + SFace + IOU tracker）｜**Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception ｜ **能力 claim 真相源**：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `face.recognition`（任何「能不能講、屬哪層」一律以此頁為準）
> **能力 grade 證據（最終事實）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（face = 🟢 pass 窄版；caveats 凌駕本頁敘事）
> **維護子檔**：`CLAUDE.md`（工作規則）｜`AGENT.md`（topic 介面契約）｜`research/`（research-only，非真相）
> **這頁不是什麼**：不是能力 pass/fail 的裁定（看 baseline-evidence）；不是量測協定（看 [`specs/2026-06-18-capability-baseline-spec.md`](../../specs/2026-06-18-capability-baseline-spec.md)）；不講陌生人拒絕 / 守護 / 「不會認錯人」。

> YuNet 偵測 + SFace 識別 + IOU 追蹤，辨認**已註冊熟人**並觸發互動（窄版：僅已註冊者）。

## 能力卡（canonical 8 欄位 → 連結 claim matrix，勿在本頁重複整份散文）

> 完整 8 欄位散文見 [claim matrix `face.recognition`](../../../mission/2026-06-18-capability-claim-matrix.md#facerecognition)。本表為速查。

| 欄位 | 值 |
|---|---|
| **Current Claim** | 6/04 trusted 量測對「已註冊的 Roy」在 ~1.5–2.4m 拿到 pass，示範認出註冊者並問候（窄版） |
| **Claim Level** | CLAIM_WITH_CAVEAT |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（n=9, registered_recall=1.0, unknown_false_accept=0.0, p50≈74ms） |
| **Pass/Degraded/Fail/Insufficient** | 🟢 pass（窄版）— 僅單一註冊者、單光照、最低 positive conf 0.2378、idle=空景 |
| **Fallback** | track 抖動 / 名字閃 → 退泛稱「看到有人靠近並打招呼」或只秀 `debug_image` 證鏈路 |
| **Non-Claims** | 陌生人拒絕 / 守護 / 陌生人警報 / 「不會認錯人」 / 身份驗證 / 門禁級確認 / 2m+ 可靠 / 通用人臉辨識 |
| **Model Candidates** | BASELINE_NOW（YuNet + SFace，現役 pass 不換） |
| **Next Retest** | #81 乾淨重跑：≥2 註冊者 + 多光照、真實陌生人樣本、conf 離開 0.24 邊界、full-stack 久放後複測 |

## 狀態卡

> **狀態卡 caveat（6/04 收斂）**：下表「完成度 95%」是模組開發進度，**非能力 pass 證據**。能力證據以 [能力卡](#能力卡canonical-8-欄位--連結-claim-matrix勿在本頁重複整份散文) + baseline-evidence 為準（face = 🟢 pass 窄版：僅已註冊熟人 / 空景 idle，**陌生人拒絕未驗證**）。

| 項目 | 值 |
|------|---|
| 狀態 | **已註冊熟人 greeting（窄版 pass）** |
| 版本/決策 | YuNet 2023mar (CPU 71.3 FPS) + SFace 2021dec |
| 完成度 | 95%（模組開發進度，非能力 pass — 見上方 caveat） |
| 最後驗證 | 2026-05-08（sim_threshold_upper 0.30→0.40 拉高陌生人門檻，避免 demo 期 60%+ 誤判）；上次完整 smoke 2026-04-06（identity_stable 21 次/2min） |
| 入口檔案 | `face_perception/face_perception/face_identity_node.py` |
| 測試 | `python3 -m pytest face_perception/test/ -v` |

## 啟動方式

```bash
# 一鍵啟動（推薦）
bash scripts/start_face_identity_tmux.sh

# 或手動
ros2 launch face_perception face_perception.launch.py
```

## 核心流程

```
RealSense D435 RGB + Depth
    |
face_identity_node（YuNet 偵測 -> SFace embedding -> IOU 追蹤）
    |
/state/perception/face（10Hz JSON：face_count, tracks[{track_id, stable_name, sim, distance_m, bbox}]）
/event/face_identity（觸發式：track_started / identity_stable / identity_changed / track_lost）
    |
interaction_executive_node 訂閱 -> WELCOME 觸發 -> TTS 問候
```

**Hysteresis 穩定化**（4/6 + 5/8 兩階段調參）：
- 4/6：`sim_threshold_upper`: 0.35 → 0.30，`sim_threshold_lower`: 0.25 → **0.22**（為了讓 known faces 認得快）
- **5/8**：`sim_threshold_upper`: 0.30 → **0.40**（為了讓 unknown 不亂叫；demo white-box 觀察 60%+ stranger 誤觸來自手 / 玻璃倒影 / 膚色物。已配 `unknown_face_accumulate_s`: 3.0 → 5.0 多 2 秒確認）
- `track_iou_threshold`: **0.15**，`track_max_misses`: **20**，`stable_hits`: **2**，`unknown_grace_s`: **2.5**
- 4/6 調參後 2 分鐘 smoke test：`identity_stable: roy` 21 次（調前 1-3 次），零誤認
- **已知限制**：track 抖動仍在（45 tracks/2min，目標 ≤5），根因是 YuNet 偵測不穩定

**face_db**：`/home/jetson/face_db/`，目前有 roy、grama 兩人。

## Skill 觸發對應（5/12 Sprint Scene 4 + 8）

> **Claim 邊界（6/04）**：下表 `stranger_alert` 是**內部事件路由機制**，**不是**已驗證的陌生人偵測/警報能力。6/04 idle 只測空景，**真實陌生人拒絕未量測**（baseline-evidence honesty caveat）。demo/簡報**不得**宣稱守護 / 陌生人警報 / 「不會認錯人」（claim matrix `face.recognition` Non-Claims）。

| 事件 | Brain 觸發 Skill | Demo Scene | 備註 |
|---|---|---|---|
| `identity_stable`（已知人臉穩定 ≥2 hits）| `greet_known_person` | Scene 4 熟人互動 | LLM 動態問候，含 `{name}` 客製化 |
| `identity_unknown`（陌生人 unknown_grace 後）| `stranger_alert` | Scene 8 陌生人 + safety stop | **5/7 night demo silence**：`SkillContract.steps[0].args["text"] = ""`，IE-node SAY return `empty_tts_text`，`/tts` 不發。`/brain/proposal` trace 仍 emit，Studio chip 仍可見。同 fall_alert b224217 模式 |
| `track_started` / `track_lost` | （無 skill 直觸）| — | 純 state 更新，由 brain 規則判讀 |

**`{name}` 客製化**：face name 從 `/state/perception/face` 取最近 `identity_stable` 的 `stable_name`，由 LLM bridge 用 say_template 渲染。同一變數也用在 `pose/README.md` 的 `fallen_alert`（「{name}，偵測到跌倒，請注意安全」）。

## 註冊新人臉（進階，post-demo）

> 5/12 demo 不開放現場註冊，只用既有 face_db。註冊機制標 **進階**，post-demo 再評估。

**手動流程**（dev only）：
1. 把目標人物 1-3 張正面照（256×256+）放進 `/home/jetson/face_db/<name>/`
2. 重啟 `face_identity_node`，啟動時自動讀 face_db 重算 SFace embedding
3. 對著鏡頭走幾步驗證 `identity_stable: <name>` 觸發

**目前不做**：
- ROS service `/face/register`（會擴大 demo scope）
- Studio 上傳 UI
- 自動相似度合併（一人多 ID 重整）

## 輸入/輸出

| Topic | 方向 | 說明 |
|-------|:----:|------|
| `/state/perception/face` | 輸出 | 人臉狀態 10Hz JSON |
| `/event/face_identity` | 輸出 | 身份事件（觸發式） |
| `/face_identity/debug_image` | 輸出 | Debug 影像 ~6.6Hz |

## 模型路徑（Jetson）

- YuNet：`/home/jetson/face_models/face_detection_yunet_2023mar.onnx`
- SFace：`/home/jetson/face_models/face_recognition_sface_2021dec.onnx`

## 已知問題

- **重複觸發打招呼**（4/8 會議確認）：同一人短時間內重複觸發 greeting，尚未設定冷卻時間
- **光線不足誤判**：低光環境偶爾出現錯誤人名
- **無人幻覺**：無人時偶爾誤判有人臉存在
- **多人骨架亂跳**：多人同時出現時追蹤混亂，無法正確區分
- track 抖動仍在（45 tracks/2min，目標 ≤5），根因是 YuNet 偵測不穩定
- 模型路徑硬編碼 `/home/jetson/face_models/`
- face_db 只有 2 人（roy, grama），Demo 可能需擴充
- OpenCV 版本限制（Jetson 4.5.4）

## 下一步

- [ ] **5/12 Sprint Scene 4 + 8 上機驗證**：`greet_known_person` 對 roy / grama 各 3 次穩定觸發；`stranger_alert` 對未知人臉 3 次穩定觸發
- [ ] Greeting 冷卻時間（防止同一人短時間重複觸發，目前已知問題）
- [ ] 多人辨識穩定化（多人同時出現時 track 不亂跳）
- [ ] Clean Architecture 重構（5/13 demo 後，詳見 `docs/archive/2026-05-docs-reorg/research-misc/2026-03-25-go2-sdk-capability-and-architecture.md` S5.4）
- [ ] 註冊新人臉 ROS service（進階，post-demo）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 模型選型研究（YuNet vs ArcFace vs SCRFD） |
| archive/ | 初階開發者分工指南（3/8，已無人使用） |
