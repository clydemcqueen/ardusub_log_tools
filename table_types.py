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
            filter: bool = False,
            surftrak: bool = False):
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
            return NamedValueFloatTable(table_name, surftrak)
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
        # Convert to degrees for convenience
        row[f'{self._table_name}.lat_deg'] = row[f'{self._table_name}.lat'] / 1.0e7
        row[f'{self._table_name}.lon_deg'] = row[f'{self._table_name}.lon'] / 1.0e7
        row[f'{self._table_name}.hdg_deg'] = row[f'{self._table_name}.hdg'] / 100.0
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
    def __init__(self, table_name: str, surftrak):
        super().__init__(table_name)
        self.surftrak = surftrak

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
            interesting_fields = ['RFTarget'] if self.surftrak else ['Lights2', 'PilotGain']
            print(f'Save these NAMED_VALUE_FLOAT fields: {interesting_fields}')
            for interesting_field in interesting_fields:
                df = self.get_one_named_value_float_type(named_value_float_df, interesting_field)
                self._df = df if self._df is None else pd.merge_ordered(self._df, df)

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


class Pose:
    """Simple 6DoF pose"""

    @staticmethod
    def norm_angle(degrees: float) -> float:
        """Normalize angle to [0, 360) degrees"""

        while degrees >= 360:
            degrees -= 360
        while degrees < 0:
            degrees += 360
        return degrees

    def __init__(self, orientation: tuple[float, float, float], position: tuple[float, float, float]):
        self.orientation = orientation
        self.position = position

    def add_angle_delta(self, angle_delta):
        # VISION_POSITION_DELTA.angle_delta should be radians, but there's a bug in the WL A50 DVL extension:
        # https://github.com/bluerobotics/BlueOS-Water-Linked-DVL/issues/36
        is_a50 = True
        if is_a50:
            self.orientation = (
                Pose.norm_angle(self.orientation[0] + angle_delta[0]),
                Pose.norm_angle(self.orientation[1] + angle_delta[1]),
                Pose.norm_angle(self.orientation[2] + angle_delta[2])
            )
        else:
            self.orientation = (
                Pose.norm_angle(self.orientation[0] + math.degrees(angle_delta[0])),
                Pose.norm_angle(self.orientation[1] + math.degrees(angle_delta[1])),
                Pose.norm_angle(self.orientation[2] + math.degrees(angle_delta[2]))
            )

    def add_position_delta(self, position_delta):
        # VISION_POSITION_DELTA.position_delta is in meters
        self.position = (
            self.position[0] + position_delta[0],
            self.position[1] + position_delta[1],
            self.position[2] + position_delta[2]
        )


class VisionPositionDeltaTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

        # Assume initial pose is flat (roll=0.0, pitch=0.0) facing north (yaw=0.0) at location (0.0, 0.0, 0.0)
        self.pose = Pose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def append(self, row: dict):
        # Flatten angle array
        row[f'{self._table_name}.roll_delta'] = row[f'{self._table_name}.angle_delta'][0]
        row[f'{self._table_name}.pitch_delta'] = row[f'{self._table_name}.angle_delta'][1]
        row[f'{self._table_name}.yaw_delta'] = row[f'{self._table_name}.angle_delta'][2]

        # Flatten position array
        row[f'{self._table_name}.x_delta'] = row[f'{self._table_name}.position_delta'][0]
        row[f'{self._table_name}.y_delta'] = row[f'{self._table_name}.position_delta'][1]
        row[f'{self._table_name}.z_delta'] = row[f'{self._table_name}.position_delta'][2]

        # Accumulate deltas to build a pose
        self.pose.add_angle_delta(row[f'{self._table_name}.angle_delta'])
        self.pose.add_position_delta(row[f'{self._table_name}.position_delta'])

        # Add pose fields
        row[f'{self._table_name}.roll'] = self.pose.orientation[0]
        row[f'{self._table_name}.pitch'] = self.pose.orientation[1]
        row[f'{self._table_name}.yaw'] = self.pose.orientation[2]

        row[f'{self._table_name}.x'] = self.pose.position[0]
        row[f'{self._table_name}.y'] = self.pose.position[1]
        row[f'{self._table_name}.z'] = self.pose.position[2]

        super().append(row)
