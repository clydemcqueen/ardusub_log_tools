# Run tests:
# python -m pytest

# Run tests and show captured stdout:
# python -m pytest -rP

import BIN_merge
import map_maker
import show_types
import tlog_info
import tlog_merge
import tlog_param
import tlog_scan


# TODO compare output to known output

class TestTools:

    def test_BIN_merge(self):
        tool = BIN_merge.DataflashLogReader('testing/small.BIN', ['VIBE'], 10000, 10000, False)
        tool.read()
        tool.write_merged_csv_file()

    def test_map_maker(self):
        map_maker.build_map_from_tlog('testing/small.tlog', 'testing/small.html', False, [None, None], 18,
                                      ['GLOBAL_POSITION_INT'], 10.0)

    def test_tlog_types(self):
        tool = show_types.TypeFinder('testing/small.tlog')
        tool.read()

    def test_BIN_types(self):
        tool = show_types.TypeFinder('testing/small.BIN')
        tool.read()

    def test_tlog_info(self):
        tool = tlog_info.TelemetryLogInfo('testing/small.tlog')
        tool.read_and_report()

    def test_tlog_merge(self):
        tool = tlog_merge.TelemetryLogReader('testing/small.tlog', ['GLOBAL_POSITION_INT'], 10000, 10000, False, True)
        tool.read_tlog()
        tool.write_merged_csv_file()

    def test_tlog_param(self):
        tool = tlog_param.TelemetryLogParam()
        tool.read('testing/small.tlog')
        tool.write('testing/small.params')

    def test_tlog_scan(self):
        tool = tlog_scan.Scanner('testing/small.tlog', ['GLOBAL_POSITION_INT'])
        tool.read()
