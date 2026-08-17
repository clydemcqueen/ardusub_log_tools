# AUXF DataFlash Message
Commit: abe1721cf5

**Purpose**: Logs auxiliary function invocation information.
**Location**: `libraries/RC_Channel/RC_Channel.cpp`

| Field | Description | Units/Note |
| :--- | :--- | :--- |
| **TimeUS** | Time since system startup | microseconds |
| **function** | ID of triggered function | See `RC_Channel::AUX_FUNC` enum |
| **pos** | Switch position when function triggered | 0: Low, 1: Middle, 2: High (`AuxSwitchPos`) |
| **source** | Source of auxiliary function invocation | 0: INIT, 1: RC, 2: BUTTON, 3: MAVLINK, 4: MISSION, 5: SCRIPTING (`AuxFuncTrigger::Source`) |
| **index** | Index within source | 0-indexed (RC channel index, button index, MAVLink channel number, mission item index; not used for scripting) |
| **result** | Result of function execution | 1 if successful, 0 otherwise |
