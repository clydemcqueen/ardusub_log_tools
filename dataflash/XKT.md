# XKT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 timing information and sample intervals.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **Cnt** | Sample count used for this message | |
| **IMUMin, IMUMax** | Min/Max IMU sample interval | seconds |
| **EKFMin, EKFMax** | Min/Max EKF average time step | seconds |
| **AngMin, AngMax** | Min/Max delta angle measurement interval | seconds |
| **VMin, VMax** | Min/Max delta velocity measurement interval | seconds |
