#!/usr/bin/env python3
import enum
import math

import pandas as pd
import pymavlink.dialects.v20.ardupilotmega as apm

import util

# Look at tables with time_boot_ms fields. Findings:
# DISTANCE_SENSOR from BlueOS is off by ~450s, so it can't be trusted
# Good readings from messages from ArduSub (RC_CHANNELS, SYSTEM_TIME, possibly others)
# tables_with_time_boot_ms = []


def norm_angle_d(degrees: float) -> float:
    """Normalize angle to [-180, 180) degrees"""

    while degrees >= 180:
        degrees -= 360
    while degrees < -180:
        degrees += 360
    return degrees


def norm_angle_r(radians: float) -> float:
    """Normalize angle to [-pi, pi) radians"""

    while radians >= math.pi:
        radians -= 2 * math.pi
    while radians < -math.pi:
        radians += 2 * math.pi
    return radians


# Sub modes: https://mavlink.io/en/messages/ardupilotmega.html#SUB_MODE
# Plus a few more
class Mode(enum.IntEnum):
    DISARMED = -10  # Helpful if we have a single state representing armed status + mode
    UNKNOWN = -9
    STABILIZE = 0
    ACRO = 1
    ALT_HOLD = 2
    AUTO = 3
    GUIDED = 4
    CIRCLE = 7
    SURFACE = 9
    POS_HOLD = 16
    MANUAL = 19
    MOTOR_DETECT = 20
    SURFTRAK = 21


MODE_NAMES = {
    -10: 'DISARMED',
    -9: 'UNKNOWN',
    0: 'STABILIZE',
    1: 'ACRO',
    2: 'ALT_HOLD',
    3: 'AUTO',
    4: 'GUIDED',
    7: 'CIRCLE',
    9: 'SURFACE',
    16: 'POS_HOLD',
    19: 'MANUAL',
    20: 'MOTOR_DETECT',
    21: 'SURFTRAK',
}


def is_armed(base_mode: int) -> bool:
    # base_mode is a bitfield, 128 == armed
    return base_mode >= 128


def combined_mode(base_mode: int, custom_mode: int) -> int:
    if is_armed(base_mode):
        return custom_mode
    else:
        return Mode.DISARMED


def mode_name(mode: int) -> str:
    if mode in MODE_NAMES:
        return MODE_NAMES[mode]
    else:
        return f'mode {mode}'


def sys_name(sys_id: int) -> str:
    if sys_id == 1:
        return 'Vehicle'
    elif sys_id == 255:
        return 'QGroundControl or similar'
    else:
        return 'unknown'


def comp_name(comp_id: int) -> str:
    return apm.enums['MAV_COMPONENT'][comp_id].name.lower()


def state_name(state_id: int) -> str:
    return apm.enums['MAV_STATE'][state_id].name.lower()


def system_status_name(state_id: int) -> str:
    if state_id == apm.MAV_STATE_CRITICAL:
        return 'CRITICAL, FAILSAFE was triggered'
    elif state_id == apm.MAV_STATE_ACTIVE:
        return 'active, sub was armed'
    elif state_id == apm.MAV_STATE_STANDBY:
        return 'standby, sub was disarmed'
    else:
        return 'unknown'


def status_severity_name(severity: int) -> str:
    if severity == apm.MAV_SEVERITY_CRITICAL:
        return 'CRITICAL'
    elif severity == apm.MAV_SEVERITY_ERROR:
        return 'ERROR'
    elif severity == apm.MAV_SEVERITY_WARNING:
        return 'WARNING'
    elif severity == apm.MAV_SEVERITY_INFO:
        return 'INFO'
    else:
        return f'severity {severity}'


class ModeCounter:
    """Count seconds spent in the various [combined] modes"""
    def __init__(self):
        self.modes = {}

    def count(self, heartbeat_data: dict):
        mode = mode_name(combined_mode(heartbeat_data['base_mode'], heartbeat_data['custom_mode']))
        if mode not in self.modes:
            self.modes[mode] = 0
        self.modes[mode] += 1


class Table:
    @staticmethod
    def create_table(
            msg_type: str,
            hdop_max: float = 100.0,
            table_name: str | None = None,
            filter_bad: bool = False):
        # table_name can be different from msg_type, e.g., HEARTBEAT_255_0 if split_source is True
        if table_name is None:
            table_name = msg_type

        if msg_type == 'AHRS2':
            return AHRS2Table(table_name)
        elif msg_type == 'BATTERY_STATUS':
            return BatteryStatusTable(table_name)
        elif msg_type == 'DISTANCE_SENSOR':
            return DistanceSensorTable(table_name)
        elif msg_type == 'HEARTBEAT':
            return HeartbeatTable(table_name)
        elif msg_type == 'GLOBAL_POSITION_INT':
            return GPSTable(msg_type, table_name, hdop_max, filter_bad)
        elif msg_type == 'GPS_INPUT':
            return GPSTable(msg_type, table_name, hdop_max, filter_bad)
        elif msg_type == 'GPS_RAW_INT':
            return GPSTable(msg_type, table_name, hdop_max, filter_bad)
        elif msg_type == 'GPS2_RAW':
            return GPSTable(msg_type, table_name, hdop_max, filter_bad)
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
        # TODO AP will split the voltage across multiple rows if required, check for this
        row[f'{self._table_name}.voltage'] = row[f'{self._table_name}.voltages'][0]
        super().append(row)


class DistanceSensorTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def append(self, row: dict):
        row[f'{self._table_name}.current_distance_m'] = row[f'{self._table_name}.current_distance'] / 100.0
        super().append(row)


class HeartbeatTable(Table):
    def __init__(self, table_name: str):
        super().__init__(table_name)

    def is_armed(self, row):
        return is_armed(row[f'{self._table_name}.base_mode'])

    def get_mode(self, row):
        return combined_mode(row[f'{self._table_name}.base_mode'], row[f'{self._table_name}.custom_mode'])

    def append(self, row: dict):
        row[f'{self._table_name}.mode'] = self.get_mode(row)
        super().append(row)


class GPSTable(Table):
    """
    Handle GPS messages: GPS_INPUT, GPS_RAW_INT, GPS2_RAW, GLOBAL_POSITION_INT
    Interesting fields:
    lat             All (degE7)
    lon             All (degE7)
    fix_type        GPS_INPUT, GPS_RAW_INT, GPS2_RAW
    hdop            GPS_INPUT
    eph             GPS_RAW_INT, GPS2_RAW (hdop * 100)
    hdg             GLOBAL_POSITION_INT (cdeg)
    yaw             GPS_INPUT (MAVLink 2 extension) (cdeg)
    alt             GLOBAL_POSITION_INT (mm), GPS_INPUT (m)
    relative_alt    GLOBAL_POSITION_INT
    """
    def __init__(self, msg_type: str, table_name: str, hdop_max: float, filter_bad: bool):
        super().__init__(table_name)
        self._msg_type = msg_type
        self._hdop_max = hdop_max
        self._filter_bad = filter_bad

    def append(self, row: dict):
        def field(f: str):
            return f'{self._table_name}.{f}'

        # Warm up messages have lat=0, lon=0, fix_type<3, hdop>max, etc.
        # This makes graphing a pain, so drop these rows
        if self._filter_bad:
            if row[field('lat')] == 0 and row[field('lon')] == 0:
                return
            if field('fix_type') in row and row[field('fix_type')] < 3:
                return
            if field('hdop') in row and row[field('hdop')] > self._hdop_max:
                return
            if field('eph') in row and row[field('eph')] / 100.0 > self._hdop_max:
                return

        # Convert to degrees and meters for convenience
        row[field('lat_deg')] = row[field('lat')] / 1.0e7
        row[field('lon_deg')] = row[field('lon')] / 1.0e7
        if self._msg_type == 'GLOBAL_POSITION_INT':
            row[field('hdg_deg')] = row[field('hdg')] / 100.0
            row[field('alt_m')] = row[field('alt')] / 1000.0
            row[field('relative_alt_m')] = row[field('relative_alt')] / 1000.0
        if field('yaw') in row:
            row[field('yaw_deg')] = row[field('yaw')] / 100.0

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
            interesting_fields = ['RFTarget', 'PilotGain']
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

    def __init__(self, orientation: tuple[float, float, float], position: tuple[float, float, float]):
        self.orientation = orientation
        self.position = position

    def add_angle_delta(self, angle_delta):
        # VISION_POSITION_DELTA.angle_delta should be radians, but there's a bug in the WL A50 DVL extension:
        # https://github.com/bluerobotics/BlueOS-Water-Linked-DVL/issues/36
        is_degrees = False
        if is_degrees:
            self.orientation = (
                norm_angle_d(self.orientation[0] + angle_delta[0]),
                norm_angle_d(self.orientation[1] + angle_delta[1]),
                norm_angle_d(self.orientation[2] + angle_delta[2])
            )
        else:
            self.orientation = (
                norm_angle_d(self.orientation[0] + math.degrees(angle_delta[0])),
                norm_angle_d(self.orientation[1] + math.degrees(angle_delta[1])),
                norm_angle_d(self.orientation[2] + math.degrees(angle_delta[2]))
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
        # Flatten angle array, and normalize while we're at it
        is_degrees = False
        if is_degrees:
            row[f'{self._table_name}.roll_delta'] = norm_angle_d(row[f'{self._table_name}.angle_delta'][0])
            row[f'{self._table_name}.pitch_delta'] = norm_angle_d(row[f'{self._table_name}.angle_delta'][1])
            row[f'{self._table_name}.yaw_delta'] = norm_angle_d(row[f'{self._table_name}.angle_delta'][2])
        else:
            row[f'{self._table_name}.roll_delta'] = norm_angle_r(row[f'{self._table_name}.angle_delta'][0])
            row[f'{self._table_name}.pitch_delta'] = norm_angle_r(row[f'{self._table_name}.angle_delta'][1])
            row[f'{self._table_name}.yaw_delta'] = norm_angle_r(row[f'{self._table_name}.angle_delta'][2])

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
