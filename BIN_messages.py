#!/usr/bin/env python3

"""
Read a dataflash (BIN) file and write the entries in the MSG and EV tables to stdout.
"""

import argparse
from enum import Enum

from pymavlink import mavutil

import util


class LogEvent(Enum):
    ARMED = 10
    DISARMED = 11
    AUTO_ARMED = 15
    LAND_COMPLETE_MAYBE = 17
    LAND_COMPLETE = 18
    LOST_GPS = 19
    FLIP_START = 21
    FLIP_END = 22
    SET_HOME = 25
    SET_SIMPLE_ON = 26
    SET_SIMPLE_OFF = 27
    NOT_LANDED = 28
    SET_SUPERSIMPLE_ON = 29
    AUTOTUNE_INITIALISED = 30
    AUTOTUNE_OFF = 31
    AUTOTUNE_RESTART = 32
    AUTOTUNE_SUCCESS = 33
    AUTOTUNE_FAILED = 34
    AUTOTUNE_REACHED_LIMIT = 35
    AUTOTUNE_PILOT_TESTING = 36
    AUTOTUNE_SAVEDGAINS = 37
    SAVE_TRIM = 38
    SAVEWP_ADD_WP = 39
    FENCE_ENABLE = 41
    FENCE_DISABLE = 42
    ACRO_TRAINER_OFF = 43
    ACRO_TRAINER_LEVELING = 44
    ACRO_TRAINER_LIMITED = 45
    GRIPPER_GRAB = 46
    GRIPPER_RELEASE = 47
    PARACHUTE_DISABLED = 49
    PARACHUTE_ENABLED = 50
    PARACHUTE_RELEASED = 51
    LANDING_GEAR_DEPLOYED = 52
    LANDING_GEAR_RETRACTED = 53
    MOTORS_EMERGENCY_STOPPED = 54
    MOTORS_EMERGENCY_STOP_CLEARED = 55
    MOTORS_INTERLOCK_DISABLED = 56
    MOTORS_INTERLOCK_ENABLED = 57
    ROTOR_RUNUP_COMPLETE = 58  # Heli only
    ROTOR_SPEED_BELOW_CRITICAL = 59  # Heli only
    EKF_ALT_RESET = 60
    LAND_CANCELLED_BY_PILOT = 61
    EKF_YAW_RESET = 62
    AVOIDANCE_ADSB_ENABLE = 63
    AVOIDANCE_ADSB_DISABLE = 64
    AVOIDANCE_PROXIMITY_ENABLE = 65
    AVOIDANCE_PROXIMITY_DISABLE = 66
    GPS_PRIMARY_CHANGED = 67
    # 68, 69, 70 were winch events
    ZIGZAG_STORE_A = 71
    ZIGZAG_STORE_B = 72
    LAND_REPO_ACTIVE = 73
    STANDBY_ENABLE = 74
    STANDBY_DISABLE = 75

    # Fence events
    FENCE_ALT_MAX_ENABLE = 76
    FENCE_ALT_MAX_DISABLE = 77
    FENCE_CIRCLE_ENABLE = 78
    FENCE_CIRCLE_DISABLE = 79
    FENCE_ALT_MIN_ENABLE = 80
    FENCE_ALT_MIN_DISABLE = 81
    FENCE_POLYGON_ENABLE = 82
    FENCE_POLYGON_DISABLE = 83

    # if the EKF's source input set is changed (e.g. via a switch or
    # a script), we log an event:
    EK3_SOURCES_SET_TO_PRIMARY = 85
    EK3_SOURCES_SET_TO_SECONDARY = 86
    EK3_SOURCES_SET_TO_TERTIARY = 87

    AIRSPEED_PRIMARY_CHANGED = 90

    SURFACED = 163
    NOT_SURFACED = 164
    BOTTOMED = 165
    NOT_BOTTOMED = 166


class DataflashLogReader:
    def __init__(self, infile: str):
        self._infile = infile
        self._messages = []

    def read(self):
        print(f'Reading {self._infile}')
        mlog = mavutil.mavlink_connection(self._infile, robust_parsing=False, dialect='ardupilotmega')

        print('Parsing messages')
        msg_count = 0
        while (msg := mlog.recv_match(blocking=False, type=['EV', 'MSG'])) is not None:
            msg_type = msg.get_type()
            raw_data = msg.to_dict()
            timestamp = getattr(msg, '_timestamp', 0.0)

            if msg_type == 'MSG':
                self._messages.append({'timestamp': timestamp, 'message': f'{raw_data["Message"]}'})
            elif msg_type == 'EV':
                try:
                    event = LogEvent(raw_data['Id'])
                    self._messages.append({'timestamp': timestamp, 'message': f'Event: {event.name}'})
                except ValueError:
                    print(f'Warning: unknown event ID {raw_data["Id"]}')
            else:
                # Should not happen
                print(f'Error: unexpected message type {msg_type}')

            msg_count += 1

        print(f'{msg_count} messages')
        self._messages.sort(key=lambda item: item['timestamp'])

    def write_messages(self, filename: str):
        print(f'Messages and events for {filename}:')
        for item in self._messages:
            print(f'  {item["timestamp"]:10.6f} {item["message"]}')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    parser.add_argument('-r', '--recurse', action='store_true',
                        help='enter directories looking for BIN files')
    parser.add_argument('path', nargs='+')
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, '.BIN')
    print(f'Processing {len(files)} files')

    for file in files:
        print('===================')
        reader = DataflashLogReader(file)
        reader.read()
        reader.write_messages(file)

if __name__ == '__main__':
    main()
