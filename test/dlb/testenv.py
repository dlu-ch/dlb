import sys
import os.path

here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.join(here, '../../src'))
sys.path.insert(0, os.path.join(here, '..'))
# make sure sys.path does not a relative path before you import a module inside
sys.path = [os.path.abspath(p) for p in sys.path]

from testtool import *
