# VIBE DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs processed vibration information from the accelerometers.
**Location**: `libraries/AP_InertialSensor/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **IMU** | Vibration instance number | 0-indexed |
| **VibeX** | Primary accelerometer filtered vibration, x-axis | m/s/s |
| **VibeY** | Primary accelerometer filtered vibration, y-axis | m/s/s |
| **VibeZ** | Primary accelerometer filtered vibration, z-axis | m/s/s |
| **Clip** | Cumulative number of clipping events (accelerometer saturation) | |
