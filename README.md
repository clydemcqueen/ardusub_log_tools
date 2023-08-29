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

ardusub_log_tools requires Python 3.10.
Other requirements are listed in [requirements.txt](requirements.txt).

### A note on BAD_DATA messages

Some BlueOS-generated messages in QGC-generated tlog files may have bad CRC values. These messages will show
up as type=BAD_DATA. See [this discussion for the cause(es) and fix(es)](https://github.com/bluerobotics/BlueOS/issues/1740).
A simple workaround is to set the `MAV_IGNORE_CRC` environment variable:
~~~
export MAV_IGNORE_CRC=1
show_types.py *.tlog
~~~

## Special tools

### map_maker.py

map_maker builds Leaflet (interactive HTML) maps from GPS coordinates found in some csv files
as well as the GPS information in MAVLink (.tlog) files.

~~~
$ map_maker.py --help
usage: map_maker.py [-h] [-r] [-v] [--lat LAT] [--lon LON] [--zoom ZOOM] [--types TYPES] [--hdop-max HDOP_MAX] path [path ...]

Read csv or tlog files and build Leaflet (interactive HTML) maps from GPS coordinates.

For csv files:
    Latitude column header should be 'gps.lat' or 'lat'
    Longitude column header should be 'gps.lon' or 'lon'

For tlog files, these messages are read:
    GPS_RAW_INT -- sensor data sent from ArduSub to QGC, will appear as a blue line, should be close to the csv file
    GLOBAL_POSITION_INT -- the filtered position estimate, green line
    GPS_INPUT -- sensor data sent from ugps-extension to ArduSub, not filtered, red line

positional arguments:
  path

options:
  -h, --help           show this help message and exit
  -r, --recurse        enter directories looking for tlog and csv files
  -v, --verbose        print a lot more information
  --lat LAT            center the map at this latitude, default is mean of all points
  --lon LON            center the map at this longitude, default is mean of all points
  --zoom ZOOM          initial zoom, default is 18
  --types TYPES        comma separated list of message types, the default is GPS_RAW_INT and GPS_GLOBAL_INT
  --hdop-max HDOP_MAX  reject GPS messages where hdop exceeds this limit, default 100.0 (no limit)
~~~

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

## Tools that open MAVLink (.tlog) files

### tlog_info.py

~~~
$ tlog_info.py --help
usage: tlog_info.py [-h] [-r] path [path ...]

Read MAVLink messages from a tlog file (telemetry log) and report on anything interesting.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
~~~

### tlog_merge.py

~~~
$ tlog_merge.py --help
usage: tlog_merge.py [-h] [-r] [-v] [--explode] [--no-merge] [--types TYPES] [--max-msgs MAX_MSGS] [--max-rows MAX_ROWS] [--rate]
                     [--sysid SYSID] [--compid COMPID] [--system-time] [--surftrak] [--split-source]
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
     21             armed, rng_hold

positional arguments:
  path

options:
  -h, --help           show this help message and exit
  -r, --recurse        enter directories looking for tlog files
  -v, --verbose        print a lot more information
  --explode            write a csv file for each message type
  --no-merge           do not merge tables, useful if you also select --explode
  --types TYPES        comma separated list of message types, the default is a set of useful types
  --max-msgs MAX_MSGS  stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS  stop if the merged table exceeds this number of rows (default 500K)
  --rate               calculate rate for each message type
  --sysid SYSID        select source system id (default is all source systems)
  --compid COMPID      select source component id (default is all source components)
  --system-time        Experimental: use ArduSub SYSTEM_TIME.time_boot_ms rather than QGC timestamp
  --surftrak           Experimental: surftrak-specific analysis, see code
  --split-source       Experimental: split messages by source (sysid, compid)
~~~

### tlog_param.py

~~~
$ tlog_param.py --help
usage: tlog_param.py [-h] [-r] path [path ...]

Read MAVLink PARAM_VALUE messages from a tlog file (telemetry log), reconstruct the parameter state of a
vehicle, and write the parameters to a QGC-compatible params file.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
~~~

### tlog_scan.py

~~~
$ tlog_scan.py --help
usage: tlog_scan.py [-h] [-r] [--types TYPES] path [path ...]

Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
  --types TYPES  comma separated list of message types
~~~

### tlog_bad_data.py

~~~
$ tlog_bad_data.py -h
usage: tlog_bad_data.py [-h] [-r] [-v] path [path ...]

Read MAVLink messages from a tlog file (telemetry log) and report on BAD_DATA messages.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for tlog files
  -v, --verbose  print a lot more information
~~~

## Tools that open Dataflash (.BIN) files 

### BIN_info.py

BIN_info opens Dataflash (.BIN) files and reports on anything interesting.

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

Read dataflash messages from a BIN file and report on anything interesting.

positional arguments:
  path

options:
  -h, --help     show this help message and exit
  -r, --recurse  enter directories looking for BIN files
~~~

### BIN_merge.py

BIN_merge opens Dataflash (.BIN) files and merges the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

BIN_merge.py can also write multiple csv files, one per type, using the --explode option.

For example, you can examine the contents of a single table using the --explode, --no-merge and --types options together:
~~~
BIN_merge.py --explode --no-merge --types GPS 000011.BIN
~~~

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
  --types TYPES        comma separated list of message types, the default is a set of useful types
  --max-msgs MAX_MSGS  stop after processing this number of messages (default 500K)
  --max-rows MAX_ROWS  stop if the merged table exceeds this number of rows (default 500K)
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

## Timestamp notes

For a QGC-generated tlog file, `msg._timestamp` is the UNIX system time when the message was logged, to the nearest ms.

References:
* [QGC log file format](https://dev.qgroundcontrol.com/master/en/file_formats/mavlink.html)
* [QGC code](https://github.com/mavlink/qgroundcontrol/blob/245f9f1f9c475a24b02271e0b1a7a150f601f80d/src/comm/MAVLinkProtocol.cc#L280)
* [pymavlink code](https://github.com/ArduPilot/pymavlink/blob/d63c5ba4e9e20c702b0b7e31ab6bd71b80f161a5/mavutil.py#L1443)

## Other tools

* https://github.com/waterlinked/examples
* https://github.com/tridge/log_analysis
