#!/usr/bin/env python3

"""
Read a tlog file (telemetry log) and report on bad timestamps.

Supports segments.
"""

import time
from argparse import ArgumentParser

from segment_reader import add_segment_args, choose_reader_list


def check_timestamps(reader):
    count = 0
    prev_timestamp = None
    tomorrow = time.time() + 24 * 60 * 60

    for msg in reader:
        sysid = msg.get_srcSystem()
        compid = msg.get_srcComponent()
        msg_type = msg.get_type()
        timestamp = getattr(msg, '_timestamp', 0.0)

        if timestamp > tomorrow:
            print(f'  Time {timestamp} is in the future; message num={count}, type={msg_type}, sysid={sysid}, compid={compid}')

        if prev_timestamp is not None and timestamp < prev_timestamp:
            print(f'  Time went backwards from {prev_timestamp} to {timestamp}; message num={count}, sysid={sysid}, compid={compid}')

        count += 1
        prev_timestamp = timestamp


def main():
    parser = ArgumentParser(description=__doc__)
    add_segment_args(parser)
    parser.add_argument('--types', default=None, help='comma separated list of message types, default is all types')
    args = parser.parse_args()
    msg_types = None if args.types is None else args.types.split(',')
    readers = choose_reader_list(args, msg_types)
    for reader in readers:
        print(f'Scanning {reader.name}...')
        check_timestamps(reader)


if __name__ == '__main__':
    main()
