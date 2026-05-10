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


def decide_velocity(zone, mode, slow_speed, normal_speed):
    """reactive_stop publish 決策 — 4 mode 狀態機。

    Mode 設計（5/11 B0 → 5/11 night 訂正）：

    **`hold_brake`** — 永遠 publish 0（permanent brake）
        用途：B5 safety 驗證、demo emergency hold。
        副作用：mux priority 200 永遠贏，nav/teleop 都驅不動 Go2。
        操作員必須主動 disable 或切 mode 才能讓 Go2 走。
        對應原 5/11 B0.1 `safety_only=True` 行為。

    **`progressive`** — danger 發 0、slow/clear 沉默
        用途：搭配 nav stack（nav 走 priority 10）做漸進避障。
        ⚠️ 已知 mux timeout 風險：clear 後 0.5s 內若 teleop 還在 hot-publish
        0.5 m/s 會接管。**搭配 demo discipline「kill teleop / 用 nav goal
        而非 hot-publish」必須嚴格執行**。對應 5/11 B0 fix 前行為。

    **`released`** — 不 publish 但 LiDAR + zone state 仍更新
        用途：操作員主動釋放給 nav 接管。zone 仍在 status JSON 顯示。
        切回 hold_brake / progressive 才會重新介入控制。

    **`disabled`** — 不 publish、不更新 zone
        用途：完全 off，連 LiDAR processing 都跳過。

    Standalone fallback（`safety_only=False` legacy 行為）：
        為了向後相容，傳 mode="" 或 None 時走 standalone — 依 zone 發
        0/slow/normal。reactive_stop 直接驅動 Go2，nav stack 不在時用。

    Args:
        zone: "danger" / "slow" / "clear" / "emergency" / "init"
        mode: "hold_brake" / "progressive" / "released" / "disabled" / ""
        slow_speed: standalone / progressive 的 slow zone 速度（m/s）
        normal_speed: standalone clear zone 速度（m/s）

    Returns:
        Optional[float] — velocity (m/s) 或 None（None = 不 publish）

    See docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0.
    """
    if mode in ("disabled", "released"):
        return None  # caller skips publish
    if mode == "hold_brake":
        return 0.0
    if mode == "progressive":
        if zone in ("danger", "emergency"):
            return 0.0
        return None  # slow/clear silent — nav 接管
    # mode == "" or unrecognized → standalone fallback (legacy behavior)
    if zone in ("danger", "emergency"):
        return 0.0
    if zone == "slow":
        return slow_speed
    return normal_speed
