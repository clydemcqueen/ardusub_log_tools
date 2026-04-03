# CTUN DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs control tuning information, primarily related to altitude and throttle control.
**Location**: `ArduSub/Log.cpp`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **ThI** | Throttle input | 0 to 1 |
| **ABst** | Angle boost | |
| **ThO** | Throttle output | 0 to 1 |
| **ThH** | Calculated hover throttle | 0 to 1 |
| **DAlt** | Desired altitude | Meters |
| **Alt** | Achieved altitude | Meters |
| **BAlt** | Barometric altitude | Meters |
| **DSAlt** | Desired rangefinder altitude | Meters |
| **SAlt** | Achieved rangefinder altitude | Meters |
| **TAlt** | Terrain altitude | Meters |
| **DCRt** | Desired climb rate | m/s |
| **CRt** | Climb rate | m/s |
