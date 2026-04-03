# DSF DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs onboard logging (DataFlash) statistics.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Dp** | Number of times a write to the backend was rejected (dropped packets) | |
| **Blk** | Current block number | |
| **Bytes** | Current write offset | Bytes |
| **FMn** | Minimum free space in write buffer in last time period | Bytes |
| **FMx** | Maximum free space in write buffer in last time period | Bytes |
| **FAv** | Average free space in write buffer in last time period | Bytes |
