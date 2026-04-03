# GPA DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs GPS accuracy and diagnostic information.
**Location**: `libraries/AP_GPS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **I** | GPS instance number | 0-indexed |
| **VDop** | Vertical Dilution of Precision | cm (needs / 100) |
| **HAcc** | Horizontal position accuracy | meters |
| **VAcc** | Vertical position accuracy | meters |
| **SAcc** | Speed accuracy | m/s |
| **YAcc** | Yaw accuracy | degrees |
| **VV** | 1 if vertical velocity is available | Boolean |
| **SMS** | Sample time since startup | milliseconds |
| **Delta** | Time delta between the last two positions | milliseconds |
| **Und** | Geoid undulation | meters |
| **RTCMFU** | RTCM fragments used | |
| **RTCMFD** | RTCM fragments discarded | |
