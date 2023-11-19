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
from tlog_param import Param


# Process these messages to build the timeline
MSG_TYPES = ['HEARTBEAT', 'STATUSTEXT', 'COMMAND_LONG', 'COMMAND_ACK', 'PARAM_SET']

# Ignore these commands
IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]

# Highlight these modes
AUTO_MODES = [
    table_types.Mode.ACRO,
    table_types.Mode.AUTO,
    table_types.Mode.GUIDED,
    table_types.Mode.CIRCLE,
    table_types.Mode.SURFACE,
    table_types.Mode.MOTOR_DETECT,
]

# A few ANSI codes
ANSI_CODES = {
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m',
    'END': '\033[0m',
}


def mav_cmd_name(cmd: int) -> str:
    if cmd in apm.enums["MAV_CMD"]:
        return f'{apm.enums["MAV_CMD"][cmd].name} ({cmd})'
    else:
        return f'unknown command {cmd}'


def mav_result_name(result: int) -> str:
    if result in apm.enums["MAV_RESULT"]:
        return f'{apm.enums["MAV_RESULT"][result].name} ({result})'
    else:
        return f'unknown result {result}'


class Timeline:
    def __init__(self, reader):
        # Track base_mode and custom mode and report on changes
        self.base_mode = apm.MAV_MODE_PREFLIGHT
        self.custom_mode = table_types.Mode.UNKNOWN
        self.system_status = apm.MAV_STATE_UNINIT

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
            elif msg_type == 'PARAM_SET':
                self.process_param_set(msg)

    def report(self, msg_str, ansi_code=None):
        if ansi_code is None:
            print(f'{self.prefix}{msg_str}')
        else:
            print(f'{self.prefix}{ANSI_CODES[ansi_code]}{msg_str}{ANSI_CODES["END"]}')

    # TODO note gaps (when QGC wasn't running)
    def process_heartbeat(self, msg):
        # Focus on the autopilot
        if msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            if (msg.base_mode != self.base_mode or
                    msg.custom_mode != self.custom_mode or
                    self.system_status != msg.system_status):
                armed_str = 'ARMED' if table_types.is_armed(msg.base_mode) else 'DISARMED'
                state_str = 'CRITICAL' if msg.system_status == apm.MAV_STATE_CRITICAL else ''
                ansi_code = 'BOLD' if msg.custom_mode in AUTO_MODES else None
                self.report(f'{armed_str} {table_types.mode_name(msg.custom_mode)} {state_str}', ansi_code)
                self.base_mode = msg.base_mode
                self.custom_mode = msg.custom_mode
                self.system_status = msg.system_status

    def process_status_text(self, msg):
        self.report(f'{table_types.status_severity_name(msg.severity)}: {msg.text}')

    def process_command_long(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(f'Command:  {mav_cmd_name(msg.command)}, param1 {msg.param1}')

    def process_command_ack(self, msg):
        if msg.command not in IGNORE_CMDS:
            self.report(f'Response: {mav_cmd_name(msg.command)}, {mav_result_name(msg.result)}')

    def process_param_set(self, msg):
        param = Param(msg)
        comment = param.comment()
        if comment is None:
            self.report(f'Set param {param.id} to {param.value_str()}', 'BOLD')
        else:
            self.report(f'Set param {param.id} to {comment} ({param.value_str()})', 'BOLD')


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
