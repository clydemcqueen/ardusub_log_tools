#!/usr/bin/env python3

"""
Read ArduSub dataflash messages from a BIN file and merge the messages into a single, wide csv file. The merge
operation does a forward-fill (data is copied from the previous row), so the resulting merged csv file may be
substantially larger than the sum of the per-type csv files.
"""

from argparse import ArgumentParser
import pandas as pd
from pymavlink import mavutil
import util

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
]

# Useful for surftrak testing, this is the default for now
SURFTRAK_MSG_TYPES = [
    'ARM',
    'ATT',
    'BAT',
    'CTUN',
    'MODE',
    'RCIN',
    'RCOU',
]


class DataflashTable:
    @staticmethod
    def create_table(msg_type: str):
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


class DataflashLogReader:
    def __init__(self,
                 input_filename: str,
                 msg_types: list[str],
                 max_msgs: int,
                 max_rows: int,
                 verbose: bool):
        self.input_filename = input_filename
        self.prefix = input_filename.split('.')[0]
        self.msg_types = msg_types
        self.max_msgs = max_msgs
        self.max_rows = max_rows
        self.verbose = verbose
        self.tables = None

    def read(self):
        self.tables = {}
        for msg_type in self.msg_types:
            self.tables[msg_type] = DataflashTable.create_table(msg_type)

        print(f'Reading {self.input_filename}')
        mlog = mavutil.mavlink_connection(self.input_filename, robust_parsing=False, dialect='ardupilotmega')

        print('Parsing messages')
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=self.msg_types)) is not None:
            msg_type = msg.get_type()
            raw_data = msg.to_dict()

            # This will pull from TimeUS, which is present in all (most?) records
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

    def write_msg_csv_files(self):
        print('Writing csv files')
        for msg_type in self.msg_types:
            df = self.tables[msg_type].get_dataframe(self.verbose)
            filename = f'{self.prefix}_{msg_type}.csv'
            df.to_csv(filename)
            print(f'Writing {len(df)} rows to {filename}')

    def write_merged_csv_file(self):
        merged_df = None
        print(f'Merging dataframes')
        for msg_type in self.msg_types:
            df = self.tables[msg_type].get_dataframe(self.verbose)
            if df.empty:
                if self.verbose:
                    print(f'{msg_type} empty, skipping')
            else:
                if merged_df is None:
                    if self.verbose:
                        print(f'Starting with {len(df)} {msg_type} rows')
                    merged_df = df
                else:
                    if self.verbose:
                        print(f'Merging {len(df)} {msg_type} rows')
                    merged_df = pd.merge_ordered(merged_df, df, on='timestamp', fill_method='ffill')
                    if self.verbose:
                        print(f'Merged dataframe has {len(merged_df)} rows')
                    if len(merged_df) > self.max_rows:
                        print('Merged dataframe is too big, stopping')
                        break
        filename = f'{self.prefix}.csv'
        print(f'Writing {len(merged_df)} rows to {filename}')
        merged_df.to_csv(filename)


def main():
    # TODO the prefix method isn't working now

    parser = ArgumentParser(description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for BIN files')
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
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.paths, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    if args.types:
        msg_types = args.types.split(',')
    else:
        msg_types = SURFTRAK_MSG_TYPES

    for file in files:
        print('===================')
        reader = DataflashLogReader(file, msg_types, args.max_msgs, args.max_rows, args.verbose)
        reader.read()
        if args.explode:
            reader.write_msg_csv_files()
        if not args.no_merge:
            reader.write_merged_csv_file()


if __name__ == '__main__':
    main()
