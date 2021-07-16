import sys
assert 'dlb' not in sys.modules, repr(sys.modules)

import dlb
import dlb.fake

assert dlb.__version__ == 'fake', repr(dlb.__version__)
dlb.fake.inform()
