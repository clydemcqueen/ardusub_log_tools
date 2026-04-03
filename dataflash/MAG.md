# MAG DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs data from the compass(es).
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | Compass instance number | 0-indexed |
| **MagX** | Magnetic field X-axis | milli-Gauss |
| **MagY** | Magnetic field Y-axis | milli-Gauss |
| **MagZ** | Magnetic field Z-axis | milli-Gauss |
| **OffX** | Hardware offset X-axis | |
| **OffY** | Hardware offset Y-axis | |
| **OffZ** | Hardware offset Z-axis | |
| **MOffX** | Motor compensation offset X-axis | |
| **MOffY** | Motor compensation offset Y-axis | |
| **MOffZ** | Motor compensation offset Z-axis | |
| **Health** | 1 if compass is healthy | Boolean |
| **SUS** | Compass timestamp or specific status | |
