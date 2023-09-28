#!/usr/bin/env python3
import math

import pandas as pd

import util

# Look at tables with time_boot_ms fields. Findings:
# DISTANCE_SENSOR from BlueOS is off by ~450s, so it can't be trusted
# Good readings from messages from ArduSub (RC_CHANNELS, SYSTEM_TIME, possibly others)
# tables_with_time_boot_ms = []


class Table:
    @staticmethod
    def create_table(
            msg_type: str,
            verbose: bool = False,
            hdop_max: float = 100.0,
            table_name: str | None = None,
            filter: bool = False):
        # table_name can be different from msg_type, e.g., HEARTBEAT_255_0 if split_source is True
        if table_name is None:
            table_name = msg_type

        if msg_type == 'AHRS2':
            return AHRS2Table(table_name)
        elif msg_type == 'BATTERY_STATUS':
            return BatteryStatusTable(table_name)
        elif msg_type == 'HEARTBEAT':
            return HeartbeatTable(table_name)
        elif msg_type == 'GLOBAL_POSITION_INT':
            return GlobalPositionIntTable(table_name)
        elif msg_type == 'GPS_INPUT':
            return GPSInputTable(table_name, verbose, hdop_max)
        elif msg_type == 'GPS_RAW_INT':
            return GPSRawIntTable(table_name, hdop_max, filter)
        elif msg_type == 'GPS2_RAW':
            return GPS2RawTable(table_name, hdop_max)
        elif msg_type == 'NAMED_VALUE_FLOAT':
            return NamedValueFloatTable(table_name)
        elif msg_type == 'RC_CHANNELS':
            return RCChannelsTable(table_name)
        elif msg_type == 'VISION_POSITION_DELTA':
            return VisionPositionDeltaTable(table_name)
        else:
            return Table(table_name)

    def __init__(self, table_name: str):
        self._table_name = table_name
        self._rows = []
        self._df = None

    def append(self, row: dict):
        # Drop fields that have array values, they don't work well in csv files
        for key in list(row.keys()):
            if isinstance(row[key], list):
                row.pop(key)

        # global tables_with_time_boot_ms
        # for key in list(row.keys()):
        #     key_str = str(key)
        #     if key_str.endswith('time_boot_ms') and key_str not in tables_with_time_boot_ms:
        #         print(f'{key_str} in seconds: {row[key_str] / 1000.0}')
        #         tables_with_time_boot_ms.append(key_str)

        self._rows.append(row)

    def add_rate_field(self, half_n=10, field_name='rate'):
        util.add_rate_field(self._rows, half_n, 4.0, f'{self._table_name}.{field_name}')

    def get_dataframe(self, verbose):
        if self._df is None:
            self._df = pd.DataFrame(self._rows)
            if verbose:
                print('-----------------')
                if self._df.empty:
                    print(f'{self._table_name} is empty')
                else:
                    print(f'{self._table_name} has {len(self._df)} rows:')
                    print(self._df.head())

        return self._df

    def __len__(self):
        return len(self._rows)


class AHRS2Table(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Add degree fields
        row[f'{self._table_name}.roll_deg'] = math.degrees(row[f'{self._table_name}.roll'])
        row[f'{self._table_name}.pitch_deg'] = math.degrees(row[f'{self._table_name}.pitch'])
        row[f'{self._table_name}.yaw_deg'] = math.degrees(row[f'{self._table_name}.yaw'])
        super().append(row)


class BatteryStatusTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Grab the voltage of the first battery
        row[f'{self._table_name}.voltage'] = row[f'{self._table_name}.voltages'][0]
        super().append(row)


class HeartbeatTable(Table):
    MODE_DISARMED = -10

    def __init__(self, table_name: str):
        super().__init__(table_name)

    def is_armed(self, row):
        # base_mode is a bitfield, 128 == armed
        # Sub modes: https://mavlink.io/en/messages/ardupilotmega.html#SUB_MODE
        return row[f'{self._table_name}.base_mode'] >= 128

    def get_mode(self, row):
        if not self.is_armed(row):
            return HeartbeatTable.MODE_DISARMED
        else:
            return row[f'{self._table_name}.custom_mode']

    def append(self, row: dict):
        row[f'{self._table_name}.mode'] = self.get_mode(row)
        super().append(row)


class GlobalPositionIntTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._table_name}.lat_deg'] = row[f'{self._table_name}.lat'] / 1.0e7
        row[f'{self._table_name}.lon_deg'] = row[f'{self._table_name}.lon'] / 1.0e7
        super().append(row)


class GPSInputTable(Table):
    def __init__(self, table_name: str, verbose: bool, hdop_max: float):
        super().__init__(table_name)
        self._verbose = verbose
        self._hdop_max = hdop_max

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._table_name}.lat_deg'] = row[f'{self._table_name}.lat'] / 1.0e7
        row[f'{self._table_name}.lon_deg'] = row[f'{self._table_name}.lon'] / 1.0e7

        if row[f'{self._table_name}.fix_type'] < 3:
            if self._verbose:
                print(f'{self._table_name}.fix_type < 3, lat {row["{self._table_name}.lat_deg"]}, lon {row["{self._table_name}.lon_deg"]}, fix_type {row["{self._table_name}.fix_type"]}')
            return

        if row[f'{self._table_name}.hdop'] > self._hdop_max:
            if self._verbose:
                print(f'{self._table_name}.hdop > {self._hdop_max}, lat {row["{self._table_name}.lat_deg"]}, lon {row["{self._table_name}.lon_deg"]}, hdop {row["{self._table_name}.hdop"]}')
            return

        super().append(row)


class GPSRawIntTable(Table):
    def __init__(self, table_name: str, hdop_max: float, filter: bool):
        super().__init__(table_name)
        self._hdop_max = hdop_max
        self._filter = filter

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._table_name}.lat_deg'] = row[f'{self._table_name}.lat'] / 1.0e7
        row[f'{self._table_name}.lon_deg'] = row[f'{self._table_name}.lon'] / 1.0e7

        # ArduSub warm up sends zillions of sensor messages with bad fix_type and eph; don't bother printing these
        if self._filter and row[f'{self._table_name}.fix_type'] < 3:
            return

        if self._filter and row[f'{self._table_name}.eph'] > self._hdop_max:
            return

        super().append(row)


class GPS2RawTable(Table):
    def __init__(self, table_name: str, hdop_max: float):
        super().__init__(table_name)
        self._hdop_max = hdop_max

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._table_name}.lat_deg'] = row[f'{self._table_name}.lat'] / 1.0e7
        row[f'{self._table_name}.lon_deg'] = row[f'{self._table_name}.lon'] / 1.0e7

        # ArduSub warm up sends zillions of sensor messages with bad fix_type and eph; don't bother printing these
        if row[f'{self._table_name}.fix_type'] < 3:
            return

        if row[f'{self._table_name}.eph'] > self._hdop_max:
            return

        super().append(row)


class NamedValueFloatTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def get_one_named_value_float_type(self, input_df, name: str):
        # Get a subset of rows
        df = input_df[input_df[f'{self._table_name}.name'] == name]

        # Get a subset of columns
        df = df[['timestamp', f'{self._table_name}.value']]

        # Rename one column
        return df.rename(columns={f'{self._table_name}.value': f'SUB_INFO.{name}'})

    def get_dataframe(self, verbose):
        if self._df is None:
            # Create the NAMED_VALUE_FLOAT dataframe, which is a set of key-value pairs
            named_value_float_df = pd.DataFrame(self._rows)

            if verbose:
                print('-----------------')
                if named_value_float_df.empty:
                    print(f'{self._table_name} is empty')
                else:
                    print(f'{self._table_name} has {len(named_value_float_df)} rows:')
                    print(named_value_float_df.head())

            # Re-arrange the data so it appears like it does in the QGC-generated csv file. Since the timestamps are
            # fine-grained this may result in an explosion of data, so let's just do this for a few key columns.
            if verbose:
                print('Pulling out Lights2 and PilotGain and rearranging')
            lights2_df = self.get_one_named_value_float_type(named_value_float_df, 'Lights2')
            pilot_gain_df = self.get_one_named_value_float_type(named_value_float_df, 'PilotGain')
            self._df = pd.merge_ordered(lights2_df, pilot_gain_df, on='timestamp', fill_method='ffill')

            if verbose:
                if self._df.empty:
                    print(f'{self._table_name} is empty')
                else:
                    print(f'{self._table_name} has {len(self._df)} rows:')
                    print(self._df.head())

        return self._df


class RCChannelsTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    RC_MAP = [(1, 'pitch'), (2, 'roll'), (3, 'throttle'), (4, 'yaw'), (5, 'forward'), (6, 'lateral')]

    def append(self, row: dict):
        # Rename a few fields for ease-of-use
        for item in RCChannelsTable.RC_MAP:
            row[f'{self._table_name}.chan{item[0]}_raw_{item[1]}'] = row.pop(f'{self._table_name}.chan{item[0]}_raw')
        super().append(row)


class VisionPositionDeltaTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        # Flatten angle array
        row[f'{self._table_name}.roll_delta'] = row[f'{self._table_name}.angle_delta'][0]
        row[f'{self._table_name}.pitch_delta'] = row[f'{self._table_name}.angle_delta'][1]
        row[f'{self._table_name}.yaw_delta'] = row[f'{self._table_name}.angle_delta'][2]

        # Flatten position array
        row[f'{self._table_name}.x_delta'] = row[f'{self._table_name}.position_delta'][0]
        row[f'{self._table_name}.y_delta'] = row[f'{self._table_name}.position_delta'][1]
        row[f'{self._table_name}.z_delta'] = row[f'{self._table_name}.position_delta'][2]

        super().append(row)
