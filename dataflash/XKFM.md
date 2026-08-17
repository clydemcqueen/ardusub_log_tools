# XKFM DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 diagnostic data for on-ground-and-not-moving check.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | 0-indexed |
| **OGNM** | True if on ground and not moving | Boolean (1 = True, 0 = False) |
| **GLR** | Gyroscope length ratio | |
| **ALR** | Accelerometer length ratio | |
| **GDR** | Gyroscope rate of change ratio | |
| **ADR** | Accelerometer rate of change ratio |
