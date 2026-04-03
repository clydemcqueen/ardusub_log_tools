# ERR DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs specifically coded error messages from various subsystems.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Subsys** | Subsystem in which the error occurred | See `LogErrorSubsystem` enum |
| **ECode** | Subsystem-specific error code | See `LogErrorCode` for the subsystem |
