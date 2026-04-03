# BARO DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs data from the barometer(s).
**Location**: `libraries/AP_Baro/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | Barometer instance number | 0-indexed |
| **Alt** | Calculated altitude | Meters |
| **Press** | Measured atmospheric pressure | Pascal |
| **Temp** | Measured atmospheric temperature | Degrees Celsius |
| **CRt** | Climb rate | m/s |
| **SMS** | Last sample time | milliseconds |
| **Offset** | Altitude offset | Meters |
| **GndTemp** | Ground temperature | Degrees Celsius |
| **Health** | 1 if healthy | Boolean |
