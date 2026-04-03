# DCM DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs DCM (Direction Cosine Matrix) estimator data (roll, pitch, yaw).
**Location**: `libraries/AP_AHRS/AP_AHRS_DCM.cpp`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Roll** | DCM estimated roll | Degrees |
| **Pitch** | DCM estimated pitch | Degrees |
| **Yaw** | DCM estimated yaw | Degrees |
