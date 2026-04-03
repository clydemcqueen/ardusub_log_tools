# FILE DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs file transfer or system file data chunks.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **Name** | Filename | char[16] |
| **Off** | Offset in the file | Bytes |
| **Len** | Data length in this packet | Bytes |
| **Data** | File content chunk | char[64] |
