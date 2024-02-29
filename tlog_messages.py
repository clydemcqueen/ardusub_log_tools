#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and write STATUSTEXT messages.
"""

import argparse

import file_reader
import util


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    file_reader.add_file_args(parser)
    args = parser.parse_args()
    readers = file_reader.FileReaderList(args, ['STATUSTEXT'])

    for reader in readers:
        outfile_name = util.get_outfile_name(reader.name, suffix='_messages', ext='.txt')
        print(f'Reading {reader.name}, writing {outfile_name}')

        with open(outfile_name, 'w') as f:
            messages = {}

            for msg in reader:
                if msg.text not in messages:
                    messages[msg.text] = 0
                messages[msg.text] += 1

            for key, count in sorted(messages.items()):
                f.write(f'{key}: {count}\n')


if __name__ == '__main__':
    main()
