# MNT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs mount (gimbal) desired and actual roll, pitch, and yaw angles.
**Location**: `libraries/AP_Mount/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | Mount instance number | 0-indexed |
| **DRoll** | Desired roll angle | Degrees |
| **Roll** | Actual roll angle | Degrees |
| **DPitch** | Desired pitch angle | Degrees |
| **Pitch** | Actual pitch angle | Degrees |
| **DYawB** | Desired yaw in body frame | Degrees |
| **YawB** | Actual yaw in body frame | Degrees |
| **DYawE** | Desired yaw in earth frame | Degrees |
| **YawE** | Actual yaw in earth frame | Degrees |
| **Dist** | Rangefinder distance from mount | Meters |
