import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from segment_reader import SegmentFormatException, parse_segment_json


def test_parse_utc_plan_json():
    plan_path = "testing/utc_plan.json"
    segments = parse_segment_json(plan_path)
    assert len(segments) == 4
    assert [s.name for s in segments] == ["T1", "T2", "T3", "T4"]
    # T1: 09:25:23 PDT on 2026-09-02 -> 1788366323.0
    assert segments[0].start == 1788366323.0
    assert segments[0].end == 1788366937.0
    assert segments[0].end - segments[0].start == 614.0


def test_parse_simple_segments_json(tmp_path):
    data = {
        "timezone": "America/Los_Angeles",
        "date": "2026-09-02",
        "segments": [
            {"name": "s_epoch", "start": 1788366323.0, "end": 1788366937.0},
            {"name": "s_iso", "start": "2026-09-02T09:25:23-07:00", "end": "2026-09-02T09:35:37-07:00"},
            {"name": "s_tc", "start_tc": "09:25:23", "end_tc": "09:35:37"},
        ],
    }
    json_file = tmp_path / "simple_segments.json"
    json_file.write_text(json.dumps(data), encoding="utf-8")

    segments = parse_segment_json(str(json_file))
    assert len(segments) == 3
    assert segments[0].name == "s_epoch"
    assert segments[1].name == "s_iso"
    assert segments[2].name == "s_tc"
    assert segments[0].start == 1788366323.0
    assert segments[1].start == 1788366323.0
    assert segments[2].start == 1788366323.0
    assert segments[0].end == 1788366937.0
    assert segments[1].end == 1788366937.0
    assert segments[2].end == 1788366937.0


def test_parse_list_segments_json(tmp_path):
    data = [
        {"name": "seg1", "start": 1000.0, "end": 1100.0},
        {"name": "seg2", "start": "2026-01-01T12:00:00Z", "end": "2026-01-01T13:00:00Z"},
    ]
    json_file = tmp_path / "list_segments.json"
    json_file.write_text(json.dumps(data), encoding="utf-8")

    segments = parse_segment_json(str(json_file))
    assert len(segments) == 2
    assert segments[0].name == "seg1"
    assert segments[0].start == 1000.0
    assert segments[0].end == 1100.0
    assert segments[1].name == "seg2"


def test_multi_site_naming():
    data = {
        "timezone": "UTC",
        "sites": [
            {
                "name": "SiteA",
                "date": "2026-09-02",
                "transects": [{"name": "T1", "start_tc": "08:00:00", "end_tc": "09:00:00"}],
            },
            {
                "name": "SiteB",
                "date": "2026-09-02",
                "transects": [{"name": "T1", "start_tc": "10:00:00", "end_tc": "11:00:00"}],
            },
        ],
    }
    segments = parse_segment_json(json.dumps(data))
    assert len(segments) == 2
    assert segments[0].name == "SiteA_T1"
    assert segments[1].name == "SiteB_T1"


def test_inline_json_string():
    raw_json = json.dumps({"segments": [{"name": "s1", "start": 100.0, "end": 200.0}]})
    segments = parse_segment_json(raw_json)
    assert len(segments) == 1
    assert segments[0].name == "s1"
    assert segments[0].start == 100.0
    assert segments[0].end == 200.0


def test_invalid_json_handling():
    with pytest.raises(SegmentFormatException, match="Segment file not found"):
        parse_segment_json("nonexistent_file.json")

    with pytest.raises(SegmentFormatException, match="Failed to parse segment JSON"):
        parse_segment_json("{malformed json:")

    with pytest.raises(SegmentFormatException, match="missing start/end"):
        parse_segment_json(json.dumps({"segments": [{"name": "bad"}]}))

    with pytest.raises(SegmentFormatException, match="must be strictly before end"):
        parse_segment_json(json.dumps({"segments": [{"name": "bad", "start": 200, "end": 100}]}))

    with pytest.raises(SegmentFormatException, match="Date is required for timecode"):
        parse_segment_json(json.dumps({"segments": [{"name": "bad", "start_tc": "09:00:00", "end_tc": "10:00:00"}]}))

    with pytest.raises(SegmentFormatException, match="Unknown or invalid timezone"):
        parse_segment_json(
            json.dumps(
                {
                    "timezone": "Invalid/Timezone",
                    "date": "2026-09-02",
                    "segments": [{"name": "bad", "start_tc": "09:00:00", "end_tc": "10:00:00"}],
                }
            )
        )


def test_mcap_explode_cli_segments(tmp_path):
    mcap_source = Path("testing/recorder_20260826_181307_no_video.mcap")
    test_mcap = tmp_path / "recorder_20260826_181307_no_video.mcap"
    shutil.copy(mcap_source, test_mcap)

    # 1787767988.0 to 1787767998.0 in PDT is 2026-08-26 11:13:08 to 11:13:18
    plan_data = {
        "timezone": "America/Los_Angeles",
        "sites": [
            {
                "name": "Shakedown",
                "date": "2026-08-26",
                "transects": [
                    {
                        "name": "T1",
                        "start_tc": "11:13:08",
                        "end_tc": "11:13:18",
                    }
                ],
            }
        ],
    }
    plan_path = tmp_path / "test_plan.json"
    plan_path.write_text(json.dumps(plan_data), encoding="utf-8")

    cmd = [
        sys.executable,
        "mcap_explode.py",
        "-s",
        str(plan_path),
        "--types",
        "HEARTBEAT",
        str(test_mcap),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(".").resolve())
    assert res.returncode == 0, f"mcap_explode failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert (tmp_path / "T1_asl_HEARTBEAT.csv").is_file()


def test_mcap_map_maker_cli_segments(tmp_path):
    mcap_source = Path("testing/recorder_20260826_181307_no_video.mcap")
    test_mcap = tmp_path / "recorder_20260826_181307_no_video.mcap"
    shutil.copy(mcap_source, test_mcap)

    plan_data = {
        "timezone": "America/Los_Angeles",
        "sites": [
            {
                "name": "Shakedown",
                "date": "2026-08-26",
                "transects": [
                    {
                        "name": "T1",
                        "start_tc": "11:13:08",
                        "end_tc": "11:13:18",
                    }
                ],
            }
        ],
    }
    plan_path = tmp_path / "test_plan.json"
    plan_path.write_text(json.dumps(plan_data), encoding="utf-8")

    cmd = [
        sys.executable,
        "mcap_map_maker.py",
        "-s",
        str(plan_path),
        str(test_mcap),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(".").resolve())
    assert res.returncode == 0, f"mcap_map_maker failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert (tmp_path / "T1_asl_map.html").is_file()
