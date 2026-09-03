# ERR DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs specifically coded error messages from various subsystems.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Subsys** | Subsystem in which the error occurred | See [`LogErrorSubsystem`](../docs/error_codes.md) |
| **ECode** | Subsystem-specific error code | See [`LogErrorCode`](../docs/error_codes.md) |

For a complete reference of all subsystems, error codes, and common dive event signatures, see [ArduSub Error Codes Guide](../docs/error_codes.md).
