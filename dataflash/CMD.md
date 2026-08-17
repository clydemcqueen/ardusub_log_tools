# CMD DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs uploaded mission command information.
**Location**: `libraries/AP_Mission/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **CTot** | Total number of mission commands | |
| **CNum** | Command sequence number / offset in mission | 0-indexed |
| **CId** | Command type / ID | See `MAV_CMD` |
| **Prm1** | Parameter 1 | |
| **Prm2** | Parameter 2 | |
| **Prm3** | Parameter 3 | |
| **Prm4** | Parameter 4 | |
| **Lat** | Command latitude | Degrees * 1e7 |
| **Lng** | Command longitude | Degrees * 1e7 |
| **Alt** | Command altitude | Meters |
| **Frame** | Coordinate frame used for position | See `MAV_FRAME` |
