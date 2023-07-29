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
    def create_table(msg_type: str, verbose: bool = False, hdop_max: float = 100.0):
        if msg_type == 'AHRS2':
            return AHRS2Table()
        elif msg_type == 'BATTERY_STATUS':
            return BatteryStatusTable()
        elif msg_type == 'HEARTBEAT':
            return HeartbeatTable()
        elif msg_type == 'GLOBAL_POSITION_INT':
            return GlobalPositionIntTable()
        elif msg_type == 'GPS_INPUT':
            return GPSInputTable(verbose, hdop_max)
        elif msg_type == 'GPS_RAW_INT':
            return GPSRawIntTable(hdop_max)
        elif msg_type == 'GPS2_RAW':
            return GPS2RawTable(hdop_max)
        elif msg_type == 'NAMED_VALUE_FLOAT':
            return NamedValueFloatTable()
        elif msg_type == 'RC_CHANNELS':
            return RCChannelsTable()
        elif msg_type == 'VISION_POSITION_DELTA':
            return VisionPositionDeltaTable()
        else:
            return Table(msg_type)

    def __init__(self, msg_type: str):
        self._msg_type = msg_type
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
        util.add_rate_field(self._rows, half_n, 4.0, f'{self._msg_type}.{field_name}')

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

    def __len__(self):
        return len(self._rows)


class AHRS2Table(Table):
    def __init__(self):
        super().__init__('AHRS2')

    def append(self, row: dict):
        # Add degree fields
        row['AHRS2.roll_deg'] = math.degrees(row['AHRS2.roll'])
        row['AHRS2.pitch_deg'] = math.degrees(row['AHRS2.pitch'])
        row['AHRS2.yaw_deg'] = math.degrees(row['AHRS2.yaw'])
        super().append(row)


class BatteryStatusTable(Table):
    def __init__(self):
        super().__init__('BATTERY_STATUS')

    def append(self, row: dict):
        # Grab the voltage of the first battery
        row['BATTERY_STATUS.voltage'] = row['BATTERY_STATUS.voltages'][0]
        super().append(row)


class HeartbeatTable(Table):
    MODE_DISARMED = -10

    @staticmethod
    def is_armed(row):
        # base_mode is a bitfield, 128 == armed
        # Sub modes: https://mavlink.io/en/messages/ardupilotmega.html#SUB_MODE
        return row['HEARTBEAT.base_mode'] >= 128

    @staticmethod
    def get_mode(row):
        if not HeartbeatTable.is_armed(row):
            return HeartbeatTable.MODE_DISARMED
        else:
            return row['HEARTBEAT.custom_mode']

    def __init__(self):
        super().__init__('HEARTBEAT')

    def append(self, row: dict):
        row['HEARTBEAT.mode'] = HeartbeatTable.get_mode(row)
        super().append(row)


class GlobalPositionIntTable(Table):
    def __init__(self):
        super().__init__('GLOBAL_POSITION_INT')

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._msg_type}.lat_deg'] = row[f'{self._msg_type}.lat'] / 1.0e7
        row[f'{self._msg_type}.lon_deg'] = row[f'{self._msg_type}.lon'] / 1.0e7
        super().append(row)


class GPSInputTable(Table):
    def __init__(self, verbose: bool, hdop_max: float):
        super().__init__('GPS_INPUT')
        self._verbose = verbose
        self._hdop_max = hdop_max

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._msg_type}.lat_deg'] = row[f'{self._msg_type}.lat'] / 1.0e7
        row[f'{self._msg_type}.lon_deg'] = row[f'{self._msg_type}.lon'] / 1.0e7

        if row['GPS_INPUT.fix_type'] < 3:
            if self._verbose:
                print(f'GPS_INPUT.fix_type < 3, lat {row["GPS_INPUT.lat_deg"]}, lon {row["GPS_INPUT.lon_deg"]}, fix_type {row["GPS_INPUT.fix_type"]}')
            return

        if row['GPS_INPUT.hdop'] > self._hdop_max:
            if self._verbose:
                print(f'GPS_INPUT.hdop > {self._hdop_max}, lat {row["GPS_INPUT.lat_deg"]}, lon {row["GPS_INPUT.lon_deg"]}, hdop {row["GPS_INPUT.hdop"]}')
            return

        super().append(row)


class GPSRawIntTable(Table):
    def __init__(self, hdop_max: float):
        super().__init__('GPS_RAW_INT')
        self._hdop_max = hdop_max

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._msg_type}.lat_deg'] = row[f'{self._msg_type}.lat'] / 1.0e7
        row[f'{self._msg_type}.lon_deg'] = row[f'{self._msg_type}.lon'] / 1.0e7

        # ArduSub warm up sends zillions of sensor messages with bad fix_type and eph; don't bother printing these
        if row['GPS_RAW_INT.fix_type'] < 3:
            return

        if row['GPS_RAW_INT.eph'] > self._hdop_max:
            return

        super().append(row)


class GPS2RawTable(Table):
    def __init__(self, hdop_max: float):
        super().__init__('GPS2_RAW')
        self._hdop_max = hdop_max

    def append(self, row: dict):
        # Convert degE7 to float
        row[f'{self._msg_type}.lat_deg'] = row[f'{self._msg_type}.lat'] / 1.0e7
        row[f'{self._msg_type}.lon_deg'] = row[f'{self._msg_type}.lon'] / 1.0e7

        # ArduSub warm up sends zillions of sensor messages with bad fix_type and eph; don't bother printing these
        if row['GPS2_RAW.fix_type'] < 3:
            return

        if row['GPS2_RAW.eph'] > self._hdop_max:
            return

        super().append(row)


class NamedValueFloatTable(Table):
    @staticmethod
    def get_one_named_value_float_type(input_df, name: str):
        # Get a subset of rows
        df = input_df[input_df['NAMED_VALUE_FLOAT.name'] == name]

        # Get a subset of columns
        df = df[['timestamp', 'NAMED_VALUE_FLOAT.value']]

        # Rename one column
        return df.rename(columns={'NAMED_VALUE_FLOAT.value': f'SUB_INFO.{name}'})

    def __init__(self):
        super().__init__('NAMED_VALUE_FLOAT')

    def get_dataframe(self, verbose):
        if self._df is None:
            # Create the NAMED_VALUE_FLOAT dataframe, which is a set of key-value pairs
            named_value_float_df = pd.DataFrame(self._rows)

            if verbose:
                print('-----------------')
                if named_value_float_df.empty:
                    print(f'{self._msg_type} is empty')
                else:
                    print(f'{self._msg_type} has {len(named_value_float_df)} rows:')
                    print(named_value_float_df.head())

            # Re-arrange the data so it appears like it does in the QGC-generated csv file. Since the timestamps are
            # fine-grained this may result in an explosion of data, so let's just do this for a few key columns.
            if verbose:
                print('Pulling out Lights2 and PilotGain and rearranging')
            lights2_df = NamedValueFloatTable.get_one_named_value_float_type(named_value_float_df, 'Lights2')
            pilot_gain_df = NamedValueFloatTable.get_one_named_value_float_type(named_value_float_df, 'PilotGain')
            self._df = pd.merge_ordered(lights2_df, pilot_gain_df, on='timestamp', fill_method='ffill')

            if verbose:
                if self._df.empty:
                    print(f'{self._msg_type} is empty')
                else:
                    print(f'{self._msg_type} has {len(self._df)} rows:')
                    print(self._df.head())

        return self._df


class RCChannelsTable(Table):
    def __init__(self):
        super().__init__('RC_CHANNELS')

    RC_MAP = [(1, 'pitch'), (2, 'roll'), (3, 'throttle'), (4, 'yaw'), (5, 'forward'), (6, 'lateral')]

    def append(self, row: dict):
        # Rename a few fields for ease-of-use
        for item in RCChannelsTable.RC_MAP:
            row[f'RC_CHANNELS.chan{item[0]}_raw_{item[1]}'] = row.pop(f'RC_CHANNELS.chan{item[0]}_raw')
        super().append(row)


class VisionPositionDeltaTable(Table):
    def __init__(self):
        super().__init__('VISION_POSITION_DELTA')

    def append(self, row: dict):
        # Flatten angle array
        row['VISION_POSITION_DELTA.roll_delta'] = row['VISION_POSITION_DELTA.angle_delta'][0]
        row['VISION_POSITION_DELTA.pitch_delta'] = row['VISION_POSITION_DELTA.angle_delta'][1]
        row['VISION_POSITION_DELTA.yaw_delta'] = row['VISION_POSITION_DELTA.angle_delta'][2]

        # Flatten position array
        row['VISION_POSITION_DELTA.x_delta'] = row['VISION_POSITION_DELTA.position_delta'][0]
        row['VISION_POSITION_DELTA.y_delta'] = row['VISION_POSITION_DELTA.position_delta'][1]
        row['VISION_POSITION_DELTA.z_delta'] = row['VISION_POSITION_DELTA.position_delta'][2]

        super().append(row)
