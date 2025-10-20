# File Name: sql_tdms_reader.py
# Project Name: dataprocess
# Description: 读取TDMS文件并直接存储到SQLite数据库中
import numpy as np
from nptdms import TdmsFile
import os
import pandas as pd
from datetime import datetime, timedelta
import re
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import yaml
from pathlib import Path
import logging
from src.core.database import DatabaseManager
import sys

logger = logging.getLogger('data_process')

def load_config():
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"配置文件加载成功: {config_path}")
    return config

def get_or_create_experiment(db_manager, folder_path):
    """获取或创建实验组记录"""
    try:
        experiment_name = os.path.basename(folder_path)
        
        # 检查实验组是否已存在
        db_manager.cursor.execute(
            "SELECT experiment_id FROM experiments WHERE folder_path = ?", 
            (folder_path,)
        )
        result = db_manager.cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # 创建新实验组
            db_manager.cursor.execute(
                "INSERT INTO experiments (experiment_name, folder_path) VALUES (?, ?)",
                (experiment_name, folder_path)
            )
            experiment_id = db_manager.cursor.lastrowid
            logger.info(f"创建实验组: {experiment_name} (ID: {experiment_id})")
            return experiment_id
            
    except Exception as e:
        logger.error(f"获取/创建实验组时出错: {str(e)}")
        raise

def check_file_exists(db_manager, experiment_id, filename):
    """检查文件是否已存在于数据库中"""
    try:
        db_manager.cursor.execute(
            "SELECT file_id FROM tdms_files WHERE experiment_id = ? AND filename = ?",
            (experiment_id, filename)
        )
        return db_manager.cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"检查文件存在性时出错: {str(e)}")
        return False

def insert_tdms_file_metadata(db_manager, experiment_id, tdms_path, start_timestamp, 
                             channel_count, data_points, sampling_rate=500000):
    """插入TDMS文件元数据"""
    try:
        filename = os.path.basename(tdms_path)
        file_size = os.path.getsize(tdms_path)
        
        db_manager.cursor.execute(
            """INSERT INTO tdms_files 
               (experiment_id, filename, start_timestamp, file_size, 
                channel_count, data_points, sampling_rate, file_path) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (experiment_id, filename, start_timestamp, file_size,
             channel_count, data_points, sampling_rate, tdms_path)
        )
        file_id = db_manager.cursor.lastrowid
        logger.info(f"插入文件: {filename} (ID: {file_id})")
        return file_id
    except Exception as e:
        logger.error(f"插入文件元数据时出错: {str(e)}")
        raise

def insert_time_domain_data_batch(db_manager, file_id, data_batch):
    """批量插入时域数据"""
    try:
        columns = ["file_id", "time_index", "timestamp"] + [f"channel{i+1}" for i in range(16)]
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO time_domain_data ({', '.join(columns)}) VALUES ({placeholders})"
        
        db_manager.cursor.executemany(sql, data_batch)
        
    except Exception as e:
        logger.error(f"批量插入时域数据时出错: {str(e)}")
        raise

def process_tdms_file(args):
    """处理单个TDMS文件并存储到数据库（适配并行处理）"""
    tdms_path, db_path, raw_data_dir = args
    db_manager = None
    try:
        logger.info(f"处理文件: {os.path.basename(tdms_path)}")
        
        # 连接到数据库
        db_manager = DatabaseManager(db_path)
        if not db_manager.connect():
            logger.error(f"无法连接到数据库: {db_path}")
            return False
        
        # 从文件名提取起始时间
        filename = os.path.basename(tdms_path)
        time_str = re.search(r'(\d{8}\d{6}\.\d+)', filename)
        if not time_str:
            logger.warning(f"文件名 {filename} 中未找到有效时间戳")
            return False
            
        start_time_str = time_str.group(1)
        start_time = datetime.strptime(start_time_str, "%Y%m%d%H%M%S.%f")
        
        # 获取实验组信息
        folder_path = os.path.dirname(tdms_path)
        experiment_id = get_or_create_experiment(db_manager, folder_path)
        
        # 检查文件是否已存在
        if check_file_exists(db_manager, experiment_id, filename):
            logger.info(f"文件已存在，跳过: {filename}")
            return True
        
        # 读取TDMS文件
        tdms_file = TdmsFile.read(tdms_path)
        
        # 获取所有组和通道
        groups = tdms_file.groups()
        if not groups:
            logger.warning(f"文件 {filename} 中没有找到任何组")
            return False
            
        group = groups[0]
        channels = [ch for ch in group.channels()]
        
        if not channels:
            logger.warning(f"组 {group.name} 中没有找到任何通道")
            return False
            
        # 确定数据长度和通道数
        data_length = len(channels[0])
        num_channels = len(channels)
        
        logger.info(f"文件 {filename}: {data_length}行, {num_channels}通道")
        
        # 插入文件元数据
        file_id = insert_tdms_file_metadata(
            db_manager, experiment_id, tdms_path, start_time_str,
            num_channels, data_length
        )
        
        # 创建时间序列
        time_interval = timedelta(microseconds=2)
        
        # 批量处理数据
        batch_size = 10000
        total_batches = (data_length + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, data_length)
            
            batch_data = []
            for i in range(start_idx, end_idx):
                current_time = start_time + i * time_interval
                time_str = current_time.strftime("%Y%m%d%H%M%S.%f")
                if len(time_str.split('.')[1]) < 6:
                    time_str = time_str.ljust(21, '0')
                
                row_data = [file_id, i, time_str]
                
                for j in range(16):
                    if j < num_channels:
                        row_data.append(float(channels[j][i]))
                    else:
                        row_data.append(None)
                
                batch_data.append(tuple(row_data))
            
            insert_time_domain_data_batch(db_manager, file_id, batch_data)
            
            if batch_num % 10 == 0:
                db_manager.connection.commit()
                logger.info(f"  {filename}: 已处理 {end_idx}/{data_length}")
        
        db_manager.connection.commit()
        logger.info(f"完成: {filename} -> 数据库 (ID: {file_id})")
        return True
        
    except Exception as e:
        logger.error(f"处理文件 {os.path.basename(tdms_path)} 时出错: {str(e)}")
        if db_manager and db_manager.connection:
            db_manager.connection.rollback()
        return False
    finally:
        if db_manager:
            db_manager.disconnect()

def process_tdms_files_parallel(tdms_files, db_path, raw_data_dir):
    """并行处理TDMS文件"""
    max_workers = multiprocessing.cpu_count()
    logger.info(f"使用 {max_workers} 个进程并行处理 {len(tdms_files)} 个文件")
    
    # 准备参数
    params = [(tdms_file, db_path, raw_data_dir) for tdms_file in tdms_files]
    
    success_count = 0
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_tdms_file, params)
        success_count = sum(results)
    
    logger.info(f"处理完成: {success_count}/{len(tdms_files)} 个文件成功")
    return success_count

def main():
    config = load_config()
    if not config:
        logger.warning("使用默认路径")
        config = {
            "raw_data_dir": "D:/Lab/test/2025.7.22",
            "database_path": "D:/Lab/results/data/lab_data.db"
        }
    
    data_folder = config["raw_data_dir"]
    db_path = config["database_path"]
    
    logger.info(f"数据目录: {data_folder}")
    logger.info(f"数据库: {db_path}")
    
    # 查找TDMS文件
    tdms_files = []
    for root, dirs, files in os.walk(data_folder):
        for file in files:
            if file.endswith('.tdms'):
                tdms_files.append(os.path.join(root, file))
    
    if not tdms_files:
        logger.warning("未找到TDMS文件")
        return
    
    logger.info(f"找到 {len(tdms_files)} 个TDMS文件")
    
    success_count = process_tdms_files_parallel(tdms_files, db_path, data_folder)
    db_manager.get_database_info()
    
    db_manager = DatabaseManager(db_path)
    if db_manager.connect():
        db_info = db_manager.get_database_info()
        logger.info(f"最终统计:")
        logger.info(f"  文件数: {db_info.get('tdms_files_count', 0)}")
        logger.info(f"  数据记录: {db_info.get('time_domain_data_count', 0)}")
        logger.info(f"  数据库大小: {db_manager._format_file_size(db_info.get('database_size', 0))}")
        db_manager.disconnect()
    
    logger.info(f"处理完成: {success_count}/{len(tdms_files)} 个文件成功")

if __name__ == "__main__":
    main()