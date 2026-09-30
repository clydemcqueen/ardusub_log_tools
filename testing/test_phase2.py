import sys
import unittest
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ardusub_log_tools.cli.main import main


class TestPhase2Explode(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase2"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_explode_tlog(self):
        ret = main(["explode", "--types", "GLOBAL_POSITION_INT", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_csv = self.tmp_dir / "small_asl_GLOBAL_POSITION_INT.csv"
        self.assertTrue(out_csv.is_file())
        with open(out_csv, "r") as f:
            header = f.readline()
            self.assertIn("timestamp", header)
            self.assertIn("lat", header)

    def test_explode_bin_preset(self):
        ret = main(["explode", "--types", "ekf", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_xkf1 = self.tmp_dir / "small2_asl_XKF1_core0.csv"
        self.assertTrue(out_xkf1.is_file())

    def test_explode_with_rate(self):
        ret = main(["explode", "--types", "GLOBAL_POSITION_INT", "--rate", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_csv = self.tmp_dir / "small_asl_GLOBAL_POSITION_INT.csv"
        self.assertTrue(out_csv.is_file())
        with open(out_csv, "r") as f:
            header = f.readline()
            self.assertIn("GLOBAL_POSITION_INT.rate", header)


class TestPhase2Merge(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase2_merge"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_merge_tlog(self):
        ret = main(["merge", "--types", "GLOBAL_POSITION_INT,ATTITUDE", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_csv = self.tmp_dir / "small_asl_merged.csv"
        self.assertTrue(out_csv.is_file())
        with open(out_csv, "r") as f:
            header = f.readline()
            self.assertIn("GLOBAL_POSITION_INT", header)
            self.assertIn("ATTITUDE", header)

    def test_merge_bin(self):
        ret = main(["merge", "--types", "ekf", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_csv = self.tmp_dir / "small2_asl_merged.csv"
        self.assertTrue(out_csv.is_file())


class TestPhase2Types(unittest.TestCase):
    def test_types(self):
        tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        ret = main(["types", tlog_file, bin_file])
        self.assertEqual(ret, 0)


class TestPhase2Map(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase2_map"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_map_tlog(self):
        ret = main(["map", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_map = self.tmp_dir / "small_asl_map.html"
        self.assertTrue(out_map.is_file())
        with open(out_map, "r") as f:
            content = f.read()
            self.assertIn("leaflet", content.lower())


class TestPhase2Plot(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase2_plot"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_plot_local_tlog(self):
        ret = main(["plot", "local", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_plot = self.tmp_dir / "small_asl_local.pdf"
        self.assertTrue(out_plot.is_file())

    def test_plot_local_bin(self):
        ret = main(["plot", "local", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_plot = self.tmp_dir / "small2_asl_local.pdf"
        self.assertTrue(out_plot.is_file())

    def test_plot_altitude(self):
        ret = main(["plot", "altitude", "-o", str(self.tmp_dir), self.bin_file])
        self.assertEqual(ret, 0)
        out_plot = self.tmp_dir / "small2_asl_altitude.pdf"
        self.assertTrue(out_plot.is_file())


class TestPhase2Split(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = REPO_ROOT / "testing" / "tmp_test_phase2_split"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        self.bin_file = str(REPO_ROOT / "testing" / "small2.BIN")

    def tearDown(self):
        if self.tmp_dir.exists():
            import shutil

            shutil.rmtree(self.tmp_dir)

    def test_split_mode(self):
        ret = main(["split", "--mode", "MANUAL", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_split = self.tmp_dir / "small_asl_MANUAL1.tlog"
        self.assertTrue(out_split.is_file())

    def test_split_keep_segment(self):
        ret = main(["split", "--keep", "1683220544,1683220546,test_seg", "-o", str(self.tmp_dir), self.tlog_file])
        self.assertEqual(ret, 0)
        out_split = self.tmp_dir / "small_asl_seg_test_seg.tlog"
        self.assertTrue(out_split.is_file())


class TestPhase2Diagnostics(unittest.TestCase):
    def test_battery_terse(self):
        tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        ret = main(["battery", "--terse", tlog_file])
        self.assertEqual(ret, 0)

    def test_mission(self):
        tlog_file = str(REPO_ROOT / "testing" / "small.tlog")
        ret = main(["mission", tlog_file])
        self.assertEqual(ret, 0)

    def test_ekf(self):
        bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        ret = main(["ekf", bin_file])
        self.assertEqual(ret, 0)

    def test_compass(self):
        bin_file = str(REPO_ROOT / "testing" / "small2.BIN")
        ret = main(["compass", bin_file])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
