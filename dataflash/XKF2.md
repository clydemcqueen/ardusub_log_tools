# XKF2 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 estimator secondary outputs (biases, wind, magnetic field).
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **AX, AY, AZ** | Estimated accelerometer bias | m/s/s |
| **VWN, VWE** | Estimated wind velocity (North, East) | m/s |
| **MN, ME, MD** | Magnetic field strength (North, East, Down) | milli-Gauss |
| **MX, MY, MZ** | Magnetic field strength (Body X, Y, Z) | milli-Gauss |
| **IDX, IDY** | Innovation in vehicle drag acceleration | |
| **IS** | Innovation in vehicle sideslip | |
