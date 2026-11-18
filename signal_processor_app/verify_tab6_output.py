#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证Tab6输出：检查图片完整性和报告内容
"""
import os
import sys

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_tab6_output')

def log(msg):
    print(f"[VERIFY] {msg}", flush=True)

def main():
    log("=" * 80)
    log("Tab6输出验证")
    log("=" * 80)
    
    if not os.path.exists(REPORT_DIR):
        log(f"错误：报告目录不存在: {REPORT_DIR}")
        return
    
    files = os.listdir(REPORT_DIR)
    log(f"目录文件数量: {len(files)}")
    
    time_imgs = sorted([f for f in files if f.startswith('batch_time_')])
    freq_imgs = sorted([f for f in files if f.startswith('batch_freq_')])
    corr_imgs = sorted([f for f in files if f.startswith('batch_corr_')])
    heatmap_imgs = sorted([f for f in files if f.startswith('batch_heatmap_')])
    md_files = [f for f in files if f.endswith('.md')]
    
    log(f"\n时域图片: {len(time_imgs)} 张")
    for img in time_imgs:
        path = os.path.join(REPORT_DIR, img)
        size = os.path.getsize(path) / 1024
        log(f"  {img}: {size:.2f} KB")
    
    log(f"\n频域图片: {len(freq_imgs)} 张")
    for img in freq_imgs:
        path = os.path.join(REPORT_DIR, img)
        size = os.path.getsize(path) / 1024
        log(f"  {img}: {size:.2f} KB")
    
    log(f"\n相关性图片: {len(corr_imgs)} 张")
    for img in corr_imgs:
        path = os.path.join(REPORT_DIR, img)
        size = os.path.getsize(path) / 1024
        log(f"  {img}: {size:.2f} KB")
    
    log(f"\n热力图图片: {len(heatmap_imgs)} 张")
    for img in heatmap_imgs:
        path = os.path.join(REPORT_DIR, img)
        size = os.path.getsize(path) / 1024
        log(f"  {img}: {size:.2f} KB")
    
    log(f"\nMD文件: {len(md_files)} 个")
    
    expected_channels = ['CH1', 'CH2', 'CH3', 'CH4']
    expected_time = len(expected_channels)
    expected_freq = len(expected_channels)
    expected_corr = len(expected_channels)
    
    log(f"\n验证结果:")
    log(f"  预期通道数: {len(expected_channels)}")
    log(f"  时域图片: {len(time_imgs)}/{expected_time} -> {'通过' if len(time_imgs) == expected_time else '失败'}")
    log(f"  频域图片: {len(freq_imgs)}/{expected_freq} -> {'通过' if len(freq_imgs) == expected_freq else '失败'}")
    log(f"  相关性图片: {len(corr_imgs)}/{expected_corr} -> {'通过' if len(corr_imgs) == expected_corr else '失败'}")
    
    for ch in expected_channels:
        has_time = f'batch_time_{ch}.png' in time_imgs
        has_freq = f'batch_freq_{ch}.png' in freq_imgs
        has_corr = f'batch_corr_{ch}.png' in corr_imgs
        log(f"  通道 {ch}: 时域={has_time}, 频域={has_freq}, 相关性={has_corr}")
    
    if md_files:
        report_path = os.path.join(REPORT_DIR, md_files[0])
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        log(f"\n报告内容检查:")
        log(f"  报告长度: {len(content)} 字符")
        log(f"  包含实验状态定义: {'实验状态定义' in content}")
        log(f"  包含时域波形对比: {'时域波形对比' in content}")
        log(f"  包含频域波形对比: {'频域波形对比' in content}")
        log(f"  包含相关性可视化: {'相关性可视化' in content}")
        log(f"  包含通道相关性排序: {'通道相关性指标排序' in content}")
        log(f"  包含加权均值表格: {'加权均值' in content}")
        
        for ch in expected_channels:
            has_time_ref = f'batch_time_{ch}' in content
            has_freq_ref = f'batch_freq_{ch}' in content
            has_corr_ref = f'batch_corr_{ch}' in content
            log(f"  通道 {ch} 引用: 时域={has_time_ref}, 频域={has_freq_ref}, 相关性={has_corr_ref}")
    
    log("\n" + "=" * 80)
    log("验证完成")
    log("=" * 80)

if __name__ == '__main__':
    main()
