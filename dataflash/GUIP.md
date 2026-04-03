# GUIP
Commit: abe1721cf5

The GUIP table contains GUIDED mode target position and velocity information for Sub, Rover, and Copter.
**Location**: `ArduSub/Log.cpp`

| Field | Units | Description |
|---|---|---|
| TimeUS | us | Timestamp |
| Type | - | Target type |
| pX | m | Target Position X (Local ENU) |
| pY | m | Target Position Y (Local ENU) |
| pZ | m | Target Position Z (Local ENU) |
| vX | m/s | Target Velocity X |
| vY | m/s | Target Velocity Y |
| vZ | m/s | Target Velocity Z |

Note: ArduSub units are meters and m/s (contrary to older notes about cm). In the code `QBffffff` with units `s-mmmnnn` and multipliers `F-000000`, 'm' is meters and 'n' is m/s. Multiplier '0' is 1.0.
