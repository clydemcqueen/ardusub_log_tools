# RATE DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs desired and achieved vehicle attitude rates.
**Location**: `libraries/AP_AHRS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **RDes** | Desired roll rate | Degrees/s |
| **R** | Achieved roll rate | Degrees/s |
| **ROut** | Normalized output for Roll | 0 to 1 |
| **PDes** | Desired pitch rate | Degrees/s |
| **P** | Achieved pitch rate | Degrees/s |
| **POut** | Normalized output for Pitch | 0 to 1 |
| **YDes** | Desired yaw rate | Degrees/s |
| **Y** | Achieved yaw rate | Degrees/s |
| **YOut** | Normalized output for Yaw | 0 to 1 |
| **ADes** | Desired vertical acceleration | m/s/s |
| **A** | Achieved vertical acceleration | m/s/s |
| **AOut** | Normalized output for Throttle | 0 to 1 |
| **AOutSlew** | Throttle output slew rate | |
