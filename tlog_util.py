import glob
import os


def expand_path(paths: list[str], recurse: bool) -> set[str]:
    files = set()

    for path in paths:
        if os.path.isfile(path):
            file_name, file_ext = os.path.splitext(path)
            if file_ext == '.tlog':
                files.add(path)
        else:
            if recurse:
                paths += glob.glob(path + '/*')

    return files
