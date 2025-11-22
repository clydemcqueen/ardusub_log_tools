# Run tests:
# python -m pytest

import os
from file_reader import FileReader
from pymavlink import mavutil
from segment_reader import Segment, SegmentReader
import tlog_filter


class TestTools:

    def test_tlog_filter(self):
        # Create a reader for a small tlog file
        reader = FileReader('testing/small.tlog', None)
        output_filename = 'testing/small_filtered.tlog'

        # Filter messages, keeping only ATTITUDE messages
        tlog_filter.filter_tlog(reader, ['ATTITUDE'], None, None, 500000, False)

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

    def test_tlog_filter_compid_0(self):
        # Create a reader for a small tlog file
        reader = FileReader('testing/small.tlog', None)
        output_filename = 'testing/small_filtered.tlog'

        # Filter messages, keeping only messages from compid 0
        tlog_filter.filter_tlog(reader, None, 0, 0, 500000, False)

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
            assert msg.get_srcComponent() == 0
        assert msg_count == 4

        # Clean up the output file
        os.remove(output_filename)

    def test_tlog_combine_segments(self):
        # Create a reader for a small tlog file
        segment1 = Segment(1622246400, 1622246400 + 1, 'segment1')
        segment2 = Segment(1622246400 + 2, 1622246400 + 3, 'segment2')

        readers = [
            SegmentReader(segment1, FileReader('testing/small.tlog', None), None),
            SegmentReader(segment2, FileReader('testing/small.tlog', None), None)
        ]
        output_filename1 = 'testing/segment1_filtered.tlog'
        output_filename2 = 'testing/segment2_filtered.tlog'

        # Filter messages, keeping only ATTITUDE messages
        for reader in readers:
            tlog_filter.filter_tlog(reader, ['ATTITUDE'], None, None, 500000, False)

        # Verify that the output files were created
        assert os.path.exists(output_filename1)
        assert os.path.exists(output_filename2)

        # Clean up the output files
        os.remove(output_filename1)
        os.remove(output_filename2)


if __name__ == '__main__':
    # When run by hand, this test will create a file named 'testing/small.tlog'
    TestTools().test_tlog_filter()
    TestTools().test_tlog_combine_segments()
