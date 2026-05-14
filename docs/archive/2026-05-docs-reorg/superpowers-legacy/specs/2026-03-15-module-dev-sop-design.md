# 模組開發 SOP 設計文件

**日期**：2026-03-15
**作者**：System Architect + Claude
**狀態**：Approved（brainstorming 完成）
**目標文件**：`docs/mission/README.md` §11

---

## 背景

2026-03-15 語音模組 30 輪驗收中，踩了 36 個坑（5 環境 / 13 腳本 / 12 observer / 6 ASR）。其中 30 個在驗收工具，6 個在語音主線。核心教訓：缺乏標準開發流程，導致每個模組都重新踩坑。

本 SOP 定義從「寫第一行 code」到「Demo 可展示」的標準流程，適用於所有模組（LLM、人臉、手勢、姿勢等）。

---

## §11.1 環境同步規範

**規則：**

| # | 規則 | 理由 |
|---|------|------|
| 1 | 要上 Jetson 驗證的變更必須先 commit；需跨機同步或交接時必須 push | 避免 dev/Jetson 分叉 |
| 2 | Jetson 上禁止直接改 code（除緊急 hotfix），hotfix 完必須 30 分鐘內 commit 回 repo | 防止隱性分叉 |
| 3 | `colcon build` 後必須 `source install/setup.zsh` + 重啟受影響 node | build 不會熱更新正在跑的 node |
| 4 | Jetson 端固定使用 zsh，腳本與手動操作需固定同一種 setup 流程。若腳本採 bash 需整段自洽，不可 bash/zsh 混 source | 混用導致環境不完整 |
| 5 | 會 `source /opt/ros/humble/setup.*` 的 shell script 預設不用 `set -u` | ROS2 Humble setup 有未定義變數 |

**同步 SOP（每次開發前）：**

```bash
# 1. dev machine: 完成變更後 commit 到當前分支
git add <files> && git commit -m "..."

# 2. 需要跨機驗證時 push（推到功能分支或 main，視情況）
git push origin <branch>

# 3. Jetson: 檢查工作樹
cd ~/elder_and_dog && git status --short

# 4. Jetson: 切到對應分支並 pull
git checkout <branch> && git pull origin <branch>

# 5. Jetson: build
colcon build --packages-select <changed_packages>

# 6. Jetson: source
source install/setup.zsh

# 7. Jetson: 重啟受影響 node

# 8. Jetson: 最小 smoke test
```

> **註**：單人快速迭代（如 Architect 本人）可直接用 main。多 agent 並行時，Builder 各用功能分支，整合時由 Integrator merge（見 §11.6）。

**Anti-pattern：**
- 不要用 `rsync --delete` 同步整個 repo
- 不要在 Jetson 上 `git reset --hard` 除非確認沒有 local stash
- 不要假設 `colcon build` 後正在跑的 node 會自動更新

---

## §11.2 裝置前置檢查

**規則：每次啟動 session 前，跑完 core + 對應模組的前置檢查。不通過不進入 build/test。**

**Core 檢查（所有模組都要跑）：**

| # | 檢查項 | 指令 | 通過條件 | 失敗處理 |
|---|--------|------|----------|----------|
| 1 | ROS2 環境 | `ros2 topic list` | 有輸出 | `source /opt/ros/humble/setup.zsh && source install/setup.zsh` |
| 2 | 無非預期殘留 node | `ps aux \| grep -E '<node_patterns>'` | 無非預期匹配 | `clean_<module>_env.sh` |

**需要 Go2 機器人的模組（語音、demo pipeline）：**

| # | 檢查項 | 指令 | 通過條件 | 失敗處理 |
|---|--------|------|----------|----------|
| R1 | Go2 連線 | `ping -c 2 <robot_ip>` | 0% loss | 檢查網線/Wi-Fi、Go2 是否開機 |

**語音模組專屬：**

| # | 檢查項 | 指令 | 通過條件 | 失敗處理 |
|---|--------|------|----------|----------|
| S1 | Go2 driver 存活 | `ros2 topic info /webrtc_req` | Subscription count ≥ 1 | 重啟 driver |
| S2 | PulseAudio 已停 | `arecord -l` 確認 capture device，再 `fuser /dev/snd/pcmC<X>D<Y>c` | 無輸出 | `pulseaudio --kill && systemctl --user mask pulseaudio.socket pulseaudio.service` |
| S3 | 麥克風可用 | `arecord -D plughw:0,0 -f S16_LE -c 2 -r 44100 -d 1 /tmp/mic_test.wav` | 錄音成功 | 檢查 USB、`arecord -l` |
| S4 | CUDA 可用 | `python3 -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` | ≥ 1 | 確認 `LD_LIBRARY_PATH` |

**人臉模組專屬：**

| # | 檢查項 | 指令 | 通過條件 |
|---|--------|------|----------|
| F1 | D435 連線 | `rs-enumerate-devices \| grep D435` | 有匹配 |
| F2 | YuNet 模型存在 | `ls <yunet_model_path>` | 檔案存在 |

**LLM 模組專屬：**

| # | 檢查項 | 指令 | 通過條件 |
|---|--------|------|----------|
| L1 | RTX server 連線 | `ping -c 2 <rtx_server_ip>` | 0% loss |
| L2 | vLLM health | `curl http://<server>:8000/health` | HTTP 200 |

**Anti-pattern：**
- 不要跳過 PulseAudio 檢查就直接開 STT
- 不要假設麥克風 device index 沒變
- 不要在有殘留 node 的狀態下開新 session

---

## §11.3 跨 Node 協調設計原則

**設計總則：**
- 狀態靠 latched state topic
- 事件靠 volatile + correlation id
- 控制靠 req/ack
- 所有跨 node 契約先登記再實作

**原則：**

| # | 原則 | 說明 |
|---|------|------|
| 1 | 新增跨 node topic 前，先在 `interaction_contract.md` 登記 | name, type, QoS, pub/sub, 頻率 |
| 2 | 狀態型 topic 用 latched（transient_local） | 晚加入的 subscriber 也能拿到最新值 |
| 3 | 事件型 topic 用 volatile + 可關聯欄位 | session_id / track_id / request_id，視場景選用 |
| 4 | 跨 node gate/mute 必須有 timeout 保護 | 避免 publisher crash 後 subscriber 永遠被 mute |
| 5 | Node 啟動時 publish 初始狀態 | latched topic 的 publisher init 時發一次初始值 |
| 6 | 新增 intent/event type 必須同步更新共享常數或契約定義 | 不能只改單一 node |

**設計模式速查：**

```
狀態廣播模式（tts_playing, robot_state, speech_state）：
  Publisher: latched QoS, init 發 false/idle, 狀態變化時發布
  Subscriber: 相同 QoS 訂閱，收到即為最新狀態

事件通知模式（intent_recognized, face_identity）：
  Publisher: volatile, 每筆帶 correlation id + timestamp
  Subscriber: 用 id 關聯同一事件鏈

請求-確認模式（round_meta_req/ack, generate_report_req/ack）：
  Publisher: volatile, 帶 request payload
  Subscriber: 處理後發 ack，ack 必須帶回 request_id
  Caller: 先開 ack listener → 發 req → 等 ack（避免 race）
```

**Anti-pattern：**
- 不要用 `asyncio.Queue` 跨執行緒傳資料（靜默丟包）
- 不要假設 volatile subscriber 能收到之前發布的訊息
- 不要用 time-based correlation 當唯一依據，能帶 id 就帶 id

---

## §11.4 驗收分級與切換條件

**核心規則：子模組靠 spec + smoke + review，整合主線才跑 YAML 驗收。**

### Level A：子模組開發驗收

| 項目 | 內容 |
|------|------|
| 適用 | 單一模組可獨立驗證、尚未依賴系統級協調 |
| 形式 | spec 定義 + smoke test script + code review |
| 通過 | smoke test 全綠 + reviewer 無 blocking issue |
| 交付物 | `scripts/smoke_test_<module>.sh` + review 紀錄 |
| 不需要 | 自動化統計、observer、YAML case |

**Smoke test 最低要求：**
- 3-5 case，覆蓋 happy path + 1 error case
- 每個 case 有明確可驗證訊號（`ros2 topic echo --once`、return code、log grep）
- 30 秒內跑完

### Level B：系統整合驗收

| 項目 | 內容 |
|------|------|
| 適用 | 模組接進 ROS2 主線、與其他 node 互動 |
| 形式 | YAML case 定義 + 自動判定 + 簡單報表 |
| 通過 | 10+ case、關鍵指標達門檻 |
| 交付物 | `test_scripts/<module>_validation.yaml` + CSV + summary JSON |

### 升級條件（A → B）

- **必須**：Level A smoke test 全綠
- **且至少滿足其一**：
  - 介面已相對穩定（短期內不會大改）
  - 開始影響 demo 主線 / 與其他 node 互動

**不滿足時，禁止花時間做 Level B 驗收工具。**

### 時間分配指引（建議，非硬規則）

| 階段 | 功能開發 | 驗收工具 |
|------|:--------:|:--------:|
| Level A | 90% | 10% |
| Level B | 60% | 40% |
| Demo 前穩定化 | 30% | 70% |

**Anti-pattern：**
- 不要在模組還在快速迭代時就做 observer
- 不要讓驗收工具的 bug 阻擋功能開發進度
- 不要把「驗收工具能跑」當成「功能已完成」

---

## §11.5 模組整合 Checklist

### 四級整合路徑

```
Level 1: Standalone → Level 2: Node-level → Level 3: System-level → Level 4: Demo-level
```

**原則上不可跳級；若要例外，需明確記錄理由與風險。**

### Level 1: Standalone（單機可跑）
- [ ] 程式碼可在目標平台執行
- [ ] 有明確 input/output 定義
- [ ] 有 `smoke_test_<module>.sh`，3-5 case 全綠
- [ ] 無硬編碼路徑（用 ROS2 parameter 或環境變數）
- [ ] Code review 通過

### Level 2: Node-level（ROS2 node 可運行）
- [ ] 模組已提供標準啟動入口（ros2 run / ros2 launch）
- [ ] Topic / service 已登記在 `interaction_contract.md`
- [ ] QoS 策略符合 §11.3 原則
- [ ] Node 啟動時 publish 初始狀態
- [ ] `colcon build` 通過

### Level 3: System-level（多 node 協同）
- [ ] 與相依 node 可在同一 ROS2 graph 共存
- [ ] 跨 node gate/mute/ack 有 timeout 保護
- [ ] 升級到 Level B 驗收（10+ case）
- [ ] 已有對應的 clean/start 腳本
- [ ] Preflight checklist 已涵蓋此模組裝置

### Level 4: Demo-level（展示可靠）
- [ ] Demo 流程文件化（操作步驟、預期行為、fallback）
- [ ] 在目標 demo pipeline 上連續 3 次 cold start 成功
- [ ] 記憶體預算確認（Jetson 8GB）
- [ ] 降級策略定義
- [ ] 展示前 SOP：preflight → clean start → warmup → demo

### 模組整合等級快照（2026-03-15）

| 模組 | 當前等級 | 下一步 |
|------|:--------:|--------|
| 語音（STT/TTS/Intent） | Level 3 | Level 4（Demo 穩定化） |
| 人臉（YuNet/SFace） | Level 1 | Level 2（ROS2 node 化） |
| AI 大腦（LLM） | 尚未開始 | Level 1（vLLM smoke test） |
| 手勢 | 研究中 | — |
| 姿勢 | 研究中 | — |

---

## §11.6 多 Agent 並行開發流程

### 角色定義

| 角色 | 職責 |
|------|------|
| **Architect** | 拆功能為子模組 spec、定義介面契約、決定整合順序。使用規劃/拆解類 workflow |
| **Builder** (×N) | 各自在 worktree 開發一個子模組，通過 Level A。**不可自行變更共享契約** |
| **Reviewer** | 對每個 Builder 的產出做 code review |
| **Integrator** | 把已過 Level A 的模組接到主線，決定合併順序與衝突優先級 |
| **Validator** | 對整合後的主線跑 Level B 驗收 |

### 流程

```
1. Architect: 大功能 → spec → 拆成 N 個子模組 spec
   每個 spec 定義：input/output、依賴、smoke test、檔案範圍
   ↓
2. Dispatch N 個 Builder agent（parallel, worktree isolation）
   每個 Builder：實作 → 單元測試 → smoke test → Reviewer → commit
   ↓
3. Integrator: 按順序 merge，解衝突，補跨 node 協調
   ↓
4. Validator: 跑 Level B 驗收
   不通過 → 對應 Builder 修 → 再驗
   通過 → merge 到 main
```

### 並行前提

- 子模組介面在 spec 層凍結
- 每個 Builder 只碰自己的檔案範圍
- 共享 constants / schema 由 Architect 先建好，Builder 只讀不改

**Anti-pattern：**
- 不要讓 Builder 同時改 `interaction_contract.md`
- 不要讓 Builder 做 Level B 驗收工具
- 不要在 spec 沒凍結時就 dispatch Builder

---

## §11.7 Code Review 規範

### 預設：Checkpoint-based

| 項目 | 內容 |
|------|------|
| 適用 | 單一子模組、小範圍改動 |
| 觸發 | Builder 完成一個 spec chunk |
| 執行 | code-reviewer agent |
| 不通過 | 原 Builder 就地修，再觸發 review |
| 通過 | commit 到功能分支 |
| 紀錄 | 對話為主，必要時摘要寫入 `docs/superpowers/reviews/` |

### 升級條件 → PR-based

符合任一條就必須升級：
- 會改 event / state / topic / schema
- 會碰整合分支或 main
- 會影響多個模組的介面
- 會影響 demo 主線
- 會改驗收工具或部署流程（**預設視為高風險**）

### Review 層次

| Layer | 時機 | 工具 | 性質 | 狀態 |
|:-----:|------|------|------|:----:|
| 1 | 每次 Edit/Write | 專案級快檢（目前：py_compile；前端路徑：eslint） | 自動，阻擋 | 已有 |
| 2 | 每個 chunk 完成 | code-reviewer agent | 手動觸發，阻擋 | 已有 |
| 3 | 整合前 PR | code-reviewer + codex/haiku 第二意見 | 正式，阻擋 | 已有 |
| 4 | 對話結束 | Stop hook (codex + haiku) | **僅補充意見，不作 merge gate** | 已有 |

> **Target**：Layer 1 擴充 ruff（Python linting）、全路徑 eslint。待專案穩定後統一配置。

### 不通過處理

- 不要換另一個 Builder 接手修同一個 review（context 不連續）
- 原 Builder 修到通過，或明確標記「需要 Architect 介入」
- 連續 3 次 review 不通過 → 升級給人類決策
