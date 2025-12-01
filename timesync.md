# Timestamps

## Summary

There are several clocks running on the ROV system, and timestamps are recorded several ways in the different logs.

We can align the timestamps for tlog and BIN logs and merge them into a single event stream. For GPS-enabled systems
this is trivial; for non-GPS systems this is still possible.

## Clocks

### ArduPilot Time Since Boot

ArduPilot has a 64-bit microsecond internal clock that starts when ArduPilot starts, often found in `time_boot_us` and `time_boot_ms` fields.
This clock is used throughout the code for all functions, including scheduling, EKF calculations and logging.

### ArduPilot Unix Time

ArduPilot also has an offset value (`rtc_shift`) that can be added to time-since-boot to get Unix time.
This can be set from several sources in priority order (`AP_RTC::source_type`):
* A hardware GPS driver, or MAVLink `GPS_INPUT` messages from an external GPS system (see below)
* MAVLink `SYSTEM_TIME` messages (see below)
* A hardware RTC (real-time clock) driver (not used by ArduSub)

ArduPilot periodically sends `SYSTEM_TIME` MAVLink messages that contain both `time_boot_ms` and `time_unix_usec` fields.
If `rtc_shift` is 0 then `time_unix_usec` is 0.

> TODO(clyde): is there a Linux RTC driver? Could we add one?

### GPS Time

All GPS (GNSS) receivers have accurate UTC time as long as they have a good fix. External GPS systems can provide this information 
by setting the `time_week` and `time_week_ms` fields in the `GPS_INPUT` messages sent to ArduPilot.

The WL UGPS extension sends `GPS_INPUT` messages, but [these do not contain UTC time](https://github.com/waterlinked/blueos-ugps-extension/issues/5).

### Raspberry Pi (BlueOS) Time

The Raspberry Pi does not have a real-time clock. The Pi cleverly remembers the last-known time, so timestamps are monotonic,
but time appears to fast-forward when the Pi connects to a network timeserver. Often this happens during boot, so you don't see it.

### Topside Time

The topside computer typically has a real-time clock, so it maintains the correct time even when it is not connected.

## Log Writers

### ArduPilot

ArduPilot writes time-since-boot in the `TimeUS` field of basically all dataflash messages in the BIN logs.
The exceptions are meta-records such as `FMT` that describe the format of the messages in the log.

The `LOG_DISARMED` parameter controls when ArduPilot starts logging:
* 0: ArduPilot starts logging when the vehicle is armed for the first time
* 1: ArduPilot starts logging immediately

> TODO(clyde): describe the log file naming method

> TODO(clyde): there is an RTC message in the code that could be logged when `rtc_shift` is set, but it is commented out

### QGroundControl

QGroundControl will send `SYSTEM_TIME` messages to ArduPilot with the topside time when it starts up.
This will set `rtc_shift` and ArduPilot will start reporting the topside time in `SYSTEM_TIME` messages.
However, this is not logged in the BIN files, as `GPS` records do not reference `rtc_shift`.

QGroundControl writes the topside time in the tlog file for each MAVLink message received. The units are microseconds 
from the UNIX epoch (64-bits), rounded to the nearest millisecond. This is stored as an 8-byte header before each message.

QGroundControl opens a new tlog file when it starts up. If you reboot QGroundControl, it will open a new file.

> TODO(clyde): describe the log file naming method

These MAVLink messages contain `time_boot_ms` fields with ArduPilot time:
* ATTITUDE
* GLOBAL_POSITION_INT
* RC_CHANNELS
* SCALED_IMU2
* SCALED_PRESSURE
* SCALED_PRESSURE2
* SYSTEM_TIME

This information can be used to compute the offset between time-since-boot time and topside time.

### BlueOS

Similar to QGroundControl, BlueOS writes the Raspberry Pi time in the tlog file as an 8-byte header before each message.

BlueOS opens a new tlog file when _the autopilot_ starts up. If you reboot the autopilot, it will open a new tlog file.
This is quite useful, as it means that BlueOS creates time-aligned log pairs (see below).

> TODO(clyde): describe the log file naming method

## Log Readers

### pymavlink

The pymavlink library can read tlog and BIN files. In both cases you can get the `_timestamp` attribute for a message:

~~~
timestamp = getattr(msg, '_timestamp', 0.0)  # float, seconds
~~~

There are three cases to consider:

For tlog files, _timestamp contains the 8-byte header from the log writer, either QGroundControl or BlueOS.

For BIN files where GPS time is available, _timestamp is the GPS time. The library cleverly scans the file
looking for a GPS record with non-zero time, computes a time offset, then rewinds the file and applies the offset using
the `TimeUS` fields.

For BIN files where GPS time is not available, _timestamp is the ArduPilot time (TimeUS converted to seconds).
Messages that lack a TimeUS field (such as FMT messages) inherit the timestamp of the previous message, or 0.0 if at the start of the log.

## Aligning MAVLink and Dataflash Logs

The easiest way to align logs is to make sure that GPS time ends up in both the tlog and BIN files.

Evidence that GPS time is not available:
* `GPS_INPUT` messages are not present in the tlog file
* `GPS_INPUT` messages have zeros for `time_week` and `time_week_ms`
* `GPS` messages are not present in the BIN file
* `GPS` messages have zeros for `GWk` and `GMS`
* `SYSTEM_TIME` messages from ArduPilot (sysid=1, compid=1) have zeros for `time_unix_usec`

Note:
* `GPS_INPUT.time_week` corresponds to `GPS.GWk`
* `GPS_INPUT.time_week_ms` corresponds to `GPS.GMS`

We can break the "no GPS" problem into two parts: (1) getting time-aligned log pairs and (2) merging them.

### Getting Time-Aligned Logs (No GPS)

BlueOS already creates time-aligned logs. Merging them creates an event stream on the Raspberry Pi clock.

For QGroundControl logs we need to do more work. This tool may be a good starting point for investigations: [dive.py](dive.py)

### Merging Time-Aligned Logs (No GPS)

We can infer the following:
* The `_timestamp` field for the tlog file contains either Raspberry Pi time (BlueOS) or topside time (QGC)
* The `_timestamp` field for the BIN file contains time-since-boot from the `TimeUS` fields, with no offset

Strategy:
* Find the first tlog message that contains a `time_boot_ms` field.
* Compute `rtc_shift = _timestamp - msg.time_boot_ms / 1e6` for that tlog message.
* Apply `rtc_shift` to all `_timestamp` values for BIN messages.
* Merge the two logs.

You can improve on this strategy by scanning the entire tlog file and finding the lowest `timestamp - msg.time_boot_ms / 1e6` value.

There is an implementation of this strategy in [dive_iter.py](dive_iter.py).

The BIN_merge.py tool supports this strategy with the experimental `--sync` option.

You can optimize this a bit more by using the [opt_rtc_shift.py](opt_rtc_shift.py) tool, though this is probably not necessary
for most applications.
