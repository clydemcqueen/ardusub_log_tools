# ArduSub Log Tools ![Test status](https://github.com/clydemcqueen/ardusub_log_tools/actions/workflows/test.yml/badge.svg?branch=main)

This is a collection of log analysis tools for working with [ArduSub](https://www.ardusub.com/) vehicles.

All tools support file globbing and recursion on Linux.

Examples:
~~~
tool.py --help
tool.py *.tlog
tool.py --recurse directory
tool.py --recurse .
~~~

## Requirements

ardusub_log_tools requires Python 3.12.
Other requirements are listed in [requirements.txt](requirements.txt).

## Docs

* [Dealing with BAD_DATA message](docs/bad_data.md)
* [Understanding timestamps and synchronizing logs](docs/timesync.md)

## Segments

Some of the tlog tools support `--keep start_time,end_time,name` options, which is a way to specify which parts of the
file you are interested in processing. Only these messages between `start_time` and `end_time` are processed; the rest
of the file is ignored.

The timestamps must be specified in Unix time (seconds since January 1st, 1970 UTC).

If you provide multiple tlog files they are logically concatenated, which allows a segment to span multiple files.

Tools that generate files will generate one file per segment, and the name of the segment will appear in the file name.

The following bash script that shows how 4 segments are processed from several tlog files:
~~~
#!/bin/bash

export SEGMENT1="--keep 1694812410,1694813075,transect1"
export SEGMENT2="--keep 1694813405,1694814090,transect2"
export SEGMENT3="--keep 1694814995,1694815740,transect3"
export SEGMENT4="--keep 1694816175,1694816945,transect4"

export SEGMENTS="$SEGMENT1 $SEGMENT2 $SEGMENT3 $SEGMENT4"

echo "Segments are:"
echo $SEGMENTS

echo "#############"
echo "Exploding (tlog_merge.py)"
echo "#############"
tlog_merge.py --types GLOBAL_POSITION_INT,GPS_GLOBAL_ORIGIN,VISION_POSITION_DELTA,LOCAL_POSITION_NED \
    --no-merge --explode --rate $SEGMENTS *.tlog

echo "#############"
echo "Making maps (tlog_map_maker)"
echo "#############"
tlog_map_maker.py $SEGMENTS *.tlog

echo "#############"
echo "Plotting position (plot_local_position)"
echo "#############"
plot_local_position.py $SEGMENTS *.tlog
~~~

## Mapping and plotting

### tlog_map_maker.py

~~~
$ tlog_map_maker.py --help
usage: tlog_map_maker.py [-h] [-r] [-k KEEP] [-v] [--lat LAT] [--lon LON] [--zoom ZOOM] [--types TYPES] [--hdop-max HDOP_MAX] path [path ...]

Read tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

By default, read these messages and draw them bottom-to-top:
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, light grey line
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, slightly darker grey line
    GLOBAL_POSITION_INT -- the filtered position estimate, blue line

Supports segments.

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  -r, --recurse         enter directories looking for files
  -k KEEP, --keep KEEP  process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1
  -v, --verbose         print a lot more information
  --lat LAT             center the map at this latitude, default is mean of all points
  --lon LON             center the map at this longitude, default is mean of all points
  --zoom ZOOM           initial zoom, default is 18
  --types TYPES         comma separated list of message types
  --hdop-max HDOP_MAX   reject GPS_INPUT messages where hdop exceeds this limit, default 100.0 (no limit)
~~~

### map_maker.py

~~~
$ map_maker.py --help
usage: map_maker.py [-h] [-r] [-v] [--lat LAT] [--lon LON] [--zoom ZOOM] path [path ...]

Read csv and txt files and build Leaflet (interactive HTML) maps from GPS coordinates.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For txt files:
    Look for NMEA 0183 GGA messages of the form $[A-Z]+ at the end of a line of text

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for csv and txt files
  -v, --verbose  print a lot more information
  --lat LAT      center the map at this latitude, default is mean of all points
  --lon LON      center the map at this longitude, default is mean of all points
  --zoom ZOOM    initial zoom, default is 18
~~~

### plot_local_position.py

plot_local_position scans MAVLink (.tlog) files for LOCAL_POSITION_NED messages and plots the (x,y) positions.
The plots are saved as PDF files.

~~~
$ plot_local_position.py --help
usage: plot_local_position.py [-h] [-r] [-k KEEP] path [path ...]

Look for LOCATION_POSITION_NED messages in tlog files, plot x and y, and write PDF files.

Supports segments.

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  -r, --recurse         enter directories looking for files
  -k KEEP, --keep KEEP  process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1
~~~

## Generating csv files

### tlog_merge.py

Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

Thie tool can also write multiple csv files, one per type, using the `--explode` option. 

This example will open a tlog file, read in a set of tables that I find useful, calculate the data rates and report on
any gaps in the data, and then write a series of csv files. Each csv file will correspond to a table type, a sysid and a
compid, so you may see multiple csv files per table type:
~~~
$ tlog_merge.py --explode --no-merge --rate --split-source '2023-09-04 09-03-22.tlog'
Processing 1 files
Looking for these types: ['AHRS', 'AHRS2', 'ATTITUDE', 'BATTERY_STATUS', 'EKF_STATUS_REPORT', 'GLOBAL_POSITION_INT', 'GLOBAL_VISION_POSITION_ESTIMATE',
'GPS2_RAW', 'GPS_GLOBAL_ORIGIN', 'GPS_RAW_INT', 'HEARTBEAT', 'LOCAL_POSITION_NED', 'POWER_STATUS', 'RANGEFINDER', 'RAW_IMU', 'RC_CHANNELS', 'SCALED_IMU2',
'SCALED_PRESSURE', 'SCALED_PRESSURE2', 'SERVO_OUTPUT_RAW', 'SET_GPS_GLOBAL_ORIGIN', 'SYS_STATUS', 'SYSTEM_TIME', 'TIMESYNC', 'VFR_HUD', 'VISION_POSITION_DELTA']
===================
Reading 2023-09-04 09-03-22.tlog
WIRE_PROTOCOL_VERSION 2.0
Parsing messages
...
$ ls *.csv
'2023-09-04 09-03-22_AHRS_1_1.csv'                 '2023-09-04 09-03-22_HEARTBEAT_1_1.csv'           '2023-09-04 09-03-22_SERVO_OUTPUT_RAW_1_1.csv'
'2023-09-04 09-03-22_AHRS2_1_1.csv'                '2023-09-04 09-03-22_HEARTBEAT_255_190.csv'       '2023-09-04 09-03-22_SET_GPS_GLOBAL_ORIGIN_1_197.csv'
'2023-09-04 09-03-22_ATTITUDE_1_1.csv'             '2023-09-04 09-03-22_LOCAL_POSITION_NED_1_1.csv'  '2023-09-04 09-03-22_SYS_STATUS_1_1.csv'
'2023-09-04 09-03-22_BATTERY_STATUS_1_1.csv'       '2023-09-04 09-03-22_POWER_STATUS_1_1.csv'        '2023-09-04 09-03-22_SYSTEM_TIME_1_1.csv'
'2023-09-04 09-03-22_EKF_STATUS_REPORT_1_1.csv'    '2023-09-04 09-03-22_RANGEFINDER_1_1.csv'         '2023-09-04 09-03-22_SYSTEM_TIME_255_190.csv'
'2023-09-04 09-03-22_GLOBAL_POSITION_INT_1_1.csv'  '2023-09-04 09-03-22_RAW_IMU_1_1.csv'             '2023-09-04 09-03-22_TIMESYNC_1_1.csv'
'2023-09-04 09-03-22_GPS_GLOBAL_ORIGIN_1_1.csv'    '2023-09-04 09-03-22_RC_CHANNELS_1_1.csv'         '2023-09-04 09-03-22_VFR_HUD_1_1.csv'
'2023-09-04 09-03-22_HEARTBEAT_1_194.csv'          '2023-09-04 09-03-22_SCALED_IMU2_1_1.csv'         '2023-09-04 09-03-22_VISION_POSITION_DELTA_1_197.csv'
'2023-09-04 09-03-22_HEARTBEAT_1_197.csv'          '2023-09-04 09-03-22_SCALED_PRESSURE_1_1.csv'
~~~

Parameters:
~~~
$ tlog_merge.py --help
usage: tlog_merge.py [-h] [-r] [-k KEEP] [-v] [--explode] [--no-merge] [--types TYPES] [--max-msgs MAX_MSGS] [--max-rows MAX_ROWS] [--rate] [--sysid SYSID]
                     [--compid COMPID] [--split-source] [--system-time]
                     path [path ...]

Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

HEARTBEAT.mode is a combination of HEARTBEAT.base_mode and HEARTBEAT.custom_mode with these values:
    -10             disarmed
      0             armed, stabilize
      1             armed, acro
      2             armed, alt_hold
      3             armed, auto
      4             armed, guided
      7             armed, circle
      9             armed, surface
     16             armed, pos_hold
     19             armed, manual
     20             armed, motor detect
     21             armed, surftrak

Supports segments.

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  -r, --recurse         enter directories looking for files
  -k KEEP, --keep KEEP  process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1
  -v, --verbose         print a lot more information
  --explode             write a csv file for each message type
  --no-merge            do not merge tables, useful if you also select --explode
  --types TYPES         comma separated list of message types, the default is a set of useful types
  --max-msgs MAX_MSGS   stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS   stop if the merged table exceeds this number of rows (default 500K)
  --rate                calculate rate for each message type
  --sysid SYSID         select source system id (default is all source systems)
  --compid COMPID       select source component id (default is all source components)
  --split-source        split messages by source (sysid, compid)
  --system-time         experimental: use ArduSub SYSTEM_TIME.time_boot_ms rather than QGC timestamp
~~~

### BIN_merge.py

Similar to tlog_merge.py, BIN_merge.py opens Dataflash (.BIN) files and merges the messages into a single, wide csv
file. The merge operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file
may be substantially larger than the sum of the per-type csv files.

Parameters:
~~~
$ BIN_merge.py -h
usage: BIN_merge.py [-h] [-r] [-v] [--explode] [--no-merge] [--types TYPES] [--max-msgs MAX_MSGS] [--max-rows MAX_ROWS] path [path ...]

Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

BIN_merge.py can also write multiple csv files, one per type, using the --explode option.

You can examine the contents of a single table using the --explode, --no-merge and --types options:
BIN_merge.py --explode --no-merge --types GPS 000011.BIN

positional arguments:
  path

options:
  -h, --help           show this help message and exit
  -r, --recurse        enter directories looking for BIN files
  -v, --verbose        print a lot more information
  --explode            write a csv file for each message type
  --no-merge           do not merge tables, useful if you also select --explode
  --types TYPES        comma separated list of message types, the default is a small set of useful types
  --max-msgs MAX_MSGS  stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS  stop if the merged table exceeds this number of rows (default 500K)
  --raw                show all records; default is to drop BARO records where id==0
~~~

## All tools

* [BIN_ekf_status.py](BIN_ekf_status.py) - Report on EKF3 status (XKF4.SS field).
* [BIN_explode.py](BIN_explode.py) - Read ArduSub dataflash messages from a BIN file and write a csv file for each message type.
* [BIN_filter.py](BIN_filter.py) - Read Dataflash (BIN) file(s), filter messages, and write new BIN file(s) with the kept messages.
* [BIN_graph_alt.py](BIN_graph_alt.py) - Read an ArduSub BIN file and produce a graph of altitude readings.
* [BIN_gyro_bias_stats.py](BIN_gyro_bias_stats.py) - Read dataflash logs and report on high / low XKF1.G? (gyro_bias) values.
* [BIN_info.py](BIN_info.py) - Read dataflash messages from a BIN file and report on a few interesting things.
* [BIN_mag_3d.py](BIN_mag_3d.py) - Note transitions to/from mag 3d fusion.
* [BIN_mag_stats.py](BIN_mag_stats.py) - Read dataflash logs and report on some MAG stats.
* [BIN_map_maker.py](BIN_map_maker.py) - Read BIN files and build Leaflet (interactive HTML) maps from GPS coordinates.
* [BIN_merge.py](BIN_merge.py) - Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file.
* [BIN_messages.py](BIN_messages.py) - Read a dataflash (BIN) file and write the entries in the MSG and EV tables to stdout.
* [BIN_param.py](BIN_param.py) - Read PARM messages from a dataflash file and write them to a params file.
* [BIN_plot_surftrak.py](BIN_plot_surftrak.py) - Read BIN files and plot rangefinder vs target for SURFTRAK and GUIDED above-terrain modes.
* [check_offset_stability.py](check_offset_stability.py) - Analyze the stability of the timestamp offset (unix_time - boot_time) in a tlog file.
* [check_rtc_time.py](check_rtc_time.py) - Check log files (Dataflash .BIN and MAVLink .tlog) for the presence of GPS or Unix time.
* [dive.py](dive.py) - Read all BIN and tlog files in a directory and figure out how they line up.
* [dive_iter.py](dive_iter.py) - Iterate through chronological MAVLink messages from overlapping tlog and BIN files.
* [map_maker.py](map_maker.py) - Read csv and txt files and build Leaflet (interactive HTML) maps from GPS coordinates.
* [mav_type_echo.py](mav_type_echo.py) - Connect to a running MAVLink system and echo a message type.
* [mission_dump.py](mission_dump.py) - Read MISSION_* messages from a tlog file (telemetry log) and print the mission(s).
* [opt_rtc_shift.py](opt_rtc_shift.py) - Optimize the RTC shift value by comparing data that appears in both tlog and BIN files.
* [plot_local_position.py](plot_local_position.py) - Look for LOCATION_POSITION_NED and VISION_POSITION_DELTA messages in tlog files, plot x and y, and write PDF files.
* [show_types.py](show_types.py) - Read messages from tlog (telemetry) and BIN (dataflash) logs and report on the message types found.
* [split_by_mode.py](split_by_mode.py) - Split ArduSub log files (tlog and BIN) into separate files based on flight modes.
* [tlog_bad_data.py](tlog_bad_data.py) - Read MAVLink messages from a tlog file (telemetry log) and report on BAD_DATA messages.
* [tlog_bad_time.py](tlog_bad_time.py) - Read a tlog file (telemetry log) and report on bad timestamps.
* [tlog_battery.py](tlog_battery.py) - Provide information about the battery type and usage.
* [tlog_explode.py](tlog_explode.py) - Read MAVLink messages from a tlog file (telemetry log) and write a csv file for each message type.
* [tlog_filter.py](tlog_filter.py) - Read one or more tlog files, filter messages, and write a single, combined, valid tlog file with the resulting messages.
* [tlog_gps_input_problems.py](tlog_gps_input_problems.py) - Read GPS_INPUT messages and look for problems.
* [tlog_info.py](tlog_info.py) - Read MAVLink messages from a tlog file (telemetry log) and report on a few interesting things.
* [tlog_map_maker.py](tlog_map_maker.py) - Read tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.
* [tlog_merge.py](tlog_merge.py) - Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file.
* [tlog_messages.py](tlog_messages.py) - Read MAVLink messages from a tlog file (telemetry log) and write STATUSTEXT messages.
* [tlog_param.py](tlog_param.py) - Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a vehicle, and write them to a params file.
* [tlog_scan.py](tlog_scan.py) - Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.
* [tlog_segment.py](tlog_segment.py) - Read MAVLink messages from one or more tlog files (telemetry logs), stitch them together in time order, then extract segments.
* [tlog_sources.py](tlog_sources.py) - Read MAVLink messages and count messages by source.
* [tlog_split_beams.py](tlog_split_beams.py) - Read DISTANCE_SENSOR messages from a tlog file and write one csv file per (src, comp, orientation) tuple.
* [tlog_template.py](tlog_template.py) - Template for tlog tools that do not support segments.
* [tlog_template_segments.py](tlog_template_segments.py) - Template for tlog tools that support segments.
* [tlog_timeline.py](tlog_timeline.py) - Read MAVLink messages from a tlog file (telemetry log) and generate a timeline.

## Other tools

### MAVExplorer.py

A terrific tool. Some nifty things it can do with tlog files:
* `map GPS_INPUT GPS_RAW_INT GLOBAL_POSITION_INT` is basically the same as tlog_map_maker.py

Nifty things it can do with BIN files:
* `map GPS POS` will show a map comparing the GPS inputs to EKF outputs

### References

* https://github.com/waterlinked/examples
* https://github.com/tridge/log_analysis
