# jetson-verify Skill Design

> Status: APPROVED
> Date: 2026-03-20
> Scope: v0 — smoke profile only

## 1. Problem

PawAI 的驗證邏輯散落在 6+ 個腳本中：`e2e_health_check.sh`（5 層診斷）、`nav_memory_guard.sh`（記憶體）、`go2_ros_preflight.sh`（ROS2 預檢）、`smoke_test_e2e.sh`（語音 smoke）、以及各啟動腳本的 preflight 檢查。

問題：
- 沒有統一入口：每次要驗不同東西得記住跑哪個腳本
- 沒有 Jetson 硬體檢查：GPU 溫度/記憶體/磁碟都沒有預檢
- 沒有結構化輸出：無法被其他 skill 或自動化程式化消費
- 檢查邏輯重複且不一致：Piper 模型路徑檢查散見 3 個腳本

## 2. Solution

建立 `jetson-verify` skill：一個 YAML-driven 的驗證框架，用 Python executor 在 Jetson 上執行 checks，輸出結構化 JSON + terminal 摘要。

### 2.1 Versioning Strategy

| Version | Profile | 內容 |
|---------|---------|------|
| v0（本次） | `smoke` | system + ROS2 基礎 + 活著的模組存活檢查 |
| v1 | `integration` | 多模組共存、資源預算、前置條件 |
| v2 | `demo` | 接近展示標準的完整 checklist，go/no-go 報告 |

v1/v2 先以空檔 + TODO header 預留，`verify.py` 明確拒絕執行空 profile。

## 3. File Structure

```
.claude/skills/jetson-verify/
├── SKILL.md                    # 觸發條件、使用方式、結果解讀
├── scripts/
│   ├── verify.py               # 主 executor (~150 行)
│   └── transport.py            # target execution 抽象 (~60 行)
├── profiles/
│   ├── smoke.yaml              # v0 實作
│   ├── integration.yaml        # v1 預留 (TODO header)
│   └── demo.yaml               # v2 預留 (TODO header)
└── references/
    └── gotchas.md              # 踩坑紀錄

# 結果輸出（專案內穩定路徑）
logs/jetson-verify/
├── verify_YYYYMMDD_HHMMSS.json
└── latest.json                 # symlink → 最近一次結果
```

### 3.1 職責分工

| 檔案 | 職責 | 不做什麼 |
|------|------|---------|
| `SKILL.md` | 觸發條件、使用方式、結果解讀指引 | 不含邏輯 |
| `verify.py` | 讀 YAML → 偵測環境 → 呼叫 transport → 收集結果 → 輸出 | 不硬編碼 checks |
| `transport.py` | 命令怎麼送到 Jetson | 不知道要送什麼 |
| `smoke.yaml` | 檢查什麼 | 不知道怎麼執行 |

## 4. transport.py — Target Execution 抽象

### 4.1 Public Interface

```python
def detect_target_env() -> str:
    """Return 'local_jetson' or 'remote_jetson'.
    判斷邏輯：/etc/nv_tegra_release 存在 → local_jetson，否則 → remote_jetson。"""

def build_target_command(cmd: str, env: str) -> list[str]:
    """Return argv list for subprocess.run().
    local_jetson:  ["bash", "-lc", cmd]
    remote_jetson: ["ssh", "jetson-nano",
                    f"cd /home/jetson/elder_and_dog && bash -lc {shlex.quote(cmd)}"]
    """

def exec_on_target(cmd: str, env: str, timeout_sec: int = 10) -> tuple[int, str, str]:
    """Execute command on target, return (returncode, stdout, stderr).
    returncode:
      0+  = 正常（命令本身的 exit code）
      -1  = transport failure（SSH 連不上、launch 失敗）
      -2  = timeout（超過 timeout_sec）
    """
```

### 4.2 Design Principles

- **Stateless**：每次呼叫獨立，不做 SSH connection pooling
- **不隱式 source ROS2**：check command 自己負責環境（例如 `source /opt/ros/humble/setup.bash && ...`）
- **argv-based**：`build_target_command()` 回傳 `list[str]`，用 `shlex.quote()` 處理 escaping
- **Transport failure vs timeout 嚴格區分**：`-1` vs `-2`，讓 verify.py 能準確報 FAIL vs ERROR
- **可獨立 import**：後續 `jetson-deploy`、`go2-debug` 直接 `from transport import exec_on_target`

## 5. smoke.yaml — Check Definition Format

### 5.1 YAML Schema (v0)

```yaml
profile: smoke
description: "部署後基本健康檢查：system → ROS2 → modules"
min_checks: 1

checks:
  - id: <string>                # 唯一 ID，格式 group.name
    command: <string>           # 在 target shell 中執行的命令
    expect: <string>            # 預期結果（見 5.2）
    blocking: <bool>            # true = 失敗觸發 FAIL，false = 失敗觸發 WARN
    timeout_sec: <int>          # 命令 timeout（秒）
    message_template: <string>  # 人可讀訊息，{value} 代入 stdout
    precondition: <string>      # (optional) 前置條件命令，失敗 → SKIP
```

每個 check 至少要有：`id`, `command`, `expect`, `blocking`, `timeout_sec`, `message_template`。

### 5.2 Expect Parser（v0 限定）

| 運算子 | 範例 | 語意 |
|--------|------|------|
| `>= N` | `>= 800` | stdout 轉 int/float，>= N |
| `<= N` | `<= 75` | stdout 轉 int/float，<= N |
| `== N` | `== 1` | 精確數值比對 |
| `contains TEXT` | `contains running` | stdout 包含子字串 |
| `nonempty` | — | stdout strip 後非空 |

型別轉換失敗（stdout 不是數字但 expect 是數值比較）→ `ERROR`，不是 `FAIL`。

### 5.2.1 `value` 欄位規則

- `PASS` / `WARN` / `FAIL`：`value` = stdout.strip()（字串）
- `SKIP`：`value` = `null`（未執行 command）
- `ERROR`：`value` = `null`（結果不可信）

### 5.3 Precondition 規則

- `precondition` 命令 returncode == 0 → 執行 check
- `precondition` 命令 returncode == 1 → `SKIP`（條件不成立，如 `grep -q` 沒匹配）
- `precondition` 命令 returncode > 1 → `ERROR`（命令本身出錯，如 command not found = 127）
- `precondition` 命令 transport/timeout 失敗（rc -1/-2）→ `ERROR`
- **System / ROS2 基礎 checks 禁止有 precondition**
- **只有 module-level checks 可以 SKIP**

### 5.3.1 `min_checks` 語意

`min_checks` 指 YAML 中定義的 check 數量（靜態驗證），不是 runtime 實際執行（非 SKIP）的數量。用於攔截空 profile 和 stub profile，不用於 runtime 計數。

### 5.4 Check Status 定義

| Status | 觸發條件 | 計入 overall |
|--------|---------|-------------|
| `PASS` | expect 通過 | 是（正面） |
| `WARN` | expect 未通過 + `blocking: false` | 否 |
| `FAIL` | expect 未通過 + `blocking: true` | 是（阻擋） |
| `SKIP` | precondition 未通過 | 否（獨立統計） |
| `ERROR` | transport failure / timeout / parse failure | 是（阻擋） |

### 5.5 v0 Smoke Checks

**Group 1 — System（blocking 除溫度）**

```yaml
checks:
  - id: system.memory
    command: "awk '/MemAvailable:/ {print int($2/1024)}' /proc/meminfo"
    expect: ">= 800"
    blocking: true
    timeout_sec: 5
    message_template: "{value}MB available (min 800MB)"

  - id: system.disk
    command: "df --output=avail /home | tail -1 | awk '{print int($1/1024)}'"
    expect: ">= 500"
    blocking: true
    timeout_sec: 5
    message_template: "{value}MB free on /home (min 500MB)"

  - id: system.gpu_temp
    command: "cat /sys/devices/virtual/thermal/thermal_zone1/temp 2>/dev/null | awk '{print int($1/1000)}'"
    expect: "<= 75"
    blocking: false
    timeout_sec: 5
    message_template: "GPU {value}°C (warn >75°C)"
```

**Group 2 — ROS2 基礎（全 blocking）**

```yaml
  - id: ros2.daemon
    command: "source /opt/ros/humble/setup.bash && ros2 daemon status 2>&1 | grep -c 'is running' || true"
    expect: ">= 1"
    blocking: true
    timeout_sec: 10
    message_template: "ROS2 daemon running"

  - id: ros2.topic_count
    command: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic list 2>/dev/null | wc -l"
    expect: ">= 1"
    blocking: true
    timeout_sec: 15
    message_template: "{value} topics discovered"
```

**Group 3 — Module checks（with precondition）**

```yaml
  - id: module.face.state_publishing
    precondition: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list 2>/dev/null | grep -q face_identity_node"
    command: "source /opt/ros/humble/setup.bash && source install/setup.bash && timeout 3 ros2 topic echo --once /state/perception/face 2>/dev/null"
    expect: "nonempty"
    blocking: false
    timeout_sec: 5
    message_template: "face state topic producing data"

  - id: module.speech.state_publishing
    precondition: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list 2>/dev/null | grep -q stt_intent_node"
    command: "source /opt/ros/humble/setup.bash && source install/setup.bash && timeout 3 ros2 topic echo --once /state/interaction/speech 2>/dev/null"
    expect: "nonempty"
    blocking: false
    timeout_sec: 5
    message_template: "speech state topic producing data"

  - id: module.vision.node_alive
    precondition: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list 2>/dev/null | grep -q vision_perception_node"
    command: "source /opt/ros/humble/setup.bash && source install/setup.bash && timeout 8 ros2 topic hz /vision_perception/debug_image --window 3 2>&1 | head -1"
    expect: "nonempty"
    blocking: false
    timeout_sec: 12
    message_template: "vision debug_image: {value}"

  - id: module.go2.webrtc_subscriber
    precondition: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 node list 2>/dev/null | grep -q go2_driver_node"
    command: "source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic info /webrtc_req 2>/dev/null | awk '/Subscription count:/ {print $NF}'"
    expect: ">= 1"
    blocking: false
    timeout_sec: 10
    message_template: "webrtc_req has {value} subscriber(s)"
```

## 6. verify.py — Main Executor

### 6.1 Execution Flow

```
CLI: python3 verify.py --profile smoke [--output-dir logs/jetson-verify/]
  │
  ├─ 1. Parse args
  │
  ├─ 2. Load profile YAML
  │    ├─ 檔案不存在 → exit 2
  │    ├─ checks 為空 or < min_checks → exit 2 ("empty/stub profile")
  │    └─ YAML parse error → exit 2
  │
  ├─ 3. detect_target_env()
  │    ├─ remote_jetson → test SSH: exec_on_target("echo ok", timeout=5)
  │    │    └─ 失敗 → exit 2 ("cannot reach jetson-nano")
  │    └─ local_jetson → continue
  │
  ├─ 4. Execute checks (YAML order = execution order)
  │    for each check:
  │      a. precondition? → exec → rc==0: continue, rc==1: SKIP, rc>1: ERROR
  │      b. exec_on_target(command, timeout_sec)
  │         ├─ returncode -1  → ERROR (transport)
  │         ├─ returncode -2  → ERROR (timeout)
  │         ├─ returncode > 0 → ERROR (command failed)
  │         └─ returncode == 0 → parse stdout with expect
  │      c. evaluate expect:
  │         ├─ pass → PASS
  │         ├─ fail + blocking → FAIL
  │         └─ fail + !blocking → WARN
  │         parse error → ERROR
  │      d. record {id, status, blocking, value, message, duration_ms}
  │
  ├─ 5. Compute overall (priority: ERROR > blocking FAIL > PASS)
  │    ├─ any ERROR → overall = "ERROR", exit 2
  │    ├─ any blocking FAIL → overall = "FAIL", exit 1
  │    └─ otherwise → overall = "PASS", exit 0
  │
  └─ 6. Output
       ├─ stdout: JSON (once, complete)
       ├─ stderr: human-readable summary
       └─ file: JSON → logs/jetson-verify/verify_{timestamp}.json
                      + update latest.json symlink
```

### 6.2 Design Decisions

- **不做 early exit**：即使 system check FAIL 也跑完所有 checks，給完整圖景
- **stdout 只有 JSON**：一次，完整，不混其他輸出
- **stderr 是人類摘要**：`[PASS]`/`[WARN]`/`[FAIL]`/`[SKIP]`/`[ERROR]` 逐行 + summary
- **check 執行順序 = YAML 定義順序**：system → ROS2 → modules（by convention）
- **rc==0 才進 expect parser**：主 command 的 returncode > 0 直接判 ERROR。這要求 check commands 在「無資料但命令成功」的情境下仍回傳 rc=0 — 對 `grep -c` 等可能回非零的命令，需尾綴 `|| true` 強制 rc=0，讓 expect parser 根據 stdout 值判斷 PASS/FAIL。

### 6.3 JSON Output Schema

```json
{
  "profile": "smoke",
  "target": "remote_jetson",
  "timestamp": "2026-03-20T14:30:00+08:00",
  "overall": "PASS",
  "exit_code": 0,
  "duration_ms": 4520,
  "summary": {
    "pass": 5,
    "warn": 1,
    "fail": 0,
    "skip": 3,
    "error": 0
  },
  "checks": [
    {
      "id": "system.memory",
      "status": "PASS",
      "blocking": true,
      "value": "2400",
      "message": "2400MB available (min 800MB)",
      "duration_ms": 312
    },
    {
      "id": "module.face.state_publishing",
      "status": "SKIP",
      "blocking": false,
      "value": null,
      "message": "precondition not met: face_identity_node not running",
      "duration_ms": 0
    }
  ]
}
```

### 6.4 Terminal Summary Format (stderr)

```
jetson-verify | profile=smoke | target=remote_jetson
──────────────────────────────────────────────
[PASS] system.memory — 2400MB available (min 800MB)  (312ms)
[PASS] system.disk — 42000MB free on /home (min 500MB)  (280ms)
[WARN] system.gpu_temp — GPU 78°C (warn >75°C)  (150ms)
[PASS] ros2.daemon — ROS2 daemon running  (1200ms)
[PASS] ros2.topic_count — 23 topics discovered  (2100ms)
[SKIP] module.face.state_publishing — precondition not met
[SKIP] module.speech.state_publishing — precondition not met
[SKIP] module.vision.node_alive — precondition not met
[PASS] module.go2.webrtc_subscriber — webrtc_req has 1 subscriber(s)  (800ms)
──────────────────────────────────────────────
PASS=5  WARN=1  FAIL=0  SKIP=3  ERROR=0
Overall: PASS (4520ms)
```

## 7. SKILL.md

```markdown
---
name: jetson-verify
description: >
  Jetson 部署驗證工具。部署後跑 smoke test、整合前做 pre-flight check、
  Demo 前產出 go/no-go 報告。觸發詞："verify"、"驗證"、"健檢"、
  "smoke test"、"check jetson"、"jetson 狀態"、"/verify"。
  在 colcon build 成功後、WSL→Jetson sync 完成後、或使用者說
  「驗證」「smoke」「健檢」「ready」時應主動建議執行。
  不要在純聊天、文件摘要、或不需實際執行檢查時觸發。
---

# jetson-verify

## 用途

部署後一鍵驗證 Jetson 環境健康。自動偵測執行環境
（Jetson 本機 = local_jetson，WSL = remote_jetson），
跑完所有 checks 後輸出結構化 JSON + terminal 摘要。

## 使用方式

在 repo root 執行：

    python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke

## 參數

- `--profile`: smoke（v0）| integration（v1 預留）| demo（v2 預留）
- `--output-dir`: 預設 logs/jetson-verify/

## 輸出約定

- `stdout`: 完整 JSON（一次，machine-readable）
- `stderr`: 人類摘要（逐行 check + summary）
- `file`: 同一份 JSON 落盤到 output-dir，含 latest.json symlink

## 結果解讀

- overall=PASS, exit 0 → 可以繼續開發/測試
- overall=FAIL, exit 1 → 有 blocking check 失敗，修完再跑
- overall=ERROR, exit 2 → 驗證本身不可信（SSH、timeout、config 問題）
- SKIP → 模組沒啟動，不計分
- WARN → 非 blocking 未通過，留意但不阻擋

## 新增 check

編輯 profiles/<profile>.yaml，加一條 check entry。
每個 check 至少需要：id, command, expect, blocking, timeout_sec, message_template。
系統/ROS2 基礎 check 禁止加 precondition。
只有 module-level check 可以用 precondition 做 SKIP。

## Gotchas

見 references/gotchas.md（隨使用持續累積）。
```

## 8. Known Gotchas (pre-populated for references/gotchas.md)

1. **check commands 一律用 `setup.bash`，不可用 `setup.zsh`**：transport.py 強制 `bash -lc`，在 bash shell 裡 source zsh script 會出錯。雖然 Jetson 日常用 zsh，但 verify 的 transport 走 bash。

2. **`system.gpu_temp` 的 thermal zone 路徑**：`thermal_zone1` 在 Jetson Orin Nano 上指向 GPU-therm，但不保證跨 Jetson 型號一致。換硬體時需要用 `cat /sys/class/thermal/thermal_zone*/type` 確認。

3. **`ros2 topic hz` 是永不退出的命令**：`module.vision.node_alive` 用 `timeout 8` 包在命令內部，讓它在 8s 後自行終止，避免 transport timeout (-2) 把它升級為 ERROR。`timeout_sec: 12` 比內部 timeout 寬裕，確保 transport 不會先殺掉命令。

4. **`detect_target_env()` 的假設**：非 Jetson 環境一律視為 `remote_jetson`，假設 SSH 到 jetson-nano 可用。這包含 WSL、macOS、CI container 等所有非 Jetson 平台。

5. **`grep -c` 和其他可能回非零的命令必須尾綴 `|| true`**：因為 `rc > 0` → ERROR，check commands 必須確保正常情境下 rc=0。`grep -c 'pattern' || true` 讓 grep 無匹配時回 rc=0 + stdout="0"，由 expect parser 判斷 PASS/FAIL。

6. **precondition 的 `grep -q` 不需要 `|| true`**：precondition 語意是 rc==0 → run，rc==1 → SKIP。`grep -q` 的 rc=1（無匹配）正好是「條件不成立」= SKIP，不需要強制 rc=0。

7. **v1 考慮加 `--dry-run` 參數**：載入 YAML 並印出 check 列表但不執行，方便開發和測試新 profile。

## 9. ralph-loop 安裝

與 jetson-verify 獨立，直接安裝第三方 plugin：

```bash
claude plugin install ralph-loop
```

安裝後可搭配 jetson-verify 使用：

```
/ralph-loop "完成 face + vision 整合測試。完成標準：
1. jetson-verify --profile smoke overall=PASS
2. face + vision 同時跑 5 分鐘不 crash
3. Foxglove 可看到 debug_image
完成後輸出 COMPLETE" --max-iterations 15 --completion-promise "COMPLETE"
```

## 10. Implementation Scope (v0)

### 要做

- `SKILL.md`
- `transport.py`（detect_target_env / build_target_command / exec_on_target）
- `verify.py`（YAML loader / expect parser / executor / JSON+summary output）
- `profiles/smoke.yaml`（9 checks: 3 system + 2 ROS2 + 4 module）
- `profiles/integration.yaml`（TODO stub）
- `profiles/demo.yaml`（TODO stub）
- `references/gotchas.md`（空檔 + header）
- `logs/jetson-verify/` 目錄（.gitkeep）
- 安裝 ralph-loop

### 不做

- integration/demo profile 實作
- SSH connection pooling
- 通用表達式語言（expect parser 只支援 5 個運算子）
- Web UI 或 Foxglove 整合
- CI pipeline 整合
- transport.py 的 config 化（SSH target 先硬編碼 jetson-nano）

## 11. Testing Strategy

- `transport.py`：在 WSL 上跑 unit test（mock subprocess），驗證 argv 組裝和 error handling
- `verify.py`：用假 YAML + mock transport 測 expect parser（5 個運算子各測邊界）、overall 計算邏輯、JSON 輸出格式
- `smoke.yaml`：在 Jetson 上手動跑一次 `python3 verify.py --profile smoke`，確認實際結果合理
- 空 profile 拒絕：嘗試 `--profile integration`，確認 exit 2 + 錯誤訊息
