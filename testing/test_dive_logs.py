import json
from pathlib import Path

import numpy as np
import pytest

from dive_logs import BinFile, Boot, DiveLogs, McapFile, optimize_depth_shift


class TestDiveLogs:
    def test_models_serialization_roundtrip(self, tmp_path):
        """Test constructing DiveLogs, saving to JSON, and reloading with exact fidelity."""
        boot = Boot(
            boot_id=1,
            rtc_shift_s=1788220000.123456,
            start_iso="2026-08-31T09:40:00.123456+00:00",
            end_iso="2026-08-31T11:00:00.123456+00:00",
            duration_s=4800.0,
            alignment_method="bin_rtc_message",
            signal_optimized=True,
            depth_correlation_r=0.9985,
            bin_files=["00000161.BIN"],
            mcap_files=["recorder_20260831_165221.mcap"],
        )

        bin_file = BinFile(
            name="00000161.BIN",
            boot_id=1,
            uptime_start_s=0.0,
            uptime_end_s=4800.0,
            duration_s=4800.0,
            start_iso="2026-08-31T09:40:00.123456+00:00",
            end_iso="2026-08-31T11:00:00.123456+00:00",
            log_disarmed=1,
            ardusub_version="4.7.0",
            has_rtc_message=True,
            has_gps_fix=False,
            mcap_files=["recorder_20260831_165221.mcap"],
        )

        mcap_file = McapFile(
            name="recorder_20260831_165221.mcap",
            boot_id=1,
            start_iso="2026-08-31T09:52:21.895000+00:00",
            end_iso="2026-08-31T09:55:35.883000+00:00",
            duration_s=193.988,
            uptime_start_s=741.77,
            uptime_end_s=935.758,
            sample_rtc_shift_s=1788220000.123,
            flight_modes=["MANUAL", "STABILIZE"],
            bin_files=["00000161.BIN"],
        )

        dive_logs = DiveLogs(
            directory=tmp_path,
            boots=[boot],
            bin_files=[bin_file],
            mcap_files=[mcap_file],
            created_iso="2026-09-11T12:00:00+00:00",
        )

        out_file = dive_logs.save()
        assert out_file.is_file()

        # Load back
        loaded = DiveLogs.load(tmp_path)
        assert loaded.directory == tmp_path.resolve()
        assert len(loaded.boots) == 1
        assert len(loaded.bin_files) == 1
        assert len(loaded.mcap_files) == 1

        b = loaded.get_boot(1)
        assert b is not None
        assert b.boot_id == 1
        assert b.alignment_method == "bin_rtc_message"
        assert b.signal_optimized is True
        assert pytest.approx(b.rtc_shift_s, rel=1e-6) == 1788220000.123456
        assert b.depth_correlation_r == 0.9985
        assert b.bin_files == ["00000161.BIN"]
        assert b.mcap_files == ["recorder_20260831_165221.mcap"]

        # Test relationships
        assert len(b.bins) == 1
        assert b.bins[0].name == "00000161.BIN"
        assert len(b.mcaps) == 1
        assert b.mcaps[0].name == "recorder_20260831_165221.mcap"

        bf = loaded.get_bin("00000161.BIN")
        assert bf is not None
        assert bf.has_rtc_message is True
        assert bf.ardusub_version == "4.7.0"

    def test_schema_conformance(self, tmp_path):
        """Validate serialized dictionary against schemas/dive_logs.schema.json."""
        schema_path = Path(__file__).resolve().parent.parent / "schemas" / "dive_logs.schema.json"
        assert schema_path.is_file()

        with open(schema_path, "r") as f:
            schema = json.load(f)

        boot = Boot(
            boot_id=1,
            rtc_shift_s=1788220000.0,
            start_iso="2026-08-31T09:40:00+00:00",
            end_iso="2026-08-31T11:00:00+00:00",
            duration_s=4800.0,
            alignment_method="mcap_rtc_shift",
            signal_optimized=False,
            bin_files=["00000161.BIN"],
            mcap_files=[],
        )
        bin_file = BinFile(
            name="00000161.BIN",
            boot_id=1,
            uptime_start_s=0.0,
            uptime_end_s=4800.0,
            duration_s=4800.0,
            mcap_files=[],
        )
        dive_logs = DiveLogs(tmp_path, [boot], [bin_file], [])
        data = dive_logs.to_dict()

        try:
            import jsonschema

            jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            # If jsonschema is not installed, verify basic required keys
            assert "schema_version" in data
            assert "boots" in data
            assert "bin_files" in data
            assert "mcap_files" in data

    def test_timeus_conversion_helpers(self, tmp_path):
        """Test timeus_to_utc_s and timeus_to_iso on BinFile."""
        shift = 1788220000.0  # seconds
        boot = Boot(
            boot_id=1,
            rtc_shift_s=shift,
            start_iso=None,
            end_iso=None,
            duration_s=100.0,
            alignment_method="mcap_rtc_shift",
        )
        bin_file = BinFile(
            name="00000001.BIN",
            boot_id=1,
            uptime_start_s=0.0,
            uptime_end_s=100.0,
            duration_s=100.0,
        )
        DiveLogs(tmp_path, [boot], [bin_file], [])

        # TimeUS = 50_000_000 (50 seconds)
        utc_s = bin_file.timeus_to_utc_s(50_000_000)
        assert utc_s == shift + 50.0

        iso_str = bin_file.timeus_to_iso(50_000_000)
        assert iso_str is not None
        assert "T" in iso_str

    def test_find_overlapping(self, tmp_path):
        """Test find_overlapping with time windows."""
        boot = Boot(1, 1000.0, "1970-01-01T00:16:40+00:00", "1970-01-01T00:50:00+00:00", 2000.0, "mcap_rtc_shift")
        b1 = BinFile("00000001.BIN", 1, 0.0, 1000.0, 1000.0, "1970-01-01T00:16:40+00:00", "1970-01-01T00:33:20+00:00")
        m1 = McapFile("rec1.mcap", 1, "1970-01-01T00:20:00+00:00", "1970-01-01T00:30:00+00:00", 600.0)
        m2 = McapFile("rec2.mcap", 1, "1970-01-01T00:40:00+00:00", "1970-01-01T00:45:00+00:00", 300.0)

        dive_logs = DiveLogs(tmp_path, [boot], [b1], [m1, m2])

        # Query window 00:22:00 to 00:25:00 should match b1 and m1, but not m2
        bins, mcaps = dive_logs.find_overlapping("1970-01-01T00:22:00+00:00", "1970-01-01T00:25:00+00:00")
        assert len(bins) == 1
        assert bins[0].name == "00000001.BIN"
        assert len(mcaps) == 1
        assert mcaps[0].name == "rec1.mcap"

    def test_depth_signal_optimizer(self):
        """Test optimize_depth_shift with synthetic sine wave depth tracks."""
        t = np.linspace(100.0, 500.0, 800)  # 400 seconds
        depth = 5.0 + 3.0 * np.sin(2 * np.pi * (t - 100.0) / 60.0)  # vertical oscillations

        bin_track = list(zip(t, depth))

        # MCAP track shifted by +0.045 seconds (45 ms transport lag)
        true_shift = 0.045
        mcap_t = np.linspace(120.0, 480.0, 720)
        mcap_depth = np.interp(mcap_t + true_shift, t, depth)
        mcap_track = list(zip(mcap_t, mcap_depth))

        res = optimize_depth_shift(bin_track, mcap_track)
        assert res is not None
        delta_s, r = res
        assert pytest.approx(delta_s, abs=0.002) == true_shift
        assert r > 0.999

    def test_unmatched_files(self, tmp_path):
        """Test representation of unmatched BIN logs and orphaned MCAPs."""
        boot1 = Boot(
            boot_id=1,
            rtc_shift_s=None,
            start_iso=None,
            end_iso=None,
            duration_s=60.0,
            alignment_method="unaligned",
            bin_files=["00000001.BIN"],
            mcap_files=[],
        )
        boot2 = Boot(
            boot_id=2,
            rtc_shift_s=1788200000.0,
            start_iso="2026-08-31T12:00:00+00:00",
            end_iso="2026-08-31T12:05:00+00:00",
            duration_s=300.0,
            alignment_method="mcap_rtc_shift",
            bin_files=[],
            mcap_files=["orphan.mcap"],
        )
        b1 = BinFile("00000001.BIN", 1, 0.0, 60.0, 60.0, mcap_files=[])
        m2 = McapFile("orphan.mcap", 2, "2026-08-31T12:00:00+00:00", "2026-08-31T12:05:00+00:00", 300.0, bin_files=[])

        dl = DiveLogs(tmp_path, [boot1, boot2], [b1], [m2])
        assert len(dl.boots) == 2
        assert dl.boots[0].bin_files == ["00000001.BIN"]
        assert dl.boots[0].mcap_files == []
        assert dl.boots[1].bin_files == []
        assert dl.boots[1].mcap_files == ["orphan.mcap"]

        # Roundtrip
        saved = dl.save()
        loaded = DiveLogs.load(saved)
        assert len(loaded.boots) == 2
        assert loaded.get_bin("00000001.BIN").mcap_files == []
        assert loaded.get_mcap("orphan.mcap").bin_files == []
