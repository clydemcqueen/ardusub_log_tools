# VISO DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs Visual Odometry body-frame deltas.
**Location**: `libraries/AP_VisualOdom/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | System time | microseconds |
| **dt** | Time period this data covers | seconds |
| **AngDX** | Angular change roll | radians |
| **AngDY** | Angular change pitch | radians |
| **AngDZ** | Angular change yaw | radians |
| **PosDX** | Position change X (Forward) | meters |
| **PosDY** | Position change Y (Right) | meters |
| **PosDZ** | Position change Z (Down) | meters |
| **conf** | Confidence | 0.0 to 1.0 |
