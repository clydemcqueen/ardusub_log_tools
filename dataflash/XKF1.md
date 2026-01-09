# XKF1

This table contains EKF3 state data for a specific core.

| Field | Units | Description |
|---|---|---|
| TimeUS | us | Time since system boot |
| Core | | EKF Core index (0, 1, 2...) |
| Roll | cdeg | Roll angle |
| Pitch | cdeg | Pitch angle |
| Yaw | cdeg | Yaw angle |
| VelN | m/s | Velocity North |
| VelE | m/s | Velocity East |
| VelD | m/s | Velocity Down |
| PosD_dot | m/s | First derivative of down position |
| PosN | m | Position North |
| PosE | m | Position East |
| PosD | m | Position Down |
| GyrX | cdeg/s | Gyro bias X |
| GyrY | cdeg/s | Gyro bias Y |
| GyrZ | cdeg/s | Gyro bias Z |
| OriginHgt | cm | WGS-84 altitude of EKF origin |
