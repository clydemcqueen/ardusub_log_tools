#!/usr/bin/env python3

"""
Read dataflash messages from a BIN file and report on a few interesting things.
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

        count_gps_records = 0
        gps_week = 0
        gps_week_ms = 0

        count_orgn_records = 0

        while (msg := mlog.recv_match(blocking=False, type=['MSG', 'GPS', 'ORGN'])) is not None:

            if msg.get_type() == 'MSG':
                message = msg.Message
                if message not in self.message_counts:
                    self.message_counts[message] = 0
                self.message_counts[message] += 1

            elif msg.get_type() == 'GPS' and gps_week == 0:
                count_gps_records += 1
                if msg.GWk > 0:
                    gps_week = msg.GWk
                    gps_week_ms = msg.GMS

            elif msg.get_type() == 'ORGN':
                count_orgn_records += 1
                origin_type = 'EKF origin' if msg.Type == 0 else 'AHRS home'
                print(f'{origin_type} set after {msg.TimeUS / 1e6 :.1f} seconds: ({msg.Lat}, {msg.Lng}, {msg.Alt})')

        if count_orgn_records == 0:
            print('No ORGN records, origin was not set')

        if count_gps_records == 0:
            print('No GPS records, no datetime information')
        elif gps_week == 0:
            print(f'{count_gps_records} GPS records, gps_week is always 0, no datetime information')
        else:
            print(f'{count_gps_records} GPS records, last record gps_week {gps_week}, gps_week_ms {gps_week_ms}')

        print('List of messages, with counts:')
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
