# -*- coding: utf-8 -*-
"""
信号处理与可视化工具 - 启动入口
"""
import sys
import os

# 将当前目录添加到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == '__main__':
    main()
