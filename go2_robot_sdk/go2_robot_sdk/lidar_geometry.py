"""Pure-Python LiDAR scan geometry helpers (no ROS dependency, testable standalone)."""
import math


def compute_front_min_distance(ranges, angle_min, angle_increment,
                               front_half_rad, range_min, range_max,
                               front_offset_rad=0.0):
    """取「Go2 物理前方」±front_half_rad 扇形內最小有效距離。

    範圍以 atan2 normalize 到 -π..+π，與 sllidar angle_min 起始（0 或 -π）無關。
    無有效點回傳 inf。

    Args:
        ranges: 1D list/iterable of distances（meters）。inf/nan/0 = invalid。
        angle_min: 起始角度 (rad)。
        angle_increment: 每點角度步進 (rad)。
        front_half_rad: 前方扇形半角度 (rad)。例如 ±30° 傳 π/6。
        range_min: 最小有效距離（小於視為自身遮蔽）。
        range_max: 最大有效距離。
        front_offset_rad: **laser frame 角度** offset 補正 — Go2 物理前方對應
            laser frame 中的哪個角度方向。

            ⚠️ 5/11 B1.5 caveat: 這個 param 與 base_link→laser TF 的 yaw 是
            **獨立兩段補正、必須一致**：
            - TF yaw=π 表示「laser 物理座標相對 base_link 旋轉 180°」
            - 此 param=π 表示「reactive_stop 在 laser frame 中找 Go2 前方
              要看 laser 0° 經 +π 補正後的方向」

            兩者語義不同（一個是空間 frame 旋轉、一個是 sensor frame 內角度
            convention），但實務上 v8 mount 兩個都填 π 才對。改 mount 角度
            時兩處都要改、不要只改一邊。

            v8 mount yaw=π → 設 math.pi（Go2 前方 = laser ±180°）。
            傳統 mount yaw=0 → 設 0（laser 0° = Go2 前方）。

            未來 B2.2 改用 base_link projection 後此 param 可廢。
    """
    min_dist = float("inf")
    for i, r in enumerate(ranges):
        if not math.isfinite(r) or r < range_min or r > range_max:
            continue
        angle = angle_min + i * angle_increment
        # Subtract offset before normalize so |angle_rel| ≤ front_half_rad
        # means "this beam points at Go2 physical front".
        angle_rel = math.atan2(math.sin(angle - front_offset_rad),
                               math.cos(angle - front_offset_rad))
        if abs(angle_rel) > front_half_rad:
            continue
        if r < min_dist:
            min_dist = r
    return min_dist


def classify_zone(distance_m, danger_m, slow_m):
    """距離 → zone 名稱（嚴格小於閾值）。

    Returns: "danger" | "slow" | "clear"
    """
    if distance_m < danger_m:
        return "danger"
    if distance_m < slow_m:
        return "slow"
    return "clear"


def decide_velocity(zone, safety_only, slow_speed, normal_speed):
    """reactive_stop publish 決策（B0.1 release gate fix）。

    safety_only=True：**任何 zone 都回 0**，目的是讓 mux priority 200 永遠
    壓住 teleop/nav，避免 5/11 B5 撞牆事件 — clear zone 沉默 → mux 0.5s
    timeout → 舊 /cmd_vel_joy=0.5 m/s 自動恢復前進。

    safety_only=False（standalone fallback）：依 zone 發 0 / slow / normal。
    這是給 nav stack 不在的 demo 備援用，reactive_stop 直接驅動 Go2。

    Args:
        zone: "danger" / "slow" / "clear" / "emergency" / "init"
        safety_only: True = mux mode（永遠發 0）；False = standalone（依 zone）
        slow_speed: standalone slow zone 速度（m/s）
        normal_speed: standalone clear zone 速度（m/s）

    Returns:
        velocity (m/s) — reactive_stop 該 publish 到 /cmd_vel_obstacle 或 /cmd_vel 的 linear.x

    See docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0.1.
    """
    if safety_only:
        return 0.0
    if zone in ("danger", "emergency"):
        return 0.0
    if zone == "slow":
        return slow_speed
    # clear / init / unknown → normal forward
    return normal_speed
