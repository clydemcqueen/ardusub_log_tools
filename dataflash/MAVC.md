# MAVC DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs MAVLink commands just executed or being executed.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **TSys** | Target System ID | |
| **TCmp** | Target Component ID | |
| **SSys** | Source System ID | |
| **SCmp** | Source Component ID | |
| **Frame** | Coordinate frame used | |
| **Cmd** | MAVLink command ID | |
| **P1** | Parameter 1 | |
| **P2** | Parameter 2 | |
| **P3** | Parameter 3 | |
| **P4** | Parameter 4 | |
| **X** | X position or Param 5 | |
| **Y** | Y position or Param 6 | |
| **Z** | Z position or Param 7 | |
| **Res** | Command result (ACK code) | See `MAV_RESULT` |
| **WL** | Was command long (TRUE/FALSE) | |
