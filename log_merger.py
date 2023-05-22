import os

import pandas as pd


class LogMerger:
    def __init__(self,
                 infile: str,
                 msg_types: list[str],
                 max_msgs: int,
                 max_rows: int,
                 verbose: bool):
        self.infile = infile
        self.prefix = infile.split('.')[0]
        self.msg_types = msg_types
        self.max_msgs = max_msgs
        self.max_rows = max_rows
        self.verbose = verbose
        self.tables = None

    def outfile(self, suffix: str = '', ext: str = '.csv'):
        dirname, basename = os.path.split(self.infile)
        root, _ = os.path.splitext(basename)
        return os.path.join(dirname, root + suffix + ext)

    def write_msg_csv_files(self):
        print('Writing csv files')
        for msg_type in self.msg_types:
            df = self.tables[msg_type].get_dataframe(self.verbose)
            if len(df):
                filename = self.outfile(suffix=f'_{msg_type}')
                print(f'Writing {len(df)} rows to {filename}')
                df.to_csv(filename)

    def write_merged_csv_file(self):
        merged_df = None
        print(f'Merging dataframes')
        for msg_type in self.msg_types:
            df = self.tables[msg_type].get_dataframe(self.verbose)
            if df.empty:
                if self.verbose:
                    print(f'{msg_type} empty, skipping')
            else:
                if merged_df is None:
                    if self.verbose:
                        print(f'Starting with {len(df)} {msg_type} rows')
                    merged_df = df
                else:
                    if self.verbose:
                        print(f'Merging {len(df)} {msg_type} rows')
                    merged_df = pd.merge_ordered(merged_df, df, on='timestamp', fill_method='ffill')
                    if self.verbose:
                        print(f'Merged dataframe has {len(merged_df)} rows')
                    if len(merged_df) > self.max_rows:
                        print('Merged dataframe is too big, stopping')
                        break

        if merged_df is None:
            print(f'Nothing to write')
        else:
            filename = self.outfile()
            print(f'Writing {len(merged_df)} rows to {filename}')
            merged_df.to_csv(filename)
