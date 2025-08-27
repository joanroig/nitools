import platform
import subprocess


def open_path(path):
    """
    Helper to open a given path using the appropriate system command.
    """
    if not path:
        return
    path = path.strip()
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", path], shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            # Fallback for Linux/other Unix-like systems
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Failed to open path: {path}. Error: {e}")
