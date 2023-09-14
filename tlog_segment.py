#!/usr/bin/env python3

"""
Read MAVLink messages from one or more tlog files (telemetry logs), stitch them together in time order, then extract
and write segments as new, smaller tlog files. The segments can be specified in one of 2 ways:

    Use one or more "--keep x,y" options to specify which segments to keep. x and y are timestamps (see below).
    Use one or more "--discard x,y" options to specify which segments to discard, the rest are kept.

Timestamps can be specified in 2 ways:

    Seconds since the start of the earliest tlog file in the list, e.g., 100.
    Unix time (seconds since January 1st, 1970 UTC), e.g., 1694633807.

Example: stitch together all tlog files in the current directory, then write 2 smaller tlog files, the first with
messages from t=100s to t=200s, and the second from t=300s to t=400s.

    tlog_segment.py --keep 100,200 300,400 *.tlog

Limitations:

    The user must provide the timestamps by examining the files.
    This only works on tlog files, not BIN (Dataflash) files.
"""

import os

# Bug? I'm seeing mavlink.WIRE_PROTOCOL_VERSION == "1.0" for some QGC-generated tlog files
# Force WIRE_PROTOCOL_VERSION to be 2.0
os.environ['MAVLINK20'] = '1'

import argparse

from pymavlink import mavutil

import table_types
import util


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for tlog files')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('-k', '--keep', default=None, nargs='+',
                        help='keep these segments, a segment is 2 timestamps separated by a comma, e.g., "100,200"')
    parser.add_argument('-d', '--discard', default=None, nargs='+',
                        help='discard these segments, and keep all the others')
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types to keep, the default is all types')
    parser.add_argument('--max-msgs', type=int, default=500000,
                        help='stop after processing this number of messages, default is 500K')
    parser.add_argument('--sysid', type=int, default=0,
                        help='source system id to keep, default is all source systems')
    parser.add_argument('--compid', type=int, default=0,
                        help='source component id to keep, default is all source components')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    if args.types:
        msg_types = args.types.split(',')
        print(f'Looking for these types: {msg_types}')
    else:
        msg_types = None

    for file in files:
        print('===================')
        print(file)
        # TODO


if __name__ == '__main__':
    main()
