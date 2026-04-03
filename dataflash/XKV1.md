# XKV1 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 state variances (primary core) for states 0 through 11.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description |
| :--- | :--- |
| **TimeUS** | Time since system startup |
| **C** | Core index |
| **V00 .. V11** | Variances for states 0-11 |
