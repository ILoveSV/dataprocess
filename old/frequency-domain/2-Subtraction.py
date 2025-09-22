#====================================================================
# File Name: 2-Subtraction.py
# Project Name: Data Process
# Description:
# 稳健的背景对消处理 - 使用频率匹配和保守插值技术
# 1. 使用PCHIP插值方法（保持单调性，对异常值稳健）
# 2. 采用保守的外推策略，限制外推范围并使用线性外推
# 3. 添加数据质量检查和验证步骤
# 4. 对每个通道(1-8)进行独立处理
#====================================================================
import os
import numpy as np
import pandas as pd
import shutil
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
from scipy import interpolate
import warnings
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 忽略SciPy的插值警告
warnings.filterwarnings("ignore", category=UserWarning)

# ====================== 用户设置区域 ======================
# 设置背景文件夹路径（B）
BACKGROUND_FOLDER = r"D:\Lab\Water\D6.25\back-close"

# 设置待处理文件夹路径（C）
DATA_FOLDER = r"D:\Lab\Water\D6.25\30hz-close"

# 设置输出文件夹路径（C'）
OUTPUT_FOLDER = r"D:\Lab\Water\D6.25\30hz-close-cancel"

# 设置要处理的通道数
CHANNEL_COUNT = 16

# 外推限制参数：允许在外推的最大频率范围（相对于数据范围的倍数）
EXTRAPOLATION_LIMIT = 0.1  # 10%的范围外推限制

# 插值方法选择: 'pchip' (推荐), 'linear', 'cubic'
INTERPOLATION_METHOD = 'pchip'
# ========================================================

def create_dir(path):
    """创建目录（如果不存在）"""
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"创建目录: {path}")

def extract_file_number(filename):
    """从文件名中提取数字用于排序"""
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else 0

def robust_interpolation(x, y, method='pchip', extrapolation_limit=0.1):
    """
    创建稳健的插值函数，带有保守的外推限制
    
    参数:
    x: 已知的x值（频率）
    y: 已知的y值（幅度）
    method: 插值方法 ('pchip', 'linear', 'cubic')
    extrapolation_limit: 外推限制（相对于数据范围的倍数）
    
    返回:
    插值函数和有效范围
    """
    # 检查输入数据有效性
    if len(x) < 2:
        logger.warning("插值数据点不足，无法创建有意义的插值函数")
        return None, (min(x), max(x)) if len(x) > 0 else (0, 0)
    
    # 确保数据已排序且唯一
    sorted_indices = np.argsort(x)
    x_sorted = x[sorted_indices]
    y_sorted = y[sorted_indices]
    
    # 移除重复的x值（取平均值）
    x_unique, indices = np.unique(x_sorted, return_index=True)
    if len(x_unique) < len(x_sorted):
        logger.info(f"移除 {len(x_sorted) - len(x_unique)} 个重复频率点")
        # 对重复的x值，计算y的平均值
        y_unique = np.zeros_like(x_unique)
        for i, val in enumerate(x_unique):
            y_unique[i] = np.mean(y_sorted[x_sorted == val])
        x_sorted, y_sorted = x_unique, y_unique
    
    # 确定数据范围和外推限制
    x_min, x_max = np.min(x_sorted), np.max(x_sorted)
    x_range = x_max - x_min
    extrap_min = x_min - extrapolation_limit * x_range
    extrap_max = x_max + extrapolation_limit * x_range
    
    logger.info(f"数据频率范围: [{x_min:.2f}, {x_max:.2f}], 允许外推范围: [{extrap_min:.2f}, {extrap_max:.2f}]")
    
    try:
        # 根据选择的插值方法创建插值函数
        if method == 'pchip' and len(x_sorted) >= 3:
            # PCHIP插值：保持单调性，对异常值稳健
            interp_func = interpolate.PchipInterpolator(x_sorted, y_sorted, extrapolate=False)
            logger.info("使用PCHIP插值方法")
        elif method == 'cubic' and len(x_sorted) >= 4:
            # 三次样条插值
            interp_func = interpolate.CubicSpline(x_sorted, y_sorted, extrapolate=False)
            logger.info("使用三次样条插值方法")
        else:
            # 线性插值（回退方法）
            interp_func = interpolate.interp1d(x_sorted, y_sorted, kind='linear', 
                                              bounds_error=False, fill_value=np.nan)
            logger.info("使用线性插值方法")
        
        # 创建包装函数，处理外推和边界情况
        def safe_interpolate(x_query):
            # 初始化结果数组
            result = np.full_like(x_query, np.nan, dtype=float)
            
            # 区分内插和外推点
            inside_mask = (x_query >= x_min) & (x_query <= x_max)
            extrap_low_mask = (x_query >= extrap_min) & (x_query < x_min)
            extrap_high_mask = (x_query > x_max) & (x_query <= extrap_max)
            
            # 内插点：使用选择的插值方法
            if np.any(inside_mask):
                result[inside_mask] = interp_func(x_query[inside_mask])
            
            # 外推点：使用保守的线性外推
            if np.any(extrap_low_mask):
                # 使用最低两个点进行线性外推
                if len(x_sorted) >= 2:
                    slope = (y_sorted[1] - y_sorted[0]) / (x_sorted[1] - x_sorted[0] + 1e-10)
                    result[extrap_low_mask] = y_sorted[0] + slope * (x_query[extrap_low_mask] - x_sorted[0])
                else:
                    result[extrap_low_mask] = y_sorted[0]  # 回退到常数外推
            
            if np.any(extrap_high_mask):
                # 使用最高两个点进行线性外推
                if len(x_sorted) >= 2:
                    slope = (y_sorted[-1] - y_sorted[-2]) / (x_sorted[-1] - x_sorted[-2] + 1e-10)
                    result[extrap_high_mask] = y_sorted[-1] + slope * (x_query[extrap_high_mask] - x_sorted[-1])
                else:
                    result[extrap_high_mask] = y_sorted[-1]  # 回退到常数外推
            
            # 超出外推限制的点保持NaN
            return result
        
        return safe_interpolate, (extrap_min, extrap_max)
    
    except Exception as e:
        logger.error(f"创建插值函数时出错: {str(e)}")
        # 回退到简单的最近邻插值
        fallback_func = interpolate.interp1d(x_sorted, y_sorted, kind='nearest', 
                                           bounds_error=False, fill_value=np.nan)
        logger.warning("使用回退的最近邻插值方法")
        return fallback_func, (x_min, x_max)

def process_channel(channel_num):
    """处理单个通道的背景对消（使用稳健的频率匹配和插值）"""
    channel_name = f"通道{channel_num}"
    logger.info(f"\n{'='*50}\n开始处理通道: {channel_name}")
    
    # 1. 处理背景文件夹(B) - 收集所有背景数据点
    all_bg_freqs = []
    all_bg_mags = []
    bg_file_count = 0
    
    for root, _, files in os.walk(BACKGROUND_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                try:
                    df_bg = pd.read_excel(os.path.join(root, file))
                    bg_file_count += 1
                    
                    # 收集所有频率-幅度对
                    for i in range(0, len(df_bg.columns), 2):
                        if i+1 >= len(df_bg.columns):
                            break
                            
                        freq_col = df_bg.columns[i]
                        mag_col = df_bg.columns[i+1]
                        
                        if 'Freq' in freq_col and 'Mag' in mag_col:
                            # 提取非NaN数据
                            freqs = df_bg[freq_col].dropna().values
                            mags = df_bg[mag_col].dropna().values
                            
                            if len(freqs) > 0 and len(mags) > 0:
                                # 确保频率和幅度数量一致
                                min_len = min(len(freqs), len(mags))
                                all_bg_freqs.extend(freqs[:min_len])
                                all_bg_mags.extend(mags[:min_len])
                except Exception as e:
                    logger.error(f"读取背景文件 {file} 错误: {str(e)}")
    
    if not all_bg_freqs:
        logger.warning(f"没有找到有效的背景数据 ({channel_name})")
        return None
    
    logger.info(f"从 {bg_file_count} 个背景文件中收集到 {len(all_bg_freqs)} 个数据点")
    
    # 转换为NumPy数组
    all_bg_freqs = np.array(all_bg_freqs)
    all_bg_mags = np.array(all_bg_mags)
    
    # 检查数据质量
    valid_mask = ~(np.isnan(all_bg_freqs) | np.isnan(all_bg_mags))
    all_bg_freqs = all_bg_freqs[valid_mask]
    all_bg_mags = all_bg_mags[valid_mask]
    
    if len(all_bg_freqs) < 10:
        logger.warning(f"背景数据点较少 ({len(all_bg_freqs)})，插值结果可能不可靠")
    
    # 2. 创建稳健的背景幅度插值函数
    interp_func, valid_range = robust_interpolation(
        all_bg_freqs, all_bg_mags, 
        method=INTERPOLATION_METHOD,
        extrapolation_limit=EXTRAPOLATION_LIMIT
    )
    
    if interp_func is None:
        logger.error(f"无法为通道 {channel_name} 创建插值函数")
        return None
    
    # 3. 处理数据文件夹(C)
    data_files = []
    for root, _, files in os.walk(DATA_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                data_files.append(os.path.join(root, file))
    
    if not data_files:
        logger.warning(f"数据文件夹中没有找到 {channel_name} 的Excel文件!")
        return None
    
    # 按文件名中的数字排序
    data_files.sort(key=lambda x: extract_file_number(os.path.basename(x)))
    logger.info(f"找到 {len(data_files)} 个数据文件进行处理")
    
    # 4. 创建输出目录结构
    output_channel_dir = os.path.join(OUTPUT_FOLDER, os.path.relpath(
        os.path.dirname(data_files[0]), DATA_FOLDER))
    create_dir(output_channel_dir)
    
    # 5. 处理每个数据文件
    processed_count = 0
    for data_file in data_files:
        try:
            df_data = pd.read_excel(data_file)
            output_path = os.path.join(output_channel_dir, os.path.basename(data_file))
            
            # 复制原始数据到新DataFrame
            df_result = df_data.copy()
            
            # 处理每一对频率-幅度列
            for i in range(0, len(df_data.columns), 2):
                if i+1 >= len(df_data.columns):
                    continue
                
                freq_col = df_data.columns[i]
                mag_col = df_data.columns[i+1]
                
                if 'Freq' not in freq_col or 'Mag' not in mag_col:
                    continue
                
                # 获取频率和幅度数据
                freqs = df_data[freq_col].values
                mags = df_data[mag_col].values
                
                # 创建结果数组
                result_mags = np.full_like(mags, np.nan)
                
                # 统计超出有效范围的频率点
                out_of_range_count = 0
                total_points = 0
                
                # 对每个有效频率点进行背景对消
                for idx, (freq, mag) in enumerate(zip(freqs, mags)):
                    if np.isnan(freq) or np.isnan(mag):
                        continue
                    
                    total_points += 1
                    
                    # 检查频率是否在有效范围内
                    if freq < valid_range[0] or freq > valid_range[1]:
                        out_of_range_count += 1
                        # 超出范围的频率点，不进行对消（保持NaN）
                        continue
                    
                    # 使用插值函数获取该频率点的背景幅度
                    bg_mag = interp_func([freq])[0]
                    
                    if np.isnan(bg_mag):
                        # 插值失败，不进行对消
                        continue
                    
                    # 执行背景对消（确保结果非负）
                    result = mag - bg_mag
                    result_mags[idx] = max(0, result)  # 负值截断为0
                
                # 记录超出范围的频率点比例
                if total_points > 0 and out_of_range_count > 0:
                    out_of_range_ratio = out_of_range_count / total_points * 100
                    logger.warning(f"文件 {os.path.basename(data_file)} 列 {freq_col}: "
                                  f"{out_of_range_ratio:.1f}% 的频率点超出有效范围")
                
                # 更新结果DataFrame
                df_result[mag_col] = result_mags
            
            # 保存结果
            df_result.to_excel(output_path, index=False)
            processed_count += 1
            logger.info(f"已处理并保存: {os.path.basename(output_path)}")
            
        except Exception as e:
            logger.error(f"处理文件 {os.path.basename(data_file)} 错误: {str(e)}")
    
    logger.info(f"完成通道处理: {channel_name}, 成功处理 {processed_count}/{len(data_files)} 个文件")
    logger.info(f"{'='*50}")
    return channel_name

def main():
    """主函数"""
    print("="*60)
    print("稳健背景对消处理开始（使用频率匹配和保守插值）")
    print(f"背景文件夹: {BACKGROUND_FOLDER}")
    print(f"数据文件夹: {DATA_FOLDER}")
    print(f"输出文件夹: {OUTPUT_FOLDER}")
    print(f"插值方法: {INTERPOLATION_METHOD}")
    print(f"外推限制: {EXTRAPOLATION_LIMIT*100}%")
    print("="*60)
    
    start_time = time.time()
    
    # 创建输出目录
    create_dir(OUTPUT_FOLDER)
    
    # 使用多进程处理
    completed_channels = []
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        # 提交所有通道处理任务
        futures = [executor.submit(process_channel, i+1) for i in range(CHANNEL_COUNT)]
        
        # 处理完成的任务
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    completed_channels.append(result)
            except Exception as e:
                logger.error(f"处理过程中发生错误: {str(e)}")
    
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print(f"背景对消处理完成! 总耗时: {elapsed:.2f}秒")
    print(f"成功处理通道: {', '.join(completed_channels)}")
    print("="*60)

if __name__ == "__main__":
    main()


'''
#====================================================================
# File Name: 2-Subtraction.py
# Project Name:Data Process
# Description:
# 1. 使用频率匹配和插值技术处理背景和待处理数据的频率差异
# 2. 设置背景文件夹(B)和待处理文件夹(C)路径
# 3. 对每个通道(1-16)进行处理：
#    a. 构建背景频率-幅度的映射关系（使用所有背景数据点）
#    b. 使用线性插值创建背景幅度函数
#    c. 对每个数据点的频率值进行插值计算背景幅度
# 4. 将结果保存到新文件夹(C')
#====================================================================
import os
import numpy as np
import pandas as pd
import shutil
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
from scipy import interpolate
import warnings

# 忽略SciPy的插值警告
warnings.filterwarnings("ignore", category=UserWarning)

# ====================== 用户设置区域 ======================
# 设置背景文件夹路径（B）
BACKGROUND_FOLDER = r"D:\Lab\test\BG"

# 设置待处理文件夹路径（C）
DATA_FOLDER = r"D:\Lab\test\GROUP2"

# 设置输出文件夹路径（C'）
OUTPUT_FOLDER = r"D:\Lab\test\GROUP3"

# 设置要处理的通道数
CHANNEL_COUNT = 8
# ========================================================

def create_dir(path):
    """创建目录（如果不存在）"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")

def extract_file_number(filename):
    """从文件名中提取数字用于排序"""
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else 0

def process_channel(channel_num):
    """处理单个通道的背景对消（使用频率匹配和插值）"""
    channel_name = f"通道{channel_num}"
    print(f"\n{'='*50}\n处理通道: {channel_name}")
    
    # 1. 处理背景文件夹(B) - 收集所有背景数据点
    all_bg_freqs = []
    all_bg_mags = []
    
    for root, _, files in os.walk(BACKGROUND_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                try:
                    df_bg = pd.read_excel(os.path.join(root, file))
                    
                    # 收集所有频率-幅度对
                    for i in range(0, len(df_bg.columns), 2):
                        if i+1 >= len(df_bg.columns):
                            break
                            
                        freq_col = df_bg.columns[i]
                        mag_col = df_bg.columns[i+1]
                        
                        if 'Freq' in freq_col and 'Mag' in mag_col:
                            # 提取非NaN数据
                            freqs = df_bg[freq_col].dropna().values
                            mags = df_bg[mag_col].dropna().values
                            
                            if len(freqs) > 0 and len(mags) > 0:
                                all_bg_freqs.extend(freqs)
                                all_bg_mags.extend(mags)
                except Exception as e:
                    print(f"读取背景文件 {file} 错误: {str(e)}")
    
    if not all_bg_freqs:
        print(f"警告: 没有找到有效的背景数据 ({channel_name})")
        return None
    
    # 转换为NumPy数组
    all_bg_freqs = np.array(all_bg_freqs)
    all_bg_mags = np.array(all_bg_mags)
    
    print(f"收集到 {len(all_bg_freqs)} 个背景数据点")
    
    # 2. 创建背景幅度插值函数
    # 按频率排序
    sorted_indices = np.argsort(all_bg_freqs)
    sorted_freqs = all_bg_freqs[sorted_indices]
    sorted_mags = all_bg_mags[sorted_indices]
    
    # 创建线性插值函数
    bg_interp_func = interpolate.interp1d(
        sorted_freqs, sorted_mags, 
        kind='linear', 
        bounds_error=False,  # 允许外插
        fill_value=(sorted_mags[0], sorted_mags[-1])  # 边界外使用最近值
    )
    
    # 3. 处理数据文件夹(C)
    data_files = []
    for root, _, files in os.walk(DATA_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                data_files.append(os.path.join(root, file))
    
    if not data_files:
        print(f"警告: 数据文件夹中没有找到 {channel_name} 的Excel文件!")
        return None
    
    # 按文件名中的数字排序
    data_files.sort(key=lambda x: extract_file_number(os.path.basename(x)))
    
    # 4. 创建输出目录结构
    output_channel_dir = os.path.join(OUTPUT_FOLDER, os.path.relpath(
        os.path.dirname(data_files[0]), DATA_FOLDER))
    create_dir(output_channel_dir)
    
    # 5. 处理每个数据文件
    for data_file in data_files:
        try:
            df_data = pd.read_excel(data_file)
            output_path = os.path.join(output_channel_dir, os.path.basename(data_file))
            
            # 复制原始数据到新DataFrame
            df_result = df_data.copy()
            
            # 处理每一对频率-幅度列
            for i in range(0, len(df_data.columns), 2):
                if i+1 >= len(df_data.columns):
                    continue
                
                freq_col = df_data.columns[i]
                mag_col = df_data.columns[i+1]
                
                if 'Freq' not in freq_col or 'Mag' not in mag_col:
                    continue
                
                # 获取频率和幅度数据
                freqs = df_data[freq_col].values
                mags = df_data[mag_col].values
                
                # 创建结果数组
                result_mags = np.full_like(mags, np.nan)
                
                # 对每个有效频率点进行背景对消
                for idx, (freq, mag) in enumerate(zip(freqs, mags)):
                    if np.isnan(freq) or np.isnan(mag):
                        continue
                    
                    # 使用插值函数获取该频率点的背景幅度
                    bg_mag = bg_interp_func(freq)
                    
                    # 执行背景对消
                    result_mags[idx] = mag - bg_mag
                
                # 更新结果DataFrame
                df_result[mag_col] = result_mags
            
            # 保存结果
            df_result.to_excel(output_path, index=False)
            print(f"已保存背景对消结果: {os.path.basename(output_path)}")
            
        except Exception as e:
            print(f"处理文件 {os.path.basename(data_file)} 错误: {str(e)}")
    
    print(f"完成通道处理: {channel_name}\n{'='*50}")
    return channel_name

def main():
    """主函数"""
    print("="*60)
    print("高级背景对消处理开始（使用频率匹配和插值）")
    print(f"背景文件夹: {BACKGROUND_FOLDER}")
    print(f"数据文件夹: {DATA_FOLDER}")
    print(f"输出文件夹: {OUTPUT_FOLDER}")
    print("="*60)
    
    start_time = time.time()
    
    # 创建输出目录
    create_dir(OUTPUT_FOLDER)
    
    # 使用多进程处理
    completed_channels = []
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        # 提交所有通道处理任务
        futures = [executor.submit(process_channel, i+1) for i in range(CHANNEL_COUNT)]
        
        # 处理完成的任务
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    completed_channels.append(result)
            except Exception as e:
                print(f"处理过程中发生错误: {str(e)}")
    
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print(f"背景对消处理完成! 总耗时: {elapsed:.2f}秒")
    print(f"成功处理通道: {', '.join(completed_channels)}")
    print("="*60)

if __name__ == "__main__":
    main()

'''

'''
#====================================================================
# File Name: background_subtraction.py
# Description:
# 1. 设置背景文件夹(B)和待处理文件夹(C)路径
# 2. 对每个通道(1-16)进行处理：
#    a. 读取背景文件夹中所有Excel文件的幅度数据
#    b. 计算每个文件位置的平均背景幅度
#    c. 从待处理文件夹的幅度数据中减去对应的平均背景幅度
# 3. 将结果保存到新文件夹(C')
#====================================================================
import os
import numpy as np
import pandas as pd
import shutil
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# ====================== 用户设置区域 ======================
# 设置背景文件夹路径（B）
BACKGROUND_FOLDER = r"D:\Lab\Water\A6.21\background"

# 设置待处理文件夹路径（C）
DATA_FOLDER = r"D:\Lab\Water\A6.21\experiment_data"

# 设置输出文件夹路径（C'）
OUTPUT_FOLDER = r"D:\Lab\Water\A6.21\experiment_data_background_subtracted"

# 设置要处理的通道数
CHANNEL_COUNT = 16
# ========================================================

def create_dir(path):
    """创建目录（如果不存在）"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")

def extract_file_number(filename):
    """从文件名中提取数字用于排序"""
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else 0

def process_channel(channel_num):
    """处理单个通道的背景对消"""
    channel_name = f"通道{channel_num}"
    print(f"\n{'='*50}\n处理通道: {channel_name}")
    
    # 1. 处理背景文件夹(B)
    bg_files = []
    for root, _, files in os.walk(BACKGROUND_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                bg_files.append(os.path.join(root, file))
    
    if not bg_files:
        print(f"警告: 背景文件夹中没有找到 {channel_name} 的Excel文件!")
        return
    
    # 按文件名中的数字排序
    bg_files.sort(key=lambda x: extract_file_number(os.path.basename(x)))
    
    # 合并所有背景文件的幅度数据
    all_bg_magnitudes = []
    for bg_file in bg_files:
        try:
            df_bg = pd.read_excel(bg_file)
            mag_cols = [col for col in df_bg.columns if 'Mag' in col]
            
            for col in mag_cols:
                # 只取有效数据（忽略NaN）
                valid_data = df_bg[col].dropna().values
                if len(valid_data) > 0:
                    all_bg_magnitudes.append(valid_data)
        except Exception as e:
            print(f"读取背景文件 {os.path.basename(bg_file)} 错误: {str(e)}")
    
    if not all_bg_magnitudes:
        print(f"警告: 没有找到有效的背景幅度数据 ({channel_name})")
        return
    
    # 计算平均背景幅度
    max_length = max(len(arr) for arr in all_bg_magnitudes)
    padded_arrays = []
    
    for arr in all_bg_magnitudes:
        if len(arr) < max_length:
            # 用NaN填充不足的部分
            padded = np.pad(arr, (0, max_length - len(arr)), 
                           mode='constant', constant_values=np.nan)
            padded_arrays.append(padded)
        else:
            padded_arrays.append(arr)
    
    # 计算每个位置的平均幅度（忽略NaN）
    bg_matrix = np.vstack(padded_arrays)
    avg_bg_magnitude = np.nanmean(bg_matrix, axis=0)
    
    # 2. 处理数据文件夹(C)
    data_files = []
    for root, _, files in os.walk(DATA_FOLDER):
        for file in files:
            if file.endswith(".xlsx") and channel_name in file:
                data_files.append(os.path.join(root, file))
    
    if not data_files:
        print(f"警告: 数据文件夹中没有找到 {channel_name} 的Excel文件!")
        return
    
    # 按文件名中的数字排序
    data_files.sort(key=lambda x: extract_file_number(os.path.basename(x)))
    
    # 3. 创建输出目录结构
    output_channel_dir = os.path.join(OUTPUT_FOLDER, os.path.relpath(
        os.path.dirname(data_files[0]), DATA_FOLDER))
    create_dir(output_channel_dir)
    
    # 4. 处理每个数据文件
    for data_file in data_files:
        try:
            df_data = pd.read_excel(data_file)
            output_path = os.path.join(output_channel_dir, os.path.basename(data_file))
            
            # 复制原始数据到新DataFrame
            df_result = df_data.copy()
            
            # 获取所有幅度列
            mag_cols = [col for col in df_data.columns if 'Mag' in col]
            
            # 对每个幅度列进行背景对消
            for col in mag_cols:
                # 获取原始幅度数据
                magnitudes = df_data[col].values
                
                # 执行背景对消
                # 注意：只对有效数据部分进行对消
                valid_length = min(len(magnitudes), len(avg_bg_magnitude))
                
                # 创建新数组用于存储结果
                result_magnitudes = np.full_like(magnitudes, np.nan)
                
                # 对有效部分进行背景对消
                for i in range(valid_length):
                    if not np.isnan(magnitudes[i]):
                        # 执行背景对消：数据幅度 - 平均背景幅度
                        result_magnitudes[i] = magnitudes[i] - avg_bg_magnitude[i]
                
                # 将结果存回DataFrame
                df_result[col] = result_magnitudes
            
            # 保存结果
            df_result.to_excel(output_path, index=False)
            print(f"已保存背景对消结果: {os.path.basename(output_path)}")
            
        except Exception as e:
            print(f"处理文件 {os.path.basename(data_file)} 错误: {str(e)}")
    
    print(f"完成通道处理: {channel_name}\n{'='*50}")

def main():
    """主函数"""
    print("="*60)
    print("背景对消处理开始")
    print(f"背景文件夹: {BACKGROUND_FOLDER}")
    print(f"数据文件夹: {DATA_FOLDER}")
    print(f"输出文件夹: {OUTPUT_FOLDER}")
    print("="*60)
    
    start_time = time.time()
    
    # 创建输出目录
    create_dir(OUTPUT_FOLDER)
    
    # 使用多进程处理
    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        futures = [executor.submit(process_channel, i+1) for i in range(CHANNEL_COUNT)]
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"处理过程中发生错误: {str(e)}")
    
    
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print(f"背景对消处理完成! 总耗时: {elapsed:.2f}秒")
    print("="*60)

if __name__ == "__main__":
    import time
    main()
'''