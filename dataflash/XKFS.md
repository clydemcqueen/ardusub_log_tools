# XKFS DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 sensor selection indices.
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **MI** | Compass selection index | |
| **BI** | Barometer selection index | |
| **GI** | GPS selection index | |
| **AI** | Airspeed selection index | |
| **SS** | Source Set index | (primary=0, secondary=1...) |
