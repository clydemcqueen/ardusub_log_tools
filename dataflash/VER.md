# VER DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs hardware and firmware version information.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Board** | Board type | |
| **Sub** | Board subtype | |
| **Maj** | Firmware major version | |
| **Min** | Firmware minor version | |
| **Ptr** | Firmware patch version | |
| **Type** | Firmware type | |
| **Git** | Git hash | 32-bit hex |
| **Fw** | Firmware string | char[64] |
| **BID** | APJ Board ID | |
| **BType** | Build type | |
