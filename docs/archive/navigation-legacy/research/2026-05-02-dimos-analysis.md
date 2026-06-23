# DimOS 分析報告（給 PawAI Brain Executive 參考）

- **Source**: https://github.com/dimensionalOS/dimos
- **Commit**: `a035fb315d35bba511dfc6156dc21827e70dbc94`
- **License**: Apache-2.0（Copyright Dimensional Inc., 2025-2026）
- **Status**: Pre-Release Beta
- **Analyzed**: 2026-05-02

---

## 1. DimOS 是什麼？

「**The Agentive Operating System for Physical Space**」— 一個**模組化機器人應用框架 + LLM agent runtime**，定位介於 ROS 和 LLM agent SDK 之間。號稱「無需 ROS 也能跑」，純 Python，pip 安裝（`uv pip install 'dimos[base,unitree]'`）。

核心三層：
- **Module**：subsystem 基底類別，用 `In[T] / Out[T]` typed streams + `@rpc` decorator 對外溝通（類似強型別 ROS node）
- **Blueprint**：`autoconnect(...)` 把多個 Module 組成可執行 stack（類似 ROS launch + 拓樸佈線）
- **Skill**：`@skill` decorator 標註的方法，自動暴露給 LLM agent（pydantic schema → OpenAI tool）和 MCP server

附帶 `dimos` CLI：`dimos run / status / log / agent-send / mcp call ...`，全生命週期管理。

## 2. 機器人支援

| 平台 | 狀態 |
|------|------|
| **Unitree Go2 pro/air** | 🟩 stable（first-class，多個 blueprints） |
| Unitree G1 | 🟨 beta |
| Unitree B1 | 🟥 experimental |
| xArm / AgileX Piper | 🟨 beta |
| MAVLink / DJI Mavic | 🟧 alpha |

**Go2 是 DimOS 的旗艦平台**。`dimos/robot/unitree/go2/` 完整實作 WebRTC 連線、`unitree_skill_container.py` 已內建 30+ Go2 sport mode skills（StandUp/Sit/Hello/Dance1/Stretch...，含 RTC api_id 1002~1027），與我們的 `WebRtcReq` 對應一致。直接 `dimos run unitree-go2 --robot-ip 192.168.123.161` 上機。

## 3. 核心 Abstraction

- **Skill = pydantic Field 化的 callable**：`AbstractRobotSkill` 子類，用 pydantic Field 宣告參數（自帶 description，給 LLM 讀），`__call__()` 執行。範例 `FollowHuman(distance=1.5, timeout=20.0)`。
- **SkillLibrary**：類別級 + 實例級兩層 registry，支援 `_running_skills` 追蹤（cancel/replace 語義）。
- **Agent = LangGraph + LangChain**：`Agent` Module 內嵌 `CompiledStateGraph`，吃 `human_input` stream，吐 `agent` BaseMessage stream，skills 以 `StructuredTool` 注入。
- **MCP first-class**：`McpServer` 把所有 `@skill` 方法當 HTTP MCP tool 暴露在 `:9990/mcp`，可被外部 Claude / GPT 直接呼叫。

## 4. 與 OM1 比較

| 軸 | DimOS | OM1 |
|----|-------|-----|
| 定位 | 機器人 OS + agent runtime（兩者並重） | LLM-first runtime（Brain 是中心） |
| Skill 寫法 | pydantic Field + `@skill` decorator | YAML / JSON config + Python action |
| Transport | 自家 Module 系統，後端可換 LCM/DDS/ROS2/Redis | 自定 input/output plugin |
| Agent stack | LangGraph + LangChain（重） | 直接呼叫 LLM API（輕） |
| MCP | 內建 `McpServer`（HTTP） | 不是核心 |
| 對 Go2 | first-class blueprint | first-class plugin |
| 風格 | 工程框架（dataclass/typed stream/blueprint composition） | 配置驅動（fast iteration） |

DimOS 偏「ROS 替代品 + agent」，OM1 偏「LLM 中樞接 ROS」。**PawAI Brain Executive 走的是 OM1 路線**（state machine + WorldState）。

## 5. ROS2 整合

`dimos/protocol/pubsub/impl/rospubsub.py` 提供 `rclpy` 透傳（QoS / Node / SingleThreadedExecutor 完整包裝），ROS_AVAILABLE flag 容錯。`dimos/navigation/rosnav.py` 的 `NavBot` 用 `ROSTransport` 直接訂 `/amcl_pose`、發 `/cmd_vel` `/goal_pose`，等同我們現在跑的 Nav2 stack 介面。**可以與我們現有 ROS2 Humble + Nav2 + AMCL 共存**，DimOS Module 作為「ROS topic 上的另一層強型別 wrapper」。

## 6. 對 PawAI Brain Executive 啟發

我們的 SkillContract / SkillPlan / SkillStep / WorldState 抽象，DimOS 已驗證的對應做法：

1. **SkillContract → pydantic Field schema**：把 description 寫在 Field 裡，LLM tool call schema 自動生（不必另寫 contract 檔）。值得 PawAI 借鏡。
2. **SkillStep 執行模型**：`_running_skills` dict + `stop()` 協議，比我們目前的 step queue 更乾淨。
3. **Spatial Memory + Object Permanence**：`dimos/perception/spatial_perception.py` 與 `object_tracker_3d.py` 已實作 spatio-temporal RAG（5/12 demo `approach_person` 可參考）。
4. **MCP exposure**：把 skill 暴露成 MCP tool，未來 PawAI Studio 可直接接外部 LLM 而不必綁定我們 cloud Qwen2.5-7B。

## 7. 可整合性

- **授權 Apache-2.0** — 商用 OK，可借用程式碼（要保留 NOTICE）。
- **直接整合風險高**：DimOS 自帶 Module/Blueprint/Transport 一整套，與我們現有 ROS2 launch + colcon 建構強衝突；硬塞會雙 runtime。
- **建議借用**：
  - `unitree_skill_container.py` 的 30+ sport mode 對照表（直接抄 RTC api_id + description，補我們現有清單）
  - `visual_navigation_skills.FollowHuman` 視覺伺服邏輯（5/12 `approach_person` 可參考）
  - `pydantic Field + description → LLM tool schema` 的 pattern（重構 SkillContract）
- **不建議整合**：Module/Blueprint runtime、LangGraph Agent、`dimos` CLI（會與我們的 ros2 launch / Brain Executive 雙頭打架）。

## 結論

DimOS 對 Go2 first-class、Apache-2.0、MCP 內建，是目前最像「Go2 用的 ROS 替代品」的開源方案。**PawAI 5/12 demo 不用切換到 DimOS**（架構替換成本太高、5/12 來不及），但**可借用 sport mode 表 + FollowHuman 視覺伺服 + pydantic skill schema 三項**強化 Brain Executive。長期可考慮以 `McpServer` 模式把 PawAI skills 暴露給外部 agent 試吃。
