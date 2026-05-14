# Mac Migration Pre-flight Housekeeping — Design Spec

**Date**: 2026-05-12
**Author**: roy422 + Claude
**Status**: Draft → Pending user review
**Scope**: Housekeeping only（最小可行集）；不含 OFFLINE_MODE 一鍵切換、不含 Cobra CLI（兩者各自單獨 spec，post-demo 再做）

---

## 1. 目標與動機

5/12 demo 後要把開發機從 WSL 搬到 Mac。為了讓 Mac 端 `git clone` 後可以無痛開工，這份 spec 做最小可行的環境攜帶準備：把所有需要跟著走的東西（custom skills、memory、寫死路徑）處理好，列出 Mac 端 setup runbook。

**判準**：完成後在 Mac 上能跑通 `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`，而且 Claude Code 的 hooks、custom skills、memory 都還在。

**不做的事**（明確排除以收斂 scope）：
- `OFFLINE_MODE=1` 一鍵切換腳本（手動切 env 即可，post-demo 再做）
- Go cobra `pawai` CLI 重寫（sub-project 開單獨 spec）
- 重構 YAML 內 `/home/jetson/` 路徑（Jetson 端配置，Mac 不直接讀）
- Jetson 上的 model files 路徑統一（無痛在 WSL/Mac/Jetson 互通屬於另個 sub-project）

---

## 2. 現況快照（2026-05-12）

### 2.1 .claude/ 追蹤狀態
- **已追蹤**：4 個 skill（brain-studio-lane / nav-avoidance-lane / jetson-verify / project-onboard）+ 7 rules + sprint-day command + settings.json
- **本地未追蹤**：5 個 skill（demo-preflight / project-deep-auditor / reviewer / ros2-test-suite / ui-ux-pro-max）
- 工作樹 clean

### 2.2 寫死路徑（Mac 會炸）
| 檔案 | 內容 | 嚴重度 |
|------|------|:----:|
| `.claude/settings.json`（4 條 hook） | `/home/roy422/newLife/elder_and_dog/scripts/hooks/...` | CRITICAL |
| `scripts/hooks/post_tool_py_syntax.sh:11` | `/home/roy422/newLife/elder_and_dog` | CRITICAL |
| `.claude/skills/jetson-verify/scripts/transport.py:27-28` | hardcode `jetson-nano` + `/home/jetson/elder_and_dog` | HIGH |

其他 `/home/jetson/` 路徑都在 Jetson YAML 內（屬 Jetson 端），或在 scripts 內有 env override（`ROBOT_IP`/`JETSON_HOST`/`LLM_ENDPOINT` 等），Mac 不需改。

### 2.3 Memory
- 位置：`~/.claude/projects/-home-roy422-newLife-elder-and-dog/memory/`
- 1741 行 / 25+ 個 .md 檔
- 含 `user_career_goals.md` + `user_career_interest.md`（個人）
- 含 `MEMORY.md` 主索引 + 多個 `project_*.md` / `finding_*.md`
- 無秘密 / API key

### 2.4 斷網 fallback 鏈（已存在，無需改）
| 層 | Cloud | Local fallback |
|------|-------|---------------|
| LLM | OpenRouter gpt-5.4-mini → gemini-3-flash | vLLM tunnel → Ollama 1.5b → RuleBrain（4 層）|
| ASR | qwen_cloud（RTX 8000）| sensevoice_local → whisper_local |
| TTS | openrouter_gemini → edge_tts | piper |
| Face/Object | — | YuNet / SFace / YOLO26n 全離線 |
| Weather | wttr.in | gracefully degrade（空字串）|

`PIPER_MODEL_PATH` 預設空字串會 init 失敗 — 走 piper 路線前必須設 env。

---

## 3. 五項變更

### 3.1 Skills whitelist 擴充（B1）

**動機**：3 個本地 skill 是專案輕量工具，Mac 端要保留。

**變更**：`.gitignore` 加 3 條：
```diff
 .claude/skills/
 !.claude/skills/jetson-verify/
 !.claude/skills/project-onboard/
 !.claude/skills/update-docs/
 !.claude/skills/jetson-deploy/
 !.claude/skills/jetson-status/
 !.claude/skills/jetson-verify/
 !.claude/skills/brain-studio-lane/
 !.claude/skills/nav-avoidance-lane/
+!.claude/skills/demo-preflight/
+!.claude/skills/reviewer/
+!.claude/skills/ros2-test-suite/
```

**操作**：`git add .gitignore .claude/skills/{demo-preflight,reviewer,ros2-test-suite}/` → commit。

**驗證**：clone 出來確認 3 個 skill 都在。

**不加的**：
- `project-deep-auditor`（22 檔含歷史 plans/，太重）
- `ui-ux-pro-max`（34 檔含 CSV 資料集，可從 plugin marketplace 重裝）

### 3.2 settings.json hook path 改 `$CLAUDE_PROJECT_DIR`（B2）

**動機**：Mac path 變 `/Users/roy422/...`，寫死無法跨平台。

**變更**：`.claude/settings.json` 4 條 hook。

現況：
```json
"command": "bash /home/roy422/newLife/elder_and_dog/scripts/hooks/pre_tool_safety.sh"
```

改為（保留 `bash` 前綴 + 路徑加雙引號避免空白炸開 + executable bit 不必要）：
```json
"command": "bash \"$CLAUDE_PROJECT_DIR/scripts/hooks/pre_tool_safety.sh\""
```

4 條都這樣改：`pre_tool_safety.sh` / `pre_tool_secret_guard.sh` / `post_tool_py_syntax.sh` / `stop_remind_build.sh`。

**驗證**：WSL 端 reload Claude Code session，確認 `echo $CLAUDE_PROJECT_DIR` 在 hook 內展開正確（用 `set -x` 加 debug 或臨時 `echo` 到 `/tmp/hook.log`）。若不通則 fallback：把 hook 寫進 `settings.local.json`（在 .gitignore 內）每台機器各自設絕對路徑。

### 3.3 Critical 寫死路徑修正（B3）

**3.3.1 `scripts/hooks/post_tool_py_syntax.sh:11`**

實際變數名是 `REPO_ROOT`（不是 PROJECT_ROOT），且下游 `FRONTEND_DIR="${REPO_ROOT}/pawai-studio/frontend"` 依賴它。要改的是 `REPO_ROOT` 本身，不是新增變數：

```diff
-REPO_ROOT="/home/roy422/newLife/elder_and_dog"
+REPO_ROOT="${PAWAI_REPO_ROOT:-${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}}"
 FRONTEND_DIR="${REPO_ROOT}/pawai-studio/frontend"
```

三層 fallback：
1. `$PAWAI_REPO_ROOT`（最高優先，給特殊環境逃生用）
2. `$CLAUDE_PROJECT_DIR`（Claude Code session 內標準路徑）
3. `git rev-parse --show-toplevel`（非 Claude 環境也能跑）
4. `pwd`（最後保底）

**3.3.2 `.claude/skills/jetson-verify/scripts/transport.py:27-28`**

```diff
 def remote_command(remote_cmd: str) -> list[str]:
-    return ["ssh", "jetson-nano", remote_cmd]
+    host = os.getenv("JETSON_HOST", "jetson-nano")
+    return ["ssh", host, remote_cmd]
 
 def remote_repo() -> str:
-    return "/home/jetson/elder_and_dog"
+    return os.getenv("JETSON_REPO", "/home/jetson/elder_and_dog")
```

需 `import os` 確認在檔頭。

**驗證**：在 WSL 用預設 env 跑 `pawai-verify`，確認行為不變。

### 3.4 Memory 私有 repo（B4）

**動機**：memory/ 內含個人筆記（user_career_*）+ 大量專案 context，要跨機器同步但不能公開。

**操作流程**：

```bash
# 在 GitHub UI 建 private repo: roy4222/pawai-claude-memory
# 不加 README / .gitignore，純空 repo

# WSL 端初始化
cd ~/.claude/projects/-home-roy422-newLife-elder-and-dog/memory/
git init
git remote add origin git@github.com:roy4222/pawai-claude-memory.git
git add .
git commit -m "init: WSL freeze before Mac migration (2026-05-12)"
git branch -M main
git push -u origin main
```

**Mac 端 setup**（寫進 runbook）：

Claude Code 的 project memory 目錄名稱跟 repo 實際 cwd path 強綁，是把絕對路徑用 `-` 編碼。所以**不要硬押目錄名**（例如 `-Users-roy422-newLife-elder-and-dog`），實際命名取決於你在 Mac 上 clone elder_and_dog 到哪。

正確流程：

```bash
# 1. Mac 端先 clone 主 repo（位置自選，例如 ~/newLife/elder_and_dog）
mkdir -p ~/newLife && cd ~/newLife
git clone git@github.com:roy4222/elder_and_dog.git
cd elder_and_dog

# 2. 用 Claude Code 開一次這個 repo，讓它自動建好 memory 目錄
claude  # 啟動 Claude Code session 然後 /exit

# 3. 找出 Claude Code 實際建的目錄名
ls ~/.claude/projects/ | grep -i elder_and_dog
# 例如可能會看到：-Users-roy422-newLife-elder-and-dog
#                  或 -Users-roy422-Documents-newLife-elder-and-dog（看你 clone 在哪）

# 4. 把 memory repo clone / rsync 進那個目錄
cd ~/.claude/projects/<實際目錄名>/
git clone git@github.com:roy4222/pawai-claude-memory.git memory
```

**維護紀律**：memory/ 內變動需定期 `git push`（建議：每天收工前 + 每次大決策後）。Mac / WSL 兩端要保持同步，否則會 diverge。

### 3.5 Mac setup runbook（B5）

**新檔**：`docs/runbook/mac-migration-setup.md`

**章節結構**：
1. **前置**：Homebrew + git + gh + Tailscale + Claude Code CLI + tmux（可選）+ Node/pnpm（給 Studio 前端用）
   - ★ **不裝 ROS2**：ROS2 runtime 留在 Jetson 上跑，Mac 只是 dev / SSH 入口。試圖在 macOS 裝 Humble 是死路。
   - 如果真的想 Mac 跑 ROS2 node（測試用），用 Docker（osrf/ros:humble-desktop）而非 native install
2. **Clone**：兩個 repo（main + memory，memory 流程見 §3.4）
3. **Env 設定**：`.env.local` 範例（OPENROUTER_KEY、JETSON_HOST、ROBOT_IP、PAWAI_LLM_MODEL、TTS_PROVIDER）
4. **SSH key 上 Jetson**：`ssh-copy-id $JETSON_HOST` + Tailscale 確認 reachable
5. **第一次驗證**：透過 SSH 在 Jetson 端跑 `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`，Mac 端只是觸發 + 看 log
6. **斷網 fallback 三個 case**（見 §4）
7. **Troubleshooting**：
   - Claude Code memory 目錄編碼（依 cwd path 不同名）
   - macOS 沒 ALSA / CoreAudio 差異（Mac 不直接播音訊，全交給 Go2 Megaphone）
   - tmux 版本差異（brew 裝的是 3.x，Jetson 是 3.x，相容）
   - SSH ControlMaster 設定（multiplex 加速 jetson-verify）

---

## 4. 斷網 Fallback 三個 case（runbook §6）

### Case A：全雲（normal）
```bash
# .env.local
export OPENROUTER_KEY="sk-or-v1-..."
export PAWAI_LLM_MODEL="openai/gpt-5.4-mini"
export TTS_PROVIDER="openrouter_gemini"  # quality lane
# ASR_PROVIDER_ORDER 預設含 qwen_cloud，需要 SSH tunnel 到 RTX 8000
ssh -f -N -L 8001:localhost:8001 user@rtx-server
```
延遲 P50 ~5-8s。Demo 預設場景。

### Case B：雲 LLM 掉但 ASR/TTS 還在
```bash
# 場景：OpenRouter 出問題，但 RTX 8000 SSH tunnel 還在、Edge TTS 還能用

# 步驟 0：先查實際在用的 key 變數名稱（可能有 alias）
grep -E 'OPENROUTER|OPENAI|ANTHROPIC' .env .env.local 2>/dev/null

# 步驟 1：unset 所有 alias，避免漏掉
unset OPENROUTER_KEY OPENROUTER_API_KEY OPENAI_API_KEY
# 同時把 .env 內的 key 改成空字串或 comment 掉，否則 source 後又會回來

# 步驟 2：TTS 改 edge_tts（純文字模型，不需要 OpenRouter）
export TTS_PROVIDER="edge_tts"

# 步驟 3：ASR 不動，仍走 qwen_cloud（不依賴 OpenRouter）
# LLM 會 fallback 到 vLLM tunnel → Ollama → RuleBrain
```
延遲增加 ~1-3s。功能堪用，audio tag 失效（emotion 沒了）。

**陷阱**：如果 `.env` 還在 shell rc 自動 source，重啟 terminal 後 key 又回來。建議直接編輯 `.env` 把 key 那行 comment 掉。

### Case C：全離線
```bash
# 場景：Demo 現場沒 Wi-Fi
unset OPENROUTER_KEY
export TTS_PROVIDER="piper"
export PIPER_MODEL_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
export PIPER_CONFIG_PATH="/home/jetson/models/piper/zh_CN-huayan-medium.onnx.json"
export ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'  # 跳過 qwen_cloud
# 殺掉 SSH tunnel（如果還在）
pkill -f "ssh.*8001:localhost"
pkill -f "ssh.*8000:localhost"
# LLM 會打不到 OpenRouter / vLLM tunnel → Ollama → RuleBrain
# RuleBrain 只能 12 字 canned reply（greet/stop/sit/stand/status）
```
延遲 P50 ~3-5s（無雲端往返）。對話品質掉到 template 等級，但 perception / motion / fallen alert 全部正常。

---

## 5. 不在範圍內的後續工作（post-demo）

下列各自開單獨 spec，不在這份 PR：

| Sub-project | 描述 | 預估 |
|-------------|------|:----:|
| **OFFLINE_MODE one-shot** | 一個 env 變數 + wrapper script 自動切 Case C | 0.5 天 |
| **PawAI Cobra CLI** | `pawai demo start/stop/status/healthcheck` Go CLI, wrap tmux | 2-3 天 |
| **YAML path env-ization** | face/speech/object yaml 全用 `${MODEL_ROOT}` 變數，跨平台共用同份 yaml | 1 天 |
| **systemd SSH tunnel** | RTX 8000 tunnel 寫成 systemd unit，斷線自動重連 | 0.5 天 |

---

## 6. 驗收標準

### 6.1 在 WSL 端（pre-migration verify）
- [ ] `.gitignore` 變更 commit 後，`git status` 看到 3 個新 skill 進 staging
- [ ] `settings.json` 改 `$CLAUDE_PROJECT_DIR` 後，reload Claude Code、隨意 Edit 一個 .py，確認 `post_tool_py_syntax.sh` hook 仍跑
- [ ] `post_tool_py_syntax.sh` 改 `git rev-parse` 後，手動執行測試正常
- [ ] `transport.py` 改 env 化後，跑 `pawai-verify` 行為不變
- [ ] Memory repo push 成功，從另一個目錄 clone 下來內容一致

### 6.2 在 Mac 端（migration day verify）
- [ ] `git clone` 主 repo + memory repo，目錄結構正確
- [ ] Claude Code 開 session，hooks 觸發（看 hook log）
- [ ] 4 個追蹤的 skill + 3 個新 skill 全部 list 出來
- [ ] `bash .claude/skills/brain-studio-lane/scripts/start.sh demo` 能跑通 Case A（全雲，需 OpenRouter key + Jetson SSH）
- [ ] Case B、Case C 至少各跑一次 smoke test

---

## 7. Out-of-Scope（避免 scope creep）

- ❌ 不重構任何 perception / brain / speech 程式碼
- ❌ 不改 contract schema
- ❌ 不改 ROS topic 名
- ❌ 不動 Jetson 上的 model files 與其路徑（YAML hardcode `/home/jetson/` 是 by design）
- ❌ 不寫一鍵離線切換腳本
- ❌ 不建 Go CLI

---

## 8. 風險與緩解

| 風險 | 機率 | 影響 | 緩解 |
|------|:----:|:----:|------|
| `$CLAUDE_PROJECT_DIR` 在某些 Claude Code 版本不支援 | 低 | 中 | WSL 端 reload session 驗證；不行 fallback 到 settings.local.json overlay |
| Memory private repo SSH key 未上 Mac → clone 失敗 | 中 | 低 | runbook 第一步先 `ssh -T git@github.com` 驗證 |
| Mac 端誤以為要裝 ROS2 native | 高 | 低 | runbook §1 明寫「不裝 ROS2，runtime 在 Jetson」；想本機跑 node 用 Docker |
| Demo 當天 Mac 突發問題 | 低 | 高 | WSL 機器作為 fallback 帶到現場，不立即下架 |

---

## 9. 引用 / 索引

- `docs/pawai-brain/architecture/0511/` — 六大模組架構快照（reference for what we're preserving）
- `.gitignore` — skills whitelist 現況
- `.claude/settings.json` — hook 配置
- Claude Code `$CLAUDE_PROJECT_DIR` 環境變數：Claude Code 啟動 session 時自動帶入當前 project root（用 `claude` CLI 啟動的目錄）。實作前先用 `echo $CLAUDE_PROJECT_DIR` 驗證在 WSL session 內可讀；若不通則退到 B 方案（settings.local.json overlay 各機器自己寫）
