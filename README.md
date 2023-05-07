## ArduSub Log Tools

This is a collection of log analysis tools for working with [ArduSub](https://www.ardusub.com/) vehicles.

All tools have a `--help` option.

All tools support file globbing and recursion.

Examples:
~~~
tool.py --help
tool.py *.tlog
tool.py --recurse directory
tool.py --recurse .
~~~

### tlog_info.py

Read MAVLink messages from a tlog file (telemetry log) and report on anything interesting.

### tlog_merge.py

Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-message csv files.

### tlog_param.py

Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log) and use these to reconstruct the parameter state of a vehicle.

### tlog_scan.py

Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.

### BIN_merge.py

Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

### map_maker.py

Read csv or tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

## Timestamps

For a QGC-generated tlog file, `msg._timestamp` is the UNIX system time when the message was logged, to the nearest ms.

References:
* [QGC log file format](https://dev.qgroundcontrol.com/master/en/file_formats/mavlink.html)
* [QGC code](https://github.com/mavlink/qgroundcontrol/blob/245f9f1f9c475a24b02271e0b1a7a150f601f80d/src/comm/MAVLinkProtocol.cc#L280)
* [pymavlink code](https://github.com/ArduPilot/pymavlink/blob/d63c5ba4e9e20c702b0b7e31ab6bd71b80f161a5/mavutil.py#L1443)

## Status

There are quite a few TODOs in the code.

There are a lot of small tools. Some of these may be combined.

Possible future tools or capabilities:
* Combine multiple telementry (tlog) files to produce a single telemetry log for a dive
* Combine multiple dataflash (.BIN) files to produce a single dataflash log for a dive
* Open Ping Sonar log (.bin) files
* Join telemetry, dataflash and ping sonar log files together
* Clip log files to 'interesting' segments based on timestamps or other markers
* Add 'theory of operation' documents describing important subsystems, e.g. WL UGPS