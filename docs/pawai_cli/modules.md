# PawAI CLI 模組對照表

CLI 內建 8 個 module，跟 ROS2 package、log target、test 命令對應。
來源：[`tools/pawai_cli/pawai_cli/modules.py`](../../tools/pawai_cli/pawai_cli/modules.py)。

> 隨時跑 `pawai dev info <module>` 拿即時資訊。

---

## 速查表

| Module | 中文 | ROS Packages | Demo Log Targets | Go2 控制 |
|--------|------|--------------|------------------|---------|
| `face` | 人臉辨識 | `face_perception` | `demo:face` | 無 |
| `speech` | 語音 | `speech_processor` | `demo:asr`、`demo:tts` | 透過 Megaphone TTS |
| `gesture` | 手勢辨識 | `vision_perception` | `demo:vision` | 透過互動 skill 間接 |
| `pose` | 姿勢辨識 | `vision_perception` | `demo:vision` | `fallen_alert` 可停 Go2 |
| `object` | 物體辨識 | `object_perception` | `demo:object` | 無 |
| `nav` | 導航避障 | `go2_robot_sdk` | `demo:go2`、`nav-cap-demo:nav_action`、`reactive-stop:reactive` | 直接動作 |
| `brain` | PawAI Brain | `pawai_brain`、`interaction_executive` | `demo:llm`、`demo:executive`、`pawai_brain:conv_graph` | 透過 `interaction_executive` |
| `studio` | Studio 前端/Gateway | （無 ROS package） | `local:/tmp/studio_frontend.log`、`demo:gateway` | 無 |

### 別名

| 你打 | 實際解析 |
|------|---------|
| `vision` | `gesture` |
| `object-perception` | `object` |
| `speech-processor` | `speech` |
| `pawai-brain` | `brain` |

---

## 詳細資訊

### face — 人臉辨識

- **Package**：`face_perception`
- **Doc**：[`docs/pawai-brain/architecture/0511/face.md`](../pawai-brain/architecture/0511/face.md)
- **Tests**：`python3 -m pytest face_perception/test -v`
- **Log**：`demo:face`
- **備註**：YuNet 偵測 + SFace 識別 + face_db 同步

```bash
pawai dev info face
pawai jetson deploy --module face
pawai logs face
```

---

### speech — 語音

- **Package**：`speech_processor`
- **Doc**：[`docs/pawai-brain/architecture/0511/speech.md`](../pawai-brain/architecture/0511/speech.md)
- **Tests**：`python3 -m pytest speech_processor/test -v`
- **Logs**：`demo:asr`、`demo:tts`
- **Go2**：TTS 透過 Megaphone DataChannel (api_id 4001/4003/4002)
- **備註**：ASR provider chain（cloud → local fallback）+ TTS fallback chain

```bash
pawai dev info speech
pawai logs speech --lines 300  # 抓 asr + tts pane
```

---

### gesture — 手勢辨識

- **Package**：`vision_perception`（與 pose 共用）
- **Doc**：[`docs/pawai-brain/architecture/0511/gesture.md`](../pawai-brain/architecture/0511/gesture.md)
- **Tests**：`python3 -m pytest vision_perception/test -v -k gesture`
- **Log**：`demo:vision`
- **Go2**：透過 interaction skill 間接（thumbs_up → wiggle 等）
- **備註**：與 pose 共享 `vision_perception` package 和 perception cache

---

### pose — 姿勢辨識

- **Package**：`vision_perception`（與 gesture 共用）
- **Doc**：[`docs/pawai-brain/architecture/0511/pose.md`](../pawai-brain/architecture/0511/pose.md)
- **Tests**：`python3 -m pytest vision_perception/test -v -k pose`
- **Log**：`demo:vision`
- **Go2**：`fallen_alert` 觸發 stop（demo 預設關閉 fallen，需 `enable_fallen:=true`）
- **備註**：跟 gesture 共 launch + perception cache

---

### object — 物體辨識

- **Package**：`object_perception`
- **Doc**：[`docs/pawai-brain/architecture/0511/object.md`](../pawai-brain/architecture/0511/object.md)
- **Tests**：`python3 -m pytest object_perception/test -v`
- **Log**：`demo:object`
- **Go2**：無
- **備註**：YOLO26n + HSV color path；brain 訂閱 `/event/object_detected` 注入 LLM prompt

---

### nav — 導航避障

- **Package**：`go2_robot_sdk`（含 nav2/AMCL/cartographer launch）
- **Docs**：
  - [`.claude/skills/nav-avoidance-lane/SKILL.md`](../../.claude/skills/nav-avoidance-lane/SKILL.md)
  - [`docs/navigation/CLAUDE.md`](../navigation/CLAUDE.md)
- **Tests**：`python3 -m pytest go2_robot_sdk/test -v`
- **Logs**：`demo:go2`、`nav-cap-demo:nav_action`、`reactive-stop:reactive`
- **Go2**：直接動作（cmd_vel → WebRTC）
- **備註**：架構文件尚未集中，目前用 lane reference

> Demo mode 預設不啟動 nav stack；要跑導航避障獨立用 `bash scripts/start_nav_capability_demo_tmux.sh`，
> 詳見 [nav-avoidance-lane skill](../../.claude/skills/nav-avoidance-lane/SKILL.md)。

---

### brain — PawAI Brain

- **Packages**：`pawai_brain`、`interaction_executive`
- **Doc**：[`docs/pawai-brain/architecture/0511/brain.md`](../pawai-brain/architecture/0511/brain.md)
- **Tests**：
  - `python3 -m pytest pawai_brain/test -v`
  - `python3 -m pytest interaction_executive/test -v`
- **Logs**：`demo:llm`、`demo:executive`、`pawai_brain:conv_graph`
- **Go2**：透過 `interaction_executive` 發 skill → Go2 driver
- **備註**：LangGraph + skill policy + trace observability

```bash
pawai dev info brain
pawai jetson deploy --module brain  # build pawai_brain + interaction_executive
pawai logs brain --lines 500
```

---

### studio — Studio 前端 / Gateway

- **Package**：無（非 ROS package）
- **Docs**：
  - [`.claude/skills/brain-studio-lane/SKILL.md`](../../.claude/skills/brain-studio-lane/SKILL.md)
  - [`.claude/skills/brain-studio-lane/references/runtime-topology.md`](../../.claude/skills/brain-studio-lane/references/runtime-topology.md)
  - `pawai-studio/docs/`
- **Tests**：`cd pawai-studio/frontend && npm run lint`
- **Logs**：
  - `local:/tmp/studio_frontend.log`（本機 next dev）
  - `demo:gateway`（Jetson 上的 WS gateway）
- **Go2**：無
- **備註**：包含 frontend (Next.js) / backend (FastAPI) / gateway (Python WebSocket bridge)

> `pawai demo start` 預設會啟動 Studio overlay（gateway + 本機 frontend）。
> 要跳過：`pawai demo start --no-studio`。

---

## 模組改動 → 該做什麼

| 改的東西 | 該跑什麼 |
|---------|---------|
| Python 程式碼 | `pawai jetson deploy --module <mod>`（增量 build 很快） |
| ROS msg / launch / config | deploy 後要 `pawai demo stop && demo start` 才生效 |
| Frontend `.tsx` / `.ts` | Next dev hot reload，存檔即生效，不用 deploy |
| Frontend `package.json` | `cd pawai-studio/frontend && npm install` |
| Persona / prompt（`pawai_brain/personas/v1/*.md`） | deploy brain（會 colcon install 進 share/） |
| 多模組 | `pawai jetson deploy --all`（全 build） |

---

## 加新 module

編輯 [`tools/pawai_cli/pawai_cli/modules.py`](../../tools/pawai_cli/pawai_cli/modules.py)：

```python
"newmod": ModuleInfo(
    key="newmod",
    title="New Module",
    packages=("new_package",),
    docs=("docs/.../new.md",),
    tests=("python3 -m pytest new_package/test -v",),
    logs=("demo:newmod",),
    go2_access="none",
    notes=("description",),
),
```

重新安裝：

```bash
uv pip install -e tools/pawai_cli
pawai dev info newmod    # 驗證
```
