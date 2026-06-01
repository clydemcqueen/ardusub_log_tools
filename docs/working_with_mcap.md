# Working with BlueOS-generated mcap files

## FAQ

Q: When does BlueOS create a new mcap file?
* BlueOS creates a new mcap file every time the Sub is armed. It is closed when the Sub is disarmed.

Q: Can I download an open mcap file from BlueOS at the end if a dive, or do I have to wait for it to close?
* Not sure, but you can disarm the Sub to close it.

Q: Do mcap files record the same information as QGC-generated tlog files?
* Mostly, yes. See differences below.

Q: How do I parse mcap files in Python?
* See [mcap_types.py](../mcap_types.py) for a simple example.

## How mcap files differ from QGC-generated tlog files

### Tools

The following tools are useful for understanding the differences:
* [mcap_to_tlog.py](../mcap_to_tlog.py) will extract MAVLink messages from an mcap file, and create a tlog file.
* [mcap_tlog_diff.py](../mcap_tlog_diff.py) will compare a QGC-generated tlog file to a BlueOS-generated mcap file.

### Span

QGC-generated tlog files cover the entire time that QGC was open, so you might end up with 1 tlog file for a dive.

mcap files cover just the time that the Sub is armed, so you might end up with a log of mcap files for a dive.

### Timestamps

QGC uses the topside clock, where BlueOS uses the Pi clock. These should be very close, but the timestamps are recorded in microseconds, so they will be a little different.

### MAVLink 2.0 fields

MAVLink 2.0 fields are missing. The MAVLink 1.0 fields cover the most important things, so this should be OK for most uses.

I think this should be resolved soon, see: https://github.com/bluerobotics/mavlink-server/issues/213

### TODO

In SITL tests I see some order differences that might be related to timestamps, but they only affect these messages:
* MANUAL_CONTROL
* HEARTBEAT
* AHRS2
* VFR_HUD

Puzzling, but not show-stoppers.
