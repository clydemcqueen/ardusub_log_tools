#!/usr/bin/env python3

"""
Read dataflash messages from a BIN file and report on anything interesting.
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import util


class DataflashLogInfo:
    def __init__(self, infile: str):
        self.infile = infile

        # Count # of msg values
        self.message_counts = {}

    def read_and_report(self):
        print(f'Results for {self.infile}')
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect='ardupilotmega')

        while (msg := mlog.recv_match(blocking=False, type=['MSG'])) is not None:
            raw_data = msg.to_dict()

            message = raw_data['Message']
            if message not in self.message_counts:
                self.message_counts[message] = 0
            self.message_counts[message] += 1

        # Print results
        for item in sorted(self.message_counts.items()):
            print(f'{item[1]:8d}  {item[0]}')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for BIN files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        reader = DataflashLogInfo(file)
        reader.read_and_report()


if __name__ == '__main__':
    main()
