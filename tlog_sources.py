#!/usr/bin/env python3

"""
Read MAVLink messages and count messages by source

Supports segments.
"""

from argparse import ArgumentParser

from segment_reader import add_segment_args, choose_reader_list


def count_by_source(reader):
    counts: dict[tuple[int, int], int] = {}

    for msg in reader:
        source = (msg.get_srcSystem(), msg.get_srcComponent())
        if source not in counts.keys():
            counts[source] = 0
        counts[source] += 1

    if len(counts) == 0:
        return

    print(f'{reader.name}')
    for source in counts.keys():
        print(f'   {source[0] :3}, {source[1] :3}: {counts[source] :6}')


def main():
    parser = ArgumentParser(description=__doc__)
    add_segment_args(parser)
    parser.add_argument('--types', default=None, help='comma separated list of message types, default is all types')
    args = parser.parse_args()
    msg_types = None if args.types is None else args.types.split(',')
    readers = choose_reader_list(args, msg_types)
    for reader in readers:
        count_by_source(reader)


if __name__ == '__main__':
    main()
