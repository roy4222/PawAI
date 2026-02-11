# Pi-Mono + Go2 Agent 整合方案 (TO-BE)

本文件是整合提案與設計草案（`TO-BE`）。本 repo 目前沒有 Node.js/TypeScript 專案骨架（例如 `package.json`），因此本文的 npm 指令是「建立新專案」的步驟，不是對此 repo 直接可執行的操作手冊。

**日期**: 2026-02-10  
**目標**: 使用 pi-mono 框架打造專屬 Go2 Agent，整合 ROS2 Skills 架構  
**參考**: [pi-mono](https://github.com/badlogic/pi-mono), [Ros2_Skills.md](./Ros2_Skills.md)

---

## 一、Pi-Mono 框架概述

**Pi-Mono** 是 Mario Zechner 開發的 AI Agent 工具包，採用 Monorepo 架構，主要包含以下核心套件：

| 套件 | 功能 | Go2 Agent 適用性 |
|-----|------|----------------|
| **@mariozechner/pi-ai** | 統一多供應商 LLM API (OpenAI, Anthropic, Google 等) | ✅ 可整合多種 LLM |
| **@mariozechner/pi-agent-core** | Agent Runtime + Tool Calling + 狀態管理 | ✅ **核心，用於 Skills 調度** |
| **@mariozechner/pi-coding-agent** | 互動式編碼 Agent CLI | ⚠️ 可參考互動模式 |
| **@mariozechner/pi-tui** | 終端 UI 函式庫 (差分渲染) | ✅ 用於本地監控介面 |
| **@mariozechner/pi-web-ui** | Web 元件庫 (AI Chat 介面) | ✅ 用於遠端控制面板 |
| **@mariozechner/pi-pods** | vLLM 部署管理 (GPU Pods) | ⚠️ 可部署本地 LLM |
| **@mariozechner/pi-mom** | Slack Bot 委派 | ❌ 暫不需要 |

**技術特點**:
- TypeScript 96.5% (純 TypeScript 技術棧)
- 統一 LLM API 抽象層
- 內建 Tool Calling 機制
- TUI/Web UI 雙介面支援
- 社群數據（stars/forks）請以查詢當天為準，本 repo 不保證同步更新。

---

## 二、整合架構方案

### 方案 A: TypeScript-based Agent (推薦 ⭐⭐⭐⭐⭐)

```
┌─────────────────────────────────────────────────────────┐
│                  Go2 Agent (pi-mono)                     │
│                  (開發機/Mac/VM)                         │
├─────────────────────────────────────────────────────────┤
│  pi-agent-core (Agent Runtime)                          │
│       ↓ Tool Calling                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ perception  │  │   motion    │  │   navigation    │ │
│  │  skills     │  │   skills    │  │     skills      │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         └─────────────────┴──────────────────┘          │
│                    ROS2 Bridge                         │
│              (roslib.js / WebSocket)                   │
└─────────────────────────┬───────────────────────────────┘
                          │ WebSocket
                          ↓
┌─────────────────────────────────────────────────────────┐
│              ROS2 Humble (Jetson Orin Nano)            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ go2_driver  │  │   skills/   │  │  sensor_gateway │ │
│  │   _node     │  │   *_service │  │                 │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**優點**:
- ✅ 統一 TypeScript 技術棧，前後端一致
- ✅ pi-agent-core 原生支援 Tool Calling 與狀態管理
- ✅ 可利用 pi-tui/pi-web-ui 快速建立監控介面
- ✅ 支援多 LLM 供應商動態切換
- ✅ Skills 架構與 pi-agent-core 天然契合

**缺點**:
- ⚠️ 需要額外 ROS2-NodeJS 橋接層
- ⚠️ Jetson 上需部署 Node.js runtime (約 100MB)
- ⚠️ 需要處理 WebSocket 連線穩定性

---

### 方案 B: Python Hybrid (穩妥 ⭐⭐⭐)

```
┌─────────────────────────────────────────────────────────┐
│              Go2 Agent (Python + pi-mono API)            │
├─────────────────────────────────────────────────────────┤
│  Python Agent Core (參考 pi-agent-core 設計)             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ pi-ai API   │  │ ROS2 Python │  │   Skill Router  │ │
│  │ (LLM call)  │  │   Client    │  │                 │ │
│  └─────────────┘  └──────┬──────┘  └─────────────────┘ │
│                          ↓                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │          rclpy (ROS2 Python Client)              │   │
│  └──────────────────────┬──────────────────────────┘   │
└─────────────────────────┼──────────────────────────────┘
                          ↓ ROS2 Topics/Services
┌─────────────────────────────────────────────────────────┐
│              ROS2 Humble (Jetson Orin Nano)            │
└─────────────────────────────────────────────────────────┘
```

**優點**:
- ✅ 直接使用現有 ROS2 Python 套件 (rclpy)
- ✅ 無需額外橋接層，通訊延遲最低
- ✅ Jetson 原生支援 Python，無額外依賴
- ✅ 與現有 `go2_robot_sdk` Python 生態相容

**缺點**:
- ❌ 無法使用 pi-agent-core 的進階功能 (需自行實現)
- ❌ 無法使用 pi-tui/pi-web-ui，UI 需額外開發
- ❌ 需要自行實現 Tool Calling 機制
- ❌ LLM API 整合需額外開發

---

### 方案 C: 純 pi-mono + MCP 混合 (漸進式 ⭐⭐⭐⭐)

```
┌─────────────────────────────────────────────────────────┐
│              pi-mono Agent (本地開發機)                  │
│         pi-coding-agent 模式改裝為 Go2 Agent            │
├─────────────────────────────────────────────────────────┤
│       ↓ MCP Protocol (stdio/sse)                        │
┌─────────────────────────────────────────────────────────┐
│              ros-mcp-server (Jetson)                    │
│         轉換為 Skills 架構 (參考 Ros2_Skills.md)         │
├─────────────────────────────────────────────────────────┤
│       ↓ ROS2                                            │
│              go2_robot_sdk + skills/                    │
└─────────────────────────────────────────────────────────┘
```

**優點**:
- ✅ 充分利用 pi-mono 完整生態 (pi-coding-agent 基礎)
- ✅ MCP 作為標準介面，可與其他 MCP Client 共用
- ✅ 可漸進遷移至純 Skills，風險最低
- ✅ 保留現有 ros-mcp-server 投資

**缺點**:
- ⚠️ 需維護 MCP 層，增加複雜度
- ⚠️ 通訊延遲較高 (stdio/sse 額外開銷)
- ⚠️ 需要處理 MCP Server 生命周期

---

## 三、方案比較總表

| 維度 | 方案 A (TS) | 方案 B (Python) | 方案 C (Hybrid) |
|-----|------------|----------------|----------------|
| **開發速度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **執行效能** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **生態完整** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **維護難度** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **擴展性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Jetson 資源** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **UI 支援** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **風險** | 中 | 低 | 低 |

---

## 四、推薦實作路徑 (方案 A)

基於 **Ros2_Skills.md** 規劃，建議採用 **方案 A (TypeScript) + 漸進遷移**：

### Phase 1: 核心 Skills 橋接 (2 週)

建立 `go2-pi-bridge` 套件：

```typescript
// packages/go2-pi-bridge/src/skills/safe-move.ts
import { Skill, SkillContext } from '@mariozechner/pi-agent-core';
import { ROS2Client } from '../ros2-client';

export const safeMoveSkill: Skill = {
  name: 'safe-move',
  description: '安全移動 Go2 機器狗',
  
  parameters: {
    linear_x: { 
      type: 'number', 
      min: -0.3, 
      max: 0.3,
      description: '前進/後退速度 (m/s)'
    },
    angular_z: { 
      type: 'number', 
      min: -0.5, 
      max: 0.5,
      description: '旋轉速度 (rad/s)'
    },
    duration: { 
      type: 'number', 
      min: 0, 
      max: 10,
      description: '持續時間 (秒)'
    }
  },
  
  async execute(params, context: SkillContext) {
    // 硬限制檢查 (Safety Gate)
    const linear_x = Math.max(-0.3, Math.min(0.3, params.linear_x));
    const angular_z = Math.max(-0.5, Math.min(0.5, params.angular_z));
    const duration = Math.max(0, Math.min(10, params.duration));
    
    context.log.info(`執行安全移動: linear=${linear_x}, angular=${angular_z}, duration=${duration}`);
    
    // 調用 ROS2 Service
    const ros = context.getService<ROS2Client>('ros2');
    const result = await ros.callService('/move_for_duration', {
      linear_x, angular_z, duration
    });
    
    return {
      success: result.success,
      message: result.message,
      actual_duration: result.actual_duration,
      clamped: {
        linear_x: linear_x !== params.linear_x,
        angular_z: angular_z !== params.angular_z,
        duration: duration !== params.duration
      }
    };
  },
  
  // 失敗時自動執行緊急停止
  async onError(error, context) {
    context.log.error(`safe-move 失敗: ${error.message}`);
    const ros = context.getService<ROS2Client>('ros2');
    await ros.callService('/stop_movement', {});
    throw error;
  }
};
```

### Phase 2: Agent Runtime 搭建 (2 週)

```typescript
// src/go2-agent.ts
import { Agent, AgentConfig } from '@mariozechner/pi-agent-core';
import { OpenAIProvider } from '@mariozechner/pi-ai';
import { ROS2Client } from './ros2-client';

// Skills
import { safeMoveSkill } from './skills/safe-move';
import { emergencyStopSkill } from './skills/emergency-stop';
import { findObjectSkill } from './skills/find-object';
import { performActionSkill } from './skills/perform-action';
import { systemStatusSkill } from './skills/system-status';
import { checkGpuSkill } from './skills/check-gpu';

async function main() {
  // 初始化 ROS2 連線
  const ros = new ROS2Client({
    url: process.env.ROS2_WS_URL || 'ws://jetson-orin:9090'
  });
  await ros.connect();
  
  // 建立 Agent
  const agent = new Agent({
    llm: new OpenAIProvider({ 
      model: 'gpt-4-turbo-preview',
      apiKey: process.env.OPENAI_API_KEY
    }),
    
    skills: [
      safeMoveSkill,
      emergencyStopSkill,
      findObjectSkill,
      performActionSkill,
      systemStatusSkill,
      checkGpuSkill
    ],
    
    services: {
      ros2: ros
    },
    
    systemPrompt: `
你是 Go2 機器狗的專屬 Agent，代號 "PawAI"。

## 核心原則
1. 安全優先 - 所有移動必須使用 safe-move skill，禁止直接發送 cmd_vel
2. 任何失敗必須先執行 emergency-stop
3. 真機執行需要明確用戶確認

## 可用 Skills
- safe-move: 安全移動 (有速度/時間限制)
- emergency-stop: 緊急停止
- find-object: 尋找物體 (視覺辨識)
- perform-action: 執行動作 (站立、蹲下等)
- system-status: 查詢系統狀態
- check-gpu: 檢查 GPU 伺服器狀態

## 互動風格
- 友善、專業、像一隻聰明的機器狗
- 執行動作前說明計畫
- 執行後回報結果
    `.trim()
  });
  
  // 啟動互動模式
  await agent.runInteractive();
}

main().catch(console.error);
```

### Phase 3: UI 介面 (1 週)

#### TUI 監控介面 (pi-tui)

```typescript
// src/tui/dashboard.tsx
import { App, Box, Text, useState, useEffect } from '@mariozechner/pi-tui';
import { ROS2Client } from '../ros2-client';

interface RobotState {
  connected: boolean;
  battery: number;
  currentAction: string;
  position: { x: number; y: number; z: number };
}

function Dashboard() {
  const [state, setState] = useState<RobotState>({
    connected: false,
    battery: 0,
    currentAction: 'idle',
    position: { x: 0, y: 0, z: 0 }
  });
  
  useEffect(() => {
    // 訂閱 ROS2 狀態
    const ros = new ROS2Client();
    ros.subscribe('/go2_states', (msg) => {
      setState(prev => ({
        ...prev,
        battery: msg.bms_state.soc,
        position: msg.position
      }));
    });
  }, []);
  
  return (
    <Box flexDirection="column" padding={1}>
      <Text bold color="cyan">🐕 Go2 Agent Dashboard</Text>
      <Box marginTop={1}>
        <Text>狀態: {state.connected ? '🟢 已連線' : '🔴 離線'}</Text>
      </Box>
      <Box>
        <Text>電量: {state.battery}% {state.battery < 20 ? '⚠️' : ''}</Text>
      </Box>
      <Box>
        <Text>當前動作: {state.currentAction}</Text>
      </Box>
      <Box>
        <Text>位置: ({state.position.x.toFixed(2)}, {state.position.y.toFixed(2)})</Text>
      </Box>
    </Box>
  );
}

const app = new App();
app.render(<Dashboard />);
app.start();
```

#### Web 控制面板 (pi-web-ui)

```typescript
// src/web/app.tsx
import { WebApp, ChatInterface, StatusPanel } from '@mariozechner/pi-web-ui';
import { Agent } from '@mariozechner/pi-agent-core';

function WebDashboard({ agent }: { agent: Agent }) {
  return (
    <div className="go2-dashboard">
      <StatusPanel 
        title="Go2 Robot Status"
        items={[
          { label: 'Connection', value: agent.isConnected() ? 'Online' : 'Offline' },
          { label: 'Skills Loaded', value: agent.skills.length.toString() }
        ]}
      />
      
      <ChatInterface 
        agent={agent}
        placeholder="輸入指令控制 Go2..."
      />
    </div>
  );
}
```

---

## 五、可實作功能清單

### 5.1 核心功能 (MVP - Phase 1)

| 功能 | Skill 名稱 | 難度 | 依賴 | 驗收標準 |
|-----|-----------|------|------|---------|
| 安全移動 | `safe-move` | ⭐ | `/move_for_duration` | 速度/時間限制生效 |
| 緊急停止 | `emergency-stop` | ⭐ | `/stop_movement` | 任意時刻可中斷 |
| 尋找物體 | `find-object` | ⭐⭐ | `/capture_snapshot` + VLM | 回傳物體位置 |
| 執行動作 | `perform-action` | ⭐⭐ | WebRTC actions | 站立/蹲下等動作 |
| 系統狀態 | `system-status` | ⭐ | `/get_topics` | 顯示所有 topics |
| GPU 檢查 | `check-gpu` | ⭐ | HTTP endpoint | GPU server 健康檢查 |

### 5.2 進階功能 (Phase 2)

| 功能 | Skill 名稱 | 難度 | 備註 |
|-----|-----------|------|------|
| 導航到點 | `navigate-to` | ⭐⭐⭐ | Nav2 Action 整合 |
| 導航狀態 | `nav-status` | ⭐⭐ | 查詢導航進度 |
| 取消導航 | `cancel-nav` | ⭐⭐ | 安全取消 |
| 語音對話 | `voice-chat` | ⭐⭐ | TTS + STT 整合 |
| 人臉追蹤 | `face-track` | ⭐⭐⭐ | YOLO + 視覺伺服 |

### 5.3 Nano Super v5.0 功能 (Phase 3)

| 功能 | Skill 名稱 | 難度 | 說明 |
|-----|-----------|------|------|
| 自動避障 | `avoid-obstacles` | ⭐⭐⭐ | Sensor Gateway 整合 |
| 地圖探索 | `explore-map` | ⭐⭐⭐⭐ | SLAM + Frontier |
| 情感互動 | `emotional-interaction` | ⭐⭐⭐⭐ | OpenClaw 整合 |
| 長期記憶 | `memory-recall` | ⭐⭐⭐ | 記憶系統 |
| 多模態感知 | `multi-modal-perception` | ⭐⭐⭐⭐ | 融合 LiDAR + Vision |

---

## 六、情感互動功能設計 (OpenClaw 整合)

```typescript
// src/skills/emotional-interaction.ts
import { Skill, SkillContext } from '@mariozechner/pi-agent-core';

export const emotionalInteractionSkill: Skill = {
  name: 'emotional-interaction',
  description: '情感互動與陪伴',
  
  parameters: {
    userInput: { type: 'string', required: true },
    urgency: { type: 'string', enum: ['low', 'medium', 'high'] }
  },
  
  async execute(params, context) {
    // Fast Path (<200ms): 本地安全處理
    if (params.urgency === 'high') {
      await context.callSkill('emergency-stop');
      await context.callSkill('speak', { text: '檢測到緊急情況，已停止移動' });
      return { success: true, mode: 'emergency' };
    }
    
    // Slow Path (2-5s): 遠端 OpenClaw 推理
    const openclaw = context.getService<OpenClawClient>('openclaw');
    const robotContext = await getRobotContext(context);
    
    const response = await openclaw.generateResponse({
      context: robotContext,
      userInput: params.userInput,
      memory: await getLongTermMemory(),
      emotions: await getCurrentEmotionalState()
    });
    
    // 執行回應動作序列
    if (response.action) {
      await context.callSkill('perform-action', { action: response.action });
    }
    
    if (response.speech) {
      await context.callSkill('speak', { text: response.speech });
    }
    
    // 儲存互動記憶
    await storeInteractionMemory({
      input: params.userInput,
      response: response,
      timestamp: Date.now()
    });
    
    return {
      success: true,
      mode: 'openclaw',
      emotion: response.emotion,
      speech: response.speech
    };
  }
};
```

---

## 七、建議技術棧

```yaml
# 開發環境
language: TypeScript 5.3+
runtime: Node.js 20 LTS
package_manager: npm / pnpm

# 核心框架
agent_framework: pi-mono (pi-agent-core, pi-ai)
ros2_bridge: roslibjs (WebSocket)
ui: pi-tui (本地) + pi-web-ui (遠端)

# LLM 支援
providers:
  - OpenAI GPT-4 Turbo
  - Anthropic Claude 3.5 Sonnet
  - Google Gemini Pro
  - Local (via pi-pods vLLM)

# 部署
deployment: Docker
platform: Jetson Orin Nano (8GB)
ros2_version: Humble Hawksbill
```

---

## 八、起步步驟（建立新專案）

### Step 1: 環境準備

```bash
# 1. Clone pi-mono
git clone https://github.com/badlogic/pi-mono.git
cd pi-mono
npm install
npm run build

# 2. 建立 Go2 Agent 專案
mkdir go2-pi-agent
cd go2-pi-agent
npm init -y

# 3. 安裝 pi-mono 套件
npm install @mariozechner/pi-agent-core @mariozechner/pi-ai
npm install @mariozechner/pi-tui @mariozechner/pi-web-ui
npm install roslib  # ROS2 WebSocket client

# 4. TypeScript 設定
npm install -D typescript @types/node
npx tsc --init
```

### Step 2: ROS2 WebSocket 橋接

在 Jetson 上啟動 rosbridge:
```bash
# Jetson Orin Nano
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

### Step 3: 實作第一個 Skill

參考上方 `safe-move.ts` 實作，連線測試:
```bash
npm run dev
```

### Step 4: 整合測試

```bash
# 測試 safe-move
> 向前走 2 秒
Agent: 計畫: 以 0.2 m/s 前進 2 秒，預計移動 0.4 米。確認執行嗎？
> 確認
Agent: 執行中... 完成！實際移動 1.8 秒
```

---

## 九、風險與對策

| 風險 | 說明 | 對策 |
|-----|------|------|
| WebSocket 斷線 | 網路不穩 | 自動重連 + 降級模式 |
| LLM API 失敗 | 網路/配額 | 本地 Fallback + 快取 |
| Node.js 記憶體 | Jetson 8GB | 限制並發 + 定期 GC |
| Tool Calling 逾時 | ROS2 卡住 | 設定 timeout + emergency-stop |
| 安全邊界被繞過 | 直接呼叫 | Skill 層強制限制 |

---

## 十、參考文件

- [pi-mono GitHub](https://github.com/badlogic/pi-mono)
- [pi-agent-core API](./pi-mono/packages/agent)（此路徑不在本 repo；僅為上游結構示意）
- [Ros2_Skills.md](./Ros2_Skills.md)
- [refactor_plan.md](./refactor_plan.md)
- [pi.dev](https://pi.dev)

---

**文件版本**: v1.0  
**最後更新**: 2026-02-10  
**建議方案**: 方案 A (TypeScript-based Agent)  
**預估工時**: 6-8 週 (MVP + UI + 進階功能)
