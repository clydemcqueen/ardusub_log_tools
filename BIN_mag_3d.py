#!/usr/bin/env python3

"""
Note transitions to/from mag 3d fusion
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import util


class Report:
    def __init__(self, filename: str):
        self.filename = filename

    def read(self):
        mlog = mavutil.mavlink_connection(self.filename)

        prev_msg = None
        sel = prev_sel = 'no info'

        # Don't crash reading a corrupt file
        try:
            while True:
                msg = mlog.recv_match(type=['XKF3'], blocking=False)
                if msg is None:
                    break

                if prev_msg is None:
                    prev_msg = msg
                    continue

                if msg.IYAW != prev_msg.IYAW:
                    sel = 'fuse yaw'
                elif msg.IMX != prev_msg.IMX or msg.IMY != prev_msg.IMY or msg.IMZ != prev_msg.IMZ:
                    sel = 'fuse mag'

                prev_msg = msg

                if sel != prev_sel:
                    print(f'{util.time_us_str(msg.TimeUS)}, core {msg.C}, {prev_sel} to {sel}')
                    prev_sel = sel

        except Exception as e:
            print(f'CRASH WITH ERROR "{e}", SHOWING PARTIAL RESULTS')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true', help='enter directories looking for BIN files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ['.BIN'])
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        print(f'Reading {file}')
        scanner = Report(file)
        scanner.read()


if __name__ == '__main__':
    main()
