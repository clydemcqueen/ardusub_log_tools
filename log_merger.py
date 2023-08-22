import pandas as pd

import util


class LogMerger:
    def __init__(self,
                 infile: str,
                 max_msgs: int,
                 max_rows: int,
                 verbose: bool):
        self.infile = infile
        self.max_msgs = max_msgs
        self.max_rows = max_rows
        self.verbose = verbose
        self.tables = {}

    def write_msg_csv_files(self):
        print('Writing csv files')
        for table_name in self.tables:
            df = self.tables[table_name].get_dataframe(self.verbose)
            if len(df):
                filename = util.get_outfile_name(self.infile, suffix=f'_{table_name}')
                print(f'Writing {len(df)} rows to {filename}')
                df.to_csv(filename)

    def write_merged_csv_file(self):
        merged_df = None
        print(f'Merging dataframes')
        for table_name in self.tables:
            df = self.tables[table_name].get_dataframe(self.verbose)
            if df.empty:
                if self.verbose:
                    print(f'{table_name} empty, skipping')
            else:
                if merged_df is None:
                    if self.verbose:
                        print(f'Starting with {len(df)} {table_name} rows')
                    merged_df = df
                else:
                    if self.verbose:
                        print(f'Merging {len(df)} {table_name} rows')
                    merged_df = pd.merge_ordered(merged_df, df, on='timestamp', fill_method='ffill')
                    if self.verbose:
                        print(f'Merged dataframe has {len(merged_df)} rows')
                    if len(merged_df) > self.max_rows:
                        print('Merged dataframe is too big, stopping')
                        break

        if merged_df is None:
            print(f'Nothing to write')
        else:
            filename = util.get_outfile_name(self.infile)
            print(f'Writing {len(merged_df)} rows to {filename}')
            merged_df.to_csv(filename)
