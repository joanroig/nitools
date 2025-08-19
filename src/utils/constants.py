import os

from appdirs import user_data_dir

from utils.bundle_utils import get_bundled_path


def get_data_dir():
    '''Get the data directory, cross-platform compatible'''
    data_dir = user_data_dir("NITools", False)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_dir(dir_name):
    '''Get directory'''
    dir_path = os.path.join(get_data_dir(), dir_name)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path

def get_file(file_name):
    '''Get file'''
    dir_path = get_data_dir()
    return os.path.join(dir_path, file_name)


CONFIG_FILE = get_file("config.json")
LOGS_PATH = get_dir("logs")
