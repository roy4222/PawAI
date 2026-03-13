# Go2 Agent 整合方案 (TO-BE)

本文件是 Go2 專屬 AI Agent 的整合提案與設計草案（`TO-BE`）。

**版本**: v2.0
**日期**: 2026-02-11
**目標**: 使用 Python Agent 框架打造專屬 Go2 Agent，整合 ROS2 Skills 架構
**參考**: [Ros2_Skills.md](./Ros2_Skills.md), [refactor_plan.md](./refactor_plan.md)

---

## 零、v2.0 變更摘要

> v1.0（2026-02-10）推薦方案 A（TypeScript / Pi-Mono）。經可行性評估後，v2.0 改推薦方案 B（Python）。
> 原方案 A 保留於[附錄 A](#附錄-a原方案-a-歷史紀錄typescriptpi-mono) 作為歷史參考。

### 變更原因

| 發現 | 影響 |
|------|------|
| Pi-Mono 為純 TypeScript 專案（96.5%），無 Python SDK | 整合需全新語言棧，學習成本極高 |
| Pi-Mono 無內建 MCP 支援（需額外 pi-mcp-adapter 擴充套件） | 架構假設不成立 |
| Pi-Mono 無安全機制（僅 TypeBox schema validation） | 機器人安全需自行從零實作 |
| Pi-Mono 無任何機器人/IoT 相關文件或範例 | 無法參考，全靠自行摸索 |
| 團隊零 TypeScript 經驗；整個 repo 為 Python/ROS2 | 技術風險過高 |
| Node.js 在 Jetson 8GB 增加 ~100MB 記憶體開銷 | 資源緊張 |
| rosbridge 僅 TypeScript 路徑需要；Python 用 rclpy 直連 | 去除不必要的延遲跳轉 |
| Pydantic AI（14.8k stars, v1.58.0）提供完整 Python Agent 框架 | Python 路徑工具成熟 |

---

## 一、Python Agent 框架選項

### 1.1 推薦：Pydantic AI（⭐⭐⭐⭐⭐）

[Pydantic AI](https://github.com/pydantic/pydantic-ai) — 14.8k stars, v1.58.0 (2026-02-10)

| 特性 | 說明 |
|------|------|
| 多供應商 LLM | OpenAI, Anthropic, Google, Ollama, vLLM 等 20+ providers |
| 型別安全 Tool Calling | 基於 Pydantic model，自動產生 JSON schema |
| 依賴注入 | `RunContext[Deps]`，適合傳入 rclpy Node |
| 記憶體開銷 | < 10MB（相比 LangChain 515MB） |
| Ollama 原生支援 | 本地模型部署友好（Jetson 8GB 適用） |
| 結構化輸出 | `result_type` 直接回傳 Pydantic model |

### 1.2 輕量替代：原生 SDK（⭐⭐⭐⭐）

Anthropic / OpenAI SDK 內建 tool calling，約 60 行即可搭建最小 agent loop。

適用場景：prototype 快速驗證、記憶體極度受限。

### 1.3 不推薦：LangChain / LangGraph

- LangChain：515MB repo、依賴過重、Jetson 8GB 不適合
- LangGraph：24.6k stars，比 LangChain 輕但仍偏重（邊緣設備）

---

## 二、整合架構方案

### 方案 B: Python Agent（推薦 ⭐⭐⭐⭐⭐）

```
┌─────────────────────────────────────────────────────────┐
│            Go2 Agent (Python / Pydantic AI)              │
│            (Jetson Orin Nano SUPER 8GB)                  │
├─────────────────────────────────────────────────────────┤
│  Pydantic AI Agent (or native SDK)                       │
│       ↓ Tool Calling                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ perception  │  │   motion    │  │   navigation    │  │
│  │  skills     │  │   skills    │  │     skills      │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         └─────────────────┴──────────────────┘           │
│                  rclpy (直連 ROS2)                        │
│              無需 rosbridge / WebSocket                   │
└─────────────────────────┬───────────────────────────────┘
                          │ ROS2 Topics/Services/Actions
                          ↓
┌─────────────────────────────────────────────────────────┐
│              ROS2 Humble (Jetson Orin Nano)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ go2_driver  │  │ move_       │  │  snapshot_      │  │
│  │   _node     │  │   service   │  │    service      │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**優點**:
- ✅ 直接使用 rclpy，無需 rosbridge / WebSocket 橋接
- ✅ 與現有 `go2_robot_sdk` Python 生態 100% 相容
- ✅ Jetson 原生 Python，零額外 runtime 開銷
- ✅ Pydantic AI 提供型別安全 Tool Calling + 結構化輸出
- ✅ 多 LLM 供應商（含 Ollama 本地模型），一行切換
- ✅ 團隊已有 Python 經驗，學習曲線最低
- ✅ move_service.py 安全層可直接呼叫（同一 process 或 rclpy service call）

**缺點**:
- ⚠️ 無 pi-tui/pi-web-ui 現成 UI（需自行用 FastAPI / Gradio 搭建）
- ⚠️ 需自行處理 Agent 狀態持久化（Pydantic AI 有 message history，但無 checkpoint）

---

### 方案 A: TypeScript / Pi-Mono（不推薦 ⭐⭐）

> 已移至 [附錄 A](#附錄-a原方案-a-歷史紀錄typescriptpi-mono)。
> 不推薦原因見 [零、v2.0 變更摘要](#零v20-變更摘要)。

---

### 方案 C: MCP 混合（漸進過渡 ⭐⭐⭐）

```
┌─────────────────────────────────────────────────────────┐
│          Python Agent (Pydantic AI / native SDK)         │
│                                                         │
│       ↓ MCP Protocol (stdio/sse)                         │
┌─────────────────────────────────────────────────────────┐
│              ros-mcp-server (Jetson)                     │
│         轉換為 Skills 架構 (參考 Ros2_Skills.md)          │
├─────────────────────────────────────────────────────────┤
│       ↓ ROS2                                             │
│              go2_robot_sdk + skills/                     │
└─────────────────────────────────────────────────────────┘
```

**優點**:
- ✅ 保留現有 ros-mcp-server 43 個工具的投資
- ✅ MCP 作為標準介面，與 Claude Desktop 等 MCP Client 相容
- ✅ 可漸進遷移至純 Skills，風險最低

**缺點**:
- ⚠️ 多一層 MCP 通訊（stdio/sse 開銷）
- ⚠️ 仍需 rosbridge（ros-mcp-server 依賴）
- ⚠️ 維護兩套 protocol（MCP + Skills）增加複雜度

**定位**: 過渡方案。Phase 1 可用 MCP 快速驗證，Phase 2 逐步遷移至純 Skills（方案 B）。

---

## 三、方案比較總表

| 維度 | 方案 A (TS/Pi-Mono) | 方案 B (Python) | 方案 C (MCP Hybrid) |
|------|:---:|:---:|:---:|
| **開發速度** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **執行效能** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **生態相容** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **維護難度** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **擴展性** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Jetson 資源** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **UI 支援** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **團隊經驗** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **安全機制** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **風險** | 高 | 低 | 低 |

---

## 四、推薦實作路徑（方案 B）

基於 **Ros2_Skills.md** 規劃，採用 **方案 B (Python) + 漸進遷移**。

### Phase 1: 核心 Skills + Agent 原型（2 週）

#### 1.1 建立 Skill 模組

```python
# skills/motion/safe_move.py
"""安全移動 Skill — 呼叫 /move_for_duration service。"""

import rclpy
from rclpy.node import Node
from go2_interfaces.srv import MoveForDuration

# 硬限制（與 move_service.py 一致）
MAX_LINEAR = 0.3    # m/s
MAX_ANGULAR = 0.5   # rad/s
MAX_DURATION = 10.0  # seconds


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


async def safe_move(
    node: Node,
    linear_x: float,
    angular_z: float = 0.0,
    duration: float = 1.0,
) -> dict:
    """安全移動 Go2 機器狗。

    所有輸入值會被 clamp 到安全範圍內。

    Args:
        node: ROS2 Node（用於 service client）
        linear_x: 前進/後退速度 (m/s)，範圍 [-0.3, 0.3]
        angular_z: 旋轉速度 (rad/s)，範圍 [-0.5, 0.5]
        duration: 持續時間 (秒)，範圍 (0, 10.0]

    Returns:
        dict: { success: bool, message: str, actual_duration: float, clamped: dict }
    """
    # Safety gate: clamp 到硬限制
    clamped_lx = clamp(linear_x, -MAX_LINEAR, MAX_LINEAR)
    clamped_az = clamp(angular_z, -MAX_ANGULAR, MAX_ANGULAR)
    clamped_dur = clamp(duration, 0.0, MAX_DURATION)

    client = node.create_client(MoveForDuration, '/move_for_duration')
    if not client.wait_for_service(timeout_sec=5.0):
        return {'success': False, 'message': '/move_for_duration service not available'}

    req = MoveForDuration.Request()
    req.linear_x = clamped_lx
    req.angular_z = clamped_az
    req.duration = clamped_dur

    future = client.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=clamped_dur + 5.0)

    if future.result() is None:
        return {'success': False, 'message': 'Service call timed out'}

    resp = future.result()
    return {
        'success': resp.success,
        'message': resp.message,
        'actual_duration': resp.actual_duration,
        'clamped': {
            'linear_x': clamped_lx != linear_x,
            'angular_z': clamped_az != angular_z,
            'duration': clamped_dur != duration,
        },
    }
```

```python
# skills/motion/emergency_stop.py
"""緊急停止 Skill — 呼叫 /stop_movement service。"""

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


async def emergency_stop(node: Node) -> dict:
    """立即停止 Go2 所有動作。

    Returns:
        dict: { success: bool, message: str }
    """
    client = node.create_client(Trigger, '/stop_movement')
    if not client.wait_for_service(timeout_sec=2.0):
        return {'success': False, 'message': '/stop_movement service not available'}

    future = client.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=3.0)

    if future.result() is None:
        return {'success': False, 'message': 'Stop service call timed out'}

    resp = future.result()
    return {'success': resp.success, 'message': resp.message}
```

#### 1.2 建立 Agent（Pydantic AI）

```python
# go2_agent/agent.py
"""Go2 專屬 Agent — 使用 Pydantic AI 框架。"""

from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from rclpy.node import Node

from skills.motion.safe_move import safe_move
from skills.motion.emergency_stop import emergency_stop


@dataclass
class RobotDeps:
    """Agent 依賴：持有 ROS2 Node 參考。"""
    node: Node


SYSTEM_PROMPT = """\
你是 Go2 機器狗的專屬 Agent，代號 "PawAI"。

## 核心原則
1. 安全優先 — 所有移動必須使用 safe-move skill，禁止直接發送 cmd_vel
2. 任何失敗必須先執行 emergency-stop
3. 真機執行需要用戶明確確認（含「確認」「執行」等關鍵詞）

## 可用 Skills
- safe-move: 安全移動（速度限制 ±0.3 m/s，角速度 ±0.5 rad/s，最長 10 秒）
- emergency-stop: 緊急停止（任意時刻可中斷）

## 互動風格
- 友善、專業、像一隻聰明的機器狗
- 執行動作前說明計畫
- 執行後回報結果
"""

agent = Agent(
    'anthropic:claude-sonnet-4-5',  # 可換成 'ollama:llama3.1' 等
    deps_type=RobotDeps,
    system_prompt=SYSTEM_PROMPT,
)


@agent.tool
async def tool_safe_move(
    ctx: RunContext[RobotDeps],
    linear_x: float,
    angular_z: float,
    duration: float,
) -> str:
    """安全移動 Go2 機器狗。

    Args:
        linear_x: 前進/後退速度 (m/s)，範圍 [-0.3, 0.3]
        angular_z: 旋轉速度 (rad/s)，範圍 [-0.5, 0.5]
        duration: 持續時間 (秒)，範圍 (0, 10]
    """
    result = await safe_move(ctx.deps.node, linear_x, angular_z, duration)
    if not result['success']:
        # 失敗時自動觸發 emergency-stop
        await emergency_stop(ctx.deps.node)
        return f"移動失敗: {result['message']}，已執行緊急停止"
    return f"移動完成: {result['message']}"


@agent.tool
async def tool_emergency_stop(ctx: RunContext[RobotDeps]) -> str:
    """緊急停止 Go2 所有動作。"""
    result = await emergency_stop(ctx.deps.node)
    return f"停止結果: {result['message']}"
```

#### 1.3 Agent 入口

```python
# go2_agent/main.py
"""Go2 Agent 入口 — 初始化 ROS2 + Agent loop。"""

import asyncio
import rclpy
from rclpy.node import Node

from go2_agent.agent import agent, RobotDeps


async def main():
    rclpy.init()
    node = Node('go2_agent')

    deps = RobotDeps(node=node)

    try:
        # 簡易互動 loop
        while rclpy.ok():
            user_input = input('\n你: ')
            if user_input.strip().lower() in ('quit', 'exit', '離開'):
                break

            result = await agent.run(user_input, deps=deps)
            print(f'PawAI: {result.data}')
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down Go2 Agent...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
```

### Phase 2: 感知 + 動作 Skills（2 週）

優先順序：

1. `find-object` — `/capture_snapshot` + GPU server VLM
2. `perform-action` — Go2 WebRTC actions（站立、蹲下、打招呼等）
3. `system-status` — ROS2 topics/services 健康檢查
4. `check-gpu` — GPU server HTTP health endpoint

### Phase 3: 導航 Skills（2 週）

1. `navigate-to` — Nav2 `NavigateToPose` Action（已有 rclpy ActionClient 範例在 `src/search_logic/`）
2. `nav-status` — 查詢導航進度
3. `cancel-nav` — 安全取消導航

### Phase 4: UI + 整合（1-2 週）

- FastAPI / Gradio Web 介面（替代 Claude Desktop）
- 語音整合（speech_processor tts_node + STT）
- Agent 狀態持久化（message history）

---

## 五、可實作功能清單

### 5.1 核心功能 (MVP — Phase 1)

| 功能 | Skill 名稱 | 難度 | 依賴 | 驗收標準 |
|------|-----------|------|------|---------|
| 安全移動 | `safe-move` | ⭐ | `/move_for_duration` | 速度/時間限制生效 |
| 緊急停止 | `emergency-stop` | ⭐ | `/stop_movement` | 任意時刻可中斷 |
| 尋找物體 | `find-object` | ⭐⭐ | `/capture_snapshot` + VLM | 回傳物體位置 |
| 執行動作 | `perform-action` | ⭐⭐ | WebRTC actions | 站立/蹲下等動作 |
| 系統狀態 | `system-status` | ⭐ | ROS2 health check | 顯示 topics + services |
| GPU 檢查 | `check-gpu` | ⭐ | HTTP endpoint | GPU server 健康檢查 |

### 5.2 進階功能 (Phase 2)

| 功能 | Skill 名稱 | 難度 | 備註 |
|------|-----------|------|------|
| 導航到點 | `navigate-to` | ⭐⭐⭐ | Nav2 Action 整合 |
| 導航狀態 | `nav-status` | ⭐⭐ | 查詢導航進度 |
| 取消導航 | `cancel-nav` | ⭐⭐ | 安全取消 |
| 語音對話 | `voice-chat` | ⭐⭐ | TTS + STT 整合 |
| 人臉追蹤 | `face-track` | ⭐⭐⭐ | YOLO + 視覺伺服 |

### 5.3 Nano Super v5.0 功能 (Phase 3)

| 功能 | Skill 名稱 | 難度 | 說明 |
|------|-----------|------|------|
| 自動避障 | `avoid-obstacles` | ⭐⭐⭐ | Sensor Gateway 整合 |
| 地圖探索 | `explore-map` | ⭐⭐⭐⭐ | SLAM + Frontier |
| 情感互動 | `emotional-interaction` | ⭐⭐⭐⭐ | 情感模型整合 |
| 長期記憶 | `memory-recall` | ⭐⭐⭐ | 記憶系統 |
| 多模態感知 | `multi-modal-perception` | ⭐⭐⭐⭐ | 融合 LiDAR + Vision |

---

## 六、情感互動功能設計

```python
# skills/interaction/emotional_interaction.py
"""情感互動 Skill — 結合 Agent 推理 + 動作執行。"""

from rclpy.node import Node
from skills.motion.emergency_stop import emergency_stop


async def emotional_interaction(
    node: Node,
    user_input: str,
    urgency: str = 'low',
) -> dict:
    """情感互動與陪伴。

    Args:
        node: ROS2 Node
        user_input: 用戶輸入文字
        urgency: 緊急程度 ('low', 'medium', 'high')

    Returns:
        dict: { success: bool, mode: str, ... }
    """
    # Fast Path (<200ms): 緊急處理
    if urgency == 'high':
        await emergency_stop(node)
        return {
            'success': True,
            'mode': 'emergency',
            'speech': '檢測到緊急情況，已停止移動',
        }

    # Slow Path (2-5s): LLM 推理 + 動作序列
    # 由 Agent 主循環處理，此處僅為架構示意
    return {
        'success': True,
        'mode': 'agent',
        'user_input': user_input,
    }
```

---

## 七、建議技術棧

```yaml
# 開發環境
language: Python 3.10+
runtime: CPython (Jetson 原生)
package_manager: uv pip

# 核心框架
agent_framework: pydantic-ai (v1.58+)
ros2_client: rclpy (直連，無需 rosbridge)
ui: FastAPI + Gradio (Web) / CLI (開發用)

# LLM 支援
providers:
  - Anthropic Claude Sonnet 4.5
  - OpenAI GPT-4o
  - Ollama (本地模型: llama3.1, qwen2.5)
  - Google Gemini Pro

# 部署
platform: Jetson Orin Nano SUPER (8GB)
ros2_version: Humble Hawksbill
install: uv pip install pydantic-ai
```

---

## 八、起步步驟

### Step 1: 環境準備

```bash
# 1. 確認 ROS2 環境
source /opt/ros/humble/setup.bash
source install/setup.bash

# 2. 安裝 Agent 框架
uv pip install pydantic-ai

# 3. 設定 LLM API Key
export ANTHROPIC_API_KEY="your-key-here"
# 或使用 Ollama 本地模型（無需 API Key）
# ollama pull llama3.1
```

### Step 2: 建立 Skills 目錄

```bash
mkdir -p skills/motion skills/perception skills/navigation skills/action skills/system
touch skills/__init__.py skills/motion/__init__.py
```

### Step 3: 實作第一個 Skill

參考上方 `safe_move.py` 實作，連線測試:

```bash
# 終端 1: 啟動 ROS2 driver + move_service
ros2 launch go2_robot_sdk robot.launch.py

# 終端 2: 啟動 Agent
python go2_agent/main.py
```

### Step 4: 整合測試

```
你: 向前走 2 秒
PawAI: 收到！計畫以 0.2 m/s 前進 2 秒，預計移動約 0.4 米。
       執行中... 完成！實際移動 1.98 秒。

你: 停
PawAI: 已執行緊急停止。
```

---

## 九、記憶體預估（Jetson 8GB）

| 元件 | 記憶體 | 備註 |
|------|--------|------|
| ROS2 Humble 基礎 | ~300MB | rclpy + 核心節點 |
| go2_driver_node | ~150MB | WebRTC + 感測器 |
| move_service + snapshot_service | ~50MB | 輕量 service nodes |
| Pydantic AI Agent | ~10MB | 極輕量 |
| LLM API Client | ~20MB | HTTP client |
| CUDA + PyTorch（coco_detector） | ~1.5GB | 僅開啟偵測時載入 |
| **合計（不含 CUDA）** | **~530MB** | 留 ~7.4GB 給系統和模型 |
| **合計（含 CUDA）** | **~2.0GB** | 留 ~6.0GB 給系統和本地模型 |

> 對比方案 A：Node.js runtime 額外 ~100MB + rosbridge ~50MB = 多 150MB 開銷。

---

## 十、風險與對策

| 風險 | 說明 | 對策 |
|------|------|------|
| LLM API 失敗 | 網路/配額 | Ollama 本地 Fallback + 快取 |
| Tool Calling 逾時 | ROS2 service 卡住 | timeout 設定 + emergency-stop |
| 安全邊界被繞過 | Agent 直接呼叫 cmd_vel | Skill 層強制限制 + move_service 硬 clamp |
| Agent 幻覺 | LLM 產生不合理指令 | 參數範圍限制 + 用戶確認機制 |
| 記憶體不足 | 多模型同時載入 | 按需載入 + 嚴格記憶體 budget |

---

## 十一、參考文件

- [Ros2_Skills.md](./Ros2_Skills.md) — MCP → Skills 重構計畫
- [refactor_plan.md](./refactor_plan.md) — 整體重構計畫
- [Pydantic AI 文件](https://ai.pydantic.dev/)
- [Anthropic SDK tool_runner 範例](https://github.com/anthropics/anthropic-sdk-python/blob/main/examples/tools_runner.py)
- [move_service.py](../../go2_robot_sdk/go2_robot_sdk/move_service.py) — 安全層實作

---

## 附錄 A：原方案 A 歷史紀錄（TypeScript/Pi-Mono）

> 以下為 v1.0 (2026-02-10) 的方案 A 原文，保留作為決策歷史紀錄。
> **結論：經可行性評估後不推薦。原因見 [零、v2.0 變更摘要](#零v20-變更摘要)。**

### Pi-Mono 框架概述

[Pi-Mono](https://github.com/badlogic/pi-mono) — Mario Zechner 開發的 AI Agent 工具包。

| 套件 | 功能 |
|------|------|
| @mariozechner/pi-ai | 統一多供應商 LLM API |
| @mariozechner/pi-agent-core | Agent Runtime + Tool Calling + 狀態管理 |
| @mariozechner/pi-tui | 終端 UI 函式庫 |
| @mariozechner/pi-web-ui | Web 元件庫 |

**不推薦原因**:
1. 純 TypeScript（96.5%），無 Python SDK
2. MCP 非內建（需 pi-mcp-adapter 擴充）
3. 無安全/guardrail 機制（僅 TypeBox schema validation）
4. 無機器人/IoT 文件或範例
5. 團隊零 TypeScript 經驗
6. 需 Node.js runtime（Jetson +100MB）
7. 需 rosbridge（roslibjs WebSocket），增加延遲

### 原方案 A 架構圖（僅供參考）

```
Go2 Agent (pi-mono)
  → pi-agent-core (Agent Runtime)
    → Tool Calling
      → ROS2 Bridge (roslibjs / WebSocket)
        → rosbridge (Jetson port 9090)
          → ROS2 Humble
```

---

**文件版本**: v2.0
**最後更新**: 2026-02-11
**建議方案**: 方案 B (Python Agent / Pydantic AI)
**預估工時**: 6-8 週 (MVP + UI + 進階功能)
