# ArduSub 4.5 Error Codes and Subsystems Reference

## Overview

ArduSub logs discrete subsystem error events to the Dataflash log under the **`ERR`** message type. These messages capture hardware faults, failsafe triggers, sensor glitches, mode changes, and subsequent recoveries.

In the ArduSub 4.5 firmware source code, these are declared in [`libraries/AP_Logger/AP_Logger.h`](../../ap/ap_Sub-4.5/libraries/AP_Logger/AP_Logger.h) and logged using the `LOGGER_WRITE_ERROR(subsys, err)` macro or `AP_Logger::Write_Error(subsys, err)`.

### Message Schema (`ERR`)

| Field | Type | Description |
|:---|:---|:---|
| **`TimeUS`** | `uint64_t` | Autopilot boot time in microseconds |
| **`Subsys`** | `uint8_t` | Subsystem identifier enum (`LogErrorSubsystem`) |
| **`ECode`** | `uint8_t` | Subsystem-specific error code enum (`LogErrorCode`) |

---

## Subsystems Reference (`LogErrorSubsystem`)

| ID | Name | ArduSub Context & Description |
|---:|:---|:---|
| **1** | `MAIN` | Main scheduler loop delay or INS timing delay |
| **2** | `RADIO` | RC / joystick packet timing |
| **3** | `COMPASS` | Magnetometer initialization and runtime health checks |
| **4** | `OPTFLOW` | Optical flow sensor (not typically used in ArduSub) |
| **5** | `FAILSAFE_RADIO` | Radio / RC receiver failsafe |
| **6** | `FAILSAFE_BATT` | Battery failsafe (low voltage / remaining capacity) |
| **7** | `FAILSAFE_GPS` | GPS failsafe (not used in ArduSub) |
| **8** | `FAILSAFE_GCS` | Ground Control Station telemetry / heartbeat timeout |
| **9** | `FAILSAFE_FENCE` | Geofence breach |
| **10** | `FLIGHT_MODE` | Flight mode change failure (rejected mode) |
| **11** | `GPS` | GPS sensor initialization, glitches, or health check |
| **12** | `CRASH_CHECK` | Crash or loss of vehicle control detected |
| **13** | `FLIP` | Flip mode abandoned (Copter only) |
| **14** | `AUTOTUNE` | Autotune failed (not used in ArduSub) |
| **15** | `PARACHUTES` | Parachute deployment failure (not used in ArduSub) |
| **16** | `EKFCHECK` | Extended Kalman Filter innovation/variance threshold check |
| **17** | `FAILSAFE_EKFINAV` | EKF / Inertial Navigation failsafe |
| **18** | `BARO` | External pressure / depth sensor health, glitches, or bad depth |
| **19** | `CPU` | Main loop CPU overload / scheduler delay failsafe |
| **20** | `FAILSAFE_ADSB` | ADS-B avoidance failsafe (not used in ArduSub) |
| **21** | `TERRAIN` | Terrain following data lookup failure |
| **22** | `NAVIGATION` | Navigation controller errors (destination outside fence, circle init) |
| **23** | `FAILSAFE_TERRAIN` | Terrain altitude failsafe |
| **24** | `EKF_PRIMARY` | EKF primary core switch |
| **25** | `THRUST_LOSS_CHECK` | Motor / thruster loss of control check |
| **26** | `FAILSAFE_SENSORS` | Critical sensor failure (e.g. depth sensor lost) |
| **27** | `FAILSAFE_LEAK` | Water ingress / leak detector probe triggered |
| **28** | `PILOT_INPUT` | Pilot manual control (joystick/controller) heartbeat lost |
| **29** | `FAILSAFE_VIBE` | High vibration failsafe |
| **30** | `INTERNAL_ERROR` | ArduPilot internal software / memory sanity check failure |
| **31** | `FAILSAFE_DEADRECKON` | Dead reckoning failsafe |

---

## Error Codes by Subsystem (`LogErrorCode`)

In ArduPilot's `LogErrorCode` enumeration, the interpretation of `ECode` is contextual and depends on `Subsys`.

### 1. Failsafe Subsystems
Applicable to: `FAILSAFE_LEAK` (27), `PILOT_INPUT` (28), `FAILSAFE_GCS` (8), `FAILSAFE_BATT` (6), `FAILSAFE_RADIO` (5), `FAILSAFE_EKFINAV` (17), `CPU` (19), `FAILSAFE_TERRAIN` (23), `THRUST_LOSS_CHECK` (25), `FAILSAFE_VIBE` (29), `FAILSAFE_DEADRECKON` (31).

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `FAILSAFE_RESOLVED` | The failsafe condition cleared and normal operation resumed |
| **1** | `FAILSAFE_OCCURRED` | The failsafe threshold was tripped and failsafe action initiated |

> [!IMPORTANT]
> `ECode=0` represents a **cleared** state (`RESOLVED`), not a failure. In analysis tools, rows with `ECode=0` should be presented as recoveries or notices rather than active alarms.

---

### 2. Leak Detector (`FAILSAFE_LEAK`, Subsys 27)
Managed in [`ArduSub/failsafe.cpp`](../../ap/ap_Sub-4.5/ArduSub/failsafe.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `FAILSAFE_RESOLVED` | Leak detector is dry / leak cleared |
| **1** | `FAILSAFE_OCCURRED` | Leak detector triggered (water ingress sensed in enclosure) |

---

### 3. Pilot Manual Control (`PILOT_INPUT`, Subsys 28)
Managed in [`ArduSub/failsafe.cpp`](../../ap/ap_Sub-4.5/ArduSub/failsafe.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `FAILSAFE_RESOLVED` | Joystick/controller packets received within timeout |
| **1** | `FAILSAFE_OCCURRED` | Lost manual control (no `MANUAL_CONTROL` packets within `FS_PILOT_TIMEOUT`) |

---

### 4. Ground Control Station (`FAILSAFE_GCS`, Subsys 8)
Managed in [`ArduSub/failsafe.cpp`](../../ap/ap_Sub-4.5/ArduSub/failsafe.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `FAILSAFE_RESOLVED` | GCS telemetry connection restored |
| **1** | `FAILSAFE_OCCURRED` | GCS heartbeat lost |

---

### 5. Compass / Magnetometer (`COMPASS`, Subsys 3)
Logged from [`libraries/AP_Compass/AP_Compass.cpp`](../../ap/ap_Sub-4.5/libraries/AP_Compass/AP_Compass.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Compass healthy / healthy state confirmed on boot |
| **1** | `FAILED_TO_INITIALISE` | Compass driver failed to initialize |
| **4** | `UNHEALTHY` | Compass reading marked unhealthy (excessive noise / missing samples) |

---

### 6. Barometer / Depth Sensor (`BARO`, Subsys 18)
Logged from [`libraries/AP_Baro/AP_Baro.cpp`](../../ap/ap_Sub-4.5/libraries/AP_Baro/AP_Baro.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Pressure / depth sensor healthy |
| **1** | `FAILED_TO_INITIALISE` | Sensor failed to initialize |
| **2** | `BARO_GLITCH` | Pressure spike / glitch detected |
| **3** | `BAD_DEPTH` | Pressure sensor returned an impossible or out-of-range depth |
| **4** | `UNHEALTHY` | Primary pressure sensor unhealthy |

---

### 7. Critical Sensor Failsafe (`FAILSAFE_SENSORS`, Subsys 26)
Logged from [`ArduSub/failsafe.cpp`](../../ap/ap_Sub-4.5/ArduSub/failsafe.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Depth sensor returned to healthy state |
| **1** | `FAILSAFE_OCCURRED` | Critical sensor failsafe active |
| **3** | `BAD_DEPTH` | Depth sensor unhealthy while in depth-dependent mode (e.g. ALT_HOLD, SURFTRAK) |

---

### 8. GPS (`GPS`, Subsys 11)
Logged from [`libraries/AP_GPS/AP_GPS.cpp`](../../ap/ap_Sub-4.5/libraries/AP_GPS/AP_GPS.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | GPS lock healthy |
| **1** | `FAILED_TO_INITIALISE` | GPS receiver failed to initialize |
| **2** | `GPS_GLITCH` | GPS position glitch detected |
| **4** | `UNHEALTHY` | GPS fix lost or unhealthy |

---

### 9. EKF Variance Check (`EKFCHECK`, Subsys 16)
Logged from [`ArduSub/failsafe.cpp`](../../ap/ap_Sub-4.5/ArduSub/failsafe.cpp):

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `EKFCHECK_VARIANCE_CLEARED` | EKF innovation / variance returned within bounds |
| **2** | `EKFCHECK_BAD_VARIANCE` | Compass, velocity, or position variance exceeded limit |

---

### 10. Flight Mode Change Failure (`FLIGHT_MODE`, Subsys 10)
Logged from [`ArduSub/mode.cpp`](../../ap/ap_Sub-4.5/ArduSub/mode.cpp). When a mode change fails or is rejected, `ECode` contains the target ArduSub flight mode number:

| ECode | Mode Name | Description |
|---:|:---|:---|
| **0** | `STABILIZE` | Manual angle stabilization with manual throttle |
| **1** | `ACRO` | Angular rate control with manual throttle |
| **2** | `ALT_HOLD` | Automatic depth/altitude hold |
| **3** | `AUTO` | Autonomous mission execution |
| **4** | `GUIDED` | Guided autonomous navigation to target |
| **7** | `CIRCLE` | Circular loiter |
| **9** | `SURFACE` | Automatic ascent to water surface |
| **16** | `POSHOLD` | Automatic horizontal position & depth hold |
| **19** | `MANUAL` | Raw thruster pass-through (no stabilization) |
| **20** | `MOTOR_DETECT` | Motor rotation auto-detection routine |
| **21** | `SURFTRAK` | Seafloor terrain tracking via rangefinder / DVL |

---

### 11. Geofence Failsafe (`FAILSAFE_FENCE`, Subsys 9)
Logged from [`ArduSub/fence.cpp`](../../ap/ap_Sub-4.5/ArduSub/fence.cpp). `ECode=0` indicates all fence breaches cleared. Non-zero values represent a bitmask of active fence breach types:

| ECode / Bit | Breach Type | Description |
|---:|:---|:---|
| **0** | `FAILSAFE_RESOLVED` | Geofence breach resolved |
| **1** | `ALT_MAX` | Maximum altitude / depth breach |
| **2** | `CIRCLE` | Circular radius breach |
| **4** | `POLYGON` | Polygon boundary breach |
| **8** | `ALT_MIN` | Minimum altitude / seafloor distance breach |

---

### 12. Navigation Controller (`NAVIGATION`, Subsys 22)

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Navigation controller error cleared |
| **2** | `FAILED_TO_SET_DESTINATION` | Controller unable to calculate trajectory to waypoint |
| **3** | `RESTARTED_RTL` | RTL re-initiated |
| **4** | `FAILED_CIRCLE_INIT` | Circle mode initialization failed |
| **5** | `DEST_OUTSIDE_FENCE` | Commanded destination lies outside the active geofence |
| **6** | `RTL_MISSING_RNGFND` | RTL aborted due to missing rangefinder data |

---

### 13. Crash / Loss of Control Checker (`CRASH_CHECK`, Subsys 12)

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Crash condition cleared |
| **1** | `CRASH_CHECK_CRASH` | Collision / physical crash detected |
| **2** | `CRASH_CHECK_LOSS_OF_CONTROL` | Attitude deviation indicates loss of control |

---

### 14. EKF Primary Core Switch (`EKF_PRIMARY`, Subsys 24)
`ECode` indicates the zero-based core index (`0`, `1`, etc.) that became the primary estimation filter.

---

### 15. ArduPilot Internal Software Error (`INTERNAL_ERROR`, Subsys 30)

| ECode | Enum Name | Meaning |
|---:|:---|:---|
| **0** | `ERROR_RESOLVED` | Internal error condition resolved |
| **1** | `INTERNAL_ERRORS_DETECTED` | Internal software sanity check failed (see `InternalError` counter) |

---

## Common Dive Log Signatures Explained

### 1. Typical Autopilot Startup Sequence (at Boot ~2.5s - 3.2s)
```markdown
| Time | Source | Type | Severity | Event Summary | Details |
|---|---|---|---|---|---|
| 09:02:46 | 00000156.BIN | ERROR | RESOLVED | 🟢 Autopilot Error: Subsys=3 (COMPASS), ECode=0 (ERROR_RESOLVED) | TimeUS=2615058 |
| 09:02:46 | 00000156.BIN | ERROR | ERROR    | 🔴 Autopilot Error: Subsys=27 (FAILSAFE_LEAK), ECode=1 (FAILSAFE_OCCURRED) | TimeUS=2845066 |
| 09:02:46 | 00000156.BIN | ERROR | ERROR    | 🔴 Autopilot Error: Subsys=28 (PILOT_INPUT), ECode=1 (FAILSAFE_OCCURRED) | TimeUS=3000047 |
| 09:02:46 | 00000156.BIN | ERROR | RESOLVED | 🟢 Autopilot Error: Subsys=27 (FAILSAFE_LEAK), ECode=0 (FAILSAFE_RESOLVED) | TimeUS=3175113 |
```
- **`Subsys=3, ECode=0`**: The compass initialized and passed its initial health check.
- **`Subsys=27, ECode=1` followed by `ECode=0`**: Transient high reading during sensor power-on / pin pullup settling on the leak sensor input. Clears within 300 ms.
- **`Subsys=28, ECode=1`**: The autopilot booted before receiving manual joystick packets over the tether (`"Lost manual control"`). Clears as soon as QGroundControl / BlueOS initiates joystick stream.

### 2. GCS Telemetry Dropouts During Dive
```markdown
| 10:59:15 | 00000162.BIN | ERROR | ERROR    | 🔴 Autopilot Error: Subsys=8 (FAILSAFE_GCS), ECode=1 (FAILSAFE_OCCURRED) | TimeUS=135794085 |
| 10:59:15 | 00000162.BIN | ERROR | RESOLVED | 🟢 Autopilot Error: Subsys=8 (FAILSAFE_GCS), ECode=0 (FAILSAFE_RESOLVED) | TimeUS=136124110 |
```
- Brief 330 ms tether ethernet or MAVLink routing hiccup where telemetry heartbeats dropped and immediately recovered.
