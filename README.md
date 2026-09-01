# ArduSub Log Tools ![Test status](https://github.com/clydemcqueen/ardusub_log_tools/actions/workflows/test.yml/badge.svg?branch=main)

This is a collection of log analysis tools for working with [ArduSub](https://www.ardusub.com/) vehicles.

## Requirements

ardusub_log_tools requires Python 3.12.
Other requirements are listed in [requirements.txt](requirements.txt).

## Docs

* [Dealing with BAD_DATA message](docs/bad_data.md)
* [Understanding timestamps and synchronizing logs](docs/timesync.md)
* [Working with BlueOS mcap logs](docs/working_with_mcap.md)
* [Dataflash table definitions](dataflash)

## File globbing and recursion

Many tools support file globbing and recursion on Linux.

Examples:
~~~
tool.py --help
tool.py *.tlog
tool.py --recurse directory
tool.py --recurse .
~~~

## Segments

Several tlog tools support `--keep start_time,end_time,name` options, which is a way to specify which parts of the
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
echo "Plotting position (tlog_plot_local)"
echo "#############"
tlog_plot_local.py $SEGMENTS *.tlog
~~~

## Tools that read tlog files

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
* [tlog_plot_local.py](tlog_plot_local.py) - Look for LOCAL_POSITION_NED and VISION_POSITION_DELTA messages in tlog files, plot x and y, and write PDF files.
* [tlog_scan.py](tlog_scan.py) - Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.
* [tlog_segment.py](tlog_segment.py) - Read MAVLink messages from one or more tlog files (telemetry logs), stitch them together in time order, then extract segments.
* [tlog_sources.py](tlog_sources.py) - Read MAVLink messages and count messages by source.
* [tlog_split_beams.py](tlog_split_beams.py) - Read DISTANCE_SENSOR messages from a tlog file and write one csv file per (src, comp, orientation) tuple.
* [tlog_template.py](tlog_template.py) - Template for tlog tools that do not support segments.
* [tlog_template_segments.py](tlog_template_segments.py) - Template for tlog tools that support segments.
* [tlog_timeline.py](tlog_timeline.py) - Read MAVLink messages from a tlog file (telemetry log) and generate a timeline.
* [check_offset_stability.py](check_offset_stability.py) - Analyze the stability of the timestamp offset (unix_time - boot_time) in a tlog file.
* [mission_dump.py](mission_dump.py) - Read MISSION_* messages from a tlog file (telemetry log) and print the mission(s).

## Tools that read BIN (dataflash) files

* [BIN_battery.py](BIN_battery.py) - Provide information about the battery type and usage from a dataflash (BIN) file.
* [BIN_ekf_status.py](BIN_ekf_status.py) - Report on EKF3 status (XKF4.SS and XKFS.SS fields).
* [BIN_explode.py](BIN_explode.py) - Read ArduSub dataflash messages from a BIN file and write a csv file for each message type.
* [BIN_extract_files.py](BIN_extract_files.py) - Extract embedded files from a dataflash (BIN) file.
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
* [BIN_plot_local.py](BIN_plot_local.py) - Look for XKF1 and VISO messages in BIN files, plot x and y, and write PDF files.
* [BIN_plot_surftrak.py](BIN_plot_surftrak.py) - Read BIN files and plot rangefinder vs target for SURFTRAK and GUIDED above-terrain modes.
* [BIN_plot_viso.py](BIN_plot_viso.py) - Read BIN files and plot VISO (Visual Odometry) data alongside EKF estimated position, EKF innovations, and thruster outputs (RCOU).
* [BIN_timeline.py](BIN_timeline.py) - Read Dataflash messages from a BIN file and generate a timeline.


## Tools that read tlog and BIN files

* [check_rtc_time.py](check_rtc_time.py) - Check log files (Dataflash .BIN and MAVLink .tlog) for the presence of GPS or Unix time.
* [dive.py](dive.py) - Read all BIN and tlog files in a directory and figure out how they line up.
* [dive_iter.py](dive_iter.py) - Iterate through chronological MAVLink messages from overlapping tlog and BIN files.
* [opt_rtc_shift.py](opt_rtc_shift.py) - Optimize the RTC shift value by comparing data that appears in both tlog and BIN files.
* [show_types.py](show_types.py) - Read messages from tlog (telemetry) and BIN (dataflash) logs and report on the message types found.
* [split_by_mode.py](split_by_mode.py) - Split ArduSub log files (tlog and BIN) into separate files based on flight modes.

## Tools that read BlueOS-generated mcap files

* [mcap_channels.py](mcap_channels.py) - Open mcap files and report on the channels.
* [mcap_dump_extension_logs.py](mcap_dump_extension_logs.py) - Extract extension logs from mcap files and write each extension's logs to a text file.
* [mcap_explode.py](mcap_explode.py) - Read MAVLink messages from an mcap file and write a csv file for each message type.
* [mcap_explode_extension_logs.py](mcap_explode_extension_logs.py) - Extract structured telemetry and diagnostic data from extension logs in mcap files to CSV or JSON files.
* [mcap_plot_local.py](mcap_plot_local.py) - Look for LOCAL_POSITION_NED and VISION_POSITION_DELTA messages in mcap files, plot x and y, and write PDF files.
* [mcap_strip_video.py](mcap_strip_video.py) - Open mcap files and copy all non-video channels to new mcap files (reduces file size by ~97%).
* [mcap_tlog_diff.py](mcap_tlog_diff.py) - Compare a QGC-generated tlog to an mcap file.
* [mcap_to_tlog.py](mcap_to_tlog.py) - Convert MCAP files containing MAVLink messages to tlog files readable by pymavlink.
* [mcap_types.py](mcap_types.py) - Read messages from mcap files and report on the message types found(similar to show_types.py).
* [mcap_wl_ugps_acoustic_info.py](mcap_wl_ugps_acoustic_info.py) - Read Water Linked UGPS extension logs from an MCAP file and print a summary of acoustic tracking performance.

## Other tools

* [map_maker.py](map_maker.py) - Read csv and txt files and build Leaflet (interactive HTML) maps from GPS coordinates.
* [mav_type_echo.py](mav_type_echo.py) - Connect to a running MAVLink system and echo a message type.

## MAVExplorer.py

MAVExplorer.py is a terrific tool. Some nifty things it can do with tlog files:
* `map GPS_INPUT GPS_RAW_INT GLOBAL_POSITION_INT` is basically the same as tlog_map_maker.py

Nifty things it can do with BIN files:
* `map GPS POS` will show a map comparing the GPS inputs to EKF outputs
