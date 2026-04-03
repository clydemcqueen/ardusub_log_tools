# BAT DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs battery status information.
**Location**: `libraries/AP_BattMonitor/LogStructure.h`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **Inst** | Battery instance number | 0-indexed |
| **Volt** | Measured voltage | Volts |
| **VoltR** | Estimated resting voltage | Volts |
| **Curr** | Measured current | Amperes |
| **CurrTot** | Consumed capacity | Ampere-hours |
| **EnrgTot** | Consumed energy | Watt-hours |
| **Temp** | Battery temperature | Degrees Celsius |
| **Res** | Estimated battery resistance | Ohms |
| **RemPct** | Remaining percentage | % |
| **H** | Health | Boolean |
| **SH** | State of Health percentage | % |

## Implementation Notes (BlueROV2 / Navigator Board)
On the Blue Robotics Navigator board (the standard hardware for nearly all BlueROV2s), the analog battery monitor (`BATT_MONITOR = 4`) uses the ADS1115 ADC chip.

### Sampling Frequency
- **Logging Rate**: 10Hz (ArduSub logs BAT every 100ms).
- **Actual Update Rate**: **~1.66Hz**.
The Linux driver for the ADS1115 cycles through its 6 mux channels sequentially. Since it only reads and starts a new one every 100ms, each specific pin is only updated once every 600ms. In log files, this results in the same current (`Curr`) and voltage (`Volt`) value being repeated 5 or 6 times across consecutive entries. Any transients shorter than 600ms may be missed or softened.
