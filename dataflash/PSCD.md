# PSCD DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs position controller diagnostics for the Down axis.
**Location**: `libraries/AP_Logger/LogStructure.h` (struct `log_PSCx`)

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **TPos** | Target position | Meters |
| **Pos** | Achieved position | Meters |
| **DVel** | Desired velocity | m/s |
| **TVel** | Target velocity | m/s |
| **Vel** | Achieved velocity | m/s |
| **DAcc** | Desired acceleration | m/s/s |
| **TAcc** | Target acceleration | m/s/s |
| **Acc** | Achieved acceleration | m/s/s |
