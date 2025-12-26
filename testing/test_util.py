
import util
import pytest

class TestUtil:

    def test_filter_blueos_tlog_paths(self):
        paths = [
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00093-2025-09-26_17-29-52.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00090-2025-09-11_21-23-28.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00000047.BIN',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00000049.BIN',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00097-2025-09-26_18-34-27.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00000050.BIN',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/transects',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/transects/2025_09_26_satellite_island_T2.csv',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/transects/2025_09_26_satellite_island_T1.csv',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00095-2025-09-26_18-11-16.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00091-2025-09-26_17-22-01.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00000048.BIN',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00000051.BIN'
        ]
        
        result = util.filter_blueos_tlog_paths(paths)
        
        expected = [
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00090-2025-09-11_21-23-28.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00091-2025-09-26_17-22-01.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00093-2025-09-26_17-29-52.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00095-2025-09-26_18-11-16.tlog',
            '2025_09_26_sj/Lutris_ardupilot_logs_pt1/00097-2025-09-26_18-34-27.tlog',
        ]
        
        assert result == expected        

    def test_filter_qgc_tlog_paths(self):
        paths = [
            '2023_04_18_surftrak3/00000016.BIN',
            '2023_04_18_surftrak3/2023-04-18 10-58-13.tlog',
            '2023_04_18_surftrak3/20230418-110542666.bin',
            '2023_04_18_surftrak3/2023-04-18 11-15-35 vehicle1.csv',
            '2023_04_18_surftrak3/2023-04-18 11-12-09.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-00-52.tlog',
            '2023_04_18_surftrak3/2023-04-18 10-07-08.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-19-46.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-22-27.tlog',
            '2023_04_18_surftrak3/2023-04-18 08-52-56 vehicle1.csv',
            '2023_04_18_surftrak3/20230418-110646909.bin',
            '2023_04_18_surftrak3/00000012.BIN',
            '2023_04_18_surftrak3/2023-04-18 11-28-50 vehicle1.csv',
            '2023_04_18_surftrak3/2023-04-18 11-08-53.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-09-39 vehicle1.csv',
            '2023_04_18_surftrak3/00000015.BIN',
            '2023_04_18_surftrak3/2023-04-18 10-15-35 vehicle1.csv',
            '2023_04_18_surftrak3/20230418-110925839.bin',
            '2023_04_18_surftrak3/2023-04-18 09-03-16.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-18-33 vehicle1.csv',
            '2023_04_18_surftrak3/2023-04-18 09-02-30 vehicle1.csv',
            '2023_04_18_surftrak3/2023-04-18 11-03-34.tlog',
            '2023_04_18_surftrak3/00000013.BIN',
            '2023_04_18_surftrak3/00000014.BIN',
            '2023_04_18_surftrak3/20230418-113444299.bin',
            '2023_04_18_surftrak3/2023-04-18 09-37-11.tlog',
            '2023_04_18_surftrak3/20230418-110925677.bin',
        ]
        
        result = util.filter_qgc_tlog_paths(paths)
        
        expected = [
            '2023_04_18_surftrak3/2023-04-18 09-00-52.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-03-16.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-19-46.tlog',
            '2023_04_18_surftrak3/2023-04-18 09-37-11.tlog',
            '2023_04_18_surftrak3/2023-04-18 10-07-08.tlog',
            '2023_04_18_surftrak3/2023-04-18 10-58-13.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-03-34.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-08-53.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-12-09.tlog',
            '2023_04_18_surftrak3/2023-04-18 11-22-27.tlog',
        ]
        
        assert result == expected
