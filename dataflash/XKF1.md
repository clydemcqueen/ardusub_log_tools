# XKF1
Commit: abe1721cf5

This table contains EKF3 state data for a specific core.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Units | Description |
|---|---|---|
| TimeUS | us | Time since system boot |
| Core | | EKF Core index (0, 1, 2...) |
| Roll | deg | Roll angle |
| Pitch | deg | Pitch angle |
| Yaw | deg | Yaw angle |
| VelN | m/s | Velocity North |
| VelE | m/s | Velocity East |
| VelD | m/s | Velocity Down |
| PosD_dot | m/s | First derivative of down position |
| PosN | m | Position North |
| PosE | m | Position East |
| PosD | m | Position Down |
| GyrX | deg/s | Gyro bias X |
| GyrY | deg/s | Gyro bias Y |
| GyrZ | deg/s | Gyro bias Z |
| OriginHgt | m | WGS-84 altitude of EKF origin |
