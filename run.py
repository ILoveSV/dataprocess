#!/usr/bin/env python3
"""
水下目标电荷探测数据分析系统 - 预设运行脚本

通过编辑本文件中的 PRESETS 字典，可以创建自定义分析组合。
运行方式: python run.py [预设名称] [可选:数据目录路径]
"""

import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# 预设分析组合 - 在这里编辑和添加你的自定义预设
PRESETS = {
    # 完整分析流程
    "full": {
        "module": "all",
        "config": "config/parameters.yaml"
    },
    
    # 仅数据加载和预处理
    "preprocess": {
        "module": "preprocess",
        "config": "config/parameters.yaml"
    },
    
    # 仅时域分析
    "time": {
        "module": "time",
        "config": "config/parameters.yaml"
    },
    
    # 仅频域分析
    "freq": {
        "module": "freq",
        "config": "config/parameters.yaml"
    },
    
    # 仅可视化
    "visualize": {
        "module": "visualize",
        "config": "config/parameters.yaml"
    },
    
    # 仅生成报告
    "report": {
        "module": "report",
        "config": "config/parameters.yaml"
    },
    
    # 添加你的自定义预设...
     "load": {
         "module": "load",
         "config": "path/to/your/config.yaml"
     }
}

def run_preset(preset_name, data_folder=None):
    """运行预设的分析组合"""
    if preset_name not in PRESETS:
        print(f"错误: 预设 '{preset_name}' 不存在")
        print(f"可用预设: {list(PRESETS.keys())}")
        return False
    
    preset = PRESETS[preset_name]
    
    # 构建命令行参数
    cmd = [sys.executable, "-m", "src.main", preset["module"]]
    
    # 添加数据文件夹参数（如果提供）
    if data_folder:
        cmd.extend(["--data-folder", data_folder])
    
    # 添加配置文件参数
    cmd.extend(["--config", preset["config"]])
    
    print(f"运行预设: {preset_name}")
    print(f"命令: {' '.join(cmd)}")
    print("-" * 50)
    
    # 运行分析
    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print(f"预设 '{preset_name}' 执行完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"预设 '{preset_name}' 执行失败: {e}")
        return False

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("请指定要运行的预设名称")
        print(f"可用预设: {list(PRESETS.keys())}")
        print("使用方法: python run.py [预设名称] [可选:数据目录路径]")
        return
    
    preset_name = sys.argv[1]
    data_folder = sys.argv[2] if len(sys.argv) > 2 else None
    
    run_preset(preset_name, data_folder)

if __name__ == "__main__":
    main()