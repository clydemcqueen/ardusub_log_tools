#!/usr/bin/env python3

"""
Read messages from tlog (telemetry) and BIN (dataflash) logs and report on the message types found.
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import util


class TypeFinder:
    def __init__(self, filename: str):
        self.filename = filename

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename, dialect='ardupilotmega')

        # Count # of messages per type
        msg_counts = {}

        # Don't crash reading a corrupt file
        try:
            while True:
                msg = mlog.recv_match(blocking=False)
                if msg is None:
                    break

                msg_type = msg.get_type()

                if msg_type not in msg_counts.keys():
                    msg_counts[msg_type] = 0

                msg_counts[msg_type] += 1

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')

        for msg_type, msg_count in sorted(msg_counts.items()):
            print(f'{msg_type:25} {msg_count:6d}')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for tlog and BIN files')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, ['.tlog', '.BIN'])
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        print(f'Reading {file}')
        scanner = TypeFinder(file)
        scanner.read()


if __name__ == '__main__':
    main()
