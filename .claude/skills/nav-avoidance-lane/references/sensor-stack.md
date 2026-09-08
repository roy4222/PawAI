# Sensor／座標核對

依本次實體安裝與設定確認 LiDAR 前向、base_link→laser、相機 extrinsics、地圖方向與初始朝向。舊 mount、yaw、scan rate、距離閾值與 map 路徑都不是現在的校正值。

用現場已知方向的物件對照 camera、scan／depth 及 TF；同時核對來源 timestamp、arrival、有限距離比例、丟包與 stale 行為。裝置節點存在不代表資料有效，frame 有資料不代表下游安全 consumer 正在使用。

查目前 launch 的 FPS／topic rate 設定，再量實際輸出，不套用互相矛盾的舊 15／30Hz 標準。安全距離還受機體外形、速度、延遲與制動影響，不能直接沿用舊單一數字。
