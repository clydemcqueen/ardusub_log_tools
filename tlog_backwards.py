#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and check to see if time goes backwards.

Supports segments.
"""

from argparse import ArgumentParser

from segment_reader import add_segment_args, choose_reader_list


def check_timestamps(reader):
    count = 0
    prev_timestamp = None

    for msg in reader:
        sysid = msg.get_srcSystem()
        compid = msg.get_srcComponent()
        timestamp = getattr(msg, '_timestamp', 0.0)

        if prev_timestamp is not None:
            if timestamp < prev_timestamp:
                print(f'Time goes backwards: count={count}, sysid={sysid}, compid={compid}, {prev_timestamp} to {timestamp}')

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
        check_timestamps(reader)


if __name__ == '__main__':
    main()
