# XKF4 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 variances and health status.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **SV** | Squared Innovation Test Ratio for Velocity | < 1 means accepted |
| **SP** | Squared Innovation Test Ratio for Position | < 1 means accepted |
| **SH** | Squared Innovation Test Ratio for Height | < 1 means accepted |
| **SM** | Squared Innovation Test Ratio for Magnetic Field | < 1 means accepted |
| **SVT** | Squared Innovation Test Ratio for Airspeed | < 1 means accepted |
| **errRP** | Filtered error in roll/pitch estimate | Degrees |
| **OFN, OFE** | Most recent position reset (North, East) | Meters |
| **FS** | Filter fault status bitmask | |
| **TS** | Filter timeout status bitmask | |
| **SS** | Filter solution status | |
| **GPS** | Filter GPS status | |
| **PI** | Primary core index | |
