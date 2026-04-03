# ATSC DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs scale factors for the attitude controller, typically used when dynamic gain scaling is active.
**Location**: `libraries/AP_AHRS/LogStructure.h` (defined in `log_ATSC`)

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **AngPScX** | Angle P scale X | |
| **AngPScY** | Angle P scale Y | |
| **AngPScZ** | Angle P scale Z | |
| **PDScX** | PD scale X | |
| **PDScY** | PD scale Y | |
| **PDScZ** | PD scale Z | |
