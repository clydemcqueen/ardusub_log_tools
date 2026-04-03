# MODE DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs vehicle control mode changes.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Mode** | Current flight mode | See vehicle-specific `ControlMode` enum |
| **ModeNum** | Mode number (redundant with Mode) | |
| **Rsn** | Reason for the mode change | See `control_mode_reason` enum |
