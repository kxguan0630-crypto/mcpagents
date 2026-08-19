"""pytest 测试环境初始化。

mcp-clients-v2 是一个可独立运行的子项目，而仓库根目录不是 Python 包安装根。
把子项目目录加入 sys.path 后，pytest 才能稳定导入 agent、config 等本地模块。
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
