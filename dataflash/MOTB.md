# MOTB DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs motor mixer and battery-related motor information.
**Location**: `libraries/AP_Motors/LogStructure.h` (referenced in `AP_Logger/LogStructure.h` as `log_MotBatt`)

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Max** | Maximum thrust available (lift_max) | |
| **Volt** | Battery voltage | Volts |
| **Limit** | Thrust limit | |
| **AVMax** | Average Max Thrust | |
| **Out** | Normalized motor output | |
| **Flags** | Motor failure flags | |
