#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and generate a timeline.

Supports segments.

EKF status bits:
  const             EKF_CONST_POS_MODE      Not enough information to estimate xy position
  att               EKF_ATTITUDE            Good estimate for attitude (roll, pitch yaw)
  pos_xy rel        EKF_POS_HORIZ_REL       Good estimate for relative xy position
  pos_xy abs        EKF_POS_HORIZ_ABS       Good estimate for absolute xy position
  pos_xy pred_rel   EKF_PRED_POS_HORIZ_REL  Good prediction for relative xy position
  pos_xy pred_abs   EKF_PRED_POS_HORIZ_ABS  Good prediction for absolute xy position
  pos_z abs         EKF_POS_VERT_ABS        Good estimate for absolute z position
  pos_z agl         EKF_POS_VERT_AGL        Good estimate for z position "above ground level"
  vel xy            EKF_VELOCITY_HORIZ      Good estimate for xy velocity
  vel z             EKF_VELOCITY_VERT       Good estimate for z velocity

Example EKF status reports:

SITL (GPS):                           att pos_xy: [rel abs pred_rel pred_abs] pos_z: [abs agl] vel: [xy z]
Sub with just a barometer:      const att pos_xy: [                         ] pos_z: [abs agl] vel: [xy z]
Sub with a DVL:                       att pos_xy: [rel     pred_rel         ] pos_z: [abs agl] vel: [xy z]
"""

import argparse
import datetime

import pymavlink.dialects.v20.ardupilotmega as apm

import table_types
from segment_reader import add_segment_args, choose_reader_list
from tlog_param import Param


# Process these messages to build the timeline
MSG_TYPES = [
    'HEARTBEAT', 'STATUSTEXT', 'COMMAND_LONG', 'COMMAND_ACK', 'PARAM_SET', 'GPS_GLOBAL_ORIGIN',
    'EKF_STATUS_REPORT', 'MISSION_CLEAR_ALL',]

# Ignore these commands
IGNORE_CMDS = [511, 512, 521, 522, 525, 527, 2504, 2505]

# Highlight these modes
AUTO_MODES = [
    table_types.Mode.ACRO,
    table_types.Mode.AUTO,
    table_types.Mode.GUIDED,
    table_types.Mode.CIRCLE,
    table_types.Mode.SURFACE,
    table_types.Mode.POS_HOLD,
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
    def __init__(self, reader, ansi):
        # Enable / disable ansi codes
        self.ansi = ansi

        # Track base_mode and custom mode and report on changes
        self.base_mode = apm.MAV_MODE_PREFLIGHT
        self.custom_mode = table_types.Mode.UNKNOWN
        self.system_status = apm.MAV_STATE_UNINIT
        self.ekf_status_flags = apm.EKF_UNINITIALIZED

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
            elif msg_type == 'GPS_GLOBAL_ORIGIN':
                self.process_gps_global_origin(msg)
            elif msg_type == 'EKF_STATUS_REPORT':
                self.process_ekf_status_report(msg)
            else:
                # Catch all
                self.report(msg_type)

    def report(self, msg_str, ansi_code=None):
        if self.ansi and ansi_code is not None:
            print(f'{self.prefix}{ANSI_CODES[ansi_code]}{msg_str}{ANSI_CODES["END"]}')
        else:
            print(f'{self.prefix}{msg_str}')

    # TODO note gaps (when QGC wasn't running)
    def process_heartbeat(self, msg):
        # Focus on the autopilot
        if msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
            if (msg.base_mode != self.base_mode or
                    msg.custom_mode != self.custom_mode or
                    self.system_status != msg.system_status):
                armed_str = 'ARMED' if table_types.is_armed(msg.base_mode) else 'DISARMED'
                mode_str = f'{table_types.mode_name(msg.custom_mode)} ({msg.custom_mode})'
                state_str = 'CRITICAL' if msg.system_status == apm.MAV_STATE_CRITICAL else ''
                ansi_code = 'BOLD' if msg.custom_mode in AUTO_MODES else None
                self.report(f'{armed_str} {mode_str} {state_str}', ansi_code)
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

    def process_gps_global_origin(self, msg):
        lat = msg.latitude / 1.0e7
        lon = msg.longitude / 1.0e7
        alt = msg.altitude / 1000.0
        self.report(f'Global origin set to ({lat}, {lon}), altitude {alt} above mean sea level', 'BOLD')

    def process_ekf_status_report(self, msg):
        if msg.flags != self.ekf_status_flags:
            if msg.flags & apm.EKF_UNINITIALIZED:
                self.report('EKF uninitialized', 'BOLD')
            elif msg.flags == 0:
                self.report('EKF initialized')
            else:
                s = f'EKF status: {msg.flags :4}'
                s += f' {"const" if msg.flags & apm.EKF_CONST_POS_MODE else "" :5}'
                s += f' {"att" if msg.flags & apm.EKF_ATTITUDE else "" :3}'
                s += ' pos_xy: ['
                s += f'{"rel" if msg.flags & apm.EKF_POS_HORIZ_REL else "" :3}'
                s += f' {"abs" if msg.flags & apm.EKF_POS_HORIZ_ABS else "" :3}'
                s += f' {"pred_rel" if msg.flags & apm.EKF_PRED_POS_HORIZ_REL else "" :8}'
                s += f' {"pred_abs" if msg.flags & apm.EKF_PRED_POS_HORIZ_ABS else "" :8}'
                s += '] pos_z: ['
                s += f'{"abs" if msg.flags & apm.EKF_POS_VERT_ABS else "" :3}'
                s += f' {"agl" if msg.flags & apm.EKF_POS_VERT_AGL else "" :3}'
                s += '] vel: ['
                s += f'{"xy" if msg.flags & apm.EKF_VELOCITY_HORIZ else "" :2}'
                s += f' {"z" if msg.flags & apm.EKF_VELOCITY_VERT else "" :1}'
                s += ']'
                self.report(s)
            self.ekf_status_flags = msg.flags


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    parser.add_argument('--ansi', action='store_true', help='add ANSI colors to several messages')
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        print(f'Results for {reader.name}')
        Timeline(reader, args.ansi)


if __name__ == '__main__':
    main()
