#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and generate a timeline.

Supports segments.
"""

import argparse
import datetime

import pymavlink.dialects.v20.ardupilotmega as apm

import table_types
from segment_reader import add_segment_args, choose_reader_list

# Process these messages to build the timeline
MSG_TYPES = ['HEARTBEAT', 'STATUSTEXT', 'COMMAND_LONG', 'COMMAND_ACK']

# Ignore these commands
IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]


def mav_cmd_name(cmd: int) -> str:
    if cmd in apm.enums["MAV_CMD"]:
        return f'{apm.enums["MAV_CMD"][cmd].name} ({cmd})'
    else:
        return f'unknown command {cmd}'


class Timeline:
    def __init__(self, reader):
        # Report on mode changes
        self.current_mode = table_types.Mode.DISARMED

        for msg in reader:
            ts = getattr(msg, '_timestamp', 0.0)
            self.prefix = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') + f' ({ts :.2f}): '

            msg_type = msg.get_type()
            if msg_type == 'HEARTBEAT':
                self.process_heartbeat(msg)
            elif msg_type == 'STATUSTEXT':
                self.process_status_text(msg)
            elif msg_type == 'COMMAND_LONG':
                self.process_command_long(msg)
            elif msg_type == 'COMMAND_ACK':
                self.process_command_ack(msg)

    def report(self, msg_str):
        print(f'{self.prefix}{msg_str}')

    # TODO note gaps (when QGC wasn't running)
    def process_heartbeat(self, msg):
        # Focus on the autopilot
        if msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            # TODO look at joystick inputs for mode changes
            # TODO perhaps split arm/disarm and mode
            heartbeat_mode = table_types.get_mode(msg.base_mode, msg.custom_mode)
            if self.current_mode != heartbeat_mode:
                msg_mode_name = table_types.mode_name(heartbeat_mode)
                if self.current_mode == table_types.Mode.DISARMED:
                    self.report(f'HEARTBEAT ARMED {msg_mode_name}')
                elif heartbeat_mode == table_types.Mode.DISARMED:
                    self.report('HEARTBEAT DISARMED')
                else:
                    self.report(f'HEARTBEAT mode is {msg_mode_name}')
                self.current_mode = heartbeat_mode

    def process_status_text(self, msg):
        self.report(f'{table_types.status_severity_name(msg.severity)}: {msg.text}')

    # TODO MAV_CMD_COMPONENT_ARM_DISARM should change self.mode
    def process_command_long(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(f'Command:  {mav_cmd_name(msg.command)}, param1 {msg.param1}')

    def process_command_ack(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(f'Response: {mav_cmd_name(msg.command)}, result {msg.result}')


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        print(f'Results for {reader.name}')
        Timeline(reader)


if __name__ == '__main__':
    main()
