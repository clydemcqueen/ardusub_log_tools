# MSG DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs textual messages from the autopilot (GCS messages).
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Message** | Text content | char[64] |
