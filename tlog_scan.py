#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and report on any pymavlink crashes.
"""

from argparse import ArgumentParser
import os
from pymavlink import mavutil
import pymavlink.dialects.v20.ardupilotmega as apm
import util


class Scanner:
    def __init__(self, filename: str, types: list[str] | None):
        self.filename = filename
        self.types = types

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename, dialect='ardupilotmega')

        count = 0
        while True:
            try:
                msg = mlog.recv_match(blocking=False, type=self.types)
            except Exception as e:
                print(f'CRASH WITH ERROR "{e}" READING {self.filename}')
                return

            if msg is None:
                break

            count += 1

        print(f'Read {count} messages from {self.filename}')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for tlog files')
    parser.add_argument('--types', default=None, help='comma separated list of message types')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    if args.types:
        types = args.types.split(',')
    else:
        types = None

    for file in files:
        scanner = Scanner(file, types)
        scanner.read()


if __name__ == '__main__':
    main()
