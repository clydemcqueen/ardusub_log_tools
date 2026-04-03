# RFND DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs data from distance sensors (Rangefinders/Sonar/Lidar).
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | Rangefinder instance number | 0-indexed |
| **Dist** | Measured distance | Meters |
| **Status** | Sensor status | See `AP_RangeFinder::RangeFinder_Status` |
| **Orient** | Sensor orientation | See `MAV_SENSOR_ORIENTATION` |
| **Qual** | Reading quality | 0 to 100 (if supported) |
