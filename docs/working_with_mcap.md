# Working with BlueOS-generated mcap files

## FAQ

Q: What versions of BlueOS are supported by these mcap tools?
* v1.15.0-beta.37. (This version does not save video by default, so the mcap files are fairly small.)

Q: Where will I find mcap files? They are not in the BlueOS _Log Browser_.
* Go to the _File Browser_, drill into `userdata/recorder`.

Q: When does BlueOS create a new mcap file?
* BlueOS creates a new mcap file every time the Sub is armed. It is closed when the Sub is disarmed.

Q: Can I download an open mcap file from BlueOS at the end if a dive, or do I have to wait for it to close?
* You should wait for it to close. You can disarm the Sub to close it.

Q: Do mcap files record the same information as QGC-generated tlog files?
* Mostly, yes. See the differences below.

Q: How do I parse mcap files in Python?
* Use `util.iter_mcap_messages()` and `util.get_mcap_summary_info()` in [util.py](../util.py). See below for details.

## channel organization

BlueOS records messages from the Zenoh message bus into MCAP channels:

* Vehicle MAVLink: `mavlink/{system_id}/{component_id}/{MESSAGE_TYPE}`
  * There are a few sub-topics for specific enum values/properties, e.g., `mavlink/1/1/HEARTBEAT/mavtype`.
* Outgoing MAVLink: `mavlink/out`
  * Aggregated stream of all outgoing MAVLink packets serialized as JSON. Note that messages sent by the vehicle autopilot appear both on `mavlink/1/1/{MESSAGE}` and in `mavlink/out`.
* Extension logs: `extensions/logs/{extension_name}` (e.g., `extensions/logs/waterlinked.ugps`)
* Service logs: `services/{service_name}/log` (e.g., `services/ardupilot-manager/log`, `services/wifi-manager/log`)
* System information: `services/system_information/*`
* Video streams: `video/*`

## MCAP file structure & high-performance reading

BlueOS writes MCAP files in `zstd`-compressed chunks with a complete index footer:
* Statistics & Summary: Stored in the file footer. Contains the exact start and end timestamps and message count per channel.
* MessageIndex: Each chunk index points to byte offsets for every message of each channel within decompressed chunk buffers.

### Fast Reading with `util.py`

The basic iterator (`mcap.reader.make_reader().iter_messages()`) can be slow because it decompresses and unpacks every single record in pure Python. Use the helper functions in [util.py](../util.py):

* `util.get_mcap_summary_info(path)`:
  Reads time bounds, channel names, and exact message counts in ~1 ms directly from the file footer without decompressing chunk records.
* `util.iter_mcap_messages(path, message_types=[...], sys_id=1, comp_id=1, ...)`:
  Uses the `MessageIndex` to jump directly to target message byte offsets in decompressed memory, 50x–150x faster than a simple iterator.

## How mcap files differ from QGC-generated tlog files

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
