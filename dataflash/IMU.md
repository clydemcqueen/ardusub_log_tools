# IMU DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs Inertial Measurement Unit raw but filtered sensor data.
**Location**: `libraries/AP_InertialSensor/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | IMU instance number | 0-indexed |
| **GyrX** | Measured rotation rate about X axis | degrees/s |
| **GyrY** | Measured rotation rate about Y axis | degrees/s |
| **GyrZ** | Measured rotation rate about Z axis | degrees/s |
| **AccX** | Recorded acceleration along X axis | m/s/s |
| **AccY** | Recorded acceleration along Y axis | m/s/s |
| **AccZ** | Recorded acceleration along Z axis | m/s/s |
| **EG** | Percentage of gyroscope error samples | % |
| **EA** | Percentage of accelerometer error samples | % |
| **T** | Recorded IMU temperature | Degrees Celsius |
| **GH** | Gyroscope health | Boolean |
| **AH** | Accelerometer health | Boolean |
| **GHz** | Gyroscope measurement rate | Hertz |
| **AHz** | Accelerometer measurement rate | Hertz |
