import numpy as np
from scipy.fft import fft, fftfreq
import pandas as pd
import os

class FrequencyDomainAnalyzer:
    """频域分析器"""
    
    def __init__(self, config):
        self.config = config
        self.sampling_frequency = config.get('sampling_frequency', 200000)
        self.threshold_ratio = config['fft'].get('threshold_ratio', 0.2)
        self.top_points = config['fft'].get('top_points', 20)
    
    def analyze(self, data):
        """
        执行频域分析
        
        Args:
            data: 时域数据字典
            
        Returns:
            dict: 频域分析结果
        """
        results = {}
        
        for folder_name, channel_data in data.items():
            results[folder_name] = {}
            
            for channel_name, signal in channel_data.items():
                # 执行FFT
                spectrum = fft(signal)
                
                if self.config['fft'].get('remove_dc', True):
                    spectrum[0] = 0  # 去除直流分量
                
                magnitude = np.abs(spectrum)
                n_points = len(signal)
                frequencies = fftfreq(n_points, d=1/self.sampling_frequency)
                
                # 处理正频率部分
                positive_freq = frequencies[:n_points//2]
                positive_mag = magnitude[:n_points//2]
                
                # 对数频率处理
                log_freq = np.log10(positive_freq + 1e-6)
                
                # 提取主要频率成分
                extracted_data = self._extract_main_components(log_freq, positive_mag)
                
                results[folder_name][channel_name] = {
                    'frequencies': positive_freq,
                    'magnitudes': positive_mag,
                    'log_frequencies': log_freq,
                    'extracted_data': extracted_data
                }
        
        return results
    
    def _extract_main_components(self, frequencies, magnitudes):
        """提取主要频率成分"""
        # 阈值筛选
        threshold = np.max(magnitudes) * self.threshold_ratio
        valid_indices = np.where(magnitudes >= threshold)[0]
        
        # 提取前N个最大点
        if valid_indices.size > 0:
            sorted_indices = valid_indices[np.argsort(-magnitudes[valid_indices])]
            top_freq = frequencies[sorted_indices[:self.top_points]]
            top_mag = magnitudes[sorted_indices[:self.top_points]]
        else:
            top_freq = np.array([])
            top_mag = np.array([])
        
        # 填充到指定数量的数据点
        top_freq = np.pad(top_freq, (0, self.top_points - len(top_freq)), constant_values=np.nan)
        top_mag = np.pad(top_mag, (0, self.top_points - len(top_mag)), constant_values=np.nan)
        
        return top_freq, top_mag
    
    def save_results(self, results, output_dir):
        """保存分析结果到Excel文件"""
        for folder_name, channel_data in results.items():
            folder_path = os.path.join(output_dir, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            for channel_name, data in channel_data.items():
                # 创建DataFrame保存提取的数据
                extracted_data = data['extracted_data']
                df = pd.DataFrame({
                    'Frequency': extracted_data[0],
                    'Magnitude': extracted_data[1]
                })
                
                # 保存到Excel
                excel_path = os.path.join(folder_path, f"{channel_name}_analysis.xlsx")
                df.to_excel(excel_path, index=False)