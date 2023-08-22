# Run tests:
# python -m pytest

# Run tests and show captured stdout:
# python -m pytest -rP

# Run a particular test:
# python -m pytest -rP testing/test_tools.py::TestTools::test_add_rate_field

import pytest

import BIN_info
import BIN_merge
import map_maker
import show_types
import tlog_bad_data
import tlog_info
import tlog_merge
import tlog_param
import tlog_scan
import util


# TODO compare output to known output

class TestTools:

    def test_dataflash_merge(self):
        tool = BIN_merge.DataflashLogReader('testing/small.BIN', ['VIBE'], 10000, 10000, False)
        tool.read()
        tool.write_merged_csv_file()

    def test_map_maker(self):
        map_maker.build_map_from_tlog('testing/small.tlog', 'testing/small.html', False, [None, None], 18,
                                      ['GLOBAL_POSITION_INT'], 10.0)

    def test_tlog_types(self):
        tool = show_types.TypeFinder('testing/small.tlog')
        tool.read()

    def test_dataflash_types(self):
        tool = show_types.TypeFinder('testing/small.BIN')
        tool.read()

    def test_bad_data(self):
        tool = tlog_bad_data.BadDataFinder('testing/small.tlog', True)
        tool.read()

    def test_tlog_info(self):
        tool = tlog_info.TelemetryLogInfo('testing/small.tlog')
        tool.read_and_report()

    def test_dataflash_info(self):
        tool = BIN_info.DataflashLogInfo('testing/small.BIN')
        tool.read_and_report()

    def test_tlog_merge(self):
        tool = tlog_merge.TelemetryLogReader('testing/small.tlog', ['GLOBAL_POSITION_INT'],
                                             10000, 10000, False, 0, 0, False, False, True)
        tool.read_tlog()
        tool.add_rate_field()
        tool.write_merged_csv_file()

    def test_tlog_param(self):
        tool = tlog_param.TelemetryLogParam()
        tool.read('testing/small.tlog')
        tool.write('testing/small.params')

    def test_tlog_scan(self):
        tool = tlog_scan.Scanner('testing/small.tlog', ['GLOBAL_POSITION_INT'])
        tool.read()

    def test_add_rate_field(self):
        messages = [
            {'timestamp': 0.0},
            {'timestamp': 0.1122},
            {'timestamp': 0.2532},
            {'timestamp': 0.3432},
            {'timestamp': 0.4974},
            {'timestamp': 0.5342},
            {'timestamp': 0.6324},
            {'timestamp': 0.7883},
            # First gap
            {'timestamp': 10.0123},
            {'timestamp': 10.1897},
            {'timestamp': 10.2321},
            {'timestamp': 10.3998},
            {'timestamp': 10.4234},
            {'timestamp': 10.5643},
            {'timestamp': 10.6248},
            {'timestamp': 10.7431},
            # Second gap, right near end
            {'timestamp': 20.0123},
            {'timestamp': 20.1328},
            {'timestamp': 20.2888},
        ]

        # Look for crashes
        util.add_rate_field(messages, 1, 4.0, 'rate')
        util.add_rate_field(messages, 2, 4.0, 'rate')
        util.add_rate_field(messages, 4, 4.0, 'rate')
        util.add_rate_field(messages, 5, 4.0, 'rate')
        util.add_rate_field(messages, 9, 4.0, 'rate')

        # Compare output at half_n == 3 to make sure we're calculating correctly
        rates = [
            3.0 / (messages[3]['timestamp'] - messages[0]['timestamp']),
            4.0 / (messages[4]['timestamp'] - messages[0]['timestamp']),
            5.0 / (messages[5]['timestamp'] - messages[0]['timestamp']),
            6.0 / (messages[6]['timestamp'] - messages[0]['timestamp']),
            6.0 / (messages[7]['timestamp'] - messages[1]['timestamp']),
            5.0 / (messages[7]['timestamp'] - messages[2]['timestamp']),
            4.0 / (messages[7]['timestamp'] - messages[3]['timestamp']),

            # First gap:
            0.0,
            0.0,

            4.0 / (messages[12]['timestamp'] - messages[8]['timestamp']),
            5.0 / (messages[13]['timestamp'] - messages[8]['timestamp']),
            6.0 / (messages[14]['timestamp'] - messages[8]['timestamp']),
            6.0 / (messages[15]['timestamp'] - messages[9]['timestamp']),
            5.0 / (messages[15]['timestamp'] - messages[10]['timestamp']),
            4.0 / (messages[15]['timestamp'] - messages[11]['timestamp']),

            # Second gap, right near the end:
            0.0,
            0.0,

            2.0 / (messages[18]['timestamp'] - messages[16]['timestamp']),

            # Last message:
            0.0,
        ]

        util.add_rate_field(messages, 3, 4.0, 'rate')

        for rate, message in zip(rates, messages):
            assert pytest.approx(rate) == message['rate']
