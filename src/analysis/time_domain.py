#====================================================================
# File Name: time_domain.py
# Project Name: 水下目标电荷探测数据分析系统
# Description: 时域分析模块，负责提取和分析时域特征
#               1.均值 (mean): 信号的平均值
#               2.标准差 (std): 信号波动程度
#               3.方差 (var): 信号离散程度
#               4.RMS: 信号的均方根值，反映信号功率
#               5.峰值 (peak): 信号的最大绝对值
#               6.峰峰值 (peak_to_peak): 信号最大值与最小值的差
#               7.偏度 (skewness): 信号分布的不对称性
#               8.峰度 (kurtosis): 信号分布的尖锐程度
#               9.能量 (energy): 信号的总能量
#               10.波形因子 (form_factor): RMS与平均绝对值的比值
#               11.脉冲因子 (impulse_factor): 峰值与平均绝对值的比值
#               12.裕度因子 (clearance_factor): 峰值与平均平方根值的平方的比值
#====================================================================

import pandas as pd
import numpy as np
import os
import glob
import re
import yaml
from scipy import stats
import logging
import warnings
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# 设置日志
logger = logging.getLogger(__name__)

class TimeDomainAnalyzer:
    def __init__(self, config_path='config/parameters.yaml'):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 加载路径配置
        paths_config_path = 'config/paths.yaml'
        with open(paths_config_path, 'r', encoding='utf-8') as f:
            self.paths_config = yaml.safe_load(f)
        
        # 从配置中获取参数
        self.time_channels = self.config.get('time_channels', 16)
        self.time_sampling_rate = self.config.get('time_sampling_rate', 500000)  # 默认500kHz
        self.time_window_size = self.config.get('time_window_size', 1000)  # 分析窗口大小
        self.n_workers = self.config.get('n_workers', max(1, cpu_count() - 1))  # 并行工作进程数
        
        # 从路径配置中获取输入输出路径
        self.input_dir = self.paths_config.get('tdms_reader_time_output_dir')
        self.output_dir = self.paths_config.get('time_output_dir')
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.results = {}
        logger.info("时域分析模块初始化完成")
        
    def natural_sort(self, l):
        """自然排序函数，确保文件按数字顺序排列"""
        convert = lambda text: int(text) if text.isdigit() else text.lower()
        alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
        return sorted(l, key=alphanum_key)
    
    def extract_time_domain_features(self, data):
        """提取时域特征"""
        features = {}
        
        # 基本统计特征
        features['mean'] = np.mean(data)
        features['std'] = np.std(data)
        features['var'] = np.var(data)
        features['rms'] = np.sqrt(np.mean(data**2))
        features['peak'] = np.max(np.abs(data))
        features['peak_to_peak'] = np.ptp(data)
        
        # 高阶统计特征
        features['skewness'] = stats.skew(data)
        features['kurtosis'] = stats.kurtosis(data)
        
        # 能量相关特征
        features['energy'] = np.sum(data**2)
        
        # 波形因子和脉冲因子
        mean_abs = np.mean(np.abs(data))
        features['form_factor'] = features['rms'] / (mean_abs + 1e-10)
        features['impulse_factor'] = features['peak'] / (mean_abs + 1e-10)
        
        # 裕度因子
        features['clearance_factor'] = features['peak'] / (np.mean(np.sqrt(np.abs(data)))**2 + 1e-10)
        
        return features
    
    def process_single_file(self, file_info):
        """处理单个文件 - 用于并行处理"""
        file_path, channels = file_info
        try:
            df = pd.read_csv(file_path)
            file_features = {}
            
            for ch in range(1, channels + 1):
                col_name = f'channel{ch}'
                if col_name in df.columns:
                    data = df[col_name].values
                    features = self.extract_time_domain_features(data)
                    file_features[f'channel_{ch}'] = features
            
            return file_features
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
            return {}
    
    def analyze_folder(self, folder_path):
        """分析单个文件夹中的所有CSV文件"""
        # 获取文件夹中的所有CSV文件
        csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
        csv_files = self.natural_sort(csv_files)
        
        if not csv_files:
            logger.warning(f"在文件夹 {folder_path} 中未找到CSV文件")
            return None
        
        logger.info(f"处理文件夹: {os.path.basename(folder_path)}，找到 {len(csv_files)} 个CSV文件")
        
        # 准备并行处理参数
        file_infos = [(file_path, self.time_channels) for file_path in csv_files]
        
        # 使用多进程并行处理文件
        folder_features = {}
        for ch in range(1, self.time_channels + 1):
            folder_features[f'channel_{ch}'] = {
                'mean': [], 'std': [], 'var': [], 'rms': [], 'peak': [], 
                'peak_to_peak': [], 'skewness': [], 'kurtosis': [], 
                'energy': [], 'form_factor': [], 'impulse_factor': [], 
                'clearance_factor': []
            }
        
        # 使用进程池并行处理
        with Pool(processes=self.n_workers) as pool:
            results = list(tqdm(
                pool.imap(self.process_single_file, file_infos),
                total=len(file_infos),
                desc="并行处理CSV文件"
            ))
        
        # 汇总所有文件的结果
        for file_result in results:
            for ch in range(1, self.time_channels + 1):
                ch_key = f'channel_{ch}'
                if ch_key in file_result:
                    for feature_name, value in file_result[ch_key].items():
                        folder_features[ch_key][feature_name].append(value)
        
        # 计算每个通道在所有文件上的统计量
        channel_stats = {}
        for ch in range(1, self.time_channels + 1):
            ch_key = f'channel_{ch}'
            ch_stats = {}
            
            for feature_name, values in folder_features[ch_key].items():
                if values:  # 确保列表不为空
                    ch_stats[f'{feature_name}_mean'] = np.mean(values)
                    ch_stats[f'{feature_name}_std'] = np.std(values)
                    ch_stats[f'{feature_name}_min'] = np.min(values)
                    ch_stats[f'{feature_name}_max'] = np.max(values)
                    ch_stats[f'{feature_name}_median'] = np.median(values)
                else:
                    ch_stats[f'{feature_name}_mean'] = np.nan
                    ch_stats[f'{feature_name}_std'] = np.nan
                    ch_stats[f'{feature_name}_min'] = np.nan
                    ch_stats[f'{feature_name}_max'] = np.nan
                    ch_stats[f'{feature_name}_median'] = np.nan
            
            channel_stats[ch_key] = ch_stats
        
        return channel_stats
    
    def save_folder_results(self, folder_name, folder_results):
        """保存单个文件夹的分析结果到CSV文件"""
        if not folder_results:
            logger.warning(f"文件夹 {folder_name} 没有可保存的结果")
            return None
        
        # 创建结果DataFrame
        all_data = []
        
        for ch_name, features in folder_results.items():
            row_data = {'channel': ch_name}
            row_data.update(features)
            all_data.append(row_data)
        
        results_df = pd.DataFrame(all_data)
        
        # 生成输出文件路径
        output_path = os.path.join(self.output_dir, f"time_feature_{folder_name}.csv")
        results_df.to_csv(output_path, index=False)
        logger.info(f"时域分析结果已保存到: {output_path}")
        
        return results_df
    
    def analyze_all_folders(self):
        """分析主文件夹下的所有子文件夹"""
        # 获取所有子文件夹
        subfolders = [f.path for f in os.scandir(self.input_dir) if f.is_dir()]
        
        if not subfolders:
            logger.warning(f"在路径 {self.input_dir} 下未找到子文件夹")
            return
        
        logger.info(f"找到 {len(subfolders)} 个子文件夹")
        
        # 分析每个子文件夹
        for folder_path in subfolders:
            folder_name = os.path.basename(folder_path)
            logger.info(f"开始分析文件夹: {folder_name}")
            
            # 分析文件夹
            folder_results = self.analyze_folder(folder_path)
            
            if folder_results:
                # 保存当前文件夹的结果
                self.save_folder_results(folder_name, folder_results)
                self.results[folder_name] = folder_results
        
        return self.results

def main():
    """
    时域分析主函数，供外部模块调用
    """
    try:
        logger.info("开始时域分析")
        
        # 创建分析器实例
        analyzer = TimeDomainAnalyzer()
        
        # 分析所有文件夹
        results = analyzer.analyze_all_folders()
        
        if not results:
            logger.error("时域分析未得到任何结果")
            return False
        
        logger.info("时域分析完成")
        return True
        
    except Exception as e:
        logger.exception(f"时域分析过程中发生错误: {e}")
        return False

# 模块直接运行时执行的代码
if __name__ == "__main__":
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 直接运行模块
    success = main()
    
    if success:
        print("时域分析完成")
    else:
        print("时域分析失败")
        exit(1)