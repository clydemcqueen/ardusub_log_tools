# Run tests:
# python -m pytest

import os
from file_reader import FileReader
from pymavlink import mavutil
import tlog_filter


class TestTools:

    def test_tlog_filter(self):
        # Create a reader for a small tlog file
        readers = [FileReader('testing/small.tlog', None)]
        output_filename = 'testing/filtered.tlog'

        # Filter messages, keeping only ATTITUDE messages
        tlog_filter.filter_tlog(readers, output_filename, ['ATTITUDE'], 0, 0, 0, False)

        # Verify that the output file was created
        assert os.path.exists(output_filename)

        # Verify the contents of the output file
        mlog = mavutil.mavlink_connection(output_filename)
        msg_count = 0
        while True:
            msg = mlog.recv_match()
            if msg is None:
                break
            msg_count += 1
            assert msg.get_type() == 'ATTITUDE'
        assert msg_count == 5245

        # Clean up the output file
        os.remove(output_filename)

    def test_tlog_combine(self):
        # Create a reader for a small tlog file
        readers = [FileReader('testing/small.tlog', None), FileReader('testing/small.tlog', None)]
        output_filename = 'testing/combined.tlog'

        # Filter messages, keeping only ATTITUDE messages
        tlog_filter.filter_tlog(readers, output_filename, ['ATTITUDE'], 0, 0, 0, False)

        # Verify that the output file was created
        assert os.path.exists(output_filename)

        # Verify the contents of the output file
        mlog = mavutil.mavlink_connection(output_filename)
        msg_count = 0
        while True:
            msg = mlog.recv_match()
            if msg is None:
                break
            msg_count += 1
            assert msg.get_type() == 'ATTITUDE'
        assert msg_count == 10490

        # Clean up the output file
        os.remove(output_filename)


if __name__ == '__main__':
    # When run by hand, this test will create a file named 'testing/small.tlog'
    TestTools().test_tlog_filter()
    TestTools().test_tlog_combine()
