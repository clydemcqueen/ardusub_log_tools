#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and report on a few interesting things.

Supports segments.
"""

import argparse

import pymavlink.dialects.v20.ardupilotmega as apm

from segment_reader import add_segment_args, choose_reader_list

MSG_TYPES = ['HEARTBEAT', 'STATUSTEXT', 'SYSTEM_TIME', 'SYS_STATUS']


class SensorInfo:
    def __init__(self, description: str):
        if description == '0x100 laser based position':
            description = '0x100 laser based position (down-facing sonar rangefinder)'

        self.description = description
        self.present = 0
        self.enabled = 0
        self.healthy = 0

    def count(self, enabled, healthy):
        self.present += 1
        if enabled:
            self.enabled += 1
        if healthy:
            self.healthy += 1

    def count_str(self, count: int) -> str:
        if count == 0:
            return 'NEVER!'
        elif count == self.present:
            return 'always'
        else:
            return f'{100.0 * count / self.present :.2f}%'

    def report(self) -> str:
        return f'{self.description}: enabled {self.count_str(self.enabled)}, healthy {self.count_str(self.healthy)}'


class CompInfo:
    @staticmethod
    def sys_name(sys_id: int) -> str:
        if sys_id == 1:
            return 'Vehicle'
        elif sys_id == 255:
            return 'QGroundControl or similar'
        else:
            return 'unknown'

    @staticmethod
    def comp_name(comp_id: int) -> str:
        return apm.enums['MAV_COMPONENT'][comp_id].name.lower()

    @staticmethod
    def state_name(state_id: int) -> str:
        return apm.enums['MAV_STATE'][state_id].name.lower()

    @staticmethod
    def ardusub_name(state_id: int) -> str:
        if state_id == apm.MAV_STATE_CRITICAL:
            return 'CRITICAL, FAILSAFE was triggered'
        elif state_id == apm.MAV_STATE_ACTIVE:
            return 'active, sub was armed'
        elif state_id == apm.MAV_STATE_STANDBY:
            return 'standby, sub was disarmed'
        else:
            return 'unknown'

    @staticmethod
    def status_severity_name(severity: int) -> str:
        if severity == apm.MAV_SEVERITY_CRITICAL:
            return 'CRITICAL'
        elif severity == apm.MAV_SEVERITY_WARNING:
            return 'WARNING'
        elif severity == apm.MAV_SEVERITY_INFO:
            return 'info'
        else:
            return 'unknown'

    def __init__(self, sys_id: int, comp_id: int):
        self._sys_id = sys_id
        self._comp_id = comp_id

        # Count # of unique HEARTBEAT.system_status values
        self._heartbeat_states = {}

        # Count # of unique STATUSTEXT.severity and .text values
        self._status_severities = {}
        self._status_strings = {}

        # Count # of non-zero SYSTEM_TIME.time_unix_usec values
        self._unix_time = 0

        # Keep stats on sensor health
        self._sensors_present: dict[int, SensorInfo] | None = None

    def process_msg(self, msg):
        msg_type = msg.get_type()
        data = msg.to_dict()

        if msg_type == 'HEARTBEAT':

            state = data['system_status']
            if state not in self._heartbeat_states:
                self._heartbeat_states[state] = 0
            self._heartbeat_states[state] += 1

        elif msg_type == 'STATUSTEXT':

            severity = data['severity']
            if severity not in self._status_severities:
                self._status_severities[severity] = 0
            self._status_severities[severity] += 1

            string = data['text']
            if string not in self._status_strings:
                self._status_strings[string] = 0
            self._status_strings[string] += 1

        elif msg_type == 'SYSTEM_TIME':

            if data['time_unix_usec'] != 0:
                self._unix_time += 1

        elif msg_type == 'SYS_STATUS':

            if self._sensors_present is None:
                self._sensors_present = {}

            for bit, entry in apm.enums['MAV_SYS_STATUS_SENSOR'].items():
                if bit == apm.MAV_SYS_STATUS_SENSOR_ENUM_END:
                    break
                if msg.onboard_control_sensors_present & bit:
                    if bit not in self._sensors_present:
                        self._sensors_present[bit] = SensorInfo(entry.description)

                    enabled = msg.onboard_control_sensors_enabled & bit
                    healthy = msg.onboard_control_sensors_health & bit
                    self._sensors_present[bit].count(enabled, healthy)

    def report_heartbeat(self):
        print('            HEARTBEAT')

        total = 0
        for si in sorted(self._heartbeat_states.items()):
            count = si[1]
            total += count

            # If ArduSub component then provide more info
            if self._sys_id == 1 and self._comp_id == 1:
                print(f'                    {count:8d} {CompInfo.ardusub_name(si[0]):20}')

        minutes = total // 60
        print(f'                    {total:8d} Total heartbeat messages, approx {minutes} minutes')

    def report_statustext(self):
        if len(self._status_severities) > 0 or len(self._status_strings) > 0:
            print('            STATUSTEXT')

            print('                severities')
            for si in sorted(self._status_severities.items()):
                print(f'                    {si[1]:8d} {CompInfo.status_severity_name(si[0])}')

            print('                strings')
            num_ardusub_versions = 0
            for si in self._status_strings.items():
                problem = ''
                if si[0].startswith('ArduSub'):
                    num_ardusub_versions += 1
                    if num_ardusub_versions > 1:
                        problem += 'FIRMWARE UPDATE!'
                    elif si[1] > 1:
                        problem += 'REBOOT!'
                print(f'                    {si[1]:8d} {si[0]} {problem}')

    def report_system_time(self):
        if self._unix_time > 0:
            print('            SYSTEM_TIME')
            print(f'                         valid time was sent {self._unix_time} time(s)')

    def report_sys_status(self):
        if self._sensors_present is not None:
            print('            SYS_STATUS')
            print('                sensors')
            for _, info in self._sensors_present.items():
                print('                         ' + info.report())

    def report(self):
        self.report_heartbeat()
        self.report_statustext()
        self.report_system_time()
        self.report_sys_status()


class TelemetryLogInfo:
    def __init__(self, reader):
        self.reader = reader

    def read_and_report(self):
        print(f'Results for {self.reader.name}')

        # Build a dictionary sys_id => system
        # Each system is a dictionary of comp_id => instance of CompInfo
        systems = {}
        for msg in self.reader:
            sys_id = msg.get_srcSystem()

            if sys_id not in systems:
                systems[sys_id] = {}

            comp_id = msg.get_srcComponent()

            if comp_id not in systems[sys_id]:
                systems[sys_id][comp_id] = CompInfo(sys_id, comp_id)

            # Scan records for interesting info
            systems[sys_id][comp_id].process_msg(msg)

        # Print results
        for si in sorted(systems.items()):
            print(f'    System = {CompInfo.sys_name(si[0])}')
            for ci in sorted(si[1].items()):
                print(f'        Component = {CompInfo.comp_name(ci[0])}')
                ci[1].report()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    add_segment_args(parser)
    args = parser.parse_args()

    readers = choose_reader_list(args, MSG_TYPES)
    for reader in readers:
        tlog_doctor = TelemetryLogInfo(reader)
        tlog_doctor.read_and_report()


if __name__ == '__main__':
    main()
