# PIDR DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs PID roll gain values and controller state.
**Location**: `libraries/AC_PID/LogStructure.h` (referenced via `PID_LABELS` in `AP_Logger/LogStructure.h`)

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Tar** | Target value for the controller | |
| **Act** | Actual achieved value | |
| **Err** | Error (Target - Actual) | |
| **P** | Proportional component of output | |
| **I** | Integral component of output | |
| **D** | Derivative component of output | |
| **FF** | Feed-forward component of output | |
| **DFF** | Derivative feed-forward component | |
| **Dmod** | Derivative modulation | |
| **SRate** | Slew rate | |
| **Flags** | Controller flags | Bitmask |
