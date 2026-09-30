import sys
import unittest
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ardusub_log_tools.cli.main import main


class TestPhase3Timeline(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase3_timeline"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        self.mcap_file = str(REPO_ROOT / "testing" / "recorder_20260816_203739.mcap")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_timeline_tlog(self):
        ret = main(["timeline", "--no-ansi", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "small_asl_timeline.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            content = f.read()
            self.assertIn("MANUAL", content)
            self.assertIn("Time", content)

    def test_timeline_bin(self):
        ret = main(["timeline", "--no-ansi", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "small2_asl_timeline.txt"
        self.assertTrue(out_txt.is_file())

    def test_timeline_mcap(self):
        ret = main(["timeline", "--no-ansi", "-o", str(self.tmp_dir), self.mcap_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "recorder_20260816_203739_asl_timeline.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            content = f.read()
            self.assertIn("ARMED MANUAL", content)
            self.assertIn("EKF status", content)

    def test_timeline_tz(self):
        ret = main(["timeline", "--no-ansi", "--tz", "America/Los_Angeles", "-o", str(self.tmp_dir), self.mcap_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "recorder_20260816_203739_asl_timeline.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 1)
            # Check timestamp is formatted
            self.assertIn("2026-08-16 13:37:39", lines[1])


class TestPhase3Messages(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase3_messages"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        self.mcap_file = str(REPO_ROOT / "testing" / "recorder_20260816_203739.mcap")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_messages_tlog_stream(self):
        ret = main(["messages", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "small_asl_messages.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            content = f.read()
            self.assertIn("ArduSub", content)

    def test_messages_tlog_summary(self):
        ret = main(["messages", "--summary", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "small_asl_messages.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            content = f.read()
            self.assertIn("ArduSub V4.1.1 BETA5", content)

    def test_messages_bin(self):
        ret = main(["messages", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "small2_asl_messages.txt"
        self.assertTrue(out_txt.is_file())

    def test_messages_mcap_summary(self):
        ret = main(["messages", "--summary", "-o", str(self.tmp_dir), self.mcap_file])
        self.assertEqual(ret, 0)
        out_txt = self.tmp_dir / "recorder_20260816_203739_asl_messages.txt"
        self.assertTrue(out_txt.is_file())
        with open(out_txt, "r") as f:
            content = f.read()
            self.assertIn("EKF3 lane switch", content)


class TestPhase3Params(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase3_params"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        self.mcap_file = str(REPO_ROOT / "testing" / "recorder_20260816_203739.mcap")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_params_tlog(self):
        ret = main(["params", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_params = self.tmp_dir / "small_asl_params.params"
        self.assertTrue(out_params.is_file())

    def test_params_bin(self):
        ret = main(["params", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_params = self.tmp_dir / "small2_asl_params.params"
        self.assertTrue(out_params.is_file())

    def test_params_mcap(self):
        ret = main(["params", "-o", str(self.tmp_dir), self.mcap_file])
        self.assertEqual(ret, 0)
        out_params = self.tmp_dir / "recorder_20260816_203739_asl_params.params"
        self.assertTrue(out_params.is_file())
        with open(out_params, "r") as f:
            content = f.read()
            self.assertIn("BTN5_SFUNCTION", content)

    def test_params_changes(self):
        ret = main(["params", "--changes", self.mcap_file])
        self.assertEqual(ret, 0)

    def test_params_filter_names(self):
        ret = main(["params", "--names", "BTN5_*", "-o", str(self.tmp_dir), self.mcap_file])
        self.assertEqual(ret, 0)
        out_params = self.tmp_dir / "recorder_20260816_203739_asl_params.params"
        self.assertTrue(out_params.is_file())
        with open(out_params, "r") as f:
            content = f.read()
            self.assertIn("BTN5_SFUNCTION", content)
            self.assertNotIn("STAT_FLTTIME", content)


class TestPhase3Info(unittest.TestCase):
    def test_info_tlog(self):
        tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        ret = main(["info", tlog_file])
        self.assertEqual(ret, 0)

    def test_info_bin(self):
        bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        ret = main(["info", bin_file])
        self.assertEqual(ret, 0)

    def test_info_mcap(self):
        mcap_file = str(REPO_ROOT / "testing" / "recorder_20260816_203739.mcap")
        ret = main(["info", mcap_file])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
