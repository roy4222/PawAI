# Face Registration And Debug Runbook

## 現況判斷

已完成：
- 有 face DB folder schema。
- 有註冊腳本 `scripts/face_identity_enroll_cv.py`。
- `face_identity_node` 啟動時會偵測 DB counts 是否變更，必要時自動重訓 `model_sface.pkl`。

未完成：
- 尚未整合到 `pawai cli`。
- 尚未有「註冊後立即驗證」的 CLI workflow。
- 尚未有刪除/覆蓋某個人的安全流程。
- 尚未把低光、角度、樣本品質檢查自動化。

## 現場註冊流程

前提：D435 和 ROS2 camera topic 已啟動。

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 scripts/face_identity_enroll_cv.py \
  --person-name alice \
  --samples 30 \
  --capture-interval 0.25 \
  --output-dir /home/jetson/face_db \
  --headless
```

完成後重啟 face node：

```bash
ros2 launch face_perception face_perception.launch.py
```

驗證：

```bash
ros2 topic echo /state/perception/face
ros2 topic echo /event/face_identity
```

成功標準：
- `/state/perception/face` 看到 `stable_name: "alice"`。
- `/event/face_identity` 出現 `identity_stable`。
- `sim` 穩定高於 `0.40`。
- `distance_m` 在 D435 可見範圍內不是 `null`。

## 建議的 pawai CLI 介面

目標不是新增模型能力，而是把現有 script 包成現場安全流程。

```bash
pawai face enroll alice --samples 30
pawai face list
pawai face verify alice
pawai face delete alice
pawai face retrain
```

建議 CLI workflow：

```text
enroll
  ├─ 檢查 camera topic 是否存在
  ├─ 檢查 YuNet/SFace model 是否存在
  ├─ 顯示目前 face_db 人名
  ├─ 若 person 已存在，要求 --append 或 --overwrite
  ├─ 呼叫 face_identity_enroll_cv.py
  ├─ 刪除舊 model_sface.pkl 或觸發 retrain
  ├─ 重啟/提示重啟 face node
  └─ verify：等 identity_stable，輸出 sim/distance
```

## 樣本品質建議

每人至少 30 張：
- 正面 10 張。
- 左右微轉頭各 5 張。
- 低頭/抬頭各 3-5 張。
- 眼鏡、帽子、口罩如會出現在 Demo，就各補一些。

避免：
- 背光。
- 臉太小。
- 一張圖裡有多張臉。
- 快速移動造成 motion blur。
- 只收同一角度，會導致側臉誤認或 unknown。

## 常見問題

### 問：「看得到我」但不知道我是誰

檢查：

```bash
ros2 topic echo /state/perception/face
```

判斷：
- `face_count > 0` 但 `stable_name=unknown`：偵測成功，識別不穩。
- `sim < 0.40`：樣本不足、角度/光線不佳、threshold 太高。
- `face_count=0`：相機、光線、topic 或 YuNet 偵測問題。

### 問：距離怎麼沒有值

檢查：

```bash
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
ros2 topic echo /state/perception/face
```

原因：
- aligned depth topic 沒啟動。
- bbox ROI 裡 depth 全 0。
- 人太近、太遠、反光、D435 深度空洞。

### 問：一直重複打招呼

先分辨是誰在發：

```bash
ros2 topic echo /event/face_identity
ros2 topic echo /brain/plan
ros2 topic echo /tts
```

可能原因：
- `/event/face_identity` 一直有 `identity_stable` 或 `identity_changed`。
- track lost/recreate 太頻繁。
- legacy router/bridge 和 Executive 都在發聲。
- Executive cooldown 因 node 重啟而重置。

修正方向：
- 增加 `track_max_misses` 或改善光線。
- 提高 `stable_hits`。
- 延長 `greet_known_person:{name}` cooldown。
- 確認 audible path 只有 Executive 主線。

### 問：陌生人警報要不要保留

建議明天先不要主打。原因是 unknown 代表「沒有穩定辨識成 DB 內的人」，不是安全語意上的陌生人。

短期處置：
- 改成 trace-only。
- 或新增 `enable_stranger_alert:=false`。

中期條件：
- unknown face 連續存在。
- 距離小於門檻。
- 沒有任何 known face。
- 非低光/低信心狀態。
- 經 Brain 二次確認或使用者確認。

## Debug Checklist

1. Camera topic：

```bash
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
```

2. Face state：

```bash
ros2 topic echo /state/perception/face
```

3. Face event：

```bash
ros2 topic echo /event/face_identity
```

4. Debug image：

```bash
ros2 topic hz /face_identity/debug_image
```

5. DB：

```bash
find /home/jetson/face_db -maxdepth 2 -name '*.png' | head
ls -lh /home/jetson/face_db/model_sface.pkl
```

6. Tests：

```bash
python3 -m pytest face_perception/test/test_utilities.py -v
```

## 明天開發優先順序

1. 先把註冊流程包進 `pawai cli`，因為到學校最需要新增同學/老師的臉。
2. 做 `pawai face verify`，讓現場知道註冊是否真的可用，不要只存照片。
3. 加一個 stranger alert disable/trace-only 參數，避免 Demo 誤觸。
4. 把重複打招呼觀測資料記下來：是 track churn、identity_changed 還是多個 audible path。
5. 若有餘力，再調整 distance 使用策略，例如 Brain 能回答「你離我大概多遠」或「靠近一點我比較看得清楚」。
