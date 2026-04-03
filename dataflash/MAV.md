# MAV DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs MAVLink GCS link statistics.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **chan** | MAVLink channel number | |
| **Tx** | Transmitted packet count | |
| **RxS** | Successfully received packet count | |
| **RxD** | Dropped packet count | |
| **FL** | MAVLink flags | |
| **SS** | Stream slowdown | milliseconds |
| **TF** | Times the output buffer was full | |
