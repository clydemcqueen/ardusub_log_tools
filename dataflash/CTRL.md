# CTRL DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs attitude control oscillation monitor diagnostics.
**Location**: `libraries/AC_AttitudeControl/ControlMonitor.cpp`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **RMSRollP** | LPF Root-Mean-Squared Roll Rate controller P+FF gain effect | |
| **RMSRollD** | LPF Root-Mean-Squared Roll rate controller D gain effect | |
| **RMSPitchP** | LPF Root-Mean-Squared Pitch Rate controller P+FF gain effect | |
| **RMSPitchD** | LPF Root-Mean-Squared Pitch Rate controller D gain effect | |
| **RMSYaw** | LPF Root-Mean-Squared Yaw Rate controller P+D+FF gain effect | |
