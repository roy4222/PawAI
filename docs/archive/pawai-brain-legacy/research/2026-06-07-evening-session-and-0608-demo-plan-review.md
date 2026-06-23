# 2026-06-07 Night Session Review and 2026-06-08 Demo Run-Through Plan

> Purpose: Translate Cloud's research/session report into two concrete things:
> 1. What was actually learned tonight.
> 2. What must be tested and developed tomorrow to run the full demo flow.
>
> Constraint: 2026-06-18 final presentation. 2026-06-08 priority is not polishing. It is to run the whole demo flow once, collect the right data, then decide the iteration list.

---

## 1. My Verdict on Cloud's Report

I accept most of Cloud's conclusions, with tighter wording.

Accepted:

- Navigation is not dead. Tonight's reported result says `goto_relative 0.3m` succeeded and Go2 physically moved, with LiDAR, odom, AMCL, Nav2, reactive_stop, and driver running.
- The claimable nav demo is now: short autonomous movement plus obstacle safety stop.
- Dynamic chair detour is still not claimable. `reactive_stop` is a stop layer, not a local detour planner.
- Object detection currently underuses YOLO. The code confirms `object_perception/config/object_perception.yaml` is locked to `class_whitelist: [41, 999]`, meaning cup-only demo mode.
- `coco_detector` exists in the upstream Go2 ROS2 SDK clone, but it is not a good replacement for current YOLO26n as the main detector.

Needs stricter wording:

- Do not say "navigation can move to Roy from the door" yet. Tonight only supports short-distance movement. Door-to-user requires longer-distance route test.
- Do not say "fallen object understanding" yet. Current object pipeline is 2D detection only. It does not know floor/table/ground plane unless we add depth logic.
- Do not say "PINTO was useless." The useful result is that model swapping is not the fastest fix for distant small cups. The faster fix is to use bigger objects, closer distance, and unlock existing COCO classes.
- Do not let Cloud collect random data tomorrow. Every measurement must answer a demo decision.

---

## 2. What Actually Happened Tonight

### 2.1 Navigation / Obstacle Avoidance

Reported tonight:

| Step | Result | Demo Meaning |
|---|---|---|
| Started nav capability stack | LiDAR, Nav2, AMCL, reactive_stop, Go2 driver were up | Nav runtime can be brought up for S1 |
| Foxglove initial pose | AMCL localization succeeded, `nav_ready=true` | Map/scan/robot pose can be shown visually |
| Sent `goto_relative 0.3m` | Go2 physically moved; action returned `SUCCEEDED` | Short autonomous movement is possible |
| Observed command path | `/cmd_vel_nav` ramped and command reached Go2 | Old "goal accepted but dog does not move" issue did not reproduce |
| Obstacle behavior | Go2 stopped before chair / obstacle; no crash | Safe stop is demo-usable |

Current claim:

> PawAI can localize on a map, move a short distance under navigation command, and stop safely when an obstacle is too close.

Not yet claimable:

> PawAI can autonomously enter from the door, route to Roy, and dynamically detour around a chair.

Why not claim dynamic detour:

- `reactive_stop` is designed to stop or suppress unsafe motion.
- It is not a path planner that turns around obstacles.
- A real detour needs Nav2 planner/controller behavior in a mapped environment, with enough space and tuning.
- For 6/18, safe stop is much safer and more honest than pretending there is robust dynamic obstacle avoidance.

### 2.2 Object Detection

Reported tonight:

| Step | Result | Demo Meaning |
|---|---|---|
| Started object stack | Realsense color and YOLO26n object_perception worked | Object pipeline can run |
| Tested white mug around 1.5m | `Det:0`, no detection | Distant small cup is not demo-safe |
| Checked config | `class_whitelist: [41, 999]` | Current demo mode only recognizes COCO cup |

The important correction:

> The problem is not that YOLO can only detect cups. The problem is that our config currently tells it to only detect cups.

Current code behavior:

- `object_perception_node` declares `class_whitelist`.
- `[-1]` sentinel means all COCO classes.
- Current YAML overrides this with `[41, 999]`.
- `41` is COCO `cup`.
- `999` is a dummy value used to force ROS2 YAML integer-array typing and is filtered out.

So current pipeline is artificially limited.

---

## 3. Why Not Switch to PINTO / Another Model First?

This is the key logic.

### 3.1 The Small-Cup Problem Is Mostly Pixel Physics

A small mug far away produces too few image pixels. A 9 cm cup at around 2 m in 640 input can become roughly a 20 px object. Once the object is that small, changing model architecture often cannot recover information that the image does not contain.

Practical conclusion:

- Do not spend tomorrow swapping models to save a 1.5-2 m mug.
- First test closer distance and larger household objects.
- If we need better small-object range later, the real paths are higher input resolution, better camera framing, or object-specific training, all higher risk before 6/18.

### 3.2 PINTO Research Still Helped

PINTO / model zoo research should be framed as:

> We evaluated alternative edge models, but for this demo the bottleneck is small-object image resolution and integration risk. The fastest reliable improvement is to unlock existing COCO classes and choose demo objects with enough visual size.

Do not frame it as:

> We looked at PINTO and it was useless.

That is not accurate.

---

## 4. What About `coco_detector` in Go2 ROS2 SDK?

There are two COCO-related things. They are easy to confuse.

### 4.1 Current PawAI Object Detector

Path:

- `object_perception/object_perception/object_perception_node.py`
- `object_perception/config/object_perception.yaml`
- `object_perception/object_perception/coco_classes.py`

Model:

- YOLO26n ONNX / TensorRT path.
- Current config uses `input_size: 640`.
- Current config only enables cup: `class_whitelist: [41, 999]`.
- It already has COCO class names.

This is the main detector we should improve first.

### 4.2 Upstream Go2 SDK `coco_detector`

Path:

- `.tmp/go2_ros2_sdk/coco_detector/coco_detector/coco_detector_node.py`

Model:

- `torchvision.models.detection.fasterrcnn_mobilenet_v3_large_320_fpn`
- Default device is CPU.
- Default threshold is 0.9.
- Subscribes to `/camera/image_raw`.
- Publishes `Detection2DArray` and annotated image.

Why not use as main detector:

- It is PyTorch/TorchVision based, not current TensorRT path.
- It is likely slower on Jetson, especially CPU default.
- It has different topic contracts from PawAI object perception.
- It does not solve small-object pixel physics.

Decision:

> Do not replace current detector with upstream `coco_detector` for 6/18. Keep it as reference code only.

---

## 5. COCO Classes Useful for Demo

Current PawAI YOLO class source:

- `object_perception/object_perception/coco_classes.py`

### Best Household Demo Classes

Use these first because they are visible, familiar, and likely larger than a cup:

| COCO ID | Class | Chinese | Demo Use |
|---:|---|---|---|
| 39 | bottle | 瓶子 | Better than mug; tall and recognizable |
| 41 | cup | 杯子 | Good only at close range |
| 45 | bowl | 碗 | Larger than cup; good tabletop/floor object |
| 56 | chair | 椅子 | Very stable; also helps environment understanding |
| 57 | couch | 沙發 | Stable if present |
| 58 | potted plant | 盆栽 | Good household visual object |
| 60 | dining table | 餐桌 | Large object; environment context |
| 62 | tv | 電視 | Large object; environment context |
| 63 | laptop | 筆電 | Useful if visible and open |
| 65 | remote | 遙控器 | Smaller; test only if available |
| 67 | cell phone | 手機 | Risky when flat/sideways |
| 73 | book | 書 | Works better upright/open than flat |
| 74 | clock | 時鐘 | If visible |
| 75 | vase | 花瓶 | Good household object |
| 77 | teddy bear | 玩偶 | Good if available; visible shape |

### Objects Not in COCO or Not Demo-Safe

| Object | Reason |
|---|---|
| key / keys | Not a COCO class; too small |
| wallet | Not a COCO class; shape varies |
| glasses | Not a COCO class; small/thin |
| medicine box | Not a COCO class unless detected as generic object, which current detector does not do |
| cable | Not a COCO class; thin |

### Recommended Whitelist for Tomorrow

Start with a household subset, not all 80 immediately:

```yaml
class_whitelist: [39, 41, 45, 56, 57, 58, 60, 62, 63, 65, 67, 73, 74, 75, 77, 999]
```

If false positives are low, test all classes using the node's sentinel:

```yaml
class_whitelist: [-1]
```

Do not start with all 80 in the official demo unless we confirm it does not create noisy boxes.

---

## 6. 2026-06-08 Main Goal

Tomorrow's goal:

> Run the complete demo flow once, in two stack segments, collect failure data, then decide what to fix.

Important:

- Do not try to make it beautiful first.
- Do not switch models first.
- Do not collect data unrelated to the demo story.
- Do not let Cloud avoid the main flow by investigating random architecture questions.

Because nav stack and brain stack are resource-heavy, the full demo is treated as two segments:

1. S1 Navigation segment.
2. S2-S5 Brain/perception/interaction segment.

The final video/demo can be edited as a coherent story, even if runtime is two sessions.

---

## 7. Tomorrow's Required Test Plan

### S1. Navigation: Move to Scene

Demo story:

> PawAI can move toward the inspection area and stop safely when an obstacle is near.

Minimum pass:

- Nav stack starts.
- Foxglove shows map, LiDAR scan, robot pose.
- `goto_relative 0.5m` succeeds in a clear area.
- Go2 visibly moves.
- Obstacle safety stop works without collision.

Stretch:

- `goto_relative 1.0m` succeeds.
- A staged chair/box stop looks good on camera.

Do not test tomorrow morning:

- Dynamic detour around chair.
- Door-to-Roy full route before short-distance tests pass.

Data to collect:

| Data | Why |
|---|---|
| `/scan_rplidar` Hz | prove LiDAR live |
| `/odom` Hz | prove driver odometry live |
| `/amcl_pose` | prove localization live |
| `/capability/nav_ready` | prove nav capability ready |
| `/cmd_vel_nav` | prove Nav2 generated motion |
| `/cmd_vel_obstacle` | prove reactive_stop behavior |
| `/cmd_vel` | prove final command reached Go2 |
| `/state/reactive_stop/status` | know whether safety layer is blocking |
| Foxglove recording/screenshot | demo visual evidence |
| pass/fail for 0.5m and 1.0m | decide demo wording |

Decision after S1:

- If 1.0m works: demo says "short autonomous navigation to the inspection area."
- If only 0.5m works: demo says "short-range navigation and safety stop."
- If movement fails: use backup video + show map/LiDAR/safe stop only.

### S2. Face + Pose Recognition

Demo story:

> Roy, welcome back. I see you are sitting down.

Minimum pass:

- Face recognizes Roy at around 1 m.
- Pose recognizes sitting at least 4/5 trials.
- TTS sentence stays conservative.

Data to collect:

| Data | Why |
|---|---|
| Roy recognition distance | decide where Roy stands/sits |
| sitting detection 5 trials | decide whether to keep sitting line |
| debug image/screen | proof it is live |

Decision:

- If face + sitting stable: keep exact line.
- If pose unstable: say "Roy, welcome back" only; show pose screen separately.

### S3. Object Detection / Item Reminder

Demo story:

> I see an object nearby. Please be careful.

Better line if reliable:

> I see a cup/bottle/bowl on the floor. Please remember to pick it up.

Minimum pass:

- Unlock household COCO subset.
- Detect at least 2-3 household objects reliably.
- Choose one floor/table object for the actual script.

Data to collect:

| Object | Distance | Placement | Result Needed |
|---|---:|---|---|
| cup | 0.7 m / 1.0 m / 1.5 m | floor + table | class, confidence, bbox |
| bottle | 0.7 m / 1.0 m / 1.5 m | floor + table | class, confidence, bbox |
| bowl | 0.7 m / 1.0 m / 1.5 m | floor + table | class, confidence, bbox |
| chair | visible room object | room | should be stable |
| laptop/book/phone | if available | table/floor | optional |

Decision:

- If cup stable only under 1 m: use close cup.
- If bottle/bowl more stable: change demo object.
- If many objects work: use "multi-object environment understanding" visual scene in Studio.
- If floor/table cannot be distinguished: do not claim "fallen object"; say "nearby object" or "object in front."

### S4. Gesture / Voice Interaction

Demo story:

> Gesture or voice can trigger safe predefined robot actions.

Minimum pass:

- Keep only 1-2 gestures.
- Confirm no idle false trigger for 30 seconds.
- Confirm one voice command like "坐下" or one Studio button.

Data:

- Which gesture works best.
- False trigger count.
- Which action maps cleanly.

Decision:

- If gesture false triggers: use voice or Studio button.
- If gesture stable: keep one short gesture segment.

### S5. Safety Refusal

Demo story:

> LLM does not directly control Go2. Unsafe requests are blocked by PawAI Brain safety layer.

Minimum pass:

- "請翻跟斗" blocked 3/3.
- Go2 does not move.
- TTS refusal works.
- Studio/trace shows blocked action.

Data:

- 3 trials result.
- Whether ASR hears "翻跟斗" correctly.
- Whether blocked screen appears.

Decision:

- If ASR unstable: use Studio text input for final demo.
- If ASR stable: use voice.

---

## 8. Tomorrow's Development Queue After Data Collection

Only start development after the first full-flow run.

### P0. Unlock YOLO COCO Household Classes

Why:

- Biggest visual improvement.
- Existing model already supports it.
- Current cup-only setting wastes the detector.

Change:

- Update `object_perception/config/object_perception.yaml`.
- Start with household whitelist.
- Verify debug image and Studio object panel.

Expected time:

- 30-60 minutes including test.

### P0. Build Demo Script Around Real Nav Capability

Why:

- Navigation claim must match what works.

Change:

- If 0.5/1.0m works, script first segment as short autonomous movement + safe stop.
- If not, script as map/LiDAR/safety capability with backup video.

Expected time:

- 30 minutes after test result.

### P1. Object Reminder Wording and Trigger

Why:

- Current system likely does not know "on floor" yet.

Change:

- Use safe wording unless depth-ground logic is added.
- Prefer "I see a cup/bottle nearby" over "fallen object" unless verified.

Expected time:

- 30 minutes for wording; 1-1.5 days if adding depth-ground logic.

### P1. Studio Evidence Panel

Why:

- Judges need to see live detection, not assume canned speech.

Change:

- Make sure object debug image, detection list, Brain trace, and safety blocked event are visible.
- Do not add map/LiDAR to Studio tomorrow; use Foxglove web for nav.

Expected time:

- 1-2 hours if UI already works; otherwise use existing panels.

### P2. Voice-to-Nav / Studio-to-Nav Trigger

Why:

- Nice demo story, but not required for tomorrow's first full run.

Risk:

- Brain and nav stacks may not run together due memory/runtime constraints.

Decision:

- Do not block tomorrow's demo flow on this.

---

## 9. Hard Instructions for Cloud Tomorrow

Use this as the prompt to constrain Cloud:

```text
Tomorrow goal is to run PawAI's demo flow once and collect only decision-making data.
Do not start by changing models, adding new architecture, or researching unrelated issues.

Demo flow:
S1 navigation: map/LiDAR localization, short goto 0.5m/1.0m, obstacle safe stop, Foxglove evidence.
S2 perception: Roy face recognition + sitting pose.
S3 object: unlock current YOLO COCO household whitelist, test cup/bottle/bowl/chair at fixed distances, choose demo object.
S4 gesture/voice: one stable gesture or one voice/button action, avoid false trigger.
S5 safety: "請翻跟斗" blocked 3/3, Go2 does not move, Studio trace shows blocked.

Only collect these data:
- nav_ready, scan Hz, odom Hz, amcl_pose, cmd_vel_nav, cmd_vel_obstacle, cmd_vel, reactive_stop status, Foxglove screenshot/recording
- face recognition distance, sitting pass count
- object class/confidence/bbox/debug image for cup/bottle/bowl/chair
- gesture false trigger count
- safety refusal 3/3 result

After all five segments are tested, produce a pass/fail table and then propose code changes.
Do not use F7/lane/internal shorthand without explaining it in plain language.
```

---

## 10. One-Line Plan

Tomorrow:

1. Run S1 nav stack and record what movement/safe-stop can honestly be shown.
2. Switch to brain stack and run S2-S5 once.
3. Unlock object whitelist and retest object scene.
4. Decide final demo script based on measured pass/fail.
5. Only then start polishing.

