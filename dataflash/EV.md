# EV DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs specifically coded event messages (e.g., mode changes, arming events).
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Id** | Event identifier | See `LogEvent` enum |
