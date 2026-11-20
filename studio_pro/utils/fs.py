import os, subprocess, sys
def open_dir(path):
    if sys.platform == "win32": os.startfile(path)
    elif sys.platform == "darwin": subprocess.run(["open", path], check=False)
    else: subprocess.run(["xdg-open", path], check=False)
