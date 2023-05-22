#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.
"""

from argparse import ArgumentParser

from pymavlink import mavutil

import table_types
import util
from log_merger import LogMerger


class TelemetryLogReader(LogMerger):
    def __init__(self,
                 infile: str,
                 msg_types: list[str],
                 max_msgs: int,
                 max_rows: int,
                 verbose: bool,
                 all_types: bool):
        super().__init__(infile, msg_types, max_msgs, max_rows, verbose)
        self.all_types = all_types

    def read_tlog(self):
        self.tables = {}
        for msg_type in self.msg_types:
            self.tables[msg_type] = table_types.Table.create_table(msg_type, self.verbose)

        print(f'Reading {self.infile}')
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=True, dialect='ardupilotmega')

        print('Parsing messages')
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=self.msg_types)) is not None:
            # Only consider messages from ArduSub
            if not self.all_types and (msg.get_srcSystem() != 1 or msg.get_srcComponent() != 1):
                continue

            msg_type = msg.get_type()
            raw_data = msg.to_dict()
            timestamp = getattr(msg, '_timestamp', 0.0)

            # Clean up the data: add the timestamp, remove mavpackettype, and rename the keys
            clean_data = {'timestamp': timestamp}
            for key in raw_data.keys():
                if key != 'mavpackettype':
                    clean_data[f'{msg_type}.{key}'] = raw_data[key]

            self.tables[msg_type].append(clean_data)

            msg_count += 1
            if msg_count > self.max_msgs:
                print(f'Too many messages, stopping')
                break
            if self.verbose and msg_count % 20000 == 0:
                print(f'{msg_count} messages')

        print(f'{msg_count} messages')


def main():
    # TODO param time granularity
    # TODO TIMESYNC?
    # TODO SYSTEM_TIME?

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for tlog files')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('--all', action='store_true',
                        help='include all sources')
    parser.add_argument('--explode', action='store_true',
                        help='write a csv file for each message type')
    parser.add_argument('--no-merge', action='store_true',
                        help='do not merge tables, useful if you also select --explode')
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types, the default is a set of useful types')
    parser.add_argument('--max-msgs', type=int, default=500000,
                        help='stop after processing this number of messages (default 500K)')
    parser.add_argument('--max-rows', type=int, default=500000,
                        help='stop if the merged table exceeds this number of rows (default 500K)')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, '.tlog')
    print(f'Processing {len(files)} files')

    if args.types:
        msg_types = args.types.split(',')
    else:
        # Basically everything I've seen in an ArduSub tlog file
        msg_types = [
            'AHRS',
            'AHRS2',
            'ATTITUDE',
            # 'AUTOPILOT_VERSION',
            'BATTERY_STATUS',
            # 'COMMAND_ACK',
            # 'COMMAND_LONG',
            # 'DISTANCE_SENSOR',
            'EKF_STATUS_REPORT',
            'GLOBAL_POSITION_INT',
            'GPS2_RAW',
            'GPS_GLOBAL_ORIGIN',
            'GPS_RAW_INT',
            'HEARTBEAT',
            # 'HOME_POSITION',
            'HWSTATUS',
            'LOCAL_POSITION_NED',
            # 'MANUAL_CONTROL',
            'MEMINFO',
            # 'MISSION_ACK',
            # 'MISSION_COUNT',
            'MISSION_CURRENT',
            # 'MISSION_REQUEST_LIST',
            'MOUNT_STATUS',
            'NAMED_VALUE_FLOAT',
            'NAV_CONTROLLER_OUTPUT',
            # 'PARAM_REQUEST_LIST',
            # 'PARAM_VALUE',
            'POWER_STATUS',
            'RANGEFINDER',
            'RAW_IMU',
            'RC_CHANNELS',
            # 'REQUEST_DATA_STREAM',
            'SCALED_IMU2',
            'SCALED_PRESSURE',
            'SCALED_PRESSURE2',
            'SENSOR_OFFSETS',
            'SERVO_OUTPUT_RAW',
            # 'STATUSTEXT',
            'SYS_STATUS',
            'SYSTEM_TIME',
            'TIMESYNC',
            'VFR_HUD',
            'VIBRATION',
        ]

    for file in files:
        print('===================')
        tlog_reader = TelemetryLogReader(file, msg_types, args.max_msgs, args.max_rows, args.verbose, args.all)
        tlog_reader.read_tlog()
        if args.explode:
            tlog_reader.write_msg_csv_files()
        if not args.no_merge:
            tlog_reader.write_merged_csv_file()


if __name__ == '__main__':
    main()
