#!/usr/bin/env python3

"""
Template for tlog tools that do not support segments.
"""

import argparse

import file_reader


def process_reader(reader):
    pass


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    file_reader.add_file_args(parser)
    args = parser.parse_args()
    readers = file_reader.FileReaderList(args, ['HEARTBEAT'])

    for reader in readers:
        print(f'Processing {reader.name}...')
        process_reader(reader)


if __name__ == '__main__':
    main()
