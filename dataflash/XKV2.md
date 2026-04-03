# XKV2 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 state variances (primary core) for states 12 through 23.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description |
| :--- | :--- |
| **TimeUS** | Time since system startup |
| **C** | Core index |
| **V12 .. V23** | Variances for states 12-23 |
