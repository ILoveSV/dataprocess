# -*- coding: utf-8 -*-
"""
测试通道敏感性分析功能
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from file_reader import load_data, get_file_info
from signal_processing import get_spectrum, compute_time_similarity_batch, BACKGROUND_SUBTRACTION_METHODS, subtract_background

# 测试数据路径
TEST_DATA_DIR = r"Z:\TC1-DC-A-2m-110-0-0625"

def find_tdms_files(base_dir):
    """查找TDMS文件"""
    tdms_files = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.tdms'):
                tdms_files.append(os.path.join(root, f))
    return tdms_files

def test_tdms_reading():
    """测试TDMS文件读取"""
    print("=" * 60)
    print("测试TDMS文件读取")
    print("=" * 60)
    
    tdms_files = find_tdms_files(TEST_DATA_DIR)
    print(f"找到 {len(tdms_files)} 个TDMS文件")
    
    if len(tdms_files) == 0:
        print("未找到TDMS文件，测试终止")
        return None, None
    
    # 测试前两个文件
    files_to_test = tdms_files[:2]
    
    data_list = []
    meta_list = []
    
    for i, filepath in enumerate(files_to_test):
        print(f"\n--- 测试文件 {i+1}: {os.path.basename(filepath)} ---")
        try:
            data, fs, meta = load_data(filepath)
            info = get_file_info(filepath)
            print(f"  数据形状: {data.shape}")
            print(f"  采样率: {fs} Hz")
            print(f"  通道数: {info['channels']}")
            print(f"  采样点数: {info['samples']}")
            print(f"  时长: {info['duration']:.2f} s")
            print(f"  数据类型: {info['dtype']}")
            print(f"  元数据: {meta}")
            
            data_list.append(data)
            meta_list.append(meta)
            meta_list[-1]['fs'] = fs
            
        except Exception as e:
            print(f"  读取失败: {e}")
    
    return data_list, meta_list

def test_basic_sensitivity():
    """测试基础响应敏感性分析"""
    print("\n" + "=" * 60)
    print("测试基础响应敏感性分析")
    print("=" * 60)
    
    tdms_files = find_tdms_files(TEST_DATA_DIR)
    if len(tdms_files) < 2:
        print("需要至少2个TDMS文件")
        return
    
    # 选择两个文件作为实验组和背景组
    exp_file = tdms_files[0]
    bg_file = tdms_files[1]
    
    print(f"\n实验组: {os.path.basename(exp_file)}")
    print(f"背景组: {os.path.basename(bg_file)}")
    
    try:
        exp_data, exp_fs, exp_meta = load_data(exp_file)
        bg_data, bg_fs, bg_meta = load_data(bg_file)
        
        print(f"\n实验组数据: {exp_data.shape}, fs={exp_fs}")
        print(f"背景组数据: {bg_data.shape}, fs={bg_fs}")
        
        # 检查通道数和采样率
        n_ch_exp = exp_data.shape[1] if exp_data.ndim > 1 else 1
        n_ch_bg = bg_data.shape[1] if bg_data.ndim > 1 else 1
        
        if n_ch_exp != n_ch_bg:
            print(f"❌ 通道数不匹配: 实验组 {n_ch_exp}, 背景组 {n_ch_bg}")
            return
        
        if abs(exp_fs - bg_fs) / exp_fs > 1e-6:
            print(f"❌ 采样率不匹配: 实验组 {exp_fs}, 背景组 {bg_fs}")
            return
        
        print("✅ 通道数和采样率匹配")
        
        # 时间切片 (0-1秒)
        start_time = 0.0
        end_time = 1.0
        start_idx = int(start_time * exp_fs)
        end_idx = int(end_time * exp_fs)
        
        exp_sliced = exp_data[start_idx:end_idx]
        bg_sliced = bg_data[start_idx:end_idx]
        
        print(f"\n时间切片: {start_time}s - {end_time}s")
        print(f"切片后数据: {exp_sliced.shape}")
        
        # 频域变换
        n_ch = n_ch_exp
        exp_freq = []
        bg_freq = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                exp_ch_data = exp_sliced[:, ch].flatten()
                bg_ch_data = bg_sliced[:, ch].flatten()
            else:
                exp_ch_data = exp_sliced.flatten()
                bg_ch_data = bg_sliced.flatten()
            
            exp_freq.append(get_spectrum(exp_ch_data, exp_fs))
            bg_freq.append(get_spectrum(bg_ch_data, bg_fs))
        
        print(f"\n频域变换完成，共 {n_ch} 个通道")
        
        # 相关性计算
        method = "皮尔逊相关系数"
        sensitivity_results = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                exp_ch_data = exp_sliced[:, ch].flatten()
                bg_ch_data = bg_sliced[:, ch].flatten()
            else:
                exp_ch_data = exp_sliced.flatten()
                bg_ch_data = bg_sliced.flatten()
            
            result = compute_time_similarity_batch(exp_ch_data, bg_ch_data, [method], fs=exp_fs)
            kb = result[0]['value'] if result and result[0].get('ok', False) else 0.0
            
            exp_spectrum = exp_freq[ch]
            bg_spectrum = bg_freq[ch]
            max_idx = np.argmax(exp_spectrum)
            ka = exp_spectrum[max_idx] - bg_spectrum[max_idx]
            
            sensitivity_results.append({
                'channel': f"CH{ch+1}",
                'Ka': ka,
                'Kb': kb
            })
        
        # 按Kb降序排列
        sensitivity_results.sort(key=lambda x: x['Kb'], reverse=True)
        
        print(f"\n敏感性排序 (按{method}降序):")
        print(f"{'排名':<6} {'通道':<8} {'Ka':<15} {'Kb':<15}")
        print("-" * 45)
        
        for rank, item in enumerate(sensitivity_results, 1):
            print(f"{rank:<6} {item['channel']:<8} {item['Ka']:<15.6f} {item['Kb']:<15.6f}")
        
        print("\n✅ 基础响应敏感性分析测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_azimuth_sensitivity():
    """测试方位差异敏感性分析"""
    print("\n" + "=" * 60)
    print("测试方位差异敏感性分析")
    print("=" * 60)
    
    tdms_files = find_tdms_files(TEST_DATA_DIR)
    if len(tdms_files) < 4:
        print(f"需要至少4个TDMS文件，当前找到 {len(tdms_files)} 个")
        return
    
    # 选择4个文件
    exp1_file = tdms_files[0]
    bg1_file = tdms_files[1]
    exp2_file = tdms_files[2]
    bg2_file = tdms_files[3]
    
    print(f"\n实验组1: {os.path.basename(exp1_file)}")
    print(f"背景组1: {os.path.basename(bg1_file)}")
    print(f"实验组2: {os.path.basename(exp2_file)}")
    print(f"背景组2: {os.path.basename(bg2_file)}")
    
    try:
        exp1_data, exp1_fs, _ = load_data(exp1_file)
        bg1_data, bg1_fs, _ = load_data(bg1_file)
        exp2_data, exp2_fs, _ = load_data(exp2_file)
        bg2_data, bg2_fs, _ = load_data(bg2_file)
        
        # 检查通道数和采样率
        fss = [exp1_fs, exp1_fs, bg1_fs, bg2_fs]
        n_chs = [
            exp1_data.shape[1] if exp1_data.ndim > 1 else 1,
            bg1_data.shape[1] if bg1_data.ndim > 1 else 1,
            exp2_data.shape[1] if exp2_data.ndim > 1 else 1,
            bg2_data.shape[1] if bg2_data.ndim > 1 else 1
        ]
        
        fs_ref = fss[0]
        fs_mismatch = False
        for fs in fss:
            if abs(fs - fs_ref) / fs_ref > 1e-6:
                fs_mismatch = True
                break
        if fs_mismatch:
            print(f"❌ 采样率不匹配")
            return
        
        if len(set(n_chs)) != 1:
            print(f"❌ 通道数不匹配")
            return
        
        fs = fss[0]
        n_ch = n_chs[0]
        print(f"✅ 所有数据匹配: {n_ch} 通道, {fs} Hz")
        
        # 时间切片
        start_time = 0.0
        end_time = 1.0
        start_idx = int(start_time * fs)
        end_idx = int(end_time * fs)
        
        exp1_sliced = exp1_data[start_idx:end_idx]
        exp2_sliced = exp2_data[start_idx:end_idx]
        bg1_sliced = bg1_data[start_idx:end_idx]
        bg2_sliced = bg2_data[start_idx:end_idx]
        
        # 背景对消
        bg_method = "直接相减"
        dbg1_data = []
        dbg2_data = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                exp1_ch = exp1_sliced[:, ch].flatten()
                exp2_ch = exp2_sliced[:, ch].flatten()
                bg1_ch = bg1_sliced[:, ch].flatten()
                bg2_ch = bg2_sliced[:, ch].flatten()
            else:
                exp1_ch = exp1_sliced.flatten()
                exp2_ch = exp2_sliced.flatten()
                bg1_ch = bg1_sliced.flatten()
                bg2_ch = bg2_sliced.flatten()
            
            min_len1 = min(len(exp1_ch), len(bg1_ch))
            min_len2 = min(len(exp2_ch), len(bg2_ch))
            
            exp1_ch = exp1_ch[:min_len1]
            bg1_ch = bg1_ch[:min_len1]
            exp2_ch = exp2_ch[:min_len2]
            bg2_ch = bg2_ch[:min_len2]
            
            dbg1 = subtract_background(exp1_ch, bg1_ch, bg_method)
            dbg2 = subtract_background(exp2_ch, bg2_ch, bg_method)
            
            dbg1_data.append(dbg1)
            dbg2_data.append(dbg2)
        
        if n_ch > 1:
            dbg1_data = np.column_stack(dbg1_data)
            dbg2_data = np.column_stack(dbg2_data)
        
        print(f"\n背景对消完成 ({bg_method})")
        
        # 相关性计算
        method = "皮尔逊相关系数"
        sensitivity_results = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                dbg1_ch = dbg1_data[:, ch].flatten()
                dbg2_ch = dbg2_data[:, ch].flatten()
            else:
                dbg1_ch = dbg1_data.flatten()
                dbg2_ch = dbg2_data.flatten()
            
            result = compute_time_similarity_batch(dbg1_ch, dbg2_ch, [method], fs=fs)
            kb = result[0]['value'] if result and result[0].get('ok', False) else 0.0
            
            sensitivity_results.append({
                'channel': f"CH{ch+1}",
                'Kb': kb
            })
        
        sensitivity_results.sort(key=lambda x: x['Kb'], reverse=True)
        
        print(f"\n敏感性排序 (按{method}降序):")
        print(f"{'排名':<6} {'通道':<8} {'Kb':<15}")
        print("-" * 30)
        
        for rank, item in enumerate(sensitivity_results, 1):
            print(f"{rank:<6} {item['channel']:<8} {item['Kb']:<15.6f}")
        
        print("\n✅ 方位差异敏感性分析测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("通道敏感性分析功能测试")
    print("=" * 60)
    
    # 测试TDMS读取
    data_list, meta_list = test_tdms_reading()
    
    # 测试基础响应敏感性分析
    test_basic_sensitivity()
    
    # 测试方位差异敏感性分析
    test_azimuth_sensitivity()
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
