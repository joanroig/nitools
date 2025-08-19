
import os
import sys


def get_bundled_path(filename: str):
    '''
    If executed from a bundled app (i.e. an exe file), return the path to the bundled file
    '''
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    else:
        return filename
