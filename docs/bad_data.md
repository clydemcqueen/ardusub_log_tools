# BAD_DATA Messages

If a MAVLink message is corrupted, many (all?) clients will return part of the data as a BAD_DATA message.

See the [tlog_bad_data.py](../tlog_bad_data.py) tool for details of how pymavlink handles this.

There is a well-known bug where CRC's are not calculated correctly, resulting in many erroneous BAD_DATA messages, or even crashes.

See these issues:
* https://github.com/bluerobotics/BlueOS/issues/1740
* https://github.com/ArduPilot/pymavlink/issues/237
* https://github.com/ArduPilot/pymavlink/issues/807
* https://github.com/mavlink/mavlink2rest/issues/80
* https://github.com/mavlink/rust-mavlink/issues/188

There is a simple workaround when working with pymavlink:
~~~bash
echo "Tell pymavlink to ignore CRC errors"
export MAV_IGNORE_CRC=1
~~~
