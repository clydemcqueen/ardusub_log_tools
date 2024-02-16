#!/usr/bin/env python3

"""
Read MISSION_* messages from a tlog file (telemetry log) and print the mission(s).

Supports segments.
"""

import argparse
import datetime

import pymavlink.dialects.v20.ardupilotmega as apm

from segment_reader import add_segment_args, choose_reader_list
from tlog_timeline import mav_cmd_name

# These are the messages that I've seen in ArduSub tlog files
MSG_TYPES = [
    'MISSION_ACK',
    'MISSION_CLEAR_ALL',
    'MISSION_COUNT',
    # 'MISSION_CURRENT',
    'MISSION_ITEM_INT',
    'MISSION_ITEM_REACHED',
    'MISSION_REQUEST',
    'MISSION_REQUEST_INT',
    'MISSION_REQUEST_LIST',
]

MSG_TYPES_TARGET_SYSTEM = [
    'MISSION_ACK',
    'MISSION_CLEAR_ALL',
    'MISSION_COUNT',
    # 'MISSION_CURRENT',
    'MISSION_ITEM_INT',
    # 'MISSION_ITEM_REACHED',
    'MISSION_REQUEST',
    'MISSION_REQUEST_INT',
    'MISSION_REQUEST_LIST',
]


def sys_name(sys):
    if sys == 1:
        return 'autopilot'
    elif sys == 255:
        return 'GCS'
    else:
        return f'other ({sys})'


def mission_type_name(mission_type):
    if mission_type == apm.MAV_MISSION_TYPE_MISSION:
        return 'MISSION'
    elif mission_type == apm.MAV_MISSION_TYPE_FENCE:
        return 'FENCE'
    elif mission_type == apm.MAV_MISSION_TYPE_RALLY:
        return 'RALLY'


class Mission:
    def __init__(self, mission_type):
        print()
        print(f'Create {mission_type_name(mission_type)}')
        self.mission_type = mission_type
        self.mission_items: dict[int, apm.MAVLink_mission_item_int_message] = {}

    def add_item(self, msg: apm.MAVLink_mission_item_int_message):
        if msg.seq not in self.mission_items:
            self.mission_items[msg.seq] = msg

    def print_all(self):
        print(f'Mission type {mission_type_name(self.mission_type)} has {len(self.mission_items)} items')
        for seq, msg in sorted(self.mission_items.items()):
            param_str = f'{msg.param1 :7.2f} {msg.param2 :7.2f} {msg.param3 :7.2f} {msg.param4 :7.2f}'
            xyz_str = f'{msg.x / 1.0e7 :11.6f} {msg.y / 1.0e7 :11.6f} {msg.z :11.6f}'
            print(f'{seq :3}: frame {msg.frame} {mav_cmd_name(msg.command) :36} params {param_str :20}   xyz {xyz_str}')


class MissionReader:
    def __init__(self, reader):
        # 0: mission, 1: fence, 2: rally
        missions = [None, None, None]

        for msg in reader:
            msg_type = msg.get_type()
            source_str = sys_name(msg.get_srcSystem())

            if msg_type in MSG_TYPES_TARGET_SYSTEM:
                target_str = sys_name(msg.target_system)
                mission_type = msg.mission_type
            else:
                target_str = 'unknown'
                mission_type = None

            ts = getattr(msg, '_timestamp', 0.0)
            self.prefix = (
                    datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') +
                    f' ({ts :.2f}): ' +
                    F'{source_str} => {target_str}: '
            )

            # There are basically 2 flows: upload a mission and download a mission
            # This is a simple script, so we're not handling the edge cases
            # We don't support fence and rally missions
            # https://mavlink.io/en/services/mission.html

            if msg_type == 'MISSION_REQUEST_LIST':
                self.report(f'MISSION_REQUEST_LIST GCS downloading {mission_type_name(mission_type)}')
                missions[mission_type] = Mission(mission_type)
            elif msg_type == 'MISSION_COUNT':
                if msg.get_srcSystem() == 255:
                    self.report(f'MISSION_COUNT        count {msg.count} GCS uploading {mission_type_name(mission_type)}')
                    missions[mission_type] = Mission(mission_type)
                else:
                    self.report(f'MISSION_COUNT        count {msg.count} response {mission_type_name(mission_type)}')
            elif msg_type == 'MISSION_ITEM_INT':
                self.report(f'MISSION_ITEM_INT     seq {msg.seq} {mission_type_name(mission_type)}')
                if missions[mission_type] is not None:
                    missions[mission_type].add_item(msg)
                else:
                    print('(Ignoring extra / repeat / late MISSION_ITEM_INT')
            elif msg_type == 'MISSION_REQUEST':
                # Old and busted request message
                self.report(f'MISSION_REQUEST      seq {msg.seq} {mission_type_name(mission_type)}')
            elif msg_type == 'MISSION_REQUEST_INT':
                # New hotness
                self.report(f'MISSION_REQUEST_INT  seq {msg.seq} {mission_type_name(mission_type)}')
            elif msg_type == 'MISSION_ACK':
                self.report(f'MISSION_ACK          type {msg.type} {mission_type_name(mission_type)}')
                if msg.type == apm.MAV_MISSION_ACCEPTED:
                    # Print and delete the mission
                    if missions[mission_type] is not None:
                        print()
                        # Future: would be nice to compare old & new missions -- what changed?
                        missions[mission_type].print_all()
                        print(f'Delete {mission_type_name(mission_type)}')
                        print()
                        missions[mission_type] = None
                else:
                    print(f'(Ignoring ACK error)')
            else:
                self.report(msg_type)

    def report(self, msg_str):
        print(f'{self.prefix}{msg_str}')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        print(f'Results for {reader.name}')
        MissionReader(reader)


if __name__ == '__main__':
    main()
