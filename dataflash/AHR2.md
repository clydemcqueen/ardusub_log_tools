# AHR2 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs backup AHRS (Attitude and Heading Reference System) data, typically from the secondary estimator or a simpler complementary filter.
**Location**: `libraries/AP_AHRS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Roll** | Estimated roll | Degrees |
| **Pitch** | Estimated pitch | Degrees |
| **Yaw** | Estimated yaw | Degrees |
| **Alt** | Estimated altitude | Meters |
| **Lat** | Estimated latitude | Degrees * 1e7 |
| **Lng** | Estimated longitude | Degrees * 1e7 |
| **Q1** | Attitude quaternion component 1 | |
| **Q2** | Attitude quaternion component 2 | |
| **Q3** | Attitude quaternion component 3 | |
| **Q4** | Attitude quaternion component 4 | |
