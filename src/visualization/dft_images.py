import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb
from PIL import Image, ImageDraw, ImageFont

class DFTImageGenerator:
    """DFT图像生成器"""
    
    def __init__(self, config):
        self.config = config
        self.dpi = config['visualization'].get('dpi', 300)
        self.color_map = config['visualization'].get('color_map', 'hsv')
    
    def generate_images(self, freq_results):
        """生成DFT图像"""
        for folder_name, channel_data in freq_results.items():
            for channel_name, data in channel_data.items():
                extracted_data = data['extracted_data']
                
                # 创建HSV色彩映射图像
                self._create_hsv_image(
                    extracted_data[0],  # 频率
                    extracted_data[1],  # 幅度
                    folder_name,
                    channel_name
                )
    
    def _create_hsv_image(self, frequencies, magnitudes, folder_name, channel_name):
        """创建HSV色彩映射图像"""
        # 归一化处理
        norm_freq = (frequencies - np.nanmin(frequencies)) / (np.nanmax(frequencies) - np.nanmin(frequencies) + 1e-10)
        norm_mag = (magnitudes - np.nanmin(magnitudes)) / (np.nanmax(magnitudes) - np.nanmin(magnitudes) + 1e-10)
        
        # 创建HSV数组
        h = norm_freq
        s = np.ones_like(h)
        v = norm_mag
        
        # 转换为RGB
        hsv_array = np.stack([h, s, v], axis=-1)
        rgb_image = np.zeros_like(hsv_array)
        
        for i in range(len(h)):
            if not np.isnan(h[i]):
                rgb_image[i] = hsv_to_rgb(hsv_array[i])
        
        # 转换为0-255整数
        rgb_image = (rgb_image * 255).astype(np.uint8)
        
        # 创建图像
        plt.figure(figsize=(5, 1))
        plt.imshow(rgb_image.reshape(1, -1, 3), aspect='auto')
        plt.axis('off')
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        # 保存图像
        output_dir = os.path.join('results', 'images', folder_name)
        os.makedirs(output_dir, exist_ok=True)
        
        img_path = os.path.join(output_dir, f"{channel_name}_dft.png")
        plt.savefig(img_path, bbox_inches='tight', pad_inches=0, dpi=self.dpi)
        plt.close()
        
        return img_path