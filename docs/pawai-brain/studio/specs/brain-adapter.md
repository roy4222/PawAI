# Brain Adapter — LLM 統一介面

**文件版本**：v1.0
**最後更新**：2026-03-13
**對齊來源**：[mission/README.md](../mission/README.md) v2.0

---

## 設計原則

> **LLM 提建議 → Interaction Executive 做決策 → Runtime 安全執行。**

Brain Adapter 是 Interaction Executive 與 LLM 之間的抽象層。無論底層是 Qwen3.5-9B、27B、0.8B 還是 Rule-based，Executive 永遠用同一個介面呼叫。

---

## 架構位置

```
Interaction Executive (Jetson)
    │
    ├── Brain Adapter (抽象介面)
    │       │
    │       ├── CloudBrain (gRPC/HTTP → RTX 8000 vLLM)        ← Level 0
    │       │     └── Qwen3.5-9B → 27B
    │       │
    │       ├── LocalBrain (本地推理，僅斷網 fallback)          ← Level 1
    │       │     └── Qwen3.5-0.8B INT4
    │       │
    │       ├── RuleBrain (規則引擎)                            ← Level 2
    │       │     └── Intent → Task → Skill 映射 + 模板回覆
    │       │
    │       └── MinimalBrain (最小保底)                         ← Level 3
    │             └── 僅 stop / greet / bye 固定指令，無 TTS
    │
    └── Safety Guard → Runtime
```

---

## Brain Adapter 介面

### Request（Executive → Brain）

```python
@dataclass
class BrainRequest:
    # 上下文
    events: list[dict]          # 近期事件摘要（face/speech/gesture）
    robot_state: dict           # 機器人當前狀態
    conversation_history: list[dict]  # 對話歷史（最近 N 輪）

    # 當前輸入
    trigger_event: dict         # 觸發本次決策的事件
    user_text: str | None       # ASR 轉寫文字（若有）

    # 系統資訊
    degradation_level: int      # 當前降級等級 0-3
    available_skills: list[str] # 當前可用技能列表
    active_tracks: int          # 追蹤中的人臉數
```

### Response（Brain → Executive）

```python
@dataclass
class BrainResponse:
    # 決策
    intent: str                 # 判定的意圖
    selected_skill: str | None  # 建議執行的技能（可為 None）
    reply_text: str             # 回覆文字（送 TTS）

    # 面板建議
    suggested_layout: str | None  # 建議的 layout preset

    # 追蹤
    reasoning: str              # 決策理由（用於 BrainPanel trace）
    confidence: float           # 決策信心度 [0.0, 1.0]

    # 記憶（可選）
    memory_update: dict | None  # 需要更新的記憶（人物、偏好等）
```

---

## 三種 Brain 實作

### CloudBrain（Level 0：雲端完整模式）

```python
class CloudBrain(BrainAdapter):
    """雲端 LLM，完整能力。"""

    def __init__(self, endpoint: str, model: str, timeout: float = 3.0):
        self.endpoint = endpoint   # e.g. "http://rtx-server:8080/v1"
        self.model = model         # e.g. "Qwen3.5-9B"
        self.timeout = timeout

    async def decide(self, request: BrainRequest) -> BrainResponse:
        prompt = self._build_prompt(request)

        try:
            result = await self._call_vllm(prompt, timeout=self.timeout)
            return self._parse_response(result)
        except TimeoutError:
            raise  # 讓 Executive 處理 fallback

    def _build_prompt(self, request: BrainRequest) -> str:
        """
        System prompt 包含：
        - PawAI 角色設定
        - 可用技能列表
        - 輸出格式要求（JSON structured output）
        - 安全規則（不可建議高風險動作）
        """
        ...
```

**雲端 LLM 能力**：
- 自然語言理解與回覆
- 多輪對話記憶
- 事件上下文推理（「剛才 Roy 來過，現在又看到他」）
- 技能調度建議
- Panel layout 建議
- 情感理解

### LocalBrain（Level 1：本地 fallback）

```python
class LocalBrain(BrainAdapter):
    """本地小模型，僅斷網時使用。"""

    def __init__(self, model_path: str):
        self.model_path = model_path  # Qwen3.5-0.8B INT4
        self.model = None             # 延遲載入

    async def decide(self, request: BrainRequest) -> BrainResponse:
        if self.model is None:
            self.model = self._load_model()  # 動態載入 ~1GB

        prompt = self._build_simple_prompt(request)
        result = self._infer(prompt)
        return self._parse_response(result)

    def unload(self):
        """釋放記憶體。"""
        del self.model
        self.model = None
```

**限制**：
- 只做基本對話，不做複雜推理
- 不支援 panel orchestration
- 不支援長上下文記憶
- ~1GB 記憶體，動態載入/卸載

### RuleBrain（Level 2：規則引擎）

```python
class RuleBrain(BrainAdapter):
    """純規則映射，零 LLM 依賴。"""

    INTENT_TO_SKILL = {
        "greet": "hello",
        "stop": "stop_move",
        "come_here": "hello",       # 安全替代
        "take_photo": None,          # 暫不支援
        "status": None,              # 純語音回覆
    }

    REPLY_TEMPLATES = {
        "greet": "哈囉，你好！",
        "stop": "好的，我停下來了。",
        "come_here": "我在這裡！",
        "status": "我目前狀態正常。",
    }

    async def decide(self, request: BrainRequest) -> BrainResponse:
        intent = request.trigger_event.get("intent", "unknown")
        return BrainResponse(
            intent=intent,
            selected_skill=self.INTENT_TO_SKILL.get(intent),
            reply_text=self.REPLY_TEMPLATES.get(intent, "我聽到了。"),
            suggested_layout=None,
            reasoning=f"rule_match: {intent}",
            confidence=1.0,
            memory_update=None,
        )
```

---

## Fallback 鏈

Executive 依序嘗試，失敗則降級：

```python
class MinimalBrain(BrainAdapter):
    """Level 3: 最小保底，只回應固定指令。"""

    FIXED_COMMANDS = {"stop", "greet", "bye"}

    async def decide(self, request: BrainRequest) -> BrainResponse:
        intent = request.trigger_event.get("intent", "unknown")
        if intent == "stop":
            return BrainResponse(intent="stop", selected_skill="stop_move",
                                 reply_text="", suggested_layout=None,
                                 reasoning="minimal: stop", confidence=1.0,
                                 memory_update=None)
        if intent == "greet":
            return BrainResponse(intent="greet", selected_skill="hello",
                                 reply_text="", suggested_layout=None,
                                 reasoning="minimal: greet", confidence=1.0,
                                 memory_update=None)
        # 其餘一律忽略
        return BrainResponse(intent="ignored", selected_skill=None,
                             reply_text="", suggested_layout=None,
                             reasoning="minimal: not a fixed command",
                             confidence=1.0, memory_update=None)
```

**Level 3 特徵**：
- 不做 TTS 回覆（`reply_text` 為空），省下 TTS 記憶體
- 只處理 `stop` / `greet` / `bye` 三個固定指令
- ASR 仍在跑（喚醒 + 辨識），但不走 LLM 也不走規則引擎全集

```python
class BrainManager:
    def __init__(self):
        self.cloud = CloudBrain(...)
        self.local = LocalBrain(...)
        self.rule = RuleBrain()
        self.minimal = MinimalBrain()
        self.current_level = 0

    async def decide(self, request: BrainRequest) -> BrainResponse:
        request.degradation_level = self.current_level

        # Level 0: 嘗試雲端
        if self.current_level == 0:
            try:
                return await self.cloud.decide(request)
            except (TimeoutError, ConnectionError):
                self.current_level = 1
                self._emit_degradation_event(0, 1)

        # Level 1: 嘗試本地 LLM
        if self.current_level == 1:
            try:
                return await self.local.decide(request)
            except MemoryError:
                self.current_level = 2
                self.local.unload()
                self._emit_degradation_event(1, 2)

        # Level 2: 規則引擎
        if self.current_level == 2:
            try:
                return await self.rule.decide(request)
            except Exception:
                self.current_level = 3
                self._emit_degradation_event(2, 3)

        # Level 3: 最小保底（永遠成功）
        return await self.minimal.decide(request)

    async def try_recover(self):
        """定期嘗試恢復到更高等級。"""
        if self.current_level > 0:
            previous = self.current_level
            if await self._check_cloud():
                self.current_level = 0
                self._emit_degradation_event(previous, 0)
```

---

## 雲端 LLM Roadmap

| 階段 | 模型 | 目標 | 時間 |
|------|------|------|------|
| 第一版 | Qwen3.5-9B | 跑通大腦鏈路 | 3/16 後 |
| 第二版 | Qwen3.5-27B | 品質升級 | 4/6 前 |
| 候選 | Qwen3.5-35B-A3B / MiniMax-M2.5 | 研究，尚未實測 | 4/13 後 |

### vLLM 部署（RTX 8000）

```bash
# GPU 0 上部署 Qwen3.5-9B
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3.5-9B \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.85 \
  --port 8080
```

### Structured Output

Brain Adapter 要求 LLM 以 JSON 格式回覆，確保可靠解析：

```json
{
  "intent": "greet",
  "skill": "hello",
  "reply": "哈囉 Roy，好久不見！",
  "layout": "chat_camera",
  "reasoning": "偵測到熟人 Roy，距離 1.4m，適合打招呼"
}
```

vLLM 的 `guided_json` 參數可強制輸出符合 schema。

---

## 與 Executive 的協作

```
1. 感知事件到達 Executive
2. Executive 組裝 BrainRequest
3. BrainManager.decide() 取得 BrainResponse
4. Executive 驗證：
   - skill 是否在 available_skills 內？
   - 是否違反 Safety Guard 規則？
   - reply_text 是否合理長度？
5. 通過驗證 → 執行 skill + TTS + layout 切換
6. 未通過 → 降級到 RuleBrain 重做決策
```

**關鍵**：Executive 永遠有最終決策權。Brain 的建議可以被拒絕。

---

*最後更新：2026-03-13*
*維護者：System Architect*
