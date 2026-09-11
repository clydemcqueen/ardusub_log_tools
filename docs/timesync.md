# Timestamps

## Summary

There are several clocks running on the ROV system, and timestamps are recorded several ways in the different logs.

We can align the timestamps for telemetry and BIN logs and merge them into a single event stream. For GPS-enabled systems
or systems running ArduSub 4.7 this is trivial; for non-GPS systems this is still possible.

## Clocks

### ArduPilot Time Since Boot

ArduPilot has a 64-bit microsecond internal clock that starts when ArduPilot starts, often found in `time_boot_us` and `time_boot_ms` fields.
This clock is used throughout the code for all functions, including scheduling, EKF calculations and logging.

### ArduPilot Unix Time

ArduPilot also has an offset value (`rtc_shift`) that can be added to time-since-boot to get Unix time.
This can be set from several sources in priority order (`AP_RTC::source_type`):
* A hardware GPS driver, or MAVLink `GPS_INPUT` messages from an external GPS system (see below)
* MAVLink `SYSTEM_TIME` messages (see below)
* A hardware RTC (real-time clock) driver (used by ArduSub 4.7)

ArduPilot periodically sends `SYSTEM_TIME` MAVLink messages that contain both `time_boot_ms` and `time_unix_usec` fields.
If `rtc_shift` is 0 then `time_unix_usec` is 0.

### GPS Time

All GPS (GNSS) receivers have accurate UTC time as long as they have a good fix. External GPS systems can provide this information 
by setting the `time_week` and `time_week_ms` fields in the `GPS_INPUT` messages sent to ArduPilot.

The WL UGPS extension sends `GPS_INPUT` messages, but [these do not contain UTC time](https://github.com/waterlinked/blueos-ugps-extension/issues/5).

### Raspberry Pi (BlueOS) Time

The Raspberry Pi does not have a real-time clock. The Pi cleverly remembers the last-known time, so timestamps are monotonic,
but time appears to fast-forward when the Pi connects to a network timeserver. Often this happens during boot, so you don't see it.
But it can happen later, perhaps when the ROV is connected to the laptop. Watch out for log filenames that look wrong, or
big jumps in timestamps.

### Topside Time

The topside computer typically has a real-time clock, so it maintains the correct time even when it is not connected.

## Log Writers

### ArduPilot

ArduPilot writes time-since-boot in the `TimeUS` field of basically all dataflash messages in the BIN logs.
The exceptions are meta-records such as `FMT` that describe the format of the messages in the log.

The `LOG_DISARMED` parameter controls when ArduPilot starts logging:
* 0: ArduPilot starts logging when the vehicle is armed for the first time
* 1: ArduPilot starts logging immediately

The `LOG_FILE_DSRMROT` parameter controls how a disarm affects logging:
* 0: Logs are not rotated, so there is one BIN log created for each boot
* 1: Logs are rotated, so there is a new BIN log created each time the vehicle arms

### QGroundControl

QGroundControl will send `SYSTEM_TIME` messages to ArduPilot with the topside time when it starts up.
This will set `rtc_shift` and ArduPilot will start reporting the topside time in `SYSTEM_TIME` messages.
However, this is not logged in the BIN files, as `GPS` records do not reference `rtc_shift`.

QGroundControl writes the topside time in the tlog file for each MAVLink message received. The units are microseconds 
from the UNIX epoch (64-bits), rounded to the nearest millisecond. This is stored as an 8-byte header before each message.

QGroundControl opens a new tlog file when it starts up. If you reboot QGroundControl, it will open a new file.

QGroundControl names log files using the topside system time when the log is created, following the format `YYYY-MM-DD HH-mm-ss.tlog`.

These MAVLink messages contain `time_boot_ms` fields with ArduPilot time:
* ATTITUDE
* GLOBAL_POSITION_INT
* RC_CHANNELS
* SCALED_IMU2
* SCALED_PRESSURE
* SCALED_PRESSURE2
* SYSTEM_TIME

This information can be used to compute the offset between time-since-boot time and topside time.

### BlueOS up to 1.4.X

BlueOS does MAVLink routing, and up to version 1.4.X these were getting more capable at writing tlog files.

Like QGroundControl, router-generated tlog files write the Raspberry Pi time in the tlog file as an 8-byte header before each message.

In general, these logs were created when the autopilot boots, so there is one tlog file per boot.

### BlueOS 1.5 (in beta)

For version 1.5 BlueOS is shifting to the MAVLink-Server router, and the mavlink-recorder system to write MCAP logs.
These MCAP logs contain channels for MAVLink messages and channels for system and extension logs.
Some beta versions also write H264 packets to these logs.

MCAP files record the Raspberry Pi time as each record is written.

A new log is created each time the vehicle is armed. Logs are not written when the vehicle is disarmed.

> NOTE: this is based on what we've seen with 1.5.0-beta.37 and 1.5.0-beta.39, and might change in the future.

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

Notes:
* pymavlink does not read MCAP files
* pymavlink does not honor the RTC records generated by ArduSub 4.7

## Aligning MAVLink and Dataflash Logs

### Using GPS time (most vehicles)

The easiest way to align logs is to make sure that GPS time ends up in both the tlog and BIN files.
This is the method used by most ArduPilot vehicles.

Evidence that GPS time is not available:
* `GPS_INPUT` messages are not present in the tlog file
* `GPS_INPUT` messages have zeros for `time_week` and `time_week_ms`
* `GPS` messages are not present in the BIN file
* `GPS` messages have zeros for `GWk` and `GMS`
* `SYSTEM_TIME` messages from ArduPilot (sysid=1, compid=1) have zeros for `time_unix_usec`

Note:
* `GPS_INPUT.time_week` corresponds to `GPS.GWk`
* `GPS_INPUT.time_week_ms` corresponds to `GPS.GMS`

### Using RTC time (ArduSub 4.7 and BlueOS)

We can use the RTC records to align time, similar to the GPS method. However, pymavlink doesn't help here.

### Aligning logs when there is no GPS or RTC values

Strategy:
* Find the first MAVLink message that contains a `time_boot_ms` field.
* Compute `rtc_shift = _timestamp - msg.time_boot_ms / 1e6` for that MAVLink message.
* Apply `rtc_shift` to all `_timestamp` pymavlink values for BIN messages.
* Merge the two log streams.

You can improve on this strategy by scanning the entire tlog file and finding the lowest (or 1st percentile) `timestamp - msg.time_boot_ms / 1e6` value.

There is an implementation of this strategy using BIN and mcap files in [dive_logs.py](dive_logs.py).
