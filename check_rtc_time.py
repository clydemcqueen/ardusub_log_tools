#!/usr/bin/env python3

"""
This tool checks log files (Dataflash .BIN and MAVLink .tlog) for the presence of GPS or Unix time.

It helps identify if log entries are timestamped with accurate global time (GPS time) or system-specific Unix time.
The tool can process individual files or recursively scan directories.

Usage:
    check_rtc_time.py <paths> [options]

Arguments:
    <paths>    One or more files or directories to scan.

Options:
    -r, --recurse    Recurse into directories to find log files.
    -v, --verbose    Provide verbose output, showing details of time sources found.

The tool outputs the type of time found (GPS, UNIX (ArduSub), or UNIX (other)) for each log file.
"""

import argparse
import os

from pymavlink import mavutil

import util


def check_bin_gps_time(filename, verbose):
    """
    Check if a BIN file has GPS time.
    """
    try:
        mlog = mavutil.mavlink_connection(filename)
    except Exception:
        return False

    # DFReader (which mavlink_connection returns for BIN files) determines the timebase during initialization. If it
    # found GPS messages, it sets a non-zero timebase (or at least uses a clock that isn't just 0-based).
    if hasattr(mlog, 'clock') and hasattr(mlog.clock, 'timebase'):
        if mlog.clock.timebase > 1:
            return True
            
    return False

def check_tlog_gps_or_unix_time(filename, verbose) -> tuple[bool, bool, bool]:
    """
    Check if a tlog file has GPS time, or Unix time in general.
    """
    try:
        mlog = mavutil.mavlink_connection(filename)
    except Exception:
        return False, False, False

    gps_time = 0
    unix_time_1_1 = 0
    unix_time_x_x = 0

    while True:
        m = mlog.recv_match(type=['GPS_INPUT', 'SYSTEM_TIME'], blocking=False)
        if m is None:
            break

        sysid = m.get_srcSystem()
        compid = m.get_srcComponent()
        msg_type = m.get_type()

        if msg_type == 'GPS_INPUT':
            if m.time_week > 0:
                # For sure this is GPS time
                gps_time += 1
        elif m.get_type() == 'SYSTEM_TIME':
            if m.time_unix_usec > 0:
                if sysid == 1 and compid == 1:
                    # This is Unix time from ArduSub, might be GPS time
                    unix_time_1_1 += 1
                else:
                    # This is Unix time from another system, likely QGC
                    unix_time_x_x += 1
    if verbose:
        if gps_time > 0:
            print(f"GPS time in {gps_time} messages")
        if unix_time_1_1 > 0:
            print(f"Unix time from ArduSub (1,1) in {unix_time_1_1} messages")
        if unix_time_x_x > 0:
            print(f"Unix time from somewhere (x,x) in {unix_time_x_x} messages")

    return gps_time > 0, unix_time_1_1 > 0, unix_time_x_x > 0

def process_file(filename, verbose):
    _, ext = os.path.splitext(filename)

    gps_time = False
    unix_time_1_1 = False
    unix_time_x_x = False

    if ext == '.BIN':
        gps_time = check_bin_gps_time(filename, verbose)
    elif ext == '.tlog':
        gps_time, unix_time_1_1, unix_time_x_x = check_tlog_gps_or_unix_time(filename, verbose)

    if gps_time:
        prefix = 'GPS'
    elif unix_time_1_1:
        prefix = 'UNIX (ArduSub)'
    elif unix_time_x_x:
        prefix = 'UNIX (other)'
    else:
        prefix = ''

    print(f"{prefix:14s} {filename}")

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('paths', nargs='+', help='Files or directories to scan')
    parser.add_argument('-r', '--recurse', action='store_true', help='Recurse into directories')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    # Require exact capitalization: '.BIN' for dataflash logs and '.tlog' for MAVLink logs
    files = util.expand_path(args.paths, args.recurse, ['.BIN', '.tlog'])
    
    for f in files:
        process_file(f, args.verbose)

if __name__ == '__main__':
    main()
