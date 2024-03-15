#!/usr/bin/env python3

"""
Read dataflash logs and report on high / low XKF1.G? (gyro_bias) values.
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import util


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for BIN files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    for file in files:
        mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect='ardupilotmega')

        gx, gy, gz = [], [], []
        while (msg := mlog.recv_match(blocking=False, type=['XKF1'])) is not None:
            gx.append(msg.GX)
            gy.append(msg.GY)
            gz.append(msg.GZ)

        print(f'{file :40} range gx ({min(gx) :6.2f}, {max(gx) :6.2f}), gy ({min(gy) :6.2f}, {max(gy) :6.2f}), gz ({min(gz) :6.2f}, {max(gz) :6.2f})')


if __name__ == '__main__':
    main()
