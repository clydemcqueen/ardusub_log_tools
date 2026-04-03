# MULT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs the mapping from a single character to a numeric multiplier.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Id** | Multiplier character ID | e.g., 'C' for 0.001 |
| **Mult** | Numeric multiplier value | |
