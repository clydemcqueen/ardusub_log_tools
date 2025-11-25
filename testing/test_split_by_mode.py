
import unittest
import os
import glob
import subprocess
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSplitByMode(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_path = os.path.join(self.project_root, 'split_by_mode.py')
        self.testing_dir = os.path.join(self.project_root, 'testing')
        
        # Files to test
        self.small_tlog = os.path.join(self.testing_dir, 'small.tlog')
        self.small_bin = os.path.join(self.testing_dir, 'small.BIN')
        # TODO(clyde): These files are too big to save in git, find 2 smaller but still interesting files
        # self.large_tlog = os.path.join(self.testing_dir, '00118-2025-10-08_18-03-06.tlog')
        # self.large_bin = os.path.join(self.testing_dir, '00000062.BIN')
        
        # Cleanup before test
        self.cleanup()

    def tearDown(self):
        # Cleanup after test
        self.cleanup()

    def cleanup(self):
        # Remove any generated files in testing dir matching pattern
        patterns = [
            '*_MANUAL*.tlog', '*_MANUAL*.BIN',
            '*_SURFTRAK*.tlog', '*_SURFTRAK*.BIN',
            '*_ALT_HOLD*.tlog', '*_ALT_HOLD*.BIN',
            '*_STABILIZE*.tlog', '*_STABILIZE*.BIN',
        ]
        
        for pattern in patterns:
            for f in glob.glob(os.path.join(self.testing_dir, pattern)):
                try:
                    os.remove(f)
                except OSError:
                    pass

    def run_script(self, args):
        cmd = [sys.executable, self.script_path] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def test_small_tlog(self):
        result = self.run_script([self.small_tlog])
        self.assertEqual(result.returncode, 0)
        
        # Expect small_MANUAL1.tlog
        expected = os.path.join(self.testing_dir, 'small_MANUAL1.tlog')
        self.assertTrue(os.path.exists(expected), f"Expected {expected} to exist")

    def test_small_bin(self):
        result = self.run_script([self.small_bin])
        self.assertEqual(result.returncode, 0)
        
        # Expect small_MANUAL1.BIN
        expected = os.path.join(self.testing_dir, 'small_MANUAL1.BIN')
        self.assertTrue(os.path.exists(expected), f"Expected {expected} to exist")

    def disabled_test_large_tlog(self):
        result = self.run_script([self.large_tlog])
        self.assertEqual(result.returncode, 0)
        
        # Expect multiple files
        expected_files = [
            '00118-2025-10-08_18-03-06_MANUAL1.tlog',
            '00118-2025-10-08_18-03-06_SURFTRAK1.tlog',
            '00118-2025-10-08_18-03-06_ALT_HOLD1.tlog',
            '00118-2025-10-08_18-03-06_SURFTRAK2.tlog',
            '00118-2025-10-08_18-03-06_ALT_HOLD2.tlog',
            '00118-2025-10-08_18-03-06_MANUAL2.tlog',
        ]
        
        for f in expected_files:
            path = os.path.join(self.testing_dir, f)
            self.assertTrue(os.path.exists(path), f"Expected {path} to exist")

    def disabled_test_large_bin(self):
        result = self.run_script([self.large_bin])
        self.assertEqual(result.returncode, 0)
        
        # Expect multiple files
        expected_files = [
            '00000062_MANUAL1.BIN',
            '00000062_SURFTRAK1.BIN',
            '00000062_ALT_HOLD1.BIN',
            '00000062_SURFTRAK2.BIN',
            '00000062_ALT_HOLD2.BIN',
            '00000062_MANUAL2.BIN',
        ]
        
        for f in expected_files:
            path = os.path.join(self.testing_dir, f)
            self.assertTrue(os.path.exists(path), f"Expected {path} to exist")

    def disabled_test_filter_modes(self):
        # Test filtering by mode
        result = self.run_script(['--modes', 'SURFTRAK', '-v', self.large_tlog])
        self.assertEqual(result.returncode, 0)
        
        # Should exist
        self.assertTrue(os.path.exists(os.path.join(self.testing_dir, '00118-2025-10-08_18-03-06_SURFTRAK1.tlog')))
        self.assertTrue(os.path.exists(os.path.join(self.testing_dir, '00118-2025-10-08_18-03-06_SURFTRAK2.tlog')))
        
        # Should NOT exist
        self.assertFalse(os.path.exists(os.path.join(self.testing_dir, '00118-2025-10-08_18-03-06_MANUAL1.tlog')))
        self.assertFalse(os.path.exists(os.path.join(self.testing_dir, '00118-2025-10-08_18-03-06_ALT_HOLD1.tlog')))

if __name__ == '__main__':
    unittest.main()
