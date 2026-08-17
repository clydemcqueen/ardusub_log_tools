# RTC DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs RTC (Unix time) information.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Epoch** | Current Unix epoch time | microseconds (since Jan 1 1970) |
| **SourceType** | Source of RTC data | 0: GPS, 1: MAVLINK_SYSTEM_TIME, 2: HW, 3: NONE (`AP_RTC::source_type`) |
