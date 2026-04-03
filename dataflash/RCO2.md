# RCO2 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs extended servo/motor output channels (15-18).
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C15 .. C18** | Channel 15 through 18 raw pulse width output | microseconds (PWM) |
