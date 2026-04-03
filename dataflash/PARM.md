# PARM DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs individual parameter values, typically recorded at startup or when changed.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Name** | Parameter name | char[16] |
| **Value** | Current parameter value | float |
| **Default** | Default parameter value | float |
| **Type** | Parameter type (optional in some formats) | |
