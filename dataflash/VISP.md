# VISP DataFlash Message -- from VISION_POSITION_ESTIMATE MAVLink messages
Commit: 740cbb712b

**Purpose**: Logs Vision Position estimates.
**Location**: `libraries/AP_VisualOdom/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | System time | microseconds |
| **RTimeUS** | Remote system time | microseconds |
| **CTimeMS** | Corrected system time | milliseconds |
| **PX** | Position X-axis (North-South) | meters |
| **PY** | Position Y-axis (East-West) | meters |
| **PZ** | Position Z-axis (Down-Up) | meters |
| **R** | Roll lean angle | degrees |
| **P** | Pitch lean angle | degrees |
| **Y** | Yaw angle | degrees |
| **PErr** | Position estimate error | meters |
| **AErr** | Attitude estimate error | radians |
| **Rst** | Position reset counter | |
| **Ign** | Ignored | |
| **Q** | Quality | |
