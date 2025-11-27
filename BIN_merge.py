#!/usr/bin/env python3

"""
Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.

BIN_merge.py can also write multiple csv files, one per type, using the --explode option.

You can examine the contents of a single table using the --explode, --no-merge and --types options:
BIN_merge.py --explode --no-merge --types GPS 000011.BIN
"""

import argparse

import pandas as pd
from pymavlink import mavutil

import util
from log_merger import LogMerger

# Basically everything I've seen in an ArduSub dataflash (BIN) file
ALL_MSG_TYPES = [
    'AHR2',
    'ARM',
    'ATT',
    'BARO',
    'BAT',
    'CTRL',
    'CTUN',
    'DSF',
    'DU32',
    'EV',
    'FMT',
    'FMTU',
    'FTN',
    'GPA',
    'GPS',
    'IMU',
    'MAG',
    'MAV',
    'MAVC',
    'MODE',
    'MOTB',
    'MSG',
    'MULT',
    'PARM',
    'PM',
    'PSCD',
    'RATE',
    'RCI2',
    'RCIN',
    'RCOU',
    'RFND',
    'UNIT',
    'VIBE',
    'XKF1',
    'XKF2',
    'XKF3',
    'XKF4',
    'XKF5',
    'XKFS',
    'XKQ',
    'XKT',
    'XKV1',
    'XKV2',
    'XKFD',  # Not on by default for ArduSub, need to add a compiler flag
]

# Stuff that looks kinda interesting
PERHAPS_USEFUL_MSG_TYPES = [
    'AHR2',
    'ARM',
    'ATT',
    'BARO',
    'BAT',
    'CTRL',
    'CTUN',
    'DSF',
    'DU32',
    'EV',
    'FMT',
    'FMTU',
    'FTN',
    'GPS',
    'IMU',
    'MAG',
    'MAV',
    'MAVC',
    'MODE',
    'MOTB',
    'MSG',
    'MULT',
    'PARM',
    'PM',
    'PSCD',
    'RATE',
    'RCI2',
    'RCIN',
    'RCOU',
    'RFND',
    'XKFD',  # Not on by default for ArduSub, need to add a compiler flag
]

# Messages types that can be split by the 'C' field
SPLIT_CORE_MSG_TYPES = [
    'XKF1',  # EKF3 estimator outputs
    'XKF2',  # EKF3 estimator secondary outputs
    'XKF3',  # EKF3 innovations
    'XKF4',  # EKF3 variances
    'XKFS',  # EKF3 sensor selection
    'XKQ',   # EKF3 quaternion defining the rotation from NED to XYZ (autopilot) axes
    'XKT',   # EKF3 timing information
    'XKTV',  # EKF3 Yaw Estimator States
]

# Messages types that can be split by the 'I' field
SPLIT_INSTANCE_MSG_TYPES = [
    'BARO',  # Barometer data
    'IMU',   # IMU data
    'MAG',   # Compass data
]

EKF_MSG_TYPES = [
    *SPLIT_CORE_MSG_TYPES,
    'XKF5',  # EKF3 Sensor innovations (primary core) and general dumping ground
    'XKV1',  # EKF3 State variances (primary core)
    'XKV2',  # more EKF3 State Variances (primary core)
]


class DataflashTable:
    @staticmethod
    def create_table(msg_type: str):
        if msg_type == 'RCIN':
            return RCINTable()
        elif msg_type == 'PSCN':
            return PSCxTable(msg_type, 'N', flip=False)
        elif msg_type == 'PSCE':
            return PSCxTable(msg_type, 'E', flip=False)
        elif msg_type == 'PSCD':
            return PSCxTable(msg_type, 'D', flip=False)
        elif msg_type == 'PSCU':
            return PSCxTable(msg_type, 'D', flip=True)
        elif msg_type == 'XKV1':
            return XKV1Table(msg_type)
        elif msg_type == 'XKV2':
            return XKV2Table(msg_type)
        elif msg_type.startswith('XKF1'):
            return XKF1Table(msg_type)
        elif msg_type.startswith('XKF4'):
            return XKF4Table(msg_type)
        elif msg_type.startswith('XKF5'):
            return XKF5Table(msg_type)
        else:
            return DataflashTable(msg_type)

    def __init__(self, msg_type: str):
        self._msg_type = msg_type
        self._rows = []
        self._df = None

    def append(self, row: dict):
        self._rows.append(row)

    def get_dataframe(self, verbose):
        if self._df is None:
            self._df = pd.DataFrame(self._rows)
            if verbose:
                print('-----------------')
                if self._df.empty:
                    print(f'{self._msg_type} is empty')
                else:
                    print(f'{self._msg_type} has {len(self._df)} rows:')
                    print(self._df.head())

        return self._df


class RCINTable(DataflashTable):
    def __init__(self):
        super().__init__('RCIN')

    RC_MAP = [(1, 'pitch'), (2, 'roll'), (3, 'throttle'), (4, 'yaw'), (5, 'forward'), (6, 'lateral')]

    def append(self, row: dict):
        # Rename a few fields for ease-of-use
        for item in RCINTable.RC_MAP:
            row[f'RCIN.C{item[0]}_{item[1]}'] = row.pop(f'RCIN.C{item[0]}')
        super().append(row)


class PSCxTable(DataflashTable):
    """
    Works with PosControl tables PSCN (north), PSCE (east), PSCD (down) and the made-up table PSCU (up)
    Suffix should be 'N', 'E', 'D'; this is used to change field names from short codes to log_PSCx struct field names
    Flip means flip the sign, e.g., from down to up
    """
    def __init__(self, table_name: str, suffix: str, flip: bool):
        super().__init__(table_name)
        self._suffix = suffix
        self._flip = flip

    MAP = [
        # log_PSCx struct field       PosControl/InertialNav method     Underlying PosControl/InertialNav variable
        ('TP', 'pos_target'),       # get_pos_target_cm().z             _pos_target.z
        ('P',  'pos'),              # _inav.get_position_z_up_cm()      _relpos_cm.z
        ('DV', 'vel_desired'),      # get_vel_desired_cms().z           _vel_desired.z
        ('TV', 'vel_target'),       # get_vel_target_cms().z            _vel_target.z
        ('V',  'vel'),              # _inav.get_velocity_z_up_cms()     _velocity_cm.z
        ('DA', 'accel_desired'),    # _accel_desired.z                  _accel_desired.z
        ('TA', 'accel_target'),     # get_accel_target_cmss().z         _accel_target.z
        ('A',  'accel')             # get_z_accel_cmss()                -(_ahrs.get_accel_ef().z + GRAVITY_MSS) * 100.0
    ]

    def append(self, row: dict):
        for item in PSCxTable.MAP:
            field = row.pop(f'{self._msg_type}.{item[0]}{self._suffix}')
            row[f'{self._msg_type}.{item[1]}'] = -field if self._flip else field
        super().append(row)


def rename_fields(row: dict, map: list[tuple], msg_type: str) -> dict:
    for item in map:
        field = row.pop(f'{msg_type}.{item[0]}')
        row[f'{msg_type}.{item[1]}'] = field
    return row


class XKV1Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    MAP = [
        ('V00', 'q0'),
        ('V01', 'q1'),
        ('V02', 'q2'),
        ('V03', 'q3'),
        ('V04', 'vel_N'),
        ('V05', 'vel_E'),
        ('V06', 'vel_D'),
        ('V07', 'pos_N'),
        ('V08', 'pos_E'),
        ('V09', 'pos_D'),
        ('V10', 'gyro_bias_X'),
        ('V11', 'gyro_bias_Y'),
    ]

    def append(self, row: dict):
        rename_fields(row, XKV1Table.MAP, self._msg_type)
        super().append(row)


class XKF1Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Add a PU (position up) field = -PD (position down)
        pd_field = f'{self._msg_type}.PD'
        if pd_field in row:
            row[f'{self._msg_type}.PU'] = -row[pd_field]
        super().append(row)


class XKV2Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    MAP = [
        ('V12', 'gyro_bias_Z'),
        ('V13', 'accel_bias_X'),
        ('V14', 'accel_bias_Y'),
        ('V15', 'accel_bias_Z'),
        ('V16', 'earth_mag_N'),
        ('V17', 'earth_mag_E'),
        ('V18', 'earth_mag_D'),
        ('V19', 'body_mag_X'),
        ('V20', 'body_mag_Y'),
        ('V21', 'body_mag_Z'),
        ('V22', 'wind_vel_N'),
        ('V23', 'wind_vel_E'),
    ]

    def append(self, row: dict):
        rename_fields(row, XKV2Table.MAP, self._msg_type)
        super().append(row)


class XKF4Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        ss_field = f'{self._msg_type}.SS'
        row[f'{self._msg_type}.const_pos'] = 1 if row[ss_field] & (1 << 7) else 0
        row[f'{self._msg_type}.horiz_rel'] = 1 if row[ss_field] & (1 << 3) else 0
        super().append(row)


class XKF5Table(DataflashTable):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Add offset_up field as negative of offset (terrainState)
        offset_field = f'{self._msg_type}.offset'
        if offset_field in row:
            row[f'{self._msg_type}.offset_up'] = -row[offset_field]
        super().append(row)


class DataflashTableSTATUS(DataflashTable):
    def __init__(self, tables: dict, verbose: bool):
        super().__init__('STATUS')

        print('Generating STATUS table')

        frames = []

        if 'MODE' in tables:
            df = tables['MODE'].get_dataframe(verbose)[['timestamp', 'MODE.TimeUS', 'MODE.Mode']].copy()
            df.rename(columns={'MODE.TimeUS': 'STATUS.TimeUS', 'MODE.Mode': 'STATUS.Mode'}, inplace=True)
            df['STATUS.Source'] = 0
            frames.append(df)

        if 'ARM' in tables:
            df = tables['ARM'].get_dataframe(verbose)[['timestamp', 'ARM.TimeUS', 'ARM.ArmState']].copy()
            df.rename(columns={'ARM.TimeUS': 'STATUS.TimeUS', 'ARM.ArmState': 'STATUS.ArmState'}, inplace=True)
            df['STATUS.Source'] = 1
            frames.append(df)

        if 'ERR' in tables:
            df = tables['ERR'].get_dataframe(verbose)[
                ['timestamp', 'ERR.TimeUS', 'ERR.Subsys', 'ERR.ECode']].copy()
            df.rename(columns={'ERR.TimeUS': 'STATUS.TimeUS', 'ERR.Subsys': 'STATUS.ERR_Subsys',
                               'ERR.ECode': 'STATUS.ERR_ECode'}, inplace=True)
            df['STATUS.Source'] = 2
            frames.append(df)

        if 'EV' in tables:
            df = tables['EV'].get_dataframe(verbose)[['timestamp', 'EV.TimeUS', 'EV.Id']].copy()
            df.rename(columns={'EV.TimeUS': 'STATUS.TimeUS', 'EV.Id': 'STATUS.EV_Id'}, inplace=True)
            df['STATUS.Source'] = 3
            frames.append(df)

        if frames:
            status_df = pd.concat(frames)
            status_df.sort_values(by=['timestamp'], inplace=True)
            self._rows = status_df.to_dict('records')


class DataflashLogReader(LogMerger):
    def __init__(self,
                 infile: str,
                 msg_types: list[str],
                 max_msgs: int,
                 max_rows: int,
                 verbose: bool,
                 raw: bool,
                 start: float,
                 stop: float,
                 rtc_shift: float = 0.0):
        super().__init__(infile, max_msgs, max_rows, verbose)
        self.msg_types = msg_types
        self.raw = raw
        self.start = start
        self.stop = stop
        self.rtc_shift = rtc_shift

        # Make up the PSCU (position control 'up') table, a flipped version of PSCD
        self.pscu = 'PSCU' in msg_types
        if self.pscu:
            if 'PSCD' in msg_types:
                print('PSCD and PSCU both requested, dropping PSCD')
            else:
                msg_types.append('PSCD')

        # Make up the STATUS table from MODE, ARM, ERR and EV
        self.status = 'STATUS' in msg_types
        if self.status:
            msg_types.remove('STATUS')
            print('STATUS is a synthetic table and requires MODE, ARM, ERR and EV')
            if 'MODE' not in msg_types:
                msg_types.append('MODE')
            if 'ARM' not in msg_types:
                msg_types.append('ARM')
            if 'ERR' not in msg_types:
                msg_types.append('ERR')
            if 'EV' not in msg_types:
                msg_types.append('EV')

    def read(self):
        self.tables = {}

        print(f'Reading {self.infile}')
        mlog = mavutil.mavlink_connection(self.infile, robust_parsing=False, dialect='ardupilotmega')

        print('Parsing messages')
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=self.msg_types)) is not None:
            msg_type = msg.get_type()
            raw_data = msg.to_dict()

            # Hack: drop readings from the barometer inside the electronics tube
            if not self.raw and msg_type == 'BARO' and raw_data['I'] == 0:
                continue

            # Hack: drop GPS and AHR2 readings where Lat/Lng are 0
            if not self.raw and (msg_type == 'AHR2' or msg_type == 'GPS') and raw_data['Lat'] == 0:
                continue

            table_name = msg_type

            # Hack: split some tables into _core0, ... and _instance0, ...
            if msg_type in SPLIT_CORE_MSG_TYPES:
                table_name = f'{msg_type}_core{msg.C}'
            elif msg_type in SPLIT_INSTANCE_MSG_TYPES:
                table_name = f'{msg_type}_instance{msg.I}'

            # Hack: make up the PSCU table
            if msg_type == 'PSCD' and self.pscu:
                table_name = 'PSCU'

            # This will pull from TimeUS, which is present in nearly all records
            timestamp = getattr(msg, '_timestamp', 0.0) + self.rtc_shift

            # Hack: process just a segment
            if self.start >= 0 and timestamp < self.start:
                continue
            if 0 < self.stop < timestamp:
                continue

            # Clean up the data: add the timestamp, remove mavpackettype, and rename the keys
            clean_data = {'timestamp': timestamp}
            for key in raw_data.keys():
                if key != 'mavpackettype':
                    clean_data[f'{table_name}.{key}'] = raw_data[key]

            if table_name not in self.tables:
                print(f'adding {table_name}')
                self.tables[table_name] = DataflashTable.create_table(table_name)

            self.tables[table_name].append(clean_data)

            msg_count += 1
            if msg_count > self.max_msgs:
                print(f'Too many messages, stopping')
                break
            if self.verbose and msg_count % 20000 == 0:
                print(f'{msg_count} messages')

        print(f'{msg_count} messages')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for BIN files')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print a lot more information')
    parser.add_argument('--explode', action='store_true',
                        help='write a csv file for each message type')
    parser.add_argument('--no-merge', action='store_true',
                        help='do not merge tables, useful if you also select --explode')
    parser.add_argument('--types', default=None,
                        help='comma separated list of message types')
    parser.add_argument('--ekf', action='store_true',
                        help='add all ekf message types to the list of types')
    parser.add_argument('--max-msgs', type=int, default=500000,
                        help='stop after processing this number of messages (default 500K)')
    parser.add_argument('--max-rows', type=int, default=500000,
                        help='stop if the merged table exceeds this number of rows (default 500K)')
    parser.add_argument('--raw', action='store_true',
                        help='show all records; default is to drop BARO records where id==0')
    parser.add_argument('--start', type=float, default=-1.0,
                        help='experiment: segment start')
    parser.add_argument('--stop', type=float, default=-1.0,
                        help='experiment: segment stop')
    parser.add_argument('--sync', default=None,
                        help='experiment: provide a tlog file to establish an rtc_shift')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    if args.types:
        msg_types = args.types.split(',')
        if args.ekf:
            msg_types.extend(EKF_MSG_TYPES)
    elif args.ekf:
        msg_types = EKF_MSG_TYPES
    else:
        msg_types = PERHAPS_USEFUL_MSG_TYPES
    print(f'Looking for {len(msg_types)} types: {msg_types}')

    if args.sync:
        print(f'Experiment: adjust timestamps using an RTC shift from {args.sync}')
        tlog_conn = mavutil.mavlink_connection(args.sync, robust_parsing=False)
        rtc_shift = util.get_rtc_shift(tlog_conn)
        if rtc_shift is None:
            print('Failed to get RTC shift')
            rtc_shift = 0
        else:
            print(f'RTC shift is {rtc_shift}')
    else:
        rtc_shift = 0

    for file in files:
        print('===================')
        reader = DataflashLogReader(file, msg_types, args.max_msgs, args.max_rows, args.verbose, args.raw, args.start, args.stop, rtc_shift)
        reader.read()
        if reader.status:
            reader.tables['STATUS'] = DataflashTableSTATUS(reader.tables, args.verbose)
        if args.explode:
            reader.write_msg_csv_files()
        if not args.no_merge:
            reader.write_merged_csv_file()


if __name__ == '__main__':
    main()
