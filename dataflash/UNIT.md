# UNIT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs the mapping from a single character ID to a full Sl unit name.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Id** | Unit character ID | e.g., 'm' for meters |
| **Unit** | Full unit name | char[64] |
