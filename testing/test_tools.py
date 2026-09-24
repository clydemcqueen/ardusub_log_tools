# Run tests:
# python -m pytest

# Run tests and show captured stdout:
# python -m pytest -rP

# Run a particular test:
# python -m pytest -rP testing/test_tools.py::TestTools::test_add_rate_field

import os

import pytest

import BIN_ekf_status
import BIN_extract_files
import BIN_graph_alt
import BIN_info
import BIN_merge
import BIN_param
import BIN_plot_local
import BIN_timeline
import map_maker
import mcap_channels
import mcap_dump_logs
import mcap_explode_extension_logs
import mcap_map_maker
import mcap_merge
import mcap_plot_local
import mcap_strip_video
import mcap_to_tlog
import mcap_wl_ugps_acoustic_info
import show_types
import table_types
import tlog_bad_data
import tlog_info
import tlog_map_maker
import tlog_merge
import tlog_param
import tlog_plot_local
import tlog_scan
import tlog_timeline
import util
from file_reader import FileReader
from segment_reader import Segment, SegmentFormatException, SegmentReader, parse_segment


class TestTools:
    def test_dataflash_merge(self):
        tool = BIN_merge.DataflashLogReader("testing/small2.BIN", ["VIBE"], 10000, 10000, False, False, -1.0, -1.0)
        tool.read()
        tool.write_merged_csv_file()
        if os.path.exists("testing/small2_asl_merged.csv"):
            os.remove("testing/small2_asl_merged.csv")

    def test_tlog_map_maker(self):
        tlog_map_maker.build_map_from_tlog(
            FileReader("testing/small.tlog", ["GLOBAL_POSITION_INT"]),
            "testing/small.html",
            False,
            [None, None],
            18,
            10.0,
        )

    def test_tlog_map_maker_segment(self):
        segment_reader = SegmentReader(
            Segment(1683220544, 1683220546, "segment99"),
            FileReader("testing/small.tlog", ["GLOBAL_POSITION_INT"]),
            None,
        )
        tlog_map_maker.build_map_from_tlog(segment_reader, "testing/segment99.html", False, [None, None], 18, 10.0)

    def test_nmea_map_maker(self):
        map_maker.build_map_from_txt("testing/nmea_log.txt", "testing/nmea_log.html", False, [None, None], 18)

    def test_tlog_plot_local(self):
        tlog_plot_local.plot_local_position(
            FileReader("testing/small.tlog", tlog_plot_local.MSG_TYPES), "testing/small.pdf"
        )

    def test_tlog_plot_local_segment(self):
        segment_reader = SegmentReader(
            Segment(1683220544, 1683220546, "segment1"),
            FileReader("testing/small.tlog", tlog_plot_local.MSG_TYPES),
            None,
        )
        tlog_plot_local.plot_local_position(segment_reader, "testing/segment1.pdf")

    def test_tlog_types(self):
        tool = show_types.TypeFinder("testing/small.tlog")
        tool.read()

    def test_dataflash_types(self):
        tool = show_types.TypeFinder("testing/small2.BIN")
        tool.read()

    def test_bad_data(self):
        tool = tlog_bad_data.BadDataFinder("testing/small.tlog", True)
        tool.read()

    def test_tlog_info(self):
        tool = tlog_info.TelemetryLogInfo(FileReader("testing/small.tlog", tlog_info.MSG_TYPES))
        tool.read_and_report()

    def test_dataflash_info(self):
        tool = BIN_info.DataflashLogInfo("testing/small2.BIN")
        tool.read_and_report()

    def test_dataflash_info_file_messages(self, monkeypatch, capsys):
        class MockFileMsg:
            def __init__(self, name, off, length):
                self.FileName = name
                self.Offset = off
                self.Length = length

            def get_type(self):
                return "FILE"

        class MockMlog:
            def __init__(self, msgs):
                self.msgs = iter(msgs)

            def recv_match(self, blocking=False, type=None):
                return next(self.msgs, None)

        msgs = [
            MockFileMsg("@ROMFS/sensors/IMU_CAL", 0, 64),
            MockFileMsg("@ROMFS/sensors/IMU_CAL", 64, 32),
            MockFileMsg("sys_config.txt", 0, 100),
        ]
        monkeypatch.setattr("pymavlink.mavutil.mavlink_connection", lambda *args, **kwargs: MockMlog(msgs))
        tool = BIN_info.DataflashLogInfo("dummy.BIN")
        tool.read_and_report()
        captured = capsys.readouterr().out
        assert "3 FILE records, embedded files:" in captured
        assert "@ROMFS/sensors/IMU_CAL (96 bytes)" in captured
        assert "sys_config.txt (100 bytes)" in captured

    def test_dataflash_extract(self, tmp_path, monkeypatch):
        class MockFileMsg:
            def __init__(self, name, off, length):
                self.FileName = name
                self.Offset = off
                self.Length = length
                self.Data = b"x" * length

            def get_type(self):
                return "FILE"

        class MockMlog:
            def __init__(self, msgs):
                self.msgs = iter(msgs)

            def recv_match(self, blocking=False, type=None):
                return next(self.msgs, None)

        msgs = [
            MockFileMsg("@ROMFS/sensors/IMU_CAL", 0, 64),
            MockFileMsg("@ROMFS/sensors/IMU_CAL", 64, 32),
            MockFileMsg("sys_config.txt", 0, 100),
        ]
        monkeypatch.setattr("pymavlink.mavutil.mavlink_connection", lambda *args, **kwargs: MockMlog(msgs))

        test_bin = tmp_path / "dummy.BIN"
        test_bin.touch()

        extractor = BIN_extract_files.DataflashFileExtractor(str(test_bin))
        extractor.extract()

        out_dir = tmp_path / "dummy_asl_extracted"
        assert out_dir.is_dir()
        assert (out_dir / "ROMFS_sensors_IMU_CAL").is_file()
        assert (out_dir / "ROMFS_sensors_IMU_CAL").stat().st_size == 96
        assert (out_dir / "sys_config.txt").is_file()
        assert (out_dir / "sys_config.txt").stat().st_size == 100

    def test_bin_graph_alt(self):
        BIN_graph_alt.process_reader(FileReader("testing/small2.BIN", ["AHR2", "XKF1", "BARO", "ORGN", "POS"]))
        if os.path.exists("testing/small2_asl_alt.pdf"):
            os.remove("testing/small2_asl_alt.pdf")

    def test_bin_ekf_status(self):
        tool = BIN_ekf_status.FilterStatusReport("testing/small2.BIN")
        tool.read_and_report()

    def test_tlog_merge(self):
        tool = tlog_merge.TelemetryLogReader(
            FileReader("testing/small.tlog", ["GLOBAL_POSITION_INT"]), 10000, 10000, False, 0, 0, False, True, False
        )
        tool.read_tlog()
        tool.add_rate_field()
        tool.write_merged_csv_file()
        if os.path.exists("testing/small_asl_merged.csv"):
            os.remove("testing/small_asl_merged.csv")

    def test_tlog_merge_segment(self):
        segment_reader = SegmentReader(
            Segment(1683220544, 1683220546, "segment1"), FileReader("testing/small.tlog", ["GLOBAL_POSITION_INT"]), None
        )
        tool = tlog_merge.TelemetryLogReader(segment_reader, 10000, 10000, False, None, None, False, True, False)
        tool.read_tlog()
        assert len(tool.tables["GLOBAL_POSITION_INT_1_1"]) == 6

    def test_tlog_param(self):
        tool = tlog_param.TelemetryLogParam("testing/small.tlog", True)
        tool.write_params_file("testing/small.params")

    def test_bin_param(self):
        from pymavlink import mavutil

        mlog = mavutil.mavlink_connection("testing/small2.BIN", robust_parsing=False, dialect="ardupilotmega")
        params = BIN_param.DataFlashParams()
        while (msg := mlog.recv_match(blocking=False, type=["PARM"])) is not None:
            params.add(msg)
        params.write_params_file("testing/small2.params")
        assert len(params.params) > 0
        BIN_param.print_changes(params, params)

    def test_tlog_scan(self):
        tool = tlog_scan.Scanner("testing/small.tlog", ["GLOBAL_POSITION_INT"])
        tool.read()

    def test_lowercase_types_arg(self, monkeypatch, capsys):
        import sys

        monkeypatch.setattr(sys, "argv", ["tlog_scan.py", "--types", "global_position_int", "testing/small.tlog"])
        tlog_scan.main()
        captured = capsys.readouterr()
        # The tlog contains GLOBAL_POSITION_INT messages which should be read when the argument is uppercased.
        assert "Read 792 messages from testing/small.tlog" in captured.out

    def test_add_rate_field(self):
        messages = [
            {"timestamp": 0.0},
            {"timestamp": 0.1122},
            {"timestamp": 0.2532},
            {"timestamp": 0.3432},
            {"timestamp": 0.4974},
            {"timestamp": 0.5342},
            {"timestamp": 0.6324},
            {"timestamp": 0.7883},
            # First gap
            {"timestamp": 10.0123},
            {"timestamp": 10.1897},
            {"timestamp": 10.2321},
            {"timestamp": 10.3998},
            {"timestamp": 10.4234},
            {"timestamp": 10.5643},
            {"timestamp": 10.6248},
            {"timestamp": 10.7431},
            # Second gap, right near end
            {"timestamp": 20.0123},
            {"timestamp": 20.1328},
            {"timestamp": 20.2888},
        ]

        # Look for crashes
        util.add_rate_field(messages, 1, 4.0, "rate")
        util.add_rate_field(messages, 2, 4.0, "rate")
        util.add_rate_field(messages, 4, 4.0, "rate")
        util.add_rate_field(messages, 5, 4.0, "rate")
        util.add_rate_field(messages, 9, 4.0, "rate")

        # Compare output at half_n == 3 to make sure we're calculating correctly
        rates = [
            3.0 / (messages[3]["timestamp"] - messages[0]["timestamp"]),
            4.0 / (messages[4]["timestamp"] - messages[0]["timestamp"]),
            5.0 / (messages[5]["timestamp"] - messages[0]["timestamp"]),
            6.0 / (messages[6]["timestamp"] - messages[0]["timestamp"]),
            6.0 / (messages[7]["timestamp"] - messages[1]["timestamp"]),
            5.0 / (messages[7]["timestamp"] - messages[2]["timestamp"]),
            4.0 / (messages[7]["timestamp"] - messages[3]["timestamp"]),
            # First gap:
            0.0,
            0.0,
            4.0 / (messages[12]["timestamp"] - messages[8]["timestamp"]),
            5.0 / (messages[13]["timestamp"] - messages[8]["timestamp"]),
            6.0 / (messages[14]["timestamp"] - messages[8]["timestamp"]),
            6.0 / (messages[15]["timestamp"] - messages[9]["timestamp"]),
            5.0 / (messages[15]["timestamp"] - messages[10]["timestamp"]),
            4.0 / (messages[15]["timestamp"] - messages[11]["timestamp"]),
            # Second gap, right near the end:
            0.0,
            0.0,
            2.0 / (messages[18]["timestamp"] - messages[16]["timestamp"]),
            # Last message:
            0.0,
        ]

        util.add_rate_field(messages, 3, 4.0, "rate")

        for rate, message in zip(rates, messages):
            assert pytest.approx(rate) == message["rate"]

    def test_parse_segment_args(self):
        segments = []
        for keep_arg in ["1683220546.0,1683220547.0,foo", "1683220546,1683220547", "bar", "fee,fie"]:
            try:
                segments.append(parse_segment(keep_arg))
            except SegmentFormatException:
                pass

        assert len(segments) == 2
        s1, s2 = segments
        assert s1.start == 1683220546.0 and s1.end == 1683220547.0 and s1.name == "foo"
        assert s2.start == 1683220546.0 and s2.end == 1683220547.0 and s2.name == "1683220546_1683220547"

    def test_unknown_comp_and_state_name(self):
        assert table_types.comp_name(230) == "mav_comp_id_230"
        assert table_types.state_name(999) == "mav_state_999"

    def test_mcap_explode(self, tmp_path):
        out_prefix = str(tmp_path / "recorder_20260816_203739")
        reader = mcap_merge.McapLogReader(
            "testing/recorder_20260816_203739.mcap",
            ["AHRS", "HEARTBEAT"],
            500000,
            False,
            None,
            None,
            False,
            False,
            False,
        )
        reader.infile = out_prefix + ".mcap"
        reader.read_mcap()
        assert len(reader.tables["AHRS"]) == 1113
        assert len(reader.tables["HEARTBEAT"]) == 346

        reader.add_rate_field()
        assert "HEARTBEAT.rate" in reader.tables["HEARTBEAT"]._rows[0]

        reader.write_msg_csv_files()
        ahrs_csv = tmp_path / "recorder_20260816_203739_asl_AHRS.csv"
        heartbeat_csv = tmp_path / "recorder_20260816_203739_asl_HEARTBEAT.csv"
        assert ahrs_csv.is_file()
        assert heartbeat_csv.is_file()

    def test_mcap_resolve_field(self):
        assert mcap_merge.resolve_field_value("mavtype", {"type": "MAV_TYPE_SUBMARINE"}) == ("type", 12)
        assert mcap_merge.resolve_field_value("base_mode", "") == ("base_mode", 0)
        assert mcap_merge.resolve_field_value("base_mode", "MAV_MODE_FLAG_SAFETY_ARMED") == ("base_mode", 128)
        assert mcap_merge.resolve_field_value("param_id", "BRD_SAFETYENABLE") == ("param_id", "BRD_SAFETYENABLE")

    def test_mcap_plot_local(self, tmp_path):
        outfile = str(tmp_path / "recorder.pdf")
        mcap_plot_local.plot_mcap_local("testing/recorder_20260816_203739.mcap", outfile, dvl=True)
        assert (tmp_path / "recorder.pdf").is_file()

    def test_mcap_explode_extension_tables(self, tmp_path):
        out_prefix = str(tmp_path / "rec")
        reader = mcap_merge.McapLogReader(
            "testing/recorder_20260826_181307_no_video.mcap",
            ["wl_ugps", "wl_ugps_external"],
            500000,
            False,
            None,
            None,
            False,
            False,
            False,
        )
        reader.infile = out_prefix + ".mcap"
        reader.read_mcap()
        assert len(reader.tables["wl_ugps"]) == 23
        assert len(reader.tables["wl_ugps_external"]) == 40
        assert "wl_ugps.acoustic_x" in reader.tables["wl_ugps"].get_dataframe(False).columns
        assert "wl_ugps_external.lat" in reader.tables["wl_ugps_external"]._rows[0]

        reader.add_rate_field()
        assert "wl_ugps.rate" in reader.tables["wl_ugps"]._rows[0]
        assert "wl_ugps_external.rate" in reader.tables["wl_ugps_external"]._rows[0]

        reader.write_msg_csv_files()
        assert (tmp_path / "rec_asl_wl_ugps.csv").is_file()
        assert (tmp_path / "rec_asl_wl_ugps_external.csv").is_file()

    def test_mcap_explode_merge(self, tmp_path):
        out_prefix = str(tmp_path / "rec_merge")
        reader = mcap_merge.McapLogReader(
            "testing/recorder_20260826_181307_no_video.mcap",
            ["HEARTBEAT", "wl_ugps"],
            500000,
            False,
            None,
            None,
            False,
            False,
            False,
        )
        reader.infile = out_prefix + ".mcap"
        reader.read_mcap()
        reader.write_merged_csv_file()
        merged_csv = tmp_path / "rec_merge_asl_merged.csv"
        assert merged_csv.is_file()
        import pandas as pd

        df = pd.read_csv(merged_csv)
        assert "HEARTBEAT.custom_mode" in df.columns
        assert "wl_ugps.master_lat" in df.columns

    def test_mcap_merge(self, tmp_path):
        out_prefix = str(tmp_path / "rec_merge_tool")
        reader = mcap_merge.McapLogReader(
            "testing/recorder_20260826_181307_no_video.mcap",
            ["HEARTBEAT", "wl_ugps"],
            500000,
            False,
            None,
            None,
            False,
            False,
            False,
        )
        reader.infile = out_prefix + ".mcap"
        reader.read_mcap()
        reader.write_merged_csv_file()
        merged_csv = tmp_path / "rec_merge_tool_asl_merged.csv"
        assert merged_csv.is_file()
        import pandas as pd

        df = pd.read_csv(merged_csv)
        assert "HEARTBEAT.custom_mode" in df.columns
        assert "wl_ugps.master_lat" in df.columns

    def test_mcap_merge_cli(self, tmp_path):
        import shutil
        import subprocess
        import sys
        from pathlib import Path

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260826_181307_no_video.mcap", test_mcap)

        cmd = [
            sys.executable,
            "mcap_merge.py",
            "--types",
            "HEARTBEAT",
            str(test_mcap),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(".").resolve())
        assert res.returncode == 0, f"mcap_merge failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        assert (tmp_path / "test_asl_merged.csv").is_file()
        assert not (tmp_path / "test_asl_HEARTBEAT.csv").is_file()

        # Explode CLI should write per-type file and not merged file
        cmd_explode = [
            sys.executable,
            "mcap_explode.py",
            "--types",
            "HEARTBEAT",
            str(test_mcap),
        ]
        res_explode = subprocess.run(cmd_explode, capture_output=True, text=True, cwd=Path(".").resolve())
        assert res_explode.returncode == 0, (
            f"mcap_explode failed:\nSTDOUT: {res_explode.stdout}\nSTDERR: {res_explode.stderr}"
        )
        assert (tmp_path / "test_asl_HEARTBEAT.csv").is_file()

    def test_mcap_explode_segment(self, tmp_path):
        seg = Segment(1787767988.0, 1787767998.0, "seg1")
        out_prefix = str(tmp_path / "seg1")
        reader = mcap_merge.McapLogReader(
            "testing/recorder_20260826_181307_no_video.mcap",
            ["wl_ugps", "HEARTBEAT"],
            500000,
            False,
            None,
            None,
            False,
            False,
            False,
            segment=seg,
        )
        reader.infile = out_prefix + ".mcap"
        reader.read_mcap()
        assert len(reader.tables["wl_ugps"]) == 14
        assert len(reader.tables["HEARTBEAT"]) == 58
        reader.write_msg_csv_files()
        assert (tmp_path / "seg1_asl_wl_ugps.csv").is_file()
        assert (tmp_path / "seg1_asl_HEARTBEAT.csv").is_file()

    def test_mcap_explode_extension_logs_segment(self, tmp_path):
        seg = Segment(1787767988.0, 1787767998.0, "seg1")
        out_prefix = str(tmp_path / "seg1")
        counts = mcap_explode_extension_logs.explode_extension_logs(
            "testing/recorder_20260826_181307_no_video.mcap",
            segment=seg,
            outfile_prefix=out_prefix,
        )
        assert counts["waterlinked.ugps"] == 14
        assert (tmp_path / "seg1_asl_waterlinked.ugps.csv").is_file()

    def test_bin_plot_local(self, tmp_path):
        outfile = str(tmp_path / "small2.pdf")
        BIN_plot_local.plot_bin_local(FileReader("testing/small2.BIN", BIN_plot_local.MSG_TYPES), outfile, dvl=True)
        assert (tmp_path / "small2.pdf").is_file()

    def test_mcap_to_tlog(self, tmp_path):
        import shutil

        from pymavlink import mavutil

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260816_203739.mcap", test_mcap)
        mcap_to_tlog.mcap_to_tlog(str(test_mcap))

        out_tlog = tmp_path / "test_asl.tlog"
        assert out_tlog.is_file()

        conn = mavutil.mavlink_connection(str(out_tlog), dialect="ardupilotmega")
        bad_count = 0
        good_count = 0
        while True:
            msg = conn.recv_msg()
            if msg is None:
                break
            if msg.get_type() == "BAD_DATA":
                bad_count += 1
            else:
                good_count += 1

        assert bad_count == 0
        assert good_count == 10361

    def test_mcap_dump_extension_logs(self, tmp_path):
        import shutil

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260826_181307_no_video.mcap", test_mcap)
        counts = mcap_dump_logs.dump_logs(str(test_mcap), extensions_only=True)

        assert counts["waterlinked.ugps"] == 779
        assert counts["clydemcqueen.wl_ugps_external"] == 120
        assert counts["blueos.major_tom"] == 92
        assert counts["clydemcqueen.surftrak_fixit"] == 21

        assert (tmp_path / "test_asl_waterlinked.ugps.txt").is_file()
        assert (tmp_path / "test_asl_clydemcqueen.wl_ugps_external.txt").is_file()
        assert (tmp_path / "test_asl_blueos.major_tom.txt").is_file()
        assert (tmp_path / "test_asl_clydemcqueen.surftrak_fixit.txt").is_file()

    def test_mcap_dump_logs(self, tmp_path):
        import shutil

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260826_181307_no_video.mcap", test_mcap)
        counts = mcap_dump_logs.dump_logs(str(test_mcap))

        # Extensions
        assert counts["waterlinked.ugps"] == 779
        assert counts["clydemcqueen.wl_ugps_external"] == 120
        assert counts["blueos.major_tom"] == 92
        assert counts["clydemcqueen.surftrak_fixit"] == 21
        # Services
        assert counts["wifi-manager"] == 75
        assert counts["beacon"] == 62
        assert counts["kraken"] == 32
        assert counts["helper"] == 22
        assert counts["cable-guy"] == 18
        assert counts["version-chooser"] == 17
        assert counts["bag-of-holding"] == 16
        assert counts["ping"] == 12
        assert counts["ardupilot-manager"] == 2
        # Frontend
        assert counts["frontend_iTSFfEaSz"] == 2

        assert (tmp_path / "test_asl_waterlinked.ugps.txt").is_file()
        assert (tmp_path / "test_asl_wifi-manager.txt").is_file()
        assert (tmp_path / "test_asl_ping.txt").is_file()
        assert (tmp_path / "test_asl_frontend_iTSFfEaSz.txt").is_file()

        # Test file with no extension logs
        test_mcap2 = tmp_path / "test2.mcap"
        shutil.copy("testing/recorder_20260816_203739.mcap", test_mcap2)
        ext_counts = mcap_dump_logs.dump_logs(str(test_mcap2), extensions_only=True)
        assert ext_counts == {}

        all_counts = mcap_dump_logs.dump_logs(str(test_mcap2))
        assert all_counts["wifi-manager"] == 317
        assert all_counts["kraken"] == 176
        assert (tmp_path / "test2_asl_wifi-manager.txt").is_file()

    def test_mcap_explode_extension_logs_csv(self, tmp_path):
        import shutil

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260826_181307_no_video.mcap", test_mcap)
        counts = mcap_explode_extension_logs.explode_extension_logs(str(test_mcap), use_json=False)

        assert counts["wl_ugps_external"] == 40
        assert counts["waterlinked.ugps"] == 23

        assert (tmp_path / "test_asl_wl_ugps_external.csv").is_file()
        assert (tmp_path / "test_asl_waterlinked.ugps.csv").is_file()

    def test_mcap_explode_extension_logs_json(self, tmp_path):
        import shutil

        test_mcap = tmp_path / "test.mcap"
        shutil.copy("testing/recorder_20260826_181307_no_video.mcap", test_mcap)
        counts = mcap_explode_extension_logs.explode_extension_logs(str(test_mcap), use_json=True)

        assert counts["wl_ugps_external"] == 40
        assert counts["waterlinked.ugps"] == 23

        assert (tmp_path / "test_asl_wl_ugps_external.json").is_file()
        assert (tmp_path / "test_asl_waterlinked.ugps.json").is_file()

    def test_waterlinked_dvl_parser(self):
        import os

        parser = mcap_explode_extension_logs.WaterlinkedDvlParser()
        example_lines = [
            '192.168.2.1 - - [01/Sep/2026 16:20:17] "[37mGET /get_status HTTP/1.1[0m" 200 -',
            '192.168.2.1 - - [01/Sep/2026 16:20:19] "[37mGET /get_status HTTP/1.1[0m" 200 -',
            "2026-09-01 16:20:20.889 | INFO     | dvl:handle_velocity:378 - Invalid  dvl reading, ignoring it.",
            '192.168.2.1 - - [01/Sep/2026 16:20:21] "[37mGET /get_status HTTP/1.1[0m" 200 -',
            "2026-09-01 16:20:22.898 | INFO     | dvl:handle_velocity:378 - Invalid  dvl reading, ignoring it.",
            '192.168.2.1 - - [01/Sep/2026 16:20:23] "[37mGET /get_status HTTP/1.1[0m" 200 -',
            '192.168.2.1 - - [01/Sep/2026 16:20:25] "[37mGET /get_status HTTP/1.1[0m" 200 -',
        ]
        records = []
        for i, line in enumerate(example_lines):
            records.extend(parser.parse_line(line))

        assert len(records) == 7
        assert [r["status"] for r in records] == [0, 0, 1, 0, 1, 0, 0]
        assert [r["timestamp"] for r in records] == [
            1788279617.0,
            1788279619.0,
            1788279620.889,
            1788279621.0,
            1788279622.898,
            1788279623.0,
            1788279625.0,
        ]
        # Test fallback when line lacks timestamp
        fallback_record = parser.parse_line("Invalid  dvl reading, ignoring it.")
        assert fallback_record == []

        if os.path.exists("tmp/recorder_20260901_161800.mcap"):
            rows = mcap_explode_extension_logs.parse_bluerobotics_water_linked_dvl("tmp/recorder_20260901_161800.mcap")
            assert len(rows) == 114
            assert sum(1 for r in rows if r["status"] == 0) == 75
            assert sum(1 for r in rows if r["status"] == 1) == 39

    def test_mcap_wl_ugps_acoustic_info(self, capsys):
        info = mcap_wl_ugps_acoustic_info.AcousticLogInfo("testing/recorder_20260826_181307_no_video.mcap")
        info.read_and_report()
        captured = capsys.readouterr().out

        assert "Total readings: 23" in captured
        assert "Valid acoustic fixes: 0 / 23 (0.00%)" in captured
        assert "Time of first valid acoustic fix: None" in captured
        assert "Transducer 0 (R1, -x, aft)" in captured

    def test_bin_timeline(self, capsys):
        reader = FileReader("testing/small2.BIN", BIN_timeline.MSG_TYPES)
        BIN_timeline.Timeline(reader, ansi=False)
        captured = capsys.readouterr().out
        assert "Arming motors" in captured
        assert "DISARMED MANUAL (19)" in captured
        assert "Event: SURFACED" in captured
        assert "Global origin set to" in captured
        assert "EKF status:" in captured

    def test_tlog_timeline(self, capsys):
        reader = FileReader("testing/small.tlog", tlog_timeline.MSG_TYPES)
        tlog_timeline.Timeline(reader, ansi=False)
        captured = capsys.readouterr().out
        assert "Time" in captured

    def test_mcap_map_maker_legend(self, capsys):
        mcap_map_maker.print_legend(mcap_map_maker.SOURCES)
        captured = capsys.readouterr().out
        assert "Global position sources" in captured
        assert "orange" in captured
        assert "red" in captured
        assert "cyan" in captured
        assert "magenta" in captured
        assert "light grey" in captured
        assert "dark grey" in captured
        assert "blue" in captured

    def test_mcap_map_maker(self, tmp_path):
        mcap_file = "testing/recorder_20260826_181307_no_video.mcap"
        outfile = tmp_path / "test_map.html"
        wanted_keys = {s[0] for s in mcap_map_maker.SOURCES}
        sources_data = mcap_map_maker.parse_mcap_sources(
            mcap_file, wanted_keys, hdop_max=100.0, segment=None, raw=False
        )
        assert "ugps_global" in sources_data
        mcap_map_maker.build_map_from_points(
            sources_data, str(outfile), False, [None, None], 18, mcap_map_maker.SOURCES
        )
        assert outfile.is_file()
        content = outfile.read_text(encoding="utf-8")
        assert "Global Position Sources" in content
        assert "leaflet" in content.lower()

    def test_mcap_summary_info(self):
        mcap_file = "testing/recorder_20260826_181307_no_video.mcap"
        info = util.get_mcap_summary_info(mcap_file)
        assert info is not None
        assert info.message_count > 0
        assert info.duration_s > 0
        assert len(info.channels) > 0
        assert len(info.channel_counts) > 0

    def test_mcap_iter_messages(self):
        mcap_file = "testing/recorder_20260826_181307_no_video.mcap"
        msgs = list(util.iter_mcap_messages(mcap_file, message_types=["HEARTBEAT"], sys_id=1, comp_id=1))
        assert len(msgs) > 0
        for schema, channel, msg in msgs:
            assert channel.topic == "mavlink/1/1/HEARTBEAT"
            assert msg.log_time > 0
            assert msg.log_time_s > 0
            assert "type" in msg.json["message"]

    def test_mcap_channels_tool(self, capsys):
        mcap_file = "testing/recorder_20260826_181307_no_video.mcap"
        # Test default fast path
        mcap_channels.count_mcap_messages(mcap_file, extract=False, raw=False)
        out_fast = capsys.readouterr().out
        assert "Message Counts for" in out_fast

        # Test raw fallback path
        mcap_channels.count_mcap_messages(mcap_file, extract=False, raw=True)
        out_raw = capsys.readouterr().out
        assert "Message Counts for" in out_raw

        # Outputs must match
        assert out_fast == out_raw

    def test_mcap_strip_video_standard(self, tmp_path):
        from mcap.writer import Writer

        input_file = tmp_path / "test_standard.mcap"
        with open(input_file, "wb") as f:
            w = Writer(f)
            w.start()
            s_vid = w.register_schema(name="foxglove.CompressedVideo", encoding="jsonschema", data=b"{}")
            c_vid = w.register_channel(topic="video/cam0", message_encoding="json", schema_id=s_vid)
            w.add_message(c_vid, 1000, b"video_frame", 1000)
            s_tel = w.register_schema(name="telemetry", encoding="jsonschema", data=b"{}")
            c_tel = w.register_channel(topic="mavlink/telem", message_encoding="json", schema_id=s_tel)
            w.add_message(c_tel, 1000, b"telem_data", 1000)
            w.finish()

        orig_size = input_file.stat().st_size
        success = mcap_strip_video.strip_video_from_mcap(str(input_file), in_place=False)
        assert success
        assert input_file.is_file()
        assert input_file.stat().st_size == orig_size

        out_file = tmp_path / "test_standard_asl_no_video.mcap"
        assert out_file.is_file()
        summary = util.get_mcap_summary_info(str(out_file))
        assert summary is not None
        assert not any("video" in k.lower() for k in summary.channel_counts)
        assert any("telem" in k.lower() for k in summary.channel_counts)

    def test_mcap_strip_video_in_place(self, tmp_path):
        from mcap.writer import Writer

        input_file = tmp_path / "dive.mcap"
        with open(input_file, "wb") as f:
            w = Writer(f)
            w.start()
            s_vid = w.register_schema(name="foxglove.CompressedVideo", encoding="jsonschema", data=b"{}")
            c_vid = w.register_channel(topic="video/Streamdevvideo0/stream", message_encoding="json", schema_id=s_vid)
            w.add_message(c_vid, 1000, b"video_frame", 1000)
            s_tel = w.register_schema(name="telemetry", encoding="jsonschema", data=b"{}")
            c_tel = w.register_channel(topic="telemetry", message_encoding="json", schema_id=s_tel)
            w.add_message(c_tel, 1000, b"telem_data", 1000)
            w.finish()

        orig_size = input_file.stat().st_size
        success = mcap_strip_video.strip_video_from_mcap(str(input_file), in_place=True)
        assert success

        video_backup = tmp_path / "dive_video.mcap"
        assert video_backup.is_file()
        assert video_backup.stat().st_size == orig_size
        assert input_file.is_file()

        # Check channels
        summary_video = util.get_mcap_summary_info(str(video_backup))
        summary_stripped = util.get_mcap_summary_info(str(input_file))
        assert any("video" in k.lower() for k in summary_video.channel_counts)
        assert not any("video" in k.lower() for k in summary_stripped.channel_counts)
        assert any("telemetry" in k.lower() for k in summary_stripped.channel_counts)

    def test_mcap_strip_video_in_place_safety_checks(self, tmp_path):
        from mcap.writer import Writer

        # 1. Test safety when target _video.mcap already exists
        target_video = tmp_path / "test_video.mcap"
        target_video.write_bytes(b"existing_video_content")
        input_file = tmp_path / "test.mcap"
        input_file.write_bytes(b"input_content")

        success = mcap_strip_video.strip_video_from_mcap(str(input_file), in_place=True)
        assert not success
        # Ensure existing data was not overwritten
        assert target_video.read_bytes() == b"existing_video_content"
        assert input_file.read_bytes() == b"input_content"

        # 2. Test safety when input file already ends with _video.mcap
        success2 = mcap_strip_video.strip_video_from_mcap(str(target_video), in_place=True)
        assert not success2
        assert target_video.read_bytes() == b"existing_video_content"

        # 3. Test safety when file has no video: file left unchanged, no _video.mcap created
        no_vid_file = tmp_path / "novideo.mcap"
        with open(no_vid_file, "wb") as f:
            w = Writer(f)
            w.start()
            s_tel = w.register_schema(name="telemetry", encoding="jsonschema", data=b"{}")
            c_tel = w.register_channel(topic="telemetry", message_encoding="json", schema_id=s_tel)
            w.add_message(c_tel, 1000, b"telem_data", 1000)
            w.finish()

        orig_novid_size = no_vid_file.stat().st_size
        success3 = mcap_strip_video.strip_video_from_mcap(str(no_vid_file), in_place=True)
        assert success3
        assert not (tmp_path / "novideo_video.mcap").exists()
        assert no_vid_file.stat().st_size == orig_novid_size
