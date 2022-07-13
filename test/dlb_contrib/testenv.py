import sys
import os.path

here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.join(here, '../../src'))
sys.path.insert(0, os.path.join(here, '..'))
sys.path = [os.path.abspath(p) for p in sys.path]

from testtool import *


def has_executable_in_path(executable: str) -> bool:
    import shutil

    p = shutil.which(executable)
    return p and os.path.basename(p) == executable
