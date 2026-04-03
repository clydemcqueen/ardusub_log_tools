# RCI2 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs extended Radio Control (RC) input channels (15-16) and status flags.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C15 .. C16** | Channel 15 and 16 raw pulse width | microseconds (PWM) |
| **OM** | Override Mask | Bitmask of overridden channels |
| **F** | Receiver flags | |
