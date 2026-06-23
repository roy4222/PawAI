# 導航避障 Maps

## 當前使用：`home_living_room_v5.{pgm,yaml,pbstream}`

- 建立：2026-04-29 20:23
- TF：base_link → laser **yaw=π (3.1416)**（雷達 0° 朝 Go2 後，需 180° 補正）
- 物理尺寸：4.85m × 11m（97 × 220 cells @ 0.05 m/pix）
- 模式：Cartographer pure scan-matching
- 供電：2464 升降壓模組（XL4015 已淘汰）

## Deprecated（yaw 修正歷程）

| 版本 | yaw 設定 | 結果 | 棄用原因 |
|------|---------|------|---------|
| v2 | 0 | map 旋轉 90° | 雷達朝向沒補正 |
| v3 | −π/2 | map 仍反向 | yaw 方向錯 |
| v4 | +π/2 | scan 朝下、map 朝右 | 還差 +π/2 |
| **v5** | **π** | **正確** ✅ | 當前主線 |

完整修正歷史：[`../2026-04-29-mount-measurement.md`](../2026-04-29-mount-measurement.md#yaw-修正歷史)
