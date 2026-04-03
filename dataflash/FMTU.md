# FMTU DataFlash Message
Commit: abe1721cf5

**Purpose**: Associates units and multipliers with fields of other messages defined via FMT.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **FmtType** | Reference to the Message ID in FMT | |
| **UnitIds** | Character sequence where each char maps to a unit in `log_Units` | char[16] |
| **MultIds** | Character sequence where each char maps to a multiplier in `log_Multipliers` | char[16] |
