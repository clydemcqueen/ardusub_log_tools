# XKQ DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs the EKF3 quaternion defining the rotation from NED to XYZ (autopilot body) axes.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **Q1, Q2, Q3, Q4** | Attitude quaternion components | |
