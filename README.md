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

## A note on BAD_DATA messages

Some BlueOS-generated messages in QGC-generated tlog files may have bad CRC values. These messages will show
up as type=BAD_DATA. See [this discussion for the cause(es) and fix(es)](https://github.com/bluerobotics/BlueOS/issues/1740).
A simple workaround is to set the `MAV_IGNORE_CRC` environment variable:
~~~
export MAV_IGNORE_CRC=1
show_types.py *.tlog
~~~

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
                     [--compid COMPID] [--split-source] [--system-time] [--surftrak]
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
  --surftrak            experimental: surftrak-specific analysis, see code
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

## General tools

### show_types.py

show_types opens MAVLink (.tlog) and Dataflash (.BIN) files and counts records by type.

Sample output:
~~~
$ show_types.py 100.BIN
Processing 1 files
-------------------
Reading 100.BIN
   824  AHR2  Backup AHRS data                                                                  
     3  ARM   Arming status changes                                                             
   824  ATT   Canonical vehicle attitude                                                        
  1652  BARO  Gathered Barometer data                                                           
   826  BAT   Gathered battery data                                                             
   824  CTRL  Attitude Control oscillation monitor diagnostics                                  
   826  CTUN  Control Tuning information                                                        
    82  DSF   Onboard logging statistics                                                        
    83  DU32  Generic 32-bit-unsigned-integer storage                                           
     3  ERR   Specifically coded error messages                                                 
     6  EV    Specifically coded event messages                                                 
   153  FMT   Message defining the format of messages in this file                              
   153  FMTU  Message defining units and multipliers used for fields of other messages          
   826  FTN   Filter Tuning Message - per motor                                                 
   193  GPA   GPS accuracy information                                                          
   193  GPS   Information received from GNSS systems attached to the autopilot                  
  4124  IMU   Inertial Measurement Unit data                                                    
    79  IOMC  TODO -- update tool                                                               
   826  MAG   Information received from compasses                                               
   246  MAV   GCS MAVLink link statistics                                                       
     4  MODE  vehicle control mode information                                                  
   824  MOTB  Motor mixer information                                                           
    68  MSG   Textual messages                                                                  
    14  MULT  Message mapping from single character to numeric multiplier                       
     2  ORGN  Vehicle navigation origin or other notable position                               
   902  PARM  parameter value                                                                   
     7  PM    autopilot system performance and general data dumping ground                      
   479  POS   Canonical vehicle position [lat/lon/alt]                                          
   826  POWR  TODO -- update tool                                                               
    29  PSCD  Position Control Down                                                             
   824  RATE  Desired and achieved vehicle attitude rates. Not logged in Fixed Wing Plane modes.
   824  RCI2  (More) RC input channels to vehicle                                               
   824  RCIN  RC input channels to vehicle                                                      
   824  RCOU  Servo channel output values 1 to 14                                               
    34  UNIT  Message mapping from single character to SI unit                                  
  1648  VIBE  Processed (acceleration) vibration information                                    
  1648  XKF1  EKF3 estimator outputs                                                            
  1648  XKF2  EKF3 estimator secondary outputs                                                  
  1648  XKF3  EKF3 innovations                                                                  
  1648  XKF4  EKF3 variances                                                                    
   824  XKF5  EKF3 Sensor innovations (primary core) and general dumping ground                 
  1648  XKFS  EKF3 sensor selection                                                             
  1648  XKQ   EKF3 quaternion defining the rotation from NED to XYZ (autopilot) axes            
    16  XKT   EKF3 timing information                                                           
   164  XKV1  EKF3 State variances (primary core)                                               
   164  XKV2  more EKF3 State Variances (primary core)                                          
   542  XKY0  EKF Yaw Estimator States                                                          
   542  XKY1  EKF Yaw Estimator Innovations                                                     
~~~

Parameters:
~~~
$ show_types.py --help
usage: show_types.py [-h] [-r] path [path ...]

Read messages from tlog (telemetry) and BIN (dataflash) logs and report on the message types found.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog and BIN files
~~~

### tlog_info.py

Read tlog files and report on a few interesting things.

~~~
$ tlog_info.py --help
usage: tlog_info.py [-h] [-r] [-k KEEP] path [path ...]

Read MAVLink messages from a tlog file (telemetry log) and report on a few interesting things.

Supports segments.

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  -r, --recurse         enter directories looking for files
  -k KEEP, --keep KEEP  process just these segments; a segment is 2 timestamps and a name, e.g., start,end,s1
~~~


### BIN_info.py

BIN_info opens Dataflash (.BIN) files and reports on a few interesting things.

Sample output:
~~~
$ BIN_info.py *.BIN
Processing 2 files
-------------------
Results for 100.BIN
193 GPS records, gps_week is always 0, no datetime information
List of messages, with counts:
       3  ArduSub V4.1.0 (f2af3c7e)
       3  ChibiOS: 93e6e03d
       1  EKF3 IMU0 stopped aiding
       1  EKF3 IMU1 stopped aiding
       2  Frame: VECTORED_6DOF
       1  GPS 1: specified as MAV
       2  IMU0: fast sampling enabled 8.0kHz/1.0kHz
       3  Lost manual control
      44  MYGCS: 255, heartbeat lost
       1  New mission
       1  Param space used: 951/3840
       3  Pixhawk1 0049001F 34395111 30323935
       1  RC Protocol: None
       2  RCOut: PWM:1-12
-------------------
Results for 102.BIN
6111 GPS records, gps_week is always 0, no datetime information
List of messages, with counts:
       2  #Gain is 30%
       4  #Gain is 40%
       3  #Gain is 50%
       2  #Gain is 60%
       1  #Gain is 70%
       1  ArduSub V4.1.0 (f2af3c7e)
       1  ChibiOS: 93e6e03d
       1  EKF3 IMU0 stopped aiding
       1  EKF3 IMU1 stopped aiding
       1  EKF3 lane switch 1
       1  GPS 1: specified as MAV
       1  Lost manual control
       1  MYGCS: 255, heartbeat lost
       1  New mission
       1  Param space used: 951/3840
       1  Pixhawk1 0049001F 34395111 30323935
       1  RC Protocol: None
~~~

Parameters:
~~~
$ BIN_info.py -h
usage: BIN_info.py [-h] [-r] path [path ...]

Read dataflash messages from a BIN file and report on a few interesting things.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for BIN files
~~~

### tlog_param.py

Generate QGC-compatible parameter files from tlog files.

~~~
$ tlog_param.py --help
usage: tlog_param.py [-h] [-r] [-c] path [path ...]

Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a
vehicle, and write the parameters to a QGC-compatible params file.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
  -c, --changes  only show changes across files, do not write *.params files
~~~

## Tools for working with Waterlinked UGPS systems

### wl_ugps_logger.py

~~~
$ wl_ugps_logger.py -h
usage: wl_ugps_logger.py [-h] [--url URL] [--filtered] [--raw] [--locator] [--g2] [--all] [--rate RATE]

Get position data from the Water Linked UGPS API and write it to one or more csv files.

To run in the field, capturing all outputs:
wl_ugps_logger.py --all

To test with the demo server, capturing all outputs:
wl_ugps_logger.py --url https://demo.waterlinked.com --all

options:
  -h, --help   show this help message and exit
  --url URL    URL of UGPS topside unit
  --filtered   log position/acoustic/filtered
  --raw        log position/acoustic/raw
  --locator    log position/global (locator)
  --g2         log position/master (G2 box)
  --all        log everything
  --rate RATE  polling rate
~~~

### wl_ugps_process.py

~~~
$ wl_ugps_process.py -h
usage: wl_ugps_process.py [-h] [-r] [--lat LAT] [--lon LON] [--heading HEADING] [--zoom ZOOM] path [path ...]

Generate a folium map from a log generated by wl_ugps_logger.py.

positional arguments:
  path

options:
  -h, --help         show this help message and exit
  -r, --recurse      enter directories looking for csv files
  --lat LAT          WL UGPS antenna latitude
  --lon LON          WL UGPS antenna longitude
  --heading HEADING  WL UGPS antenna heading
  --zoom ZOOM        initial zoom, default is 18
~~~

## MAVLink debugging tools

These might be useful when debugging tlog files or pymavlink.

* tlog_scan.py: report on any pymavlink crashes
* tlog_bad_data.py: report on BAD_DATA messages
* tlog_backwards.py: read the timestamps and note when time appears to go backwards

## Timestamp notes

For a QGC-generated tlog file, `msg._timestamp` is the UNIX system time when the message was logged, to the nearest ms.

References:
* [QGC log file format](https://dev.qgroundcontrol.com/master/en/file_formats/mavlink.html)
* [QGC code](https://github.com/mavlink/qgroundcontrol/blob/245f9f1f9c475a24b02271e0b1a7a150f601f80d/src/comm/MAVLinkProtocol.cc#L280)
* [pymavlink code](https://github.com/ArduPilot/pymavlink/blob/d63c5ba4e9e20c702b0b7e31ab6bd71b80f161a5/mavutil.py#L1443)

## Other tools

### MAVExplorer.py

A terrific tool. Some nifty things it can do with tlog files:
* `map GPS_INPUT GPS_RAW_INT GLOBAL_POSITION_INT` is basically the same as tlog_map_maker.py

Nifty things it can do with BIN files:
* `map GPS POS` will show a map comparing the GPS inputs to EKF outputs

### References

* https://github.com/waterlinked/examples
* https://github.com/tridge/log_analysis
