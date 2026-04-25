"""姿勢辨識 v2 — 改善坐姿、新增 Hands on hips / Kneeling on one knee"""
import cv2
import mediapipe as mp
import numpy as np
import math
from collections import deque

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils
mp_draw_styles = mp.solutions.drawing_styles

# ── 索引常數 ──────────────────────────────────────────
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28
L_HEEL,     R_HEEL     = 29, 30

VIS_THRESH = 0.45   # landmark 可見度門檻
SMOOTH_N   = 5      # 時間平滑視窗（frames）

# ── 工具函式 ──────────────────────────────────────────
def angle_between(a, b, c):
    """三點夾角（b 為頂點），回傳度數 0–180"""
    ba = np.array([a.x - b.x, a.y - b.y])
    bc = np.array([c.x - b.x, c.y - b.y])
    cos_a = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return math.degrees(math.acos(np.clip(cos_a, -1, 1)))

def dist2d(a, b):
    """兩點歐氏距離（normalized image coords）"""
    return math.hypot(a.x - b.x, a.y - b.y)

def visible(*lms):
    """所有 landmark 都達到可見度門檻才回傳 True"""
    return all(lm.visibility >= VIS_THRESH for lm in lms)

def trunk_angle_deg(lm):
    """軀幹與垂直線夾角（度）"""
    mid_sh = np.array([(lm[L_SHOULDER].x + lm[R_SHOULDER].x) / 2,
                       (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2])
    mid_hp = np.array([(lm[L_HIP].x + lm[R_HIP].x) / 2,
                       (lm[L_HIP].y + lm[R_HIP].y) / 2])
    vec = mid_sh - mid_hp          # 向上為負 y
    vertical = np.array([0, -1])
    cos_t = np.dot(vec, vertical) / (np.linalg.norm(vec) + 1e-6)
    return math.degrees(math.acos(np.clip(cos_t, -1, 1)))

# ── 主分類器 ──────────────────────────────────────────
def classify_pose(landmarks):
    """
    回傳 (pose_name, debug_dict)
    優先順序：fallen → kneeling_one_knee → hands_on_hips
             → standing → sitting → crouching → bending → unknown
    """
    lm = landmarks.landmark

    # ── 基礎角度（只用可見點）──
    use_hip = visible(lm[L_SHOULDER], lm[L_HIP], lm[L_KNEE],
                      lm[R_SHOULDER], lm[R_HIP], lm[R_KNEE])
    use_knee = visible(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE],
                       lm[R_HIP], lm[R_KNEE], lm[R_ANKLE])

    hip_angle = (
        angle_between(lm[L_SHOULDER], lm[L_HIP], lm[L_KNEE]) +
        angle_between(lm[R_SHOULDER], lm[R_HIP], lm[R_KNEE])
    ) / 2 if use_hip else None

    knee_angle = (
        angle_between(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE]) +
        angle_between(lm[R_HIP], lm[R_KNEE], lm[R_ANKLE])
    ) / 2 if use_knee else None

    trunk_angle = trunk_angle_deg(lm) if visible(
        lm[L_SHOULDER], lm[R_SHOULDER], lm[L_HIP], lm[R_HIP]) else None

    # ── 手肘彎曲角（shoulder-elbow-wrist）──
    elbow_angle_l = angle_between(lm[L_SHOULDER], lm[L_ELBOW], lm[L_WRIST]) \
        if visible(lm[L_SHOULDER], lm[L_ELBOW], lm[L_WRIST]) else None
    elbow_angle_r = angle_between(lm[R_SHOULDER], lm[R_ELBOW], lm[R_WRIST]) \
        if visible(lm[R_SHOULDER], lm[R_ELBOW], lm[R_WRIST]) else None

    # 蹲姿預判（給後續跪地/插腰排除用）
    is_crouching_likely = (hip_angle is not None and knee_angle is not None and
                           hip_angle < 145 and knee_angle < 130)

    debug = dict(hip=hip_angle, knee=knee_angle, trunk=trunk_angle,
                 elbow_l=elbow_angle_l, elbow_r=elbow_angle_r)

    # ── 1. Fallen：軀幹接近水平 ──
    if trunk_angle is not None and trunk_angle > 60:
        return "fallen", debug

    # ── 2. Kneeling on one knee（優先於 hands_on_hips）──
    # 跪姿特徵：
    #   A. 兩膝 y 座標落差大（跪地膝較低）
    #   B. 站立腳膝角直（> 130），與跪地腳有明顯差異
    #   C. 跪地側腳踝不可見 OR 腳踝 y 非常接近膝蓋 y（腳背貼地）
    #   D. 軀幹直立，且整體不像在蹲（排除蹲下）
    if not is_crouching_likely and \
       visible(lm[L_KNEE], lm[R_KNEE], lm[L_HIP], lm[R_HIP]):
        ly, ry = lm[L_KNEE].y, lm[R_KNEE].y
        knee_y_diff = abs(ly - ry)
        if knee_y_diff > 0.07:                      # 兩膝高低差要夠大
            down_side   = "L" if ly > ry else "R"
            kneel_knee  = lm[L_KNEE]  if down_side == "L" else lm[R_KNEE]
            kneel_ankle = lm[L_ANKLE] if down_side == "L" else lm[R_ANKLE]
            stand_knee  = lm[R_KNEE]  if down_side == "L" else lm[L_KNEE]
            stand_ankle = lm[R_ANKLE] if down_side == "L" else lm[L_ANKLE]
            stand_hip   = lm[R_HIP]   if down_side == "L" else lm[L_HIP]
            kneel_hip   = lm[L_HIP]   if down_side == "L" else lm[R_HIP]

            ankle_hidden    = kneel_ankle.visibility < VIS_THRESH
            ankle_near_knee = abs(kneel_ankle.y - kneel_knee.y) < 0.08

            stand_k = angle_between(stand_hip, stand_knee, stand_ankle) \
                if visible(stand_hip, stand_knee, stand_ankle) else None
            kneel_k = angle_between(kneel_hip, kneel_knee, kneel_ankle) \
                if visible(kneel_hip, kneel_knee, kneel_ankle) else None

            # 站立腳要夠直，跪地腳要彎（或腳踝消失）
            stand_ok = stand_k is not None and stand_k > 130
            kneel_ok = (kneel_k is not None and kneel_k < 140) \
                       or ankle_hidden or ankle_near_knee
            # 站/跪膝角差距要明顯（避免蹲下時兩腳都彎但高度略有差）
            angle_diff_ok = (stand_k is None or kneel_k is None) or \
                            (stand_k - (kneel_k or 0) > 25)

            # 額外條件：另一腳呈「坐姿型」幾何（髖膝近同高 + 小腿往下）
            # 對應需求：一膝著地，另一腳像坐姿那樣彎曲支撐
            support_leg_sitting_like = False
            if visible(stand_hip, stand_knee, stand_ankle):
                hip_knee_level_close = abs(stand_hip.y - stand_knee.y) < 0.12
                shin_vertical_down = (stand_ankle.y - stand_knee.y) > 0.10
                knee_bent_like_sit = stand_k is not None and 70 < stand_k < 130
                support_leg_sitting_like = hip_knee_level_close and shin_vertical_down and knee_bent_like_sit

            if (stand_ok and angle_diff_ok or support_leg_sitting_like) and kneel_ok and \
               trunk_angle is not None and trunk_angle < 45:
                return "kneeling_one_knee", debug

    # ── 3. Hands on hips ──
    # 判斷依據（全部要同時成立）：
    #   A. 手腕 y 接近髖部 y（±0.10）
    #   B. 手腕 x 在肩膀與髖部之間
    #   C. 手腕距同側髖部近（< 0.14）
    #   D. 手肘明顯彎曲（elbow_angle < 145）← 排除雙手自然垂放
    #   E. 軀幕直立（trunk < 35）
    #   F. 膝角要直（> 145）← 排除蹲下
    if not is_crouching_likely and \
       visible(lm[L_WRIST], lm[R_WRIST], lm[L_HIP], lm[R_HIP],
               lm[L_SHOULDER], lm[R_SHOULDER]):
        lw, rw = lm[L_WRIST], lm[R_WRIST]
        lh, rh = lm[L_HIP],   lm[R_HIP]
        ls, rs = lm[L_SHOULDER], lm[R_SHOULDER]

        lw_y_ok  = abs(lw.y - lh.y) < 0.10
        rw_y_ok  = abs(rw.y - rh.y) < 0.10
        lw_x_ok  = lh.x - 0.12 < lw.x < ls.x + 0.08
        rw_x_ok  = rs.x - 0.08 < rw.x < rh.x + 0.12
        lw_close = dist2d(lw, lh) < 0.14
        rw_close = dist2d(rw, rh) < 0.14

        # 手肘彎曲條件（自然垂手時手肘幾乎打直 ≈ 160–180°）
        l_elbow_bent = elbow_angle_l is not None and elbow_angle_l < 145
        r_elbow_bent = elbow_angle_r is not None and elbow_angle_r < 145

        both_hands = (lw_y_ok and lw_x_ok and lw_close) and \
                     (rw_y_ok and rw_x_ok and rw_close)

        if both_hands and l_elbow_bent and r_elbow_bent and \
           trunk_angle is not None and trunk_angle < 35 and \
           (knee_angle is None or knee_angle > 145):
            return "hands_on_hips", debug

    # ── 4. Standing：髖角直、膝角直、軀幹直 ──
    if hip_angle is not None and knee_angle is not None and trunk_angle is not None:
        if hip_angle > 155 and knee_angle > 155 and trunk_angle < 30:
            return "standing", debug

    # ── 5. Sitting ──
    # 關鍵：臀部 y 座標明顯高於踝部（normalized，y 向下），
    #        膝蓋彎曲，軀幹直立
    if visible(lm[L_HIP], lm[R_HIP], lm[L_ANKLE], lm[R_ANKLE],
               lm[L_KNEE], lm[R_KNEE]):
        hip_y  = (lm[L_HIP].y  + lm[R_HIP].y)  / 2
        ankle_y = (lm[L_ANKLE].y + lm[R_ANKLE].y) / 2
        knee_y  = (lm[L_KNEE].y  + lm[R_KNEE].y)  / 2

        # 坐著時臀部 y 接近膝蓋 y（高度相近），且都遠低於踝部
        hip_knee_diff = abs(hip_y - knee_y)     # 小 → 臀膝同高（大椅子）
        hip_above_ankle = ankle_y - hip_y        # 正值 → 臀部在踝部上方

        # 兩種坐法：
        #   大椅子：hip_knee_diff 小，hip_above_ankle 大
        #   小椅子（矮凳）：knee_y > hip_y 也可接受
        is_seated_geometry = (
            hip_above_ankle > 0.10 and          # 臀部確實比踝部高很多
            (hip_knee_diff < 0.12 or knee_y > hip_y)  # 膝與臀同高，或膝蓋高於臀
        )

        if is_seated_geometry and trunk_angle is not None and trunk_angle < 45:
            if knee_angle is not None and knee_angle < 145:
                return "sitting", debug

    # ── 6. Crouching：膝角小、髖角小 ──
    if hip_angle is not None and knee_angle is not None:
        if hip_angle < 145 and knee_angle < 125:
            return "crouching", debug

    # ── 7. Bending：軀幹前傾、膝較直 ──
    # trunk_angle 是主要依據；knee_angle 若看不到（腳踝出框）視為膝直通過
    # 明確排除蹲下（is_crouching_likely）
    if trunk_angle is not None and trunk_angle > 30 and not is_crouching_likely:
        knee_straight = (knee_angle is None or knee_angle > 130)
        hip_bent      = (hip_angle  is None or hip_angle  < 160)
        if knee_straight and hip_bent:
            return "bending", debug

    return "unknown", debug


# ── 顯示設定 ──────────────────────────────────────────
POSE_COLOR = {
    "standing":        (0, 220, 100),
    "sitting":         (0, 180, 255),
    "crouching":       (255, 200, 0),
    "bending":         (255, 140, 0),
    "fallen":          (0, 0, 255),
    "hands_on_hips":   (200, 0, 255),
    "kneeling_one_knee": (0, 255, 220),
    "unknown":         (180, 180, 180),
}

POSE_LABEL = {
    "standing":          "Standing",
    "sitting":           "Sitting",
    "crouching":         "Crouching",
    "bending":           "Bending",
    "fallen":            "FALLEN ⚠",
    "hands_on_hips":     "Hands on Hips",
    "kneeling_one_knee": "Kneeling (one knee)",
    "unknown":           "Unknown",
}

# ── 時間平滑 ──────────────────────────────────────────
pose_history = deque(maxlen=SMOOTH_N)

def smoothed_pose(raw_pose):
    pose_history.append(raw_pose)
    return max(set(pose_history), key=pose_history.count)


def infer_pose_from_bgr(frame_bgr, return_annotated=False):
    """單張影像推論，回傳可給前端的姿勢資料。"""
    annotated_frame = frame_bgr.copy() if return_annotated else None
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = pose_model.process(rgb)

    if not result.pose_landmarks:
        return {
            "pose": "unknown",
            "confidence": 0.0,
            "debug": {},
            "annotated_bgr": annotated_frame,
        }

    if annotated_frame is not None:
        mp_draw.draw_landmarks(
            annotated_frame,
            result.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_draw_styles.get_default_pose_landmarks_style(),
        )

    raw_pose, debug = classify_pose(result.pose_landmarks)
    pose_name = smoothed_pose(raw_pose)

    # 規則式分類沒有模型機率，先提供穩健的工程近似值。
    base_confidence = {
        "standing": 0.86,
        "sitting": 0.82,
        "crouching": 0.78,
        "bending": 0.76,
        "fallen": 0.90,
        "hands_on_hips": 0.84,
        "kneeling_one_knee": 0.80,
        "unknown": 0.35,
    }

    return {
        "pose": pose_name,
        "confidence": base_confidence.get(pose_name, 0.5),
        "debug": debug,
        "annotated_bgr": annotated_frame,
    }


def run_demo_loop():
    """本地視窗 Demo（原始行為）。"""
    cap = cv2.VideoCapture(0)
    # 要求鏡頭輸出最高解析度（不支援的鏡頭會自動 fallback）
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 建立可縮放視窗，初始顯示 1280×720
    cv2.namedWindow("Pose Classifier v2", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pose Classifier v2", 1280, 720)

    print("按 q 離開。視窗可以用滑鼠拖動邊緣自由縮放！")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose_model.process(rgb)

        if result.pose_landmarks:
            # 繪製骨架
            mp_draw.draw_landmarks(
                frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_draw_styles.get_default_pose_landmarks_style(),
            )

            raw_pose, debug = classify_pose(result.pose_landmarks)
            pose_name = smoothed_pose(raw_pose)
            color = POSE_COLOR.get(pose_name, (200, 200, 200))
            label = POSE_LABEL.get(pose_name, pose_name)

            # 半透明背景條
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (frame.shape[1], 100), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

            cv2.putText(frame, label, (14, 52),
                        cv2.FONT_HERSHEY_DUPLEX, 1.6, color, 2, cv2.LINE_AA)

            # debug 列
            parts = []
            if debug["hip"]     is not None: parts.append(f"hip={debug['hip']:.0f}")
            if debug["knee"]    is not None: parts.append(f"knee={debug['knee']:.0f}")
            if debug["trunk"]   is not None: parts.append(f"trunk={debug['trunk']:.0f}")
            if debug["elbow_l"] is not None: parts.append(f"el={debug['elbow_l']:.0f}")
            if debug["elbow_r"] is not None: parts.append(f"er={debug['elbow_r']:.0f}")
            cv2.putText(frame, "  ".join(parts), (14, 82),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)

        cv2.imshow("Pose Classifier v2", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


# ── 主迴圈 ───────────────────────────────────────────
pose_model = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

if __name__ == "__main__":
    run_demo_loop()