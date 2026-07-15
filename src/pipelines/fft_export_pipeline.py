#====================================================================
# File Name: tdms_reader_frequency.py
# Project Name: dataprocess
# Description:
# 1銆佽鍙栨椂鍩烠SV鏂囦欢锛氶亶鍘唗dms_reader_time杈撳嚭鐨勬墍鏈塁SV鏂囦欢
# 2銆佹墽琛孎FT鍒嗘瀽锛氬姣忎釜閫氶亾鐨勬椂鍩熸暟鎹繘琛屽揩閫熷倕閲屽彾鍙樻崲
# 3銆佺敓鎴愰鍩烠SV鏂囦欢锛?
#   鍒楀悕         鏁版嵁绫诲瀷                   鎻忚堪
#   frequency    鏁板€?(float)    棰戠巼杞达紝鍙寘鍚棰戠巼閮ㄥ垎(Hz)
#   amplitude1   鏁板€?(float)    閫氶亾1鐨勫箙搴﹁氨(褰掍竴鍖?
#   phase1       鏁板€?(float)    閫氶亾1鐨勭浉浣嶈氨(寮у害)
#   amplitude2   鏁板€?(float)    閫氶亾2鐨勫箙搴﹁氨(褰掍竴鍖?
#   phase2       鏁板€?(float)    閫氶亾2鐨勭浉浣嶈氨(寮у害)
#   ...          ...             ...
#   amplitude16  鏁板€?(float)    閫氶亾16鐨勫箙搴﹁氨(褰掍竴鍖?
#   phase16      鏁板€?(float)    閫氶亾16鐨勭浉浣嶈氨(寮у害)
# 4銆佽嚜鍔ㄨ鍙栧厓鏁版嵁JSON鏂囦欢鑾峰彇鐪熷疄閲囨牱鐜囷紝纭繚棰戠巼绮惧害
# 5銆佹敮鎸佸閫氶亾骞惰FFT璁＄畻锛屼繚鐣欏畬鏁寸殑棰戝煙淇℃伅
# 6銆佹敮鎸佸杩涚▼骞惰澶勭悊锛屾彁楂樺ぇ鏂囦欢澶勭悊鏁堢巼
# 7銆佸垎鍧楀啓鍏SV鏂囦欢锛岄伩鍏嶅唴瀛樻孩鍑洪棶棰?
#====================================================================
import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import re
import gc  # 鍨冨溇鍥炴敹
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import json

from src.utils.perf_timing import add_counter, record_file_size, timed_step
from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata

logger = logging.getLogger('data_process')

def load_config():
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"閰嶇疆鏂囦欢鍔犺浇鎴愬姛: {config_path}")
    return config

def normalize_sampling_rate(metadata, default_rate=500000):
    """Parse sampling rate from metadata and return a positive integer Hz."""
    if metadata:
        raw_interval = metadata.get('sampling_interval_seconds')
        if raw_interval is not None:
            try:
                interval = float(raw_interval)
                if interval > 0:
                    return int(round(1.0 / interval))
            except (TypeError, ValueError):
                pass

        raw_rate = metadata.get('sampling_rate_hz')
        if raw_rate is not None:
            try:
                rate = int(round(float(raw_rate)))
                if rate > 0:
                    return rate
            except (TypeError, ValueError):
                pass

    return int(default_rate)

def perform_fft_analysis(data, sampling_rate=50000):
    """
    瀵规暟鎹繘琛孎FT鍒嗘瀽锛岃繑鍥為鐜囥€佸箙搴﹀拰鐩镐綅
    
    鍙傛暟:
    data: 杈撳叆鏁版嵁鏁扮粍
    sampling_rate: 閲囨牱鐜囷紝榛樿涓?00kHz
    
    杩斿洖:
    freqs: 棰戠巼鏁扮粍
    amplitude: 骞呭害鏁扮粍
    phase: 鐩镐綅鏁扮粍
    """
    n = len(data)
    
    # 鎵цFFT
    fft_result = np.fft.fft(data)
    
    # 璁＄畻棰戠巼杞?
    sampling_rate = int(round(float(sampling_rate)))
    if sampling_rate <= 0:
        raise ValueError('Invalid sampling_rate: {}'.format(sampling_rate))

    freqs = np.fft.fftfreq(n, 1/sampling_rate)
    
    # 璁＄畻骞呭害鍜岀浉浣?
    amplitude = np.abs(fft_result) / n  # 褰掍竴鍖?
    phase = np.angle(fft_result)
    
    # 鍙繑鍥炴棰戠巼閮ㄥ垎
    positive_freq_idx = freqs > 0
    return freqs[positive_freq_idx], amplitude[positive_freq_idx], phase[positive_freq_idx]

def process_csv_file(csv_path, output_base_dir, input_base_dir):
    """Process one CSV file and export FFT result CSV."""
    try:
        logger.info(f"寮€濮嬪鐞嗘枃浠? {csv_path}")
        
        # 璇诲彇瀵瑰簲鐨勫厓鏁版嵁鏂囦欢鑾峰彇鐪熷疄閲囨牱鐜?
        metadata_path = csv_path.replace('.csv', '_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            sampling_rate = normalize_sampling_rate(metadata)  # 浠庡厓鏁版嵁鑾峰彇鐪熷疄閲囨牱鐜?
            logger.info(f"浣跨敤鍏冩暟鎹噰鏍风巼: {sampling_rate} Hz")
        else:
            logger.warning(f"鏈壘鍒板厓鏁版嵁鏂囦欢 {metadata_path}锛屼娇鐢ㄩ粯璁ら噰鏍风巼200kHz")
            sampling_rate = 500000  # 榛樿閲囨牱鐜?
        
        # 璇诲彇鏁翠釜CSV鏂囦欢
        with timed_step('freqdata.csv_read', file=os.path.basename(csv_path)):
            df = pd.read_csv(csv_path)
        add_counter('freqdata.input_files', 1)
        add_counter('freqdata.input_rows', len(df))
        logger.info(f"鎴愬姛璇诲彇鏂囦欢: {os.path.basename(csv_path)}, 鏁版嵁闀垮害: {len(df)}")
        
        # 纭畾閫氶亾鍒?
        channel_columns = [col for col in df.columns if col.startswith('channel')]
        num_channels = len(channel_columns)
        
        if num_channels == 0:
            logger.warning(f"No channel columns found in {os.path.basename(csv_path)}")
            return
        
        logger.info(f"澶勭悊鏂囦欢: {os.path.basename(csv_path)}, 閫氶亾鏁? {num_channels}")
        
        # 鍒濆鍖栬緭鍑烘暟鎹粨鏋?
        output_data = {}
        
        # 瀵规瘡涓€氶亾杩涜FFT鍒嗘瀽锛堟暣涓俊鍙凤級
        for channel in channel_columns:
            channel_idx = channel.replace("channel", "")
            
            # 鑾峰彇閫氶亾鏁版嵁
            channel_data = df[channel].values
            
            # 鎵цFFT鍒嗘瀽
            with timed_step('freqdata.fft_compute', file=os.path.basename(csv_path), channel=channel):
                freqs, amplitude, phase = perform_fft_analysis(channel_data, sampling_rate)
            
            # 濡傛灉鏄涓€涓€氶亾锛屼繚瀛橀鐜囨暟缁?
            if not output_data:
                output_data['frequency'] = freqs
            
            # 淇濆瓨骞呭害鍜岀浉浣?
            output_data[f'amplitude{channel_idx}'] = amplitude
            output_data[f'phase{channel_idx}'] = phase
        
        # 鍒涘缓杈撳嚭鏁版嵁妗?
        df_output = pd.DataFrame(output_data)
        
        # 鍒涘缓杈撳嚭鐩綍缁撴瀯
        relative_path = os.path.relpath(os.path.dirname(csv_path), input_base_dir)
        output_dir = os.path.join(output_base_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 淇濆瓨涓篊SV鏂囦欢
        input_filename = os.path.basename(csv_path)
        output_filename = f"FFT_{input_filename}"
        output_path = os.path.join(output_dir, output_filename)
        
        # 鍒嗗潡鍐欏叆CSV锛岄伩鍏嶅唴瀛樹笉瓒?
        output_chunk_size = 100000  # 姣忔澶勭悊10涓囪
        for i in range(0, len(df_output), output_chunk_size):
            end_idx = min(i + output_chunk_size, len(df_output))
            chunk_df = df_output.iloc[i:end_idx]
            
            mode = 'w' if i == 0 else 'a'
            header = (i == 0)
            with timed_step('freqdata.fft_csv_write', file=output_filename, rows=len(chunk_df)):
                chunk_df.to_csv(output_path, mode=mode, header=header, index=False, encoding='utf-8-sig')
            
            logger.info(f"  宸插啓鍏?{end_idx}/{len(df_output)} 琛孎FT鏁版嵁")
        
        add_counter('freqdata.output_files', 1)
        add_counter('freqdata.output_rows', len(df_output))
        record_file_size(output_path, 'freqdata.output_bytes')
        logger.info(f"宸插鐞? {input_filename} -> {output_path}")
        
        # 閲婃斁鍐呭瓨
        del df, df_output
        gc.collect()
        
    except MemoryError:
        logger.error(f"澶勭悊鏂囦欢 {os.path.basename(csv_path)} 鏃跺唴瀛樹笉瓒筹紝鏂囦欢杩囧ぇ")
    except Exception as e:
        logger.error(f"澶勭悊鏂囦欢 {os.path.basename(csv_path)} 鏃跺嚭閿? {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def process_csv_file_wrapper(args):
    """Wrapper for multiprocessing."""
    csv_path, output_base_dir, input_base_dir = args
    from src.utils.logging_utils import setup_logging
    import os
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if os.path.exists(log_config_path):
        setup_logging(log_config_path)
    return process_csv_file(csv_path, output_base_dir, input_base_dir)

def process_csv_files_parallel(csv_files, output_base_dir, input_base_dir):
    """Parallel process CSV files."""
    max_workers = multiprocessing.cpu_count()
    logger.info("TIMING freqdata.workers count=%s files=%s", max_workers, len(csv_files))
    params = [(csv_file, output_base_dir, input_base_dir) for csv_file in csv_files]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(process_csv_file_wrapper, params))

def resolve_scan_folder(base_dir, data_folder=None):
    """Resolve scan folder; support absolute or relative path."""
    base_path = Path(base_dir).resolve()
    if not data_folder:
        return str(base_path)

    selected_path = Path(data_folder)
    if not selected_path.is_absolute():
        selected_path = base_path / selected_path
    selected_path = selected_path.resolve()

    if not selected_path.exists():
        logger.error(f"data folder does not exist: {selected_path}")
        return None
    if not selected_path.is_dir():
        logger.error(f"data folder is not a directory: {selected_path}")
        return None

    return str(selected_path)

def _expected_fft_outputs(csv_files, output_base_dir, input_base_dir):
    outputs = []
    for csv_file in csv_files:
        relative_path = os.path.relpath(os.path.dirname(csv_file), input_base_dir)
        outputs.append(Path(output_base_dir) / relative_path / f"FFT_{Path(csv_file).name}")
    return outputs


def main(data_folder=None, force=False, skip_existing=True):
    with timed_step('freqdata.module_total'):
        config = load_config()

        input_root = config["tdms_reader_time_output_dir"]
        output_base_dir = config["tdms_reader_frequency_output_dir"]

        if data_folder:
            raw_data_dir = config["raw_data_dir"]
            raw_path = Path(raw_data_dir).resolve()
            input_path = Path(input_root).resolve()

            data_path = Path(data_folder).resolve()
            if data_path == raw_path or str(data_path).startswith(str(raw_path)):
                relative = data_path.relative_to(raw_path) if data_path != raw_path else Path('.')
                scan_folder = str(input_path / relative)
            else:
                scan_folder = str(data_path)
        else:
            scan_folder = input_root

        if not os.path.exists(scan_folder):
            logger.error(f"scan folder does not exist: {scan_folder}")
            return

        logger.info(f"输入目录: {input_root}")
        logger.info(f"扫描目录: {scan_folder}")
        logger.info(f"输出目录: {output_base_dir}")

        csv_files = []
        with timed_step('freqdata.file_scan', folder=scan_folder):
            for root, dirs, files in os.walk(scan_folder):
                for file in files:
                    if file.endswith('.csv') and not file.startswith('FFT_'):
                        csv_files.append(os.path.join(root, file))
        add_counter('freqdata.discovered_files', len(csv_files))

        if not csv_files:
            logger.warning("未找到可处理的CSV文件")
            return

        logger.info(f"共找到 {len(csv_files)} 个CSV文件")

        expected_outputs = _expected_fft_outputs(csv_files, output_base_dir, input_root)
        params = {
            'stage': 'freqdata',
            'fft_function': 'np.fft.fft',
            'frequency_filter': 'freqs > 0',
            'amplitude_normalization': 'abs(fft_result) / n',
            'sampling_rate_source': 'metadata sampling_interval_seconds or sampling_rate_hz fallback 500000',
            'output_columns': 'frequency amplitudeN phaseN',
        }
        metadata_path = Path(output_base_dir) / '.cache' / 'freqdata_cache.json'
        hit, reason = is_cache_hit(
            'freqdata',
            csv_files,
            expected_outputs,
            params,
            metadata_path,
            force=force,
            skip_existing=skip_existing,
        )
        if hit:
            return []

        logger.info("开始并行执行FFT处理...")
        process_csv_files_parallel(csv_files, output_base_dir, input_root)

        logger.info("FFT处理完成")
        write_cache_metadata(
            metadata_path,
            build_cache_metadata('freqdata', csv_files, expected_outputs, params, input_dir=scan_folder, output_dir=output_base_dir),
        )
        return

def _legacy_main_disabled(data_folder=None):
    module_timer = timed_step('freqdata.module_total')
    module_timer.__enter__()
    if True:
        config = load_config()
    
        input_root = config["tdms_reader_time_output_dir"]
        output_base_dir = config["tdms_reader_frequency_output_dir"]
    
    # 解析扫描目录：支持从原始数据文件夹或直接指定time输出目录
    if data_folder:
        raw_data_dir = config["raw_data_dir"]
        raw_path = Path(raw_data_dir).resolve()
        input_path = Path(input_root).resolve()
        
        data_path = Path(data_folder).resolve()
        if data_path == raw_path or str(data_path).startswith(str(raw_path)):
            # 用户指定了原始数据目录，转换为对应的time输出目录
            relative = data_path.relative_to(raw_path) if data_path != raw_path else Path('.')
            scan_folder = str(input_path / relative)
        else:
            # 用户直接指定了输出目录结构中的路径
            scan_folder = str(data_path)
    else:
        scan_folder = input_root
    
    if not os.path.exists(scan_folder):
        logger.error(f"扫描目录不存在: {scan_folder}")
        return
    
    logger.info(f"输入目录: {input_root}")
    logger.info(f"扫描目录: {scan_folder}")
    logger.info(f"输出目录: {output_base_dir}")
    
    csv_files = []
    for root, dirs, files in os.walk(scan_folder):
        for file in files:
            if file.endswith('.csv') and not file.startswith('FFT_'):
                csv_files.append(os.path.join(root, file))
    
    if not csv_files:
        logger.warning("未找到可处理的CSV文件")
        return
    
    logger.info(f"共找到 {len(csv_files)} 个CSV文件")
    
    logger.info("开始并行执行FFT处理...")
    process_csv_files_parallel(csv_files, output_base_dir, input_root)
    
    logger.info("FFT处理完成")
from src.features.fft_core import perform_fft_analysis as perform_fft_analysis
from src.io.metadata_io import normalize_sampling_rate as normalize_sampling_rate


if __name__ == "__main__":
    main()


