# XKFD DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 body-frame odometry errors (innovations and variances).
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **IX, IY, IZ** | Innovation in velocity (Body X, Y, Z) | m/s |
| **IVX, IVY, IVZ** | Variance in velocity (Body X, Y, Z) | |
