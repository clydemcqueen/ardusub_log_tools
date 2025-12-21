#!/usr/bin/env python3

"""
Template for tlog tools that support segments.
"""

import argparse

import segment_reader


def process_reader(reader):
    pass


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    segment_reader.add_segment_args(parser)
    args = parser.parse_args()
    readers = segment_reader.choose_reader_list(args, ['HEARTBEAT'])

    for reader in readers:
        print(f'Processing {reader.name}...')
        process_reader(reader)


if __name__ == '__main__':
    main()
