# ARM DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs changes in the vehicle's arming status.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **ArmState** | 1 if Armed, 0 if Disarmed | Boolean |
| **ArmChecks** | Bitmask of arming checks performed | See `AP_Arming::ArmingChecks` |
| **Forced** | 1 if the arm/disarm was forced | Boolean |
| **Method** | Method used for arming | See `AP_Arming::Method` |
