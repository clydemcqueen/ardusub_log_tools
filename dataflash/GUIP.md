# GUIP

The GUIP table contains GUIDED mode target position and velocity information for Sub, Rover, and Copter:
* Sub: units are cm and cm/s.
* Rover: units are cm and cm/s. The frame field is not used.
* Copter: units are m and m/s.

| Field | Units | Description |
|---|---|---|
| TimeUS | s | Timestamp |
| Type | - | Target type |
| Frame | - | Altitude frame |
| pX | cm | Target Position X |
| pY | cm | Target Position Y |
| pZ | cm | Target Position Z |
| vX | cm/s | Target Velocity X |
| vY | cm/s | Target Velocity Y |
| vZ | cm/s | Target Velocity Z |
