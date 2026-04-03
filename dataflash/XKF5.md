# XKF5 DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs EKF3 sensor innovations and additional diagnostics (Optical Flow, Rangefinder, Terrain).
**Location**: `libraries/AP_NavEKF3/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **C** | EKF3 core index | |
| **NI** | Normalised flow innovation | |
| **FIX, FIY** | Optical flow LOS rate vector innovations | |
| **AFI** | Optical flow innovation from terrain offset estimator | |
| **HAGL** | Height Above Ground Level | Meters |
| **offset** | Estimated vertical position of terrain rel to datum | Meters |
| **RI** | Range finder innovations | Meters |
| **rng** | Measured range | Meters |
| **Herr** | Filter ground offset state error | |
| **eAng, eVel, ePos** | Magnitudes of angular, velocity, and position errors | |
