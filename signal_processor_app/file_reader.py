# -*- coding: utf-8 -*-
"""
文件读取模块
支持格式：CSV, TXT, Excel, NI TDM/TDMS/LVM, HDF5, 通用二进制
"""
import numpy as np
import pandas as pd
import os
import struct
from io import BytesIO


def load_data(filepath):
    """
    通用数据加载函数，自动识别文件格式
    返回: (data_array, sampling_rate, header_info)
    data_array: numpy ndarray, 形状为 (n_samples, n_channels) 或 (n_samples,)
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.csv':
        return _load_csv(filepath)
    elif ext == '.txt' or ext == '.dat':
        return _load_txt(filepath)
    elif ext in ['.xlsx', '.xls']:
        return _load_excel(filepath)
    elif ext == '.tdms':
        return _load_tdms(filepath)
    elif ext == '.tdm':
        return _load_tdm(filepath)
    elif ext == '.lvm':
        return _load_lvm(filepath)
    elif ext == '.h5' or ext == '.hdf5':
        return _load_hdf5(filepath)
    elif ext == '.bin':
        return _load_binary(filepath)
    elif ext in ['.wav', '.wave']:
        return _load_wav(filepath)
    else:
        # 尝试用通用方法读取
        return _load_generic(filepath)


def _load_csv(filepath):
    """读取CSV文件，支持多种分隔符和编码"""
    delimiters = [',', '\t', ';', ' ', '|']
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1', 'cp1252']
    
    for encoding in encodings:
        for delimiter in delimiters:
            try:
                # 先读取前几行判断是否有表头
                with open(filepath, 'r', encoding=encoding) as f:
                    first_lines = [f.readline() for _ in range(5)]
                
                # 检测是否包含非数字字符（可能是表头）
                has_header = False
                if first_lines:
                    first_parts = first_lines[0].strip().split(delimiter)
                    # 如果第一行包含非数字内容，认为有表头
                    for part in first_parts[:3]:
                        try:
                            float(part)
                        except ValueError:
                            has_header = True
                            break
                
                df = pd.read_csv(filepath, delimiter=delimiter, encoding=encoding, 
                                header=0 if has_header else None, engine='python')
                
                # 提取数值数据
                data = df.select_dtypes(include=[np.number]).values
                if data.size == 0:
                    # 尝试全部列
                    data = df.values.astype(float)
                
                # 尝试获取采样率
                fs = _extract_sampling_rate(first_lines)
                
                return data, fs, {'format': 'CSV', 'delimiter': delimiter, 'encoding': encoding}
            except Exception:
                continue
    
    raise ValueError(f"无法读取CSV文件: {filepath}")


def _load_txt(filepath):
    """读取TXT文件，支持多种格式"""
    delimiters = [None, '\t', ',', ' ', ';', '|']
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1', 'cp1252']
    
    for encoding in encodings:
        for delimiter in delimiters:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    first_lines = [f.readline() for _ in range(10)]
                
                # 检测NI LVM文件标记
                if any('LabVIEW' in line or 'Writer_Version' in line for line in first_lines):
                    return _load_lvm(filepath)
                
                # 检测是否有表头
                has_header = False
                for line in first_lines:
                    if line.strip().startswith('#') or line.strip().startswith('//'):
                        continue
                    parts = line.strip().split(delimiter) if delimiter else line.strip().split()
                    for part in parts[:3]:
                        try:
                            float(part)
                        except ValueError:
                            has_header = True
                            break
                    break
                
                df = pd.read_csv(filepath, delimiter=delimiter, encoding=encoding,
                                header=0 if has_header else None, 
                                comment='#', engine='python')
                
                data = df.select_dtypes(include=[np.number]).values
                if data.size == 0:
                    data = df.values.astype(float)
                
                fs = _extract_sampling_rate(first_lines)
                
                return data, fs, {'format': 'TXT', 'delimiter': delimiter, 'encoding': encoding}
            except Exception:
                continue
    
    raise ValueError(f"无法读取TXT文件: {filepath}")


def _load_excel(filepath):
    """读取Excel文件"""
    try:
        df = pd.read_excel(filepath, engine='openpyxl')
        data = df.select_dtypes(include=[np.number]).values
        if data.size == 0:
            data = df.values.astype(float)
        return data, None, {'format': 'Excel'}
    except Exception as e:
        raise ValueError(f"无法读取Excel文件: {filepath}, {e}")


def _load_tdms(filepath):
    """读取NI TDMS文件"""
    # 先单独尝试导入 nptdms，便于给出精确诊断
    try:
        from nptdms import TdmsFile
    except ImportError as ie:
        import sys
        import importlib.util
        spec = importlib.util.find_spec('nptdms')
        diag = (
            f"\n---------- 诊断信息 ----------"
            f"\n实际运行的 Python: {sys.executable}"
            f"\nPython 版本: {sys.version.split()[0]}"
            f"\nnptdms 查找结果: {spec}"
            f"\nImportError 详情: {ie}"
            f"\nsys.path: {sys.path}"
            f"\n------------------------------"
        )
        if spec is None:
            raise ValueError(
                "未找到 nptdms 库（该 Python 环境中未安装）。"
                "请使用上方诊断信息中的 Python 路径执行安装：\n"
                f'  "{sys.executable}" -m pip install nptdms h5py' + diag
            )
        else:
            raise ValueError(
                "nptdms 已安装但导入失败（通常是 numpy 等依赖版本不兼容）。"
                "请根据上方诊断信息修复依赖，可尝试：\n"
                f'  "{sys.executable}" -m pip install --upgrade nptdms numpy h5py' + diag
            )

    try:
        tdms_file = TdmsFile.read(filepath)

        all_data = []
        fs = None
        channel_names = []
        
        for group in tdms_file.groups():
            for channel in group.channels():
                ch_data = channel[:]
                if len(ch_data) > 0:
                    all_data.append(ch_data)
                    channel_names.append(channel.name)
                # 尝试获取采样率
                if fs is None:
                    if 'wf_increment' in channel.properties:
                        dt = channel.properties['wf_increment']
                        if dt > 0:
                            fs = 1.0 / dt
                    elif 'wf_sampling_rate' in channel.properties:
                        fs = float(channel.properties['wf_sampling_rate'])

        if not all_data:
            raise ValueError("TDMS文件中没有数据通道")

        data = np.column_stack(all_data) if len(all_data) > 1 else all_data[0].reshape(-1, 1)
        
        if fs is not None:
            fs = round(fs, 6)
        
        meta = {'format': 'TDMS'}
        if channel_names:
            meta['channels'] = channel_names
        
        return data, fs, meta
    except Exception as e:
        raise ValueError(f"无法读取TDMS文件: {filepath}, {e}")


def _load_tdm(filepath):
    """读取NI TDM文件（XML格式）"""
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # TDM文件通常引用一个TDS文件
        # 这里做一个简化的解析
        all_data = []
        for elem in root.iter():
            if elem.tag.endswith('double') or elem.tag.endswith('float'):
                try:
                    val = float(elem.text)
                    all_data.append(val)
                except:
                    pass
        
        if not all_data:
            raise ValueError("TDM文件解析未找到数据")
        
        data = np.array(all_data).reshape(-1, 1)
        return data, None, {'format': 'TDM'}
    except Exception as e:
        raise ValueError(f"无法读取TDM文件: {filepath}, {e}")


def _load_lvm(filepath):
    """读取NI LVM文件（LabVIEW Measurement File）"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 解析头部信息
        fs = None
        data_start = 0
        delimiter = '\t'
        
        for i, line in enumerate(lines):
            if line.startswith('Delta_X'):
                try:
                    fs = 1.0 / float(line.split('\t')[1].strip())
                except:
                    pass
            elif line.startswith('***End_of_Header***'):
                data_start = i + 1
                break
            elif line.startswith('X_Value') or line.startswith('Channels'):
                data_start = i + 1
                break
        
        # 读取数据
        data_lines = []
        for line in lines[data_start:]:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split(delimiter)
                try:
                    row = [float(p) for p in parts if p.strip()]
                    if row:
                        data_lines.append(row)
                except:
                    pass
        
        if not data_lines:
            raise ValueError("LVM文件中没有数据")
        
        data = np.array(data_lines)
        return data, fs, {'format': 'LVM'}
    except Exception as e:
        raise ValueError(f"无法读取LVM文件: {filepath}, {e}")


def _load_hdf5(filepath):
    """读取HDF5文件"""
    try:
        import h5py
        with h5py.File(filepath, 'r') as f:
            # 递归查找数据集
            datasets = []
            
            def find_datasets(name, obj):
                if isinstance(obj, h5py.Dataset):
                    datasets.append((name, obj[:]))
            
            f.visititems(find_datasets)
            
            if not datasets:
                raise ValueError("HDF5文件中没有数据集")
            
            # 选择最大的数据集作为主数据
            largest = max(datasets, key=lambda x: x[1].size)
            data = largest[1]
            
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            
            return data, None, {'format': 'HDF5', 'dataset': largest[0]}
    except ImportError:
        raise ValueError("需要安装h5py库: pip install h5py")
    except Exception as e:
        raise ValueError(f"无法读取HDF5文件: {filepath}, {e}")


def _load_binary(filepath, dtype=None, shape=None):
    """读取二进制文件"""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        
        # 尝试常见格式
        if dtype is None:
            # 尝试float64
            try:
                data = np.frombuffer(raw, dtype=np.float64)
                if len(data) > 0:
                    data = data.reshape(-1, 1)
                    return data, None, {'format': 'Binary', 'dtype': 'float64'}
            except:
                pass
            
            # 尝试float32
            try:
                data = np.frombuffer(raw, dtype=np.float32)
                if len(data) > 0:
                    data = data.reshape(-1, 1)
                    return data, None, {'format': 'Binary', 'dtype': 'float32'}
            except:
                pass
            
            # 尝试int16
            try:
                data = np.frombuffer(raw, dtype=np.int16)
                if len(data) > 0:
                    data = data.reshape(-1, 1)
                    return data, None, {'format': 'Binary', 'dtype': 'int16'}
            except:
                pass
        else:
            data = np.frombuffer(raw, dtype=dtype)
            if shape:
                data = data.reshape(shape)
            else:
                data = data.reshape(-1, 1)
            return data, None, {'format': 'Binary', 'dtype': str(dtype)}
        
        raise ValueError("无法解析二进制文件格式")
    except Exception as e:
        raise ValueError(f"无法读取二进制文件: {filepath}, {e}")


def _load_wav(filepath):
    """读取WAV音频文件"""
    try:
        from scipy.io import wavfile
        fs, data = wavfile.read(filepath)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return data, float(fs), {'format': 'WAV'}
    except Exception as e:
        raise ValueError(f"无法读取WAV文件: {filepath}, {e}")


def _load_generic(filepath):
    """通用加载方法，尝试所有可能的格式"""
    errors = []
    
    for loader in [_load_csv, _load_txt, _load_binary]:
        try:
            return loader(filepath)
        except Exception as e:
            errors.append(str(e))
    
    raise ValueError(f"无法识别文件格式: {filepath}. 尝试过的方法均失败: {'; '.join(errors[:3])}")


def _extract_sampling_rate(lines):
    """从文件头部提取采样率"""
    keywords = ['sampling rate', 'sample rate', 'fs', 'frequency', 'hz', 'dt', 'delta_t', 'time increment']
    
    for line in lines:
        lower = line.lower()
        for kw in keywords:
            if kw in lower:
                # 尝试提取数字
                import re
                numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
                if numbers:
                    try:
                        val = float(numbers[0])
                        if 'dt' in lower or 'increment' in lower:
                            if val > 0:
                                return 1.0 / val
                        else:
                            if val > 0 and val < 1e9:  # 合理的采样率范围
                                return val
                    except:
                        pass
    
    return None


def get_file_info(filepath):
    """获取文件信息摘要"""
    try:
        data, fs, meta = load_data(filepath)
        info = {
            'filename': os.path.basename(filepath),
            'format': meta.get('format', 'Unknown'),
            'shape': data.shape,
            'samples': data.shape[0],
            'channels': data.shape[1] if data.ndim > 1 else 1,
            'sampling_rate': fs,
            'dtype': str(data.dtype),
            'duration': data.shape[0] / fs if fs else None
        }
        return info
    except Exception as e:
        return {'error': str(e)}


if __name__ == '__main__':
    # 测试
    import sys
    if len(sys.argv) > 1:
        info = get_file_info(sys.argv[1])
        print(info)
