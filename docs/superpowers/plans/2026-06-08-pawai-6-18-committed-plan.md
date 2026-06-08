# PawAI 6/18 Committed 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 6/18 committed 能力（導航短距自走+停障+stop-resume、視覺多類別+容錯切換+具名問候+手勢demo+Brain感知政策+Studio證據+效能）做到 DEMO_READY，bonus 不碰。

**Architecture:** 兩條軌。**Track A（WSL 可 code，TDD）**：物體 runtime callback、Brain 感知政策、手勢 demo mode、face CLI —— 純邏輯、可單元測、今天就能做完不需硬體。**Track B（Jetson+Go2 runbook）**：導航 4 票 + face 具名問候驗證 + 效能 —— HITL 場測，給精確指令 + pass/fail gate。**Track C（verify-only）**：Studio 證據已實作，跑測試確認即可。

**Tech Stack:** ROS2 Humble / rclpy、Python pytest、click(pawai_cli)、Nav2/AMCL、YOLO26n ONNX、MediaPipe、Next.js(Studio gateway)。

**執行順序（Roy 鎖定）：** 導航 `NAV-1→NAV-2→NAV-3`（NAV-4 committed-lite 不擋主線）；視覺 `BRAIN-1→VIS-1→VIS-2→VIS-3→VIS-4→VIS-5→VIS-7/VIS-8`。bonus（NAV-5/6/7、VIS-6 換模型/9/11）不碰。

**原則：** 先做 committed；committed-lite 不擋主線；bonus 不要先碰。正式導航主線 = 短距自走 + 安全停障 + stop-resume 保底（**不是** route 進場）。

---

## Part 0 — Recon 修正過的地面真相（執行者必讀）

| 主題 | 真相（file:line） | 對計畫的影響 |
|---|---|---|
| Brain 感知 choke point | `conversation_graph_node._on_object/gesture/pose`（:947-981）只快取；LangGraph 只由 speech/text 觸發。主動發言 choke point 在 `interaction_executive/brain_node.py` | BRAIN-1 / VIS-5 改 `brain_node.py` + `world_snapshot.py`，**不要**改 conversation_graph 觸發流 |
| 具名問候 | live emit 在 `interaction_executive/brain_node.py:1038-1064`（ENGAGED gate + 20s/name cooldown），conversation_graph 只存 `_recent_face_identity` | VIS-4 = 硬體 re-verify，BRAIN-1 face 規則=已存在 |
| object whitelist 過濾 | `object_perception_node.py:352` 讀 `self.allowed_classes`（mutable instance attr）；無 set_parameters_callback | VIS-2 加 callback 即時生效，CONFIRMED 可行 |
| object person 排除 + dedup | `world_snapshot.py:14`（`_OBJECT_EXCLUDE_CLASSES=("person",)`）+ :12（`_OBJECT_WINDOW_S=30.0`）+ class-dedup 已有 | BRAIN-1 object 規則 = 把 30→60s + 鎖既有行為，不是從零 |
| 手勢 thumbs_up→wiggle | `brain_node.py:670`（`_GESTURE_CONFIRM={"thumbs_up":"wiggle",...}`）→ :759-772 發 `say_canned "比 OK 我就做 {skill}"` | VIS-5 = demo mode 把 thumbs_up 移出 _GESTURE_CONFIRM（**不要**改成一步觸發 wiggle，Roy 要的是不引出 wiggle） |
| Studio 證據 | gateway 已訂 face/gesture/pose/object + 4 brain trace（`studio_gateway.py:72-83`）+ 3 video（`video_bridge.py:22-29`）+ 前端 panel 齊 | VIS-7 = verify-only |
| 家用 7 類 | Roy 鎖定 `[39,41,45,56,63,67,73]`（bottle/cup/bowl/chair/laptop/cell phone/book）。recon 的 `[0,16,39,41,56,60]` 是 yaml 舊註解，**作廢** | VIS-1 用 Roy 的清單，無 person（對齊 BRAIN-1 不講 person） |

---

# Part A — WSL Code（TDD，今天可做，不需硬體）

## Task 1: VIS-1 — class_whitelist 同步回 git（家用 7 類）

**Files:**
- Modify: `object_perception/config/object_perception.yaml:16-20`

- [ ] **Step 1: 改 yaml whitelist（exact replace）**

把現況：
```yaml
    # 5/27 demo video mode: 只認 cup (COCO #41)
    # YAML parser pitfall: [41] 會被推成 BYTE_ARRAY (CLAUDE.md 警告)
    # 加 dummy 999 (不存在 COCO class) 強制推成 INTEGER_ARRAY，999 被 filter 排除
    # 5/28+ 視需求擴回 P0 subset [0, 16, 39, 41, 56, 60]
    class_whitelist: [41, 999]
```
改成：
```yaml
    # 2026-06-08 VIS-1: 家用 7 類（Roy grill 鎖定）
    # bottle=39 cup=41 bowl=45 chair=56 laptop=63 cell phone=67 book=73
    # 皆 < 80、>1 個元素 → rclpy 正確推 INTEGER_ARRAY，不需 dummy 999
    # 不含 person(0)：BRAIN-1「物體不講 person」，人由 face 路徑處理
    # 現場容錯切換見 VIS-2（runtime callback）；全 80 類設 [-1]
    class_whitelist: [39, 41, 45, 56, 63, 67, 73]
```

- [ ] **Step 2: 驗證 contract / yaml 合法**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -c "import yaml; d=yaml.safe_load(open('object_perception/config/object_perception.yaml')); print(d)"`
Expected: 印出 dict，`class_whitelist` = `[39, 41, 45, 56, 63, 67, 73]`，無 exception。

- [ ] **Step 3: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add object_perception/config/object_perception.yaml
git commit -m "fix(object): VIS-1 sync class_whitelist to 家用7類 [39,41,45,56,63,67,73]"
```

---

## Task 2: VIS-2/VIS-3 — object runtime param callback（即時切換，免重啟）

**Files:**
- Modify: `object_perception/object_perception/object_perception_node.py:173-177`（抽成 helper）、`:221-233` 後（註冊 callback）、新增 `_parse_whitelist` module function + `_on_param_changed` method
- Test: `object_perception/test/test_object_perception.py`（新增 `TestParseWhitelist`）

設計：把現有 whitelist 解析抽成 module-level 純函式 `_parse_whitelist`，`__init__` 與新 callback 共用（DRY）。純函式 CI-safe（不需 ONNX/ROS spin）。

- [ ] **Step 1: 寫失敗測試**

在 `object_perception/test/test_object_perception.py` 末尾加：
```python
# ------------------------------------------------------------------
# VIS-2: runtime class_whitelist parsing (pure function, CI-safe)
# ------------------------------------------------------------------
from object_perception.object_perception_node import _parse_whitelist


class TestParseWhitelist:
    def test_household_seven(self):
        assert _parse_whitelist([39, 41, 45, 56, 63, 67, 73]) == {39, 41, 45, 56, 63, 67, 73}

    def test_filters_dummy_over_79(self):
        assert _parse_whitelist([41, 999]) == {41}

    def test_empty_defaults_to_all_80(self):
        out = _parse_whitelist([])
        assert out == set(COCO_CLASSES.keys())
        assert len(out) == 80

    def test_sentinel_neg1_defaults_to_all_80(self):
        # -1 不在 0..79 → 被過濾成空 → 回退全 80（sentinel 語意）
        assert _parse_whitelist([-1]) == set(COCO_CLASSES.keys())
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest object_perception/test/test_object_perception.py::TestParseWhitelist -v`
Expected: FAIL with `ImportError: cannot import name '_parse_whitelist'`

- [ ] **Step 3: 新增 module 純函式 `_parse_whitelist`**

在 `object_perception_node.py` 的 import 區之後、`class ObjectPerceptionNode` 之前，新增：
```python
def _parse_whitelist(raw) -> set:
    """Parse class_whitelist param value → allowed COCO class id set.

    Filters out-of-range (keeps 0..79; drops dummy ≥80 e.g. 999 and -1
    sentinel). Empty result → all 80 classes (sentinel/empty = 全開).
    Shared by __init__ and the runtime set_parameters callback (VIS-2).
    """
    wl_clean = [int(i) for i in (raw or []) if 0 <= int(i) <= 79]
    return set(wl_clean) if wl_clean else set(COCO_CLASSES.keys())
```

- [ ] **Step 4: 改 `__init__` 用 helper（exact replace :173-177）**

把現況：
```python
        wl = list(self.get_parameter("class_whitelist").value or [])
        # 2026-05-23: -1 sentinel = all classes (避開 empty [] rclpy type 推論問題)
        # 並過濾 yaml dummy >=80 (e.g. 999) 不在 COCO 集合
        wl_clean = [int(i) for i in wl if 0 <= int(i) <= 79]
        self.allowed_classes: set = set(wl_clean) if wl_clean else set(COCO_CLASSES.keys())
```
改成：
```python
        wl = list(self.get_parameter("class_whitelist").value or [])
        # 2026-06-08 VIS-2: 解析邏輯抽到 _parse_whitelist，與 runtime callback 共用
        self.allowed_classes: set = _parse_whitelist(wl)
```

- [ ] **Step 5: 跑測試確認通過**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest object_perception/test/test_object_perception.py::TestParseWhitelist -v`
Expected: 4 passed

- [ ] **Step 6: 加 callback 註冊（在 :233 logger.info 之後）**

在 `__init__` 的 `self.get_logger().info(...)`（現況 :228-233 那段 ObjectPerceptionNode started log）之後加一行：
```python
        # 2026-06-08 VIS-2: runtime 切換 whitelist 免重啟（現場某物效果差時切備援）
        self.add_on_set_parameters_callback(self._on_param_changed)
```

- [ ] **Step 7: 加 `_on_param_changed` method**

在 `__init__` 結束後、下一個 method 之前，新增：
```python
    def _on_param_changed(self, params):
        """VIS-2: runtime class_whitelist 變更即時生效（detect 迴圈讀 self.allowed_classes）。"""
        from rcl_interfaces.msg import SetParametersResult

        for p in params:
            if p.name == "class_whitelist":
                self.allowed_classes = _parse_whitelist(list(p.value or []))
                self.get_logger().info(
                    f"class_whitelist updated → {len(self.allowed_classes)} classes "
                    f"{sorted(self.allowed_classes) if len(self.allowed_classes) < 80 else '(all 80)'}"
                )
        return SetParametersResult(successful=True)
```

- [ ] **Step 8: 全套測試 + py_compile**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m py_compile object_perception/object_perception/object_perception_node.py && python3 -m pytest object_perception/test/ -v`
Expected: 既有 test + 4 新 test 全 PASS。

- [ ] **Step 9: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add object_perception/object_perception/object_perception_node.py object_perception/test/test_object_perception.py
git commit -m "feat(object): VIS-2 runtime class_whitelist callback + parse helper + tests"
```

> **VIS-2 現場用法（runbook，Jetson）**：`ros2 param set /object_perception_node class_whitelist "[56]"`（只看椅子）/ `"[39,41,45,56,63,67,73]"`（家用 7 類）/ `"[-1]"`（全 80）。下一幀生效。Studio preset 鈕 = operator fallback（gateway 呼叫同一 param set，前端工作非本計畫 committed 範圍，列 VIS-2 follow-up）。

---

## Task 3: BRAIN-1 — 最小感知→說話政策（object window 30→60s + 鎖既有規則）

**Files:**
- Modify: `pawai_brain/pawai_brain/capability/world_snapshot.py:12`（`_OBJECT_WINDOW_S` 30→60）
- Test: `pawai_brain/test/test_world_snapshot.py`（新增 60s window + person-exclude regression）

> **BRAIN-1 五條規則的真實歸屬（recon 修正後）**：
> 1. **Face stable+ENGAGED 20s** → 已存在 `brain_node.py:1038-1064`，由 **VIS-4** 硬體驗證。
> 2. **Object 只白名單** → 由 **VIS-1/VIS-2**（上游只偵測白名單）達成；**不講 person** → `world_snapshot.py:14` 已排除（本 task 加 regression 鎖死）；**60s dedup** → 本 task 改。
> 3. **Gesture thumbs_up 不觸發 wiggle** → **VIS-5**（Task 4）。
> 4. **Pose sitting <4/5 不出聲** → brain_node 不主動講 pose（只 fallen 走 careful_remind），sitting 只進 LLM context；故為「demo 台詞/Studio-only」決策（VIS-6 wording），無新 code。
> 5. **Studio trace 標 evidence 來源** → 已有：rule brain `_emit(build_plan(..., source=, reason=))`（如 `source="rule:gesture"`），LLM brain trace 有 stage/status/detail。本 task 不改，VIS-7 verify。
>
> 故 BRAIN-1 唯一新 code = object window 30→60s + 鎖既有 person-exclude/color-gate 行為（防回歸）。「不講掉落物」是 LLM persona prompt guard（無 ground-truth class），列 BRAIN-1 follow-up（需 persona 檔，非今天 committed code）。

- [ ] **Step 1: 寫失敗測試（60s window + person 排除）**

在 `pawai_brain/test/test_world_snapshot.py` 末尾加（若無此檔則新建，import 對齊現有 test pattern）：
```python
import json
import time

from pawai_brain.capability.world_snapshot import WorldSnapshot, _OBJECT_WINDOW_S


class TestBrain1ObjectPolicy:
    def test_window_is_60s(self):
        # BRAIN-1: object dedup window 延長到 60s
        assert _OBJECT_WINDOW_S == 60.0

    def test_person_excluded(self):
        snap = WorldSnapshot()
        payload = json.dumps({
            "event_type": "object_detected",
            "objects": [
                {"class_name": "person", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
                {"class_name": "chair", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            ],
        })
        snap.apply_object_detected_json(payload)
        classes = {o["class"] for o in snap.get_recent_objects()}
        assert "person" not in classes
        assert "chair" in classes

    def test_recent_object_within_60s_window(self):
        snap = WorldSnapshot()
        snap.apply_object_detected_json(json.dumps({
            "event_type": "object_detected",
            "objects": [{"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
        }))
        # 預設 window 取回應含 cup
        assert any(o["class"] == "cup" for o in snap.get_recent_objects())
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/test_world_snapshot.py::TestBrain1ObjectPolicy -v`
Expected: `test_window_is_60s` FAIL（現值 30.0）；其餘可能 PASS（既有行為）。

- [ ] **Step 3: 改 window 30→60（exact replace `world_snapshot.py:12`）**

把現況：
```python
_OBJECT_WINDOW_S = 30.0
```
改成：
```python
_OBJECT_WINDOW_S = 60.0  # 2026-06-08 BRAIN-1: 30→60s，降低同物重複播報
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/test_world_snapshot.py -v`
Expected: 全 PASS（含 3 新 test）。

- [ ] **Step 5: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add pawai_brain/pawai_brain/capability/world_snapshot.py pawai_brain/test/test_world_snapshot.py
git commit -m "feat(brain): BRAIN-1 object dedup window 30→60s + person-exclude regression tests"
```

---

## Task 4: VIS-5 — gesture demo mode（thumbs_up 不引出 wiggle）

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py:243-262`（新 param）、`:291-300`（init demo 邏輯）
- Modify: `interaction_executive/config/executive.yaml:1-24`（開 flag）
- Test: `interaction_executive/test/test_brain_rules.py`

> **修正 recon 誤讀**：Roy 要的是 thumbs_up **不要**引出 wiggle confirmation（不問「比 OK 我就做 wiggle」），改成簡單正向回應。**不是**把 wiggle 變一步觸發。做法：demo flag 把 thumbs_up 移出 `_GESTURE_CONFIRM`，改發一句輕量正向 `say_canned`。

- [ ] **Step 1: 寫失敗測試**

在 `interaction_executive/test/test_brain_rules.py` 末尾加：
```python
def test_thumbs_up_demo_ack_no_wiggle_confirm(make_brain):
    """VIS-5: demo mode 下 thumbs_up 不進 PendingConfirm、不問『比 OK 做 wiggle』，
    改發輕量正向 say_canned。"""
    node = make_brain(thumbs_up_demo_ack=True)
    assert "thumbs_up" not in node._GESTURE_CONFIRM
    assert "thumbs_up" not in node._GESTURE_DIRECT  # 不一步觸發 wiggle
    node._on_gesture(_gesture_msg("thumbs_up"))
    # 不進 PENDING
    assert node._pending_confirm.state != ConfirmState.PENDING
    # 發了一句正向 say_canned，且文字不含 wiggle/OK 提示
    last = node._last_emitted_plan()
    assert last.skill == "say_canned"
    assert "wiggle" not in last.args.get("text", "")
    assert "OK" not in last.args.get("text", "")


def test_thumbs_up_default_still_confirm(make_brain):
    """flag 關閉時維持既有 confirm 行為（不回歸）。"""
    node = make_brain(thumbs_up_demo_ack=False)
    assert node._GESTURE_CONFIRM.get("thumbs_up") == "wiggle"
```

> 註：`make_brain` fixture、`_gesture_msg`、`_last_emitted_plan` 對齊 `test_brain_rules.py` 既有 helper；若 helper 名不同，執行者先 `grep -n "def make_brain\|def _gesture_msg\|_last_emitted" interaction_executive/test/test_brain_rules.py` 對齊。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -k thumbs_up -v`
Expected: FAIL（無 `thumbs_up_demo_ack` 參數）。

- [ ] **Step 3: 宣告 param（在 `brain_node.py:262` `peace_direct_stretch` 宣告後）**

在 `self.declare_parameter("peace_direct_stretch", False)` 之後加：
```python
        # 2026-06-08 VIS-5 demo gesture mode (Roy「thumbs_up 不要引出 wiggle」):
        # True → thumbs_up 移出 _GESTURE_CONFIRM（不問「比 OK 我就做 wiggle」），
        # 改發一句輕量正向 say_canned；不進 PendingConfirm、不一步觸發 wiggle。
        self.declare_parameter("thumbs_up_demo_ack", False)
```
並在讀取其他 param 的區段（同 `self.peace_direct_stretch = ...` 旁）加：
```python
        self.thumbs_up_demo_ack = self.get_parameter("thumbs_up_demo_ack").value
```

- [ ] **Step 4: init demo 邏輯（在 `:291-300` peace_direct_stretch block 之後）**

在 `if self.peace_direct_stretch:` 那個 block 之後加：
```python
        if self.thumbs_up_demo_ack:
            # VIS-5: thumbs_up 不走 confirm（不問 OK）、也不一步觸發 wiggle，
            # 由 _on_gesture 的 demo-ack 分支發輕量正向回應。
            self._GESTURE_CONFIRM = {
                k: v for k, v in self._GESTURE_CONFIRM.items() if k != "thumbs_up"
            }
```

- [ ] **Step 5: `_on_gesture` 加 demo-ack 分支（在 `:748` `if gesture in self._GESTURE_DIRECT:` 之前）**

在 direct/confirm 判斷之前插入：
```python
        if self.thumbs_up_demo_ack and gesture == "thumbs_up":
            # VIS-5 demo: 簡單正向回應，不引出 wiggle confirmation
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": "[happy] 收到，謝謝你！"},
                    source="rule:gesture",
                    reason="gesture:thumbs_up:demo_ack",
                )
            )
            return
```

- [ ] **Step 6: 跑測試確認通過**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -k thumbs_up -v`
Expected: 2 passed。

- [ ] **Step 7: 開 demo flag（`executive.yaml`，在 `peace_direct_stretch: true` 之後）**

```yaml
    # 2026-06-08 VIS-5: thumbs_up demo mode — 簡單正向回應，不引出 wiggle 確認
    thumbs_up_demo_ack: true
```

- [ ] **Step 8: 全套 + py_compile**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m py_compile interaction_executive/interaction_executive/brain_node.py && python3 -m pytest interaction_executive/test/test_brain_rules.py -v`
Expected: 全 PASS。

- [ ] **Step 9: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add interaction_executive/interaction_executive/brain_node.py interaction_executive/config/executive.yaml interaction_executive/test/test_brain_rules.py
git commit -m "feat(brain): VIS-5 thumbs_up demo-ack (no wiggle confirm) + flag + tests"
```

---

## Task 5: VIS-10-min — `pawai face` CLI（list / enroll / rebuild / test）

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`（新增 `@cli.group("face")` + 4 子命令，置於 `demo.group` 之後）
- Test: `tools/pawai_cli/tests/test_cli.py`（新增 face 子命令測試，用 click `CliRunner`）

參考既有 `@demo.group("school")` 模式（main.py:978+）與 `shell.run_remote`/`shell.jetson_repo`。`list` 走本機掃描（CI-safe）；`enroll`/`rebuild` 走 SSH；`test` 跑本機 pytest。

- [ ] **Step 1: 寫失敗測試**

在 `tools/pawai_cli/tests/test_cli.py` 末尾加：
```python
from click.testing import CliRunner
from pawai_cli.main import cli


def test_face_group_exists():
    res = CliRunner().invoke(cli, ["face", "--help"])
    assert res.exit_code == 0
    for sub in ("list", "enroll", "rebuild", "test"):
        assert sub in res.output


def test_face_list_help():
    res = CliRunner().invoke(cli, ["face", "list", "--help"])
    assert res.exit_code == 0


def test_face_enroll_requires_name():
    # 缺 --person-name 應報錯（exit != 0）
    res = CliRunner().invoke(cli, ["face", "enroll"])
    assert res.exit_code != 0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest tools/pawai_cli/tests/test_cli.py -k face -v`
Expected: FAIL（無 face group）。

- [ ] **Step 3: 新增 face group + 4 子命令（main.py，置於 `@demo.group("school")` 區塊之前或之後同層）**

```python
@cli.group("face")
def face() -> None:
    """人臉資料庫管理（list / enroll / rebuild / test）。"""


@face.command("list")
def face_list() -> None:
    """列出 Jetson face_db 內的人物與樣本數（SSH 掃描）。"""
    repo = shell.jetson_repo()
    script = (
        "import os; d='/home/jetson/face_db'; "
        "ppl=[p for p in sorted(os.listdir(d)) "
        "if os.path.isdir(os.path.join(d,p))] if os.path.isdir(d) else []; "
        "print('（DB 未初始化或無樣本）') if not ppl else "
        "[print(f'{p} ('+str(len([f for f in os.listdir(os.path.join(d,p)) "
        "if f.endswith(\".png\")]))+')') for p in ppl]"
    )
    shell.run_remote(f"cd {shlex.quote(repo)} && python3 -c {shlex.quote(script)}")


@face.command("enroll")
@click.option("--person-name", required=True, help="要註冊的人名（建 face_db 子資料夾）。")
@click.option("--samples", default=30, show_default=True, help="採樣張數。")
def face_enroll(person_name: str, samples: int) -> None:
    """在 Jetson 上跑 face_identity_enroll_cv.py 採樣（headless）。"""
    repo = shell.jetson_repo()
    cmd = (
        f"cd {shlex.quote(repo)} && source /opt/ros/humble/setup.zsh && "
        f"source install/setup.zsh && "
        f"python3 scripts/face_identity_enroll_cv.py "
        f"--person-name {shlex.quote(person_name)} --samples {int(samples)} "
        f"--output-dir /home/jetson/face_db --headless"
    )
    shell.run_remote(cmd)


@face.command("rebuild")
def face_rebuild() -> None:
    """刪除 model_sface.pkl 觸發 face_identity_node 下次啟動重訓。"""
    repo = shell.jetson_repo()
    cmd = (
        f"cd {shlex.quote(repo)} && rm -f /home/jetson/face_db/model_sface.pkl && "
        f"echo 'model_sface.pkl removed; restart face_identity_node to retrain'"
    )
    shell.run_remote(cmd)


@face.command("test")
def face_test() -> None:
    """跑 face_perception 本機單元測試。"""
    repo = shell.jetson_repo()
    cmd = (
        f"cd {shlex.quote(repo)} && source /opt/ros/humble/setup.zsh && "
        f"source install/setup.zsh && python3 -m pytest face_perception/test -v"
    )
    shell.run_remote(cmd)
```

> 執行者注意：確認 `shlex` 已 import（school group 已用 → 應已 import）；確認 `shell.run_remote` / `shell.jetson_repo` 簽名與既有用法一致（`grep -n "def run_remote\|def jetson_repo" tools/pawai_cli/pawai_cli/shell.py`）。若 `run_remote` 需要不同參數，對齊既有呼叫點。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest tools/pawai_cli/tests/test_cli.py -k face -v`
Expected: 3 passed。

- [ ] **Step 5: py_compile + 全 CLI 測試**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m py_compile tools/pawai_cli/pawai_cli/main.py && python3 -m pytest tools/pawai_cli/tests/test_cli.py -v`
Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): VIS-10-min pawai face list/enroll/rebuild/test"
```

---

# Part B — Hardware Runbook（Jetson + Go2，HITL 場測）

> 這些**不是 TDD**，是場測 runbook。前置：`ssh jetson-nano`、repo `~/elder_and_dog`、`source /opt/ros/humble/setup.zsh` → `source ~/rplidar_ws/install/setup.zsh` → `source install/setup.zsh`。每段給 pass/fail gate；過不了就照「降級」走。
> **致命組合（每次起 stack 前確認，SKILL.md）**：teleop:=false、`danger_distance_m≥1.0`、`GO2_PUBLISH_ODOM_TF=1`（amcl）、無殘留 driver（`pkill -9 go2_driver` 等）、reactive_stop 非 hold_brake。

## Task 6: NAV-1 — 短距自走穩定化（解 F7）

- [ ] **Step 1: 起 capability stack（fresh）**

```bash
ssh jetson-nano
cd ~/elder_and_dog
ROBOT_IP=192.168.123.161 MAP=/home/jetson/maps/home_living_room_v8.yaml bash scripts/start_nav_capability_demo_tmux.sh
# 等 ~50s lifecycle active；Foxglove 設 /initialpose（真實位置+朝向）；等 AMCL cov<0.45
```

- [ ] **Step 2: F7 診斷哨兵（另開 window）**

```bash
ros2 topic hz /cmd_vel_nav        # goal 期間應有 publisher 且有 rate
ros2 lifecycle get /controller_server   # 應 active
ros2 lifecycle get /planner_server      # 應 active
```
若送 goal 後 `/cmd_vel_nav` 無 publisher / 無 rate → F7 復現：看 nav2 log、costmap、inflation；先試 fresh restart（F7 在新 stack 常不復現，5/13 觀察）。

- [ ] **Step 3: 0.3m × 5**

```bash
for i in 1 2 3 4 5; do echo "[0.3m #$i]"; python3 scripts/send_relative_goal.py --distance 0.3; sleep 3; done
```
記每次 `result: success / actual_distance`。

- [ ] **Step 4: 0.5m × 5**

```bash
for i in 1 2 3 4 5; do echo "[0.5m #$i]"; python3 scripts/send_relative_goal.py --distance 0.5; sleep 3; done
```

- [ ] **Step 5: Pass/Fail gate**
- **PASS**：連 5 次 goto 都動（無 no_progress ABORT）；0.5m actual ≥ 0.45m。
- **FAIL**：仍 no_progress / 不動 → 記 log，demo 用「fresh restart 後第一發」當保底；台詞退回靜態展示。

---

## Task 7: NAV-2 — 安全停障 demo-ready

- [ ] **Step 1: 確認 reactive_stop publisher + 監控**

```bash
ros2 topic info /cmd_vel_obstacle -v | grep -i reactive   # 應有 reactive_stop publisher
# 另開 window:
ros2 topic echo /state/reactive_stop/status
```

- [ ] **Step 2: 擋路測試 × 5**

送 0.5m goal，行進中把椅子/人移入正前方 danger zone（<1.1m）。觀察 zone=danger → `/cmd_vel_obstacle` 發 0 → Go2 停。移開 → zone→slow/clear。

```bash
for i in 1 2 3 4 5; do echo "[block #$i]"; python3 scripts/send_relative_goal.py --distance 0.5; sleep 6; done
```

- [ ] **Step 3: Pass/Fail gate**
- **PASS**：擋路 5/5 停住、0/5 暴衝（撞上）；移開後不暴衝。Studio/Foxglove 看得到 LiDAR + pose + reactive_stop status + depth_clear。
- **FAIL**：有暴衝 → 檢查 danger_distance_m≥1.1、mux priority obstacle=200>nav=10、teleop 未跑。

---

## Task 8: NAV-3 — stop-resume

- [ ] **Step 1: 起 route + 行進中 pause**

```bash
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: 'sample'}" &
sleep 4
ros2 service call /nav/pause std_srvs/srv/Trigger
ros2 topic echo /state/nav/paused --once   # 應 true
```
（或 mux 自動釋放路徑：行進中擋路 → reactive_stop 停 → 移開觀察是否自動續行。）

- [ ] **Step 2: 關鍵測 — 停 >10s 是否 ABORT**

pause/擋路維持 >12s，觀察 nav goal 是否被 `no_progress_timeout` ABORT（`progress_check.py` PROGRESS_TIMEOUT_S=10.0）。

- [ ] **Step 3: resume**

```bash
ros2 service call /nav/resume std_srvs/srv/Trigger
ros2 topic echo /state/nav/paused --once   # 應 false；Go2 續行
```

- [ ] **Step 4: Pass/Fail gate**
- **PASS**：自動續行或 pause/resume 3/5 成功；停 >10s 不會把 goal 弄死（若會 → 用 route_runner pause/resume 而非裸 mux，並記「stop 期間 nav goal 會 timeout」為已知限制）。
- **保底**：手動 re-send goal（台詞：「操作員重新下達」）。

---

## Task 9: NAV-4 — route 進場（committed-lite，不擋主線）

- [ ] **Step 1: 建 classroom_entry route**

```bash
mkdir -p ~/elder_and_dog/runtime/nav_capability/routes
cat > ~/elder_and_dog/runtime/nav_capability/routes/classroom_entry.json << 'EOF'
{"schema_version": 1, "route_id": "classroom_entry", "frame_id": "map",
 "map_id": "home_living_room_v8",
 "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
 "waypoints": [
   {"id": "wp1", "task": "normal", "pose": {"x": 0.5, "y": 0.0, "yaw": 0.0}, "tolerance": 0.15, "timeout_sec": 30},
   {"id": "wp2", "task": "normal", "pose": {"x": 1.0, "y": 0.3, "yaw": 0.785}, "tolerance": 0.15, "timeout_sec": 30},
   {"id": "wp3", "task": "tts", "pose": {"x": 1.2, "y": 0.5, "yaw": 1.57}, "tolerance": 0.15, "timeout_sec": 30, "tts_text": "我到展示區了"}
 ]}
EOF
```
> 座標依實際場地用 Foxglove 量；先短段、每段 ≤ AMCL 可過距離。

- [ ] **Step 2: 跑 route × 3**

```bash
for i in 1 2 3; do echo "[route #$i]"; ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: 'classroom_entry'}"; done
# 另開：ros2 topic echo /event/nav/waypoint_reached
```

- [ ] **Step 3: Pass/Fail gate**
- **PASS（升級展示）**：route 走完所有 waypoint 3/5、轉彎不撞、終點停下播 TTS。台詞可加「依預設路線自主進場」。
- **FAIL**：退回 NAV-1/2/3 主線，**不影響 demo**。轉彎不俐落 → 拆更短段或遙控轉場（台詞「操作員輔助轉場」）。

---

## Task 10: VIS-4 — 具名問候硬體驗證

- [ ] **Step 1: 起 brain stack（從 WSL repo 根目錄，依賴 .env.local）**

```bash
cd /home/roy422/newLife/elder_and_dog
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
```

- [ ] **Step 2: 驗證 greet 路徑（brain_node.py:1038-1064）**

Roy 站到鏡頭前 ~1.5m **靜止 3 秒**（觸發 AttentionState.ENGAGED）。觀察是否自動「歡迎回來，Roy」。
```bash
# Jetson 另開：看 rule:known_face trace
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 topic echo /brain/proposal" | grep -i greet
```

- [ ] **Step 3: Pass/Fail gate**
- **PASS**：Roy 正面 ~1m/1.5m ENGAGED → 具名 TTS 4/5；20s/name cooldown 生效；非註冊者不誤叫名。
- **FAIL（斷線）**：查 (a) AttentionState 是否進 ENGAGED、(b) `/event/face_identity` identity_stable、(c) brain_node 是否訂 face topic。斷了才補接線。台詞退「generic 歡迎」。

---

## Task 11: VIS-8 — Jetson 多感知效能檢查

> 現有 `bench_l3_full_stack.py` = face+pose+whisper（**缺 object**）；`start_stress_test_tmux.sh` = camera+face+vision（**缺 object**）。本 task 先用現有壓測 + 手動加 object node 量測（完整 object 整合壓測腳本列 follow-up，非 committed code）。

- [ ] **Step 1: 起四感知 + Studio video**

```bash
ssh jetson-nano "cd ~/elder_and_dog && bash scripts/start_stress_test_tmux.sh 180"
# 另開 window 啟 object：
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && ros2 launch object_perception object_perception.launch.py"
```

- [ ] **Step 2: 量 FPS + 資源**

```bash
ros2 topic hz /state/perception/face
ros2 topic hz /vision_perception/debug_image
ros2 topic hz /event/object_detected
# 資源：tegrastats 或 benchmarks JetsonMonitor
ssh jetson-nano "tegrastats --interval 1000" | head -20
```

- [ ] **Step 3: Pass/Fail gate（Orin Nano 8GB）**
- **PASS**：face >3Hz、vision debug >5Hz、object >2Hz；溫度 <85°C；RAM 餘 >500MB；功率 <15W；Studio 延遲 <500ms；無 crash。
- **FAIL**：定位瓶頸（模型/Jetson/網路）。GPU 爭用（whisper+object 同 GPU）→ object 走 CPU 或關 whisper。記數據供「換不換模型」決策（VIS-9 bonus）。

---

# Part C — Verify-only

## Task 12: VIS-7 — Studio 證據（已實作，跑測試確認）

**Files（只讀確認）：** `pawai-studio/gateway/studio_gateway.py:72-83`、`video_bridge.py:22-29`、frontend panels。

- [ ] **Step 1: gateway / video 訂閱測試**

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/gateway
python -m pytest test_gateway.py -v
python -m pytest test_video_bridge.py -v
```
Expected: PASS；TOPIC_MAP 含 face/gesture/pose/object + 4 brain trace；VIDEO_TOPIC_MAP 含 face/vision/object。

- [ ] **Step 2: 前端 panel 存在性確認**

```bash
cd /home/roy422/newLife/elder_and_dog
ls pawai-studio/frontend/components/{face,gesture,pose,object}/*-panel.tsx
grep -c "FacePanel\|GesturePanel\|PosePanel\|ObjectPanel" pawai-studio/frontend/components/sheet/feature-sheet.tsx
```
Expected: 4 panel 檔存在；feature-sheet 引用齊。

- [ ] **Step 3: Pass/Fail gate**
- **PASS**：gateway+video 測試綠 + 4 panel 在 → VIS-7 視為 demo-ready（不需新 code）。
- **缺口**（已知）：ChatPanel 不顯示 brain trace（要 DevPanel `?dev=1`）；SkillResult 無完整列表。demo 前確認用哪個面板展示 trace。

---

## Self-Review（對 spec 的覆蓋檢查）

| Committed 票 | 對應 Task | 類型 | 狀態 |
|---|---|---|---|
| VIS-1 | Task 1 | config | ✅ |
| VIS-2 | Task 2 | code TDD | ✅ |
| VIS-3（單元層） | Task 2 Step1（矩陣硬體層在 NAV/VIS-8 場測） | code/hw | ✅ 單元；矩陣硬體=runbook |
| BRAIN-1 | Task 3（+VIS-4/VIS-5 分擔，Part 0 表） | code TDD | ✅（persona「不講掉落物」列 follow-up） |
| VIS-5 | Task 4 | code TDD | ✅ |
| VIS-10-min | Task 5 | code TDD | ✅ |
| NAV-1/2/3 | Task 6/7/8 | runbook | ✅ |
| NAV-4(lite) | Task 9 | runbook | ✅ |
| VIS-4 | Task 10 | runbook | ✅ |
| VIS-8 | Task 11 | runbook（object 整合腳本 follow-up） | ✅ |
| VIS-7 | Task 12 | verify | ✅ already_done |

**已知非-placeholder 的開放項（明說，非 TODO）：**
1. BRAIN-1「不講掉落物/person 台詞」屬 LLM persona prompt guard，需 persona 檔（`pawai_brain` persona 6 檔）才能寫精確 edit → 列 BRAIN-1 follow-up，非今天 committed code。
2. VIS-2 Studio preset 鈕（前端）= operator fallback，前端工作非 committed；底層 callback（Task 2）已足夠用 `ros2 param set` 切換。
3. VIS-8 object 整合進 `bench_l3_full_stack.py` + grader = follow-up；Task 11 用現有壓測 + 手動 object 量測達 gate。

**Bonus（明確不在本計畫）：** NAV-5 reactive bypass、NAV-6 detour、NAV-7 GotoRotate、VIS-6 換模型、VIS-9 YOLO A/B、VIS-11 fine-tune。

---

## Execution Handoff

Track A（Task 1-5）可在 WSL 今天做完並 commit（純 code+測試，不需硬體）。Track B（Task 6-11）要 Jetson+Go2。Track C（Task 12）跑測試即可。

建議執行法（兩選一）：
1. **Subagent-Driven（推薦）** — 每個 Task 派 fresh subagent，Task 間 review。
2. **Inline** — 本 session 直接執行 Track A，Track B 上 Jetson 手動跑 runbook。
