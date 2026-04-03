# XKF3 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 innovations (difference between predicted and measured values).
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **IVN, IVE, IVD** | Innovation in velocity (N, E, D) | m/s |
| **IPN, IPE, IPD** | Innovation in position (N, E, D) | meters |
| **IMX, IMY, IMZ** | Innovation in magnetic field (Body X, Y, Z) | milli-Gauss |
| **IYAW** | Innovation in vehicle yaw | Degrees |
| **IVT** | Innovation in true-airspeed | m/s |
| **RErr** | Accumulated relative error | |
| **ErSc** | Consolidated error score | Higher = less healthy |
