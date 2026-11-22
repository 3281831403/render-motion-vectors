"""把仓库根加入 sys.path，保证直接运行 pytest 时能导入 motionvec。"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
