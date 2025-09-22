#====================================================================
# File Name: logging_utils.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 日志配置工具
#====================================================================

#!/usr/bin/env python3

import logging
import logging.config
import yaml
import os
from datetime import datetime

def setup_logging(default_path='config/logging.yaml', default_level=logging.INFO):
    """
    设置日志配置
    
    Args:
        default_path: 日志配置文件路径
        default_level: 默认日志级别
    """
    # 确保日志目录存在
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 尝试从YAML文件加载日志配置
    config_path = default_path
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 动态设置日志文件名包含日期
            for handler_name, handler_config in config.get('handlers', {}).items():
                if 'filename' in handler_config:
                    # 在文件名中插入日期
                    base, ext = os.path.splitext(handler_config['filename'])
                    dated_filename = f"{base}_{datetime.now().strftime('%Y%m%d')}{ext}"
                    handler_config['filename'] = os.path.join(log_dir, dated_filename)
            
            logging.config.dictConfig(config)
        except Exception as e:
            print(f"加载日志配置文件失败: {e}")
            logging.basicConfig(level=default_level)
    else:
        # 使用默认配置
        logging.basicConfig(
            level=default_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')),
                logging.StreamHandler()
            ]
        )
    
    return logging.getLogger(__name__)