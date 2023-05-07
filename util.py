import glob
import os


def expand_path(paths: list[str], recurse: bool, ext: str | list[str]) -> set[str]:
    files = set()

    if ext is str:
        ext = [ext]

    for path in paths:
        if os.path.isfile(path):
            _, file_ext = os.path.splitext(os.path.basename(path))
            if file_ext in ext:
                files.add(path)
        else:
            if recurse:
                paths += glob.glob(path + '/*')

    return files
