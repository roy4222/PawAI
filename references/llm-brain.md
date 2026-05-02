# LLM / AI 大腦 Reference

## 定位

Cloud LLM（Qwen2.5-7B-Instruct）作為 AI 大腦，處理對話、決策、動作指令。
llm_bridge_node 是語音+人臉觸發 → LLM → TTS+動作的中樞。

## 權威文件

- **語音模組設計**（含 LLM 段）：`docs/pawai-brain/speech/README.md`
- **LLM 整合規格**：`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-16-llm-integration-mini-spec.md`
- **Benchmark 研究**：`docs/archive/2026-05-docs-reorg/research-misc/llm_local.md`

## 核心程式

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/llm_bridge_node.py` | LLM 呼叫 + RuleBrain fallback + greet dedup |
| `speech_processor/speech_processor/llm_contract.py` | LLM JSON 契約定義（純 Python） |
| `benchmarks/scripts/bench_llm_local.py` | 本地 LLM benchmark |

## 雲端 LLM

- **模型**：Qwen2.5-7B-Instruct（純文字 CausalLM）
- **伺服器**：RTX 8000 @ 140.136.155.5:8000（vLLM 0.17.1）
- **API**：OpenAI-compatible
- **延遲**：~1.5s（vLLM Prefix Cache 生效）
- **max_tokens**：120，prompt 限 reply 25 字
- **SSH tunnel**：`ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5`

## 本地 LLM（備援）

- Qwen2.5-0.5B：P50 0.8s, 139MB（JETSON_LOCAL）
- Qwen2.5-1.5B：HYBRID 待測

## 兩條觸發路徑

- **Path A（語音）**：`/event/speech_intent_recognized` → LLM → `/tts` + `/webrtc_req`
- **Path B（人臉）**：`/event/face_identity`（identity_stable + 具名）→ LLM → 叫名字 + 揮手

## 防護機制

- **RuleBrain fallback**：LLM 失敗自動 fallback，`force_fallback:=true` 可強制測試
- **空 reply 防守**：SYSTEM_PROMPT 強制 + 代碼防守 + RuleBrain rescue
- **greet dedup cooldown**（3/23 新增）：5s 內同一來源的 greet 只處理一次

## 已知陷阱

- Qwen3.5-9B 不可用（多模態模型，vLLM encoder profiling 15+ 分鐘未完成）
- interaction_executive 空殼 → 語音流和視覺流無仲裁，同一人可能觸發兩次 Hello

## 啟動

```bash
# SSH tunnel（必要）
ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5

# 啟動 llm_bridge_node
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_endpoint:="http://localhost:8000/v1/chat/completions" \
  -p llm_model:="Qwen/Qwen2.5-7B-Instruct"

# 強制 RuleBrain fallback（debug）
ros2 run speech_processor llm_bridge_node --ros-args -p force_fallback:=true
```
