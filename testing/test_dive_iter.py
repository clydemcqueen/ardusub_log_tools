
import unittest
from unittest.mock import MagicMock, patch
from dive_iter import DiveIterator

class MockMsg:
    def __init__(self, type_name, timestamp=None, time_us=None, **kwargs):
        self._type = type_name
        if timestamp is not None:
            self._timestamp = timestamp
        if time_us is not None:
            self.TimeUS = time_us
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get_type(self):
        return self._type

class TestDiveIterator(unittest.TestCase):

    @patch('dive_iter.mavutil.mavlink_connection')
    def test_sync_and_read(self, mock_conn):
        # Setup Tlog mock
        tlog_mock = MagicMock()
        # Tlog messages:
        # 1. HEARTBEAT (ts=100.0)
        # 2. ATTITUDE (ts=101.0, time_boot_ms=1000) -> Offset = 101.0 - 1.0 = 100.0s = 100000000us
        # 3. ATTITUDE (ts=102.0)
        # 4. ATTITUDE (ts=103.0)
        
        # Setup BIN mock
        bin_mock = MagicMock()
        # BIN messages:
        # 1. FMT (TimeUS=0) -> Unix=100.0s
        # 2. MSG1 (TimeUS=1500000) -> 1.5s boot -> Unix=101.5s
        # 3. MSG2 (TimeUS=2500000) -> 2.5s boot -> Unix=102.5s
        # 4. MSG3 (TimeUS=3500000) -> 3.5s boot -> Unix=103.5s
        
        # Intersection:
        # Tlog starts at 100.0
        # BIN starts at 100.0 (0 + offset)
        # Start time = 100.0
        
        # Tlog ends at 103.0
        # BIN ends at 103.5
        # Should stop when Tlog ends (at 103.0, after yielding Tlog 103.0)
        # Wait, if Tlog yields 103.0, then next call returns None.
        # Then __next__ sees Tlog is None, should raise StopIteration.
        
        original_tlog_msgs = [
            MockMsg('HEARTBEAT', timestamp=100.0),
            MockMsg('ATTITUDE', timestamp=101.0, time_boot_ms=1000),
            MockMsg('ATTITUDE', timestamp=102.0),
            MockMsg('ATTITUDE', timestamp=103.0),
            None
        ]
        
        original_bin_msgs = [
            MockMsg('FMT', TimeUS=0, timestamp=0.0),
            MockMsg('MSG1', TimeUS=1500000, timestamp=1.5), # 101.5s
            MockMsg('MSG2', TimeUS=2500000, timestamp=2.5), # 102.5s
            MockMsg('MSG3', TimeUS=3500000, timestamp=3.5), # 103.5s
            None
        ]
        
        # State for mocks
        tlog_state = {'msgs': list(original_tlog_msgs)}
        bin_state = {'msgs': list(original_bin_msgs)}
        
        def tlog_recv(blocking=False, type=None):
            if tlog_state['msgs']:
                return tlog_state['msgs'].pop(0)
            return None
            
        def bin_recv(blocking=False, type=None):
            if bin_state['msgs']:
                return bin_state['msgs'].pop(0)
            return None

        def tlog_rewind():
            tlog_state['msgs'] = list(original_tlog_msgs)
            
        def bin_rewind():
            bin_state['msgs'] = list(original_bin_msgs)

        tlog_mock.recv_match.side_effect = tlog_recv
        tlog_mock.rewind.side_effect = tlog_rewind
        
        bin_mock.recv_match.side_effect = bin_recv
        bin_mock.rewind.side_effect = bin_rewind
        
        # Configure mock_conn to return tlog_mock or bin_mock based on path
        def side_effect(path, **kwargs):
            if 'tlog' in path:
                return tlog_mock
            else:
                return bin_mock
        
        mock_conn.side_effect = side_effect
        
        # Run DiveIterator
        parser = DiveIterator('test.tlog', 'test.bin')
        
        # Expected order:
        # Offset = 100.0s
        # 1. Tlog HEARTBEAT (100.0)
        # 2. BIN FMT (100.0)
        # 3. Tlog ATTITUDE (101.0)
        # 4. BIN MSG1 (101.5)
        # 5. Tlog ATTITUDE (102.0)
        # 6. BIN MSG2 (102.5)
        # 7. Tlog ATTITUDE (103.0)
        # Stop (Tlog empty)
        
        msgs = list(parser)
        
        # Check types
        types = [m.get_type() for m in msgs]
        print("Yielded types:", types)
        
        expected_types = ['HEARTBEAT', 'FMT', 'ATTITUDE', 'MSG1', 'ATTITUDE', 'MSG2', 'ATTITUDE']
        
        self.assertEqual(types, expected_types)

if __name__ == '__main__':
    unittest.main()
