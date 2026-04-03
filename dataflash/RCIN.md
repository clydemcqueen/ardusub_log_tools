# RCIN DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs the first 14 channels of Radio Control (RC) input.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C1 .. C14** | Channel 1 through 14 raw pulse width | microseconds (PWM) |
