#!/usr/bin/env python3

"""
Report on EKF3 status (XKF4.SS field).
"""

import datetime
from argparse import ArgumentParser

from pymavlink import mavutil

import util


# TODO copy process_ekf_status_report from tlog_timeline.py to reduce output

STATUS_BITS =[
   'attitude          ',  # 0 - true if attitude estimate is valid
   'horiz_vel         ',  # 1 - true if horizontal velocity estimate is valid
   'vert_vel          ',  # 2 - true if the vertical velocity estimate is valid
   'horiz_pos_rel     ',  # 3 - true if the relative horizontal position estimate is valid
   'horiz_pos_abs     ',  # 4 - true if the absolute horizontal position estimate is valid
   'vert_pos          ',  # 5 - true if the vertical position estimate is valid
   'terrain_alt       ',  # 6 - true if the terrain height estimate is valid
   'const_pos_mode    ',  # 7 - true if we are in const position mode
   'pred_horiz_pos_rel',  # 8 - true if filter expects it can produce a good relative horizontal position estimate - used before takeoff
   'pred_horiz_pos_abs',  # 9 - true if filter expects it can produce a good absolute horizontal position estimate - used before takeoff
   'takeoff_detected  ',  # 10 - true if optical flow takeoff has been detected
   'takeoff           ',  # 11 - true if filter is compensating for baro errors during takeoff
   'touchdown         ',  # 12 - true if filter is compensating for baro errors during touchdown
   'using_gps         ',  # 13 - true if we are using GPS position
   'gps_glitching     ',  # 14 - true if GPS glitching is affecting navigation accuracy
   'gps_quality_good  ',  # 15 - true if we can use GPS for navigation
   'initialized       ',  # 16 - true if the EKF has ever been healthy
   'rejecting_airspeed',  # 17 - true if we are rejecting airspeed data
   'dead_reckoning    ',  # 18 - true if we are dead reckoning (e.g. no position or velocity source)
]


class FilterStatusReport:
    def __init__(self, infile: str):
        self.infile = infile

        # Count # of msg values
        self.message_counts = {}

    def read_and_report(self):
        print(f'Results for {self.infile}')
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect='ardupilotmega')

        prev_status = 0

        while (msg := mlog.recv_match(blocking=False, type=['XKF4'])) is not None:
            curr_status = msg.SS

            if curr_status != prev_status:
                for bit in range(19):
                    prev_val = bool(prev_status & 1 << bit)
                    curr_val = bool(curr_status & 1 << bit)
                    if curr_val != prev_val:
                        print(f'{util.time_us_str(msg.TimeUS)} {"+" if curr_val else "-"} {STATUS_BITS[bit]}')
                print()

            prev_status = curr_status


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', help='enter directories looking for BIN files', action='store_true')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    for file in files:
        print('-------------------')
        reader = FilterStatusReport(file)
        reader.read_and_report()


if __name__ == '__main__':
    main()
