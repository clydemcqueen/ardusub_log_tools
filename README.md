## ArduSub Log Tools

This is a collection of log analysis tools for working with [ArduSub](https://www.ardusub.com/) vehicles.

All tools support file globbing and recursion.

Examples:
~~~
tool.py --help
tool.py *.tlog
tool.py --recurse directory
tool.py --recurse .
~~~

### tlog_info.py

~~~
$ tlog_info.py --help
usage: tlog_info.py [-h] [-r] paths [paths ...]

Read MAVLink messages from a tlog file (telemetry log) and report on anything interesting.

positional arguments:
  paths

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
~~~

### tlog_merge.py

~~~
$ tlog_merge.py --help
usage: tlog_merge.py [-h] [-r] [-v] [--all] [--explode] [--no-merge] [--types TYPES] [--max-msgs MAX_MSGS] [--max-rows MAX_ROWS]
                     paths [paths ...]

Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file. The merge operation does a
forward-fill (data is copied from the previous row), so the resulting merged csv file may be substantially larger than the sum of the per-
type csv files.

positional arguments:
  paths

options:
  -h, --help           show this help message and exit
  -r, --recurse        enter directories looking for tlog files
  -v, --verbose        print a lot more information
  --all                include all sources
  --explode            write a csv file for each message type
  --no-merge           do not merge tables, useful if you also select --explode
  --types TYPES        comma separated list of message types, the default is a set of useful types
  --max-msgs MAX_MSGS  stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS  stop if the merged table exceeds this number of rows (default 500K)
~~~

### tlog_param.py

~~~
$ tlog_param.py --help
usage: tlog_param.py [-h] [-r] paths [paths ...]

Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log) and use these to reconstruct the parameter state of a vehicle.

positional arguments:
  paths

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
~~~

### tlog_scan.py

~~~
$ tlog_scan.py --help
usage: tlog_scan.py [-h] [-r] [--types TYPES] paths [paths ...]

Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.

positional arguments:
  paths

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
  --types TYPES  comma separated list of message types
~~~

### tlog_types.py

~~~
$ tlog_types.py --help
usage: tlog_types.py [-h] [-r] paths [paths ...]

Read MAVLink messages from a tlog file (telemetry log) and report on the message types found.

positional arguments:
  paths

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
~~~

### BIN_merge.py

~~~
clyde@fastr:~/projects/ardusub_log_tools (main *)$ BIN_merge.py --help
usage: BIN_merge.py [-h] [-r] [-v] [--explode] [--no-merge] [--types TYPES] [--max-msgs MAX_MSGS] [--max-rows MAX_ROWS] paths [paths ...]

Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge operation does a forward-fill
(data is copied from the previous row), so the resulting merged csv file may be substantially larger than the sum of the per-type csv files.

positional arguments:
  paths

options:
  -h, --help           show this help message and exit
  -r, --recurse        enter directories looking for BIN files
  -v, --verbose        print a lot more information
  --explode            write a csv file for each message type
  --no-merge           do not merge tables, useful if you also select --explode
  --types TYPES        comma separated list of message types, the default is a set of useful types
  --max-msgs MAX_MSGS  stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS  stop if the merged table exceeds this number of rows (default 500K)
~~~

### map_maker.py

~~~
$ map_maker.py --help
usage: map_maker.py [-h] [-r] [-v] [--lat LAT] [--lon LON] [--zoom ZOOM] [--types TYPES] [--hdop HDOP]
                    paths [paths ...]

Read csv or tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For tlog files, these messages are read:
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, will appear as a blue line, should be close to the csv file
    GLOBAL_POSITION_INT -- the filtered position estimate, green line
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, not filtered, red line

positional arguments:
  paths

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog and csv files
  -v, --verbose  print a lot more information
  --lat LAT      center the map at this latitude, default is mean of all points
  --lon LON      center the map at this longitude, default is mean of all points
  --zoom ZOOM    initial zoom, default is 18
  --types TYPES  comma separated list of message types, the default is GPS_RAW_INT and GPS_GLOBAL_INT
  --hdop HDOP    reject GPS_INPUT messages where hdop exceeds this limit, default 100.0 (no limit)
~~~

## Timestamp notes

For a QGC-generated tlog file, `msg._timestamp` is the UNIX system time when the message was logged, to the nearest ms.

References:
* [QGC log file format](https://dev.qgroundcontrol.com/master/en/file_formats/mavlink.html)
* [QGC code](https://github.com/mavlink/qgroundcontrol/blob/245f9f1f9c475a24b02271e0b1a7a150f601f80d/src/comm/MAVLinkProtocol.cc#L280)
* [pymavlink code](https://github.com/ArduPilot/pymavlink/blob/d63c5ba4e9e20c702b0b7e31ab6bd71b80f161a5/mavutil.py#L1443)

## Project status

There are quite a few TODOs in the code.

There are a lot of small tools. Some of these may be combined.

Possible future tools or capabilities:
* Combine multiple telementry (tlog) files to produce a single telemetry log for a dive
* Combine multiple dataflash (.BIN) files to produce a single dataflash log for a dive
* Open Ping Sonar log (.bin) files
* Join telemetry, dataflash and ping sonar log files together
* Clip log files to 'interesting' segments based on timestamps or other markers
* Add 'theory of operation' documents describing important subsystems, e.g. WL UGPS