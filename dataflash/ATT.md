# ATT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs the canonical vehicle attitude (achieved vs desired).
**Location**: `libraries/AP_AHRS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **DesRoll** | Desired roll angle | Degrees |
| **Roll** | Achieved roll angle | Degrees |
| **DesPitch** | Desired pitch angle | Degrees |
| **Pitch** | Achieved pitch angle | Degrees |
| **DesYaw** | Desired yaw angle | Degrees |
| **Yaw** | Achieved yaw angle | Degrees |
| **ErrRP** | Roll/Pitch error (lowest gyro drift estimate) | Degrees |
| **ErrYaw** | Yaw error | Degrees |
| **AEKF** | Active EKF type | |
