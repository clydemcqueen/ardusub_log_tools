# PM DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs autopilot system performance and general diagnostic data.
**Location**: `libraries/AP_Logger/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **NLon** | Number of long loops | |
| **NLoop** | Number of loops | |
| **MaxT** | Maximum loop time | microseconds |
| **Mem** | Free memory available | Bytes |
| **Load** | CPU load | 0 to 1000 |
| **IEL** | Internal error last line | |
| **Ierr** | Internal error bitmask | |
| **Ierc** | Internal error count | |
| **spic** | SPI transaction count | |
| **i2cc** | I2C transaction count | |
| **i2ci** | I2C ISR count | |
| **ExLoop** | Extra loop time | microseconds |
