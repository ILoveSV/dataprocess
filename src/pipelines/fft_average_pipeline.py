#====================================================================
# File Name: tdms_reader_frequency_average.py
# Project Name: dataprocess
# Description:
# 1銆佽鍙朏FT CSV鏂囦欢锛氶亶鍘嗛鐜囨暟鎹洰褰曚笅鐨勬墍鏈夊瓙鏂囦欢澶?
# 2銆佺敓鎴愬钩鍧嘑FT CSV鏂囦欢锛氬鍚屼竴鏂囦欢澶逛笅鐨勬墍鏈塅FT鏂囦欢杩涜骞冲潎璁＄畻
# 3銆丆SV鏂囦欢缁撴瀯锛?
#   鍒楀悕         鏁版嵁绫诲瀷                   鎻忚堪
#   frequency    鏁板€?(float)    棰戠巼杞存暟鎹紙Hz锛?
#   amplitude1   鏁板€?(float)    閫氶亾1鐨勫钩鍧囧箙搴﹁氨
#   phase1       鏁板€?(float)    閫氶亾1鐨勫钩鍧囩浉浣嶈氨
#   amplitude2   鏁板€?(float)    閫氶亾2鐨勫钩鍧囧箙搴﹁氨
#   phase2       鏁板€?(float)    閫氶亾2鐨勫钩鍧囩浉浣嶈氨
#   ...          ...             ...
#   amplitudeN   鏁板€?(float)    閫氶亾N鐨勫钩鍧囧箙搴﹁氨
#   phaseN       鏁板€?(float)    閫氶亾N鐨勫钩鍧囩浉浣嶈氨
# 4銆佷繚鎸佸師濮嬫枃浠跺す缁撴瀯锛氭寜30hz銆?0hz銆乥ack绛夊師濮嬫枃浠跺す鍒嗙粍澶勭悊
# 5銆佽緭鍑烘枃浠跺懡鍚嶏細average_fft_鏂囦欢澶瑰悕_鏂囦欢鏁伴噺files.csv
# 6銆佹敮鎸佸杩涚▼骞惰澶勭悊锛屾彁楂樺ぇ鏂囦欢澶勭悊鏁堢巼
# 7銆佽嚜鍔ㄩ獙璇佹暟鎹竴鑷存€э細妫€鏌ラ鐜囪酱鍜屾暟鎹粨鏋勫尮閰嶆€?
# 8銆佺敓鎴愬鐞嗘眹鎬绘姤鍛婏紝璁板綍澶勭悊缁熻淇℃伅
#====================================================================
import numpy as np
import pandas as pd
import os
from pathlib import Path
import yaml
import logging
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import json
from datetime import datetime

from src.utils.perf_timing import add_counter, record_file_size, timed_step
from src.utils.cache_utils import build_cache_metadata, is_cache_hit, write_cache_metadata

logger = logging.getLogger('data_process')

def load_config():
    """鍔犺浇閰嶇疆鏂囦欢"""
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = project_root / "config" / "paths.yaml"
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    logger.info(f"閰嶇疆鏂囦欢鍔犺浇鎴愬姛: {config_path}")
    return config

def group_files_by_folder(csv_files, input_base_dir):
    """
    鏍规嵁鍘熷鏂囦欢澶圭粨鏋勫鏂囦欢杩涜鍒嗙粍
    
    鍙傛暟:
    csv_files: CSV鏂囦欢璺緞鍒楄〃
    input_base_dir: 杈撳叆鍩哄噯鐩綍
    
    杩斿洖:
    grouped_files: 鎸夋枃浠跺す鍒嗙粍鐨勬枃浠跺瓧鍏?{鏂囦欢澶硅矾寰? [鏂囦欢璺緞鍒楄〃]}
    """
    grouped_files = defaultdict(list)
    
    for csv_file in csv_files:
        # 鑾峰彇鐩稿浜庡熀鍑嗙洰褰曠殑鏂囦欢澶硅矾寰?
        relative_dir = os.path.relpath(os.path.dirname(csv_file), input_base_dir)
        grouped_files[relative_dir].append(csv_file)
    
    logger.info(f"Grouped into {len(grouped_files)} folders")
    for folder, files in grouped_files.items():
        logger.info(f"  Folder {folder}: {len(files)} files")
    
    return grouped_files

def calculate_average_fft(files_group):
    """
    璁＄畻涓€缁勬枃浠剁殑FFT骞冲潎鍊?
    
    鍙傛暟:
    files_group: 鍚屼竴鏂囦欢澶逛笅鐨勬枃浠惰矾寰勫垪琛?
    
    杩斿洖:
    average_data: 骞冲潎鍚庣殑FFT鏁版嵁瀛楀吀
    group_info: 鍒嗙粍淇℃伅 (鏂囦欢澶瑰悕, 鏂囦欢鏁伴噺)
    """
    if not files_group:
        return None, None
    
    # 璇诲彇绗竴涓枃浠惰幏鍙栧垪缁撴瀯
    first_file = files_group[0]
    with timed_step('freqavedata.csv_read', file=os.path.basename(first_file)):
        first_df = pd.read_csv(first_file)
    
    # 鍒濆鍖栫疮鍔犲櫒
    sum_data = {col: np.zeros(len(first_df)) for col in first_df.columns if col != 'frequency'}
    frequency_col = first_df['frequency'].values
    
    file_count = 0
    
    for file_index, file_path in enumerate(files_group):
        try:
            if file_index == 0:
                df = first_df
            else:
                with timed_step('freqavedata.csv_read', file=os.path.basename(file_path)):
                    df = pd.read_csv(file_path)
            
            # 楠岃瘉鏂囦欢缁撴瀯鏄惁涓€鑷?
            if 'frequency' not in df.columns or len(df) != len(first_df):
                logger.warning(f"鏂囦欢 {os.path.basename(file_path)} 缁撴瀯涓嶅尮閰嶏紝璺宠繃")
                continue
            
            # 楠岃瘉棰戠巼鍒楁槸鍚︿竴鑷?
            if not np.allclose(df['frequency'].values, frequency_col):
                logger.warning(f"File {os.path.basename(file_path)} frequency axis mismatch, skipped")
                continue
            
            # 绱姞鏁版嵁
            for col in sum_data.keys():
                if col in df.columns:
                    sum_data[col] += df[col].values
                else:
                    logger.warning(f"鏂囦欢 {os.path.basename(file_path)} 缂哄皯鍒?{col}")
            
            file_count += 1
            add_counter('freqavedata.input_files', 1)
            add_counter('freqavedata.input_rows', len(df))
#            logger.info(f"  宸插鐞?{file_count}/{len(files_group)} 涓枃浠? {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"澶勭悊鏂囦欢 {file_path} 鏃跺嚭閿? {str(e)}")
            continue
    
    if file_count == 0:
        logger.error("娌℃湁鎴愬姛璇诲彇浠讳綍鏂囦欢")
        return None, None
    
    # 璁＄畻骞冲潎鍊?
    average_data = {'frequency': frequency_col}
    for col, sum_values in sum_data.items():
        average_data[col] = sum_values / file_count
    
    # 鑾峰彇鏂囦欢澶逛俊鎭?
    folder_name = os.path.basename(os.path.dirname(first_file))
    
    return average_data, (folder_name, file_count)

def save_average_fft(average_data, group_info, output_dir, relative_folder):
    """
    淇濆瓨骞冲潎鍚庣殑FFT鏁版嵁
    
    鍙傛暟:
    average_data: 骞冲潎鍚庣殑FFT鏁版嵁
    group_info: 鍒嗙粍淇℃伅 (鏂囦欢澶瑰悕, 鏂囦欢鏁伴噺)
    output_dir: 杈撳嚭鐩綍
    relative_folder: 鐩稿鏂囦欢澶硅矾寰?
    """
    folder_name, file_count = group_info
    
    # 鍒涘缓杈撳嚭鐩綍锛堜繚鎸佸師濮嬫枃浠跺す缁撴瀯锛?
    output_folder = os.path.join(output_dir, relative_folder)
    os.makedirs(output_folder, exist_ok=True)
    
    # 鐢熸垚杈撳嚭鏂囦欢鍚?
    output_filename = f"average_fft_{folder_name}_{file_count}files.csv"
    output_path = os.path.join(output_folder, output_filename)
    
    # 鍒涘缓DataFrame骞朵繚瀛?
    df_output = pd.DataFrame(average_data)
    with timed_step('freqavedata.csv_write', file=output_filename, rows=len(df_output)):
        df_output.to_csv(output_path, index=False, encoding='utf-8-sig')
    add_counter('freqavedata.output_files', 1)
    add_counter('freqavedata.output_rows', len(df_output))
    record_file_size(output_path, 'freqavedata.output_bytes')
    
    logger.info(f"宸蹭繚瀛樺钩鍧嘑FT鏁版嵁: {output_path}")
    return output_path

def process_folder_group(args):
    """
    澶勭悊鍗曚釜鏂囦欢澶圭粍鐨勫寘瑁呭嚱鏁帮紝鐢ㄤ簬澶氳繘绋?
    
    鍙傛暟:
    args: (folder_path, files, output_dir, relative_folder)
    """
    folder_path, files, output_dir, relative_folder = args
    
    # 鍦ㄥ瓙杩涚▼涓噸鏂伴厤缃棩蹇?
    from src.utils.logging_utils import setup_logging
    project_root = Path(__file__).resolve().parent.parent.parent
    log_config_path = project_root / "config" / "logging.yaml"
    if os.path.exists(log_config_path):
        setup_logging(log_config_path)

    logger.info(f"Processing folder {relative_folder}, files: {len(files)}")
    
    with timed_step('freqavedata.average_aggregate', folder=relative_folder, files=len(files)):
        average_data, group_info = calculate_average_fft(files)
    
    if average_data is not None:
        output_path = save_average_fft(average_data, group_info, output_dir, relative_folder)
        return output_path
    else:
        logger.error(f"Failed to process folder: {relative_folder}")
        return None

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
def generate_summary_report(successful_files, output_dir):
    """
    生成处理汇总报告
    
    参数:
        successful_files: 成功生成的文件路径列表
        output_dir: 输出目录
    """
    if not successful_files:
        logger.warning("没有成功处理的文件，跳过报告生成")
        return
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("FFT 平均处理汇总报告")
    report_lines.append("=" * 60)
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    grouped = defaultdict(list)
    for f in successful_files:
        folder = os.path.basename(os.path.dirname(f))
        grouped[folder].append(f)
    
    report_lines.append(f"成功处理: {len(successful_files)} 个目录")
    report_lines.append("")
    
    for folder, files in sorted(grouped.items()):
        report_lines.append(f"  [{folder}]")
        for f in sorted(files):
            filename = os.path.basename(f)
            file_count_match = re.search(r'_(\d+)files\.csv$', filename)
            count = file_count_match.group(1) if file_count_match else "?"
            report_lines.append(f"    - {filename} ({count} 个文件平均)")
        report_lines.append("")
    
    report_path = os.path.join(output_dir, "processing_summary.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f"汇总报告已保存: {report_path}")

def _expected_average_outputs(grouped_files, output_dir):
    outputs = [Path(output_dir) / "processing_summary.txt"]
    for relative_folder, files in grouped_files.items():
        if not files:
            continue
        first_file = Path(files[0])
        folder_name = first_file.parent.name
        outputs.append(Path(output_dir) / relative_folder / f"average_fft_{folder_name}_{len(files)}files.csv")
    return outputs


def main(data_folder=None, force=False, skip_existing=True):
    with timed_step('freqavedata.module_total'):
        config = load_config()

        input_root = config["tdms_reader_frequency_output_dir"]
        output_dir = config["tdms_reader_frequency_average_output_dir"]

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

        logger.info(f"FFT input dir: {input_root}")
        logger.info(f"Scan dir: {scan_folder}")
        logger.info(f"Average FFT output dir: {output_dir}")

        csv_files = []
        with timed_step('freqavedata.file_scan', folder=scan_folder):
            for root, dirs, files in os.walk(scan_folder):
                for file in files:
                    if file.endswith('.csv') and file.startswith('FFT_'):
                        csv_files.append(os.path.join(root, file))
        add_counter('freqavedata.discovered_files', len(csv_files))

        if not csv_files:
            logger.warning("No FFT CSV files found")
            return

        logger.info(f"Found {len(csv_files)} FFT CSV files")

        grouped_files = group_files_by_folder(csv_files, input_root)
        expected_outputs = _expected_average_outputs(grouped_files, output_dir)
        params = {
            'stage': 'freqavedata',
            'average_method': 'column_sum_divide_by_file_count',
            'output_filename_rule': 'average_fft_{folder_name}_{file_count}files.csv',
        }
        metadata_path = Path(output_dir) / '.cache' / 'freqavedata_cache.json'
        hit, reason = is_cache_hit(
            'freqavedata',
            csv_files,
            expected_outputs,
            params,
            metadata_path,
            force=force,
            skip_existing=skip_existing,
        )
        if hit:
            return []

        process_args = []
        for relative_folder, files in grouped_files.items():
            if len(files) == 0:
                continue
            process_args.append((relative_folder, files, output_dir, relative_folder))

        max_workers = min(multiprocessing.cpu_count(), len(process_args))
        logger.info("TIMING freqavedata.workers count=%s groups=%s", max_workers, len(process_args))

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_folder_group, process_args))

        successful = [r for r in results if r is not None]
        logger.info(f"Completed: success {len(successful)}/{len(process_args)} folders")

        generate_summary_report(successful, output_dir)
        write_cache_metadata(
            metadata_path,
            build_cache_metadata('freqavedata', csv_files, expected_outputs, params, input_dir=scan_folder, output_dir=output_dir),
        )
        return

def _legacy_main_disabled(data_folder=None):
    with timed_step('freqavedata.module_total'):
        config = load_config()
    
        input_root = config["tdms_reader_frequency_output_dir"]
        output_dir = config["tdms_reader_frequency_average_output_dir"]
    
    # 解析扫描目录：支持从原始数据文件夹或直接指定frequency输出目录
    if data_folder:
        raw_data_dir = config["raw_data_dir"]
        raw_path = Path(raw_data_dir).resolve()
        input_path = Path(input_root).resolve()
        
        data_path = Path(data_folder).resolve()
        if data_path == raw_path or str(data_path).startswith(str(raw_path)):
            # 用户指定了原始数据目录，转换为对应的frequency输出目录
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

    logger.info(f"FFT输入目录: {input_root}")
    logger.info(f"扫描目录: {scan_folder}")
    logger.info(f"平均FFT输出目录: {output_dir}")
    
    csv_files = []
    for root, dirs, files in os.walk(scan_folder):
        for file in files:
            if file.endswith('.csv') and file.startswith('FFT_'):
                csv_files.append(os.path.join(root, file))
    
    if not csv_files:
        logger.warning("未找到可处理的FFT CSV文件")
        return
    
    logger.info(f"共找到 {len(csv_files)} 个FFT CSV文件")
    
    grouped_files = group_files_by_folder(csv_files, input_root)

    process_args = []
    for relative_folder, files in grouped_files.items():
        if len(files) == 0:
            continue
        process_args.append((relative_folder, files, output_dir, relative_folder))

    max_workers = min(multiprocessing.cpu_count(), len(process_args))
    logger.info(f"使用 {max_workers} 个进程并行处理")
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_folder_group, process_args))

    successful = [r for r in results if r is not None]
    logger.info(f"处理完成: 成功 {len(successful)}/{len(process_args)} 个目录")

    generate_summary_report(successful, output_dir)
if __name__ == "__main__":
    main()
