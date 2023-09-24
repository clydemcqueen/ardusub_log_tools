#!/usr/bin/env python3

"""
Read MAVLink messages from one or more tlog files (telemetry logs), stitch them together in time order, then extract
and write segments as new, smaller tlog files. Segments are specified with one or more "--keep x,y,name" options, where
x and y are timestamps. Timestamps can be specified in 2 ways:

    Seconds since the start of the earliest tlog file in the list, e.g., 100.
    Unix time (seconds since January 1st, 1970 UTC), e.g., 1694633807.

Example: stitch together all tlog files in the current directory, then write 2 smaller tlog files, the first with
messages from t=100s to t=200s, and the second from t=300s to t=400s.

    tlog_segment.py --keep 100,200 --keep 300,400 *.tlog

Limitations:

    The user must provide the timestamps by examining the files.
    This only works on tlog files, not BIN (Dataflash) files.
"""

import argparse

from segment_reader import add_segment_args, parse_segment_args


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types to keep, the default is all types')
    parser.add_argument('--sysid', type=int, default=0,
                        help='source system id to keep, default is all source systems')
    parser.add_argument('--compid', type=int, default=0,
                        help='source component id to keep, default is all source components')
    args = parser.parse_args()

    segments = parse_segment_args(args.keep)
    print(f'Segments: {segments}')

    if args.types:
        msg_types = args.types.split(',')
        print(f'Looking for these types: {msg_types}')

    # TODO implement tlog file writing


if __name__ == '__main__':
    main()
