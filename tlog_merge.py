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
                 sysid: int,
                 compid: int):
        super().__init__(infile, msg_types, max_msgs, max_rows, verbose)
        self.sysid = sysid
        self.compid = compid

    def read_tlog(self):
        self.tables = {}
        for msg_type in self.msg_types:
            self.tables[msg_type] = table_types.Table.create_table(msg_type, self.verbose)

        print(f'Reading {self.infile}')
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=True, dialect='ardupilotmega')

        print('Parsing messages')
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=self.msg_types)) is not None:
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()

            # Filter by sysid and compid
            if self.sysid > 0 and self.sysid != sysid:
                continue
            if self.compid > 0 and self.compid != compid:
                continue

            msg_type = msg.get_type()

            # Suppress DISTANCE_SENSOR msgs from ArduSub, makes it easier to analyze the raw sensor msgs from BlueOS
            # if msg_type == 'DISTANCE_SENSOR' and compid == 1:
            #     continue

            # Only consider HEARTBEAT msgs from ArduSub
            # if msg_type == 'HEARTBEAT' and compid != 1:
            #     continue

            raw_data = msg.to_dict()

            # Add timestamp, sysid and compid
            timestamp = getattr(msg, '_timestamp', 0.0)
            clean_data = {'timestamp': timestamp, f'{msg_type}.sysid': sysid, f'{msg_type}.compid': compid}

            # Add a prefix to the existing keys
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

    def add_rate_field(self, half_n=10, field_name='rate'):
        for msg_type in self.msg_types:
            self.tables[msg_type].add_rate_field(half_n, field_name)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for tlog files')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
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
    parser.add_argument('--rate', action='store_true',
                        help='calculate rate for each message type')
    parser.add_argument('--sysid', type=int, default=0,
                        help='select source system id (default is all source systems)')
    parser.add_argument('--compid', type=int, default=0,
                        help='select source component id (default is all source components)')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.tlog')
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
            # 'TIMESYNC',
            'VFR_HUD',
            'VIBRATION',
        ]

    for file in files:
        print('===================')
        tlog_reader = TelemetryLogReader(file, msg_types, args.max_msgs, args.max_rows, args.verbose,
                                         args.sysid, args.compid)

        tlog_reader.read_tlog()

        if args.rate:
            tlog_reader.add_rate_field()

        if args.explode:
            tlog_reader.write_msg_csv_files()

        if not args.no_merge:
            tlog_reader.write_merged_csv_file()


if __name__ == '__main__':
    main()
