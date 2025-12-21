# GPS DataFlash Message

**Purpose**: Logs information received from GNSS (Global Navigation Satellite System) systems attached to the autopilot.
**Location**: `libraries/AP_GPS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | GPS instance number | 0-indexed |
| **Status** | GPS Fix type | 2D fix, 3D fix, etc. (See `AP_GPS::GPS_Status`) |
| **GMS** | Milliseconds since start of GPS Week | ms |
| **GWk** | Weeks since 5 Jan 1980 | |
| **NSats** | Number of satellites visible | |
| **HDop** | Horizontal dilution of precision | |
| **Lat** | Latitude | Degrees * 1e7 |
| **Lng** | Longitude | Degrees * 1e7 |
| **Alt** | Altitude | Meters |
| **Spd** | Ground speed | m/s |
| **GCrs** | Ground course | Degrees |
| **VZ** | Vertical speed | m/s |
| **Yaw** | Vehicle yaw | Degrees |
| **U** | Used | Boolean (1 if used for navigation) |
