# POS DataFlash Message

**Purpose**: Logs the canonical vehicle position estimate from the AHRS (Attitude and Heading Reference System).
**Location**: `libraries/AP_AHRS/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Lat** | Canonical vehicle latitude | Degrees * 1e7 |
| **Lng** | Canonical vehicle longitude | Degrees * 1e7 |
| **Alt** | Canonical vehicle altitude | Meters |
| **RelHomeAlt** | Altitude relative to home | Meters |
| **RelOriginAlt** | Altitude relative to navigation origin | Meters |
