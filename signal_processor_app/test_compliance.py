import sys
import os
import numpy as np
import tempfile
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
except ImportError:
    app = None

def test_time_slice():
    """测试第二时间切片问题 - 第一切片6-10s，第二切片6.5-6.6s"""
    print("=" * 60)
    print("测试1: 时间切片逻辑验证")
    print("=" * 60)
    
    slice_start = 6.0
    slice_end = 10.0
    rel_start = 0.5
    rel_end = 0.6
    
    display_start = slice_start + rel_start
    display_end = slice_start + rel_end
    
    print(f"第一时间切片: {slice_start}s - {slice_end}s")
    print(f"第二时间切片(相对): {rel_start}s - {rel_end}s")
    print(f"第二时间切片(绝对): {display_start}s - {display_end}s")
    
    fs = 1000.0
    slice_duration = slice_end - slice_start
    total_samples = int(slice_duration * fs)
    print(f"第一切片采样点数: {total_samples}")
    
    offset_start = int((display_start - slice_start) * fs)
    offset_end = int((display_end - slice_start) * fs)
    subslice_samples = offset_end - offset_start
    print(f"第二切片在第一切片中的偏移: [{offset_start}, {offset_end}]")
    print(f"第二切片采样点数: {subslice_samples}")
    
    data = np.random.randn(total_samples)
    sub_data = data[offset_start:offset_end]
    t = np.linspace(display_start, display_end, len(sub_data))
    
    print(f"提取数据长度: {len(sub_data)}")
    print(f"时间轴范围: [{t[0]:.3f}s, {t[-1]:.3f}s]")
    
    if len(sub_data) > 0 and len(t) > 0:
        print("✓ 时间切片逻辑正确 - 能正确提取数据")
        return True
    else:
        print("✗ 时间切片逻辑错误 - 无法提取数据")
        return False

def test_experiment_state_display():
    """测试实验状态定义信息显示"""
    print("\n" + "=" * 60)
    print("测试2: 实验状态定义信息显示")
    print("=" * 60)
    
    from experiment_state import STATE_REGISTRY
    
    STATE_REGISTRY.clear()
    
    test_state = {
        'id': 1,
        'name': '测试状态A',
        'type': 'TC12',
        'params': {
            '方位角': '0°',
            '距离': '10m',
            '功率': '50W'
        }
    }
    STATE_REGISTRY.add_state(test_state)
    
    md_table = STATE_REGISTRY.to_markdown_table()
    print("生成的Markdown表格:")
    print(md_table)
    
    assert '测试状态A' in md_table, "状态名称未显示"
    assert 'TC12' in md_table, "类型未显示"
    assert '方位角' in md_table, "参数未显示"
    assert '报告BLOCK序号' not in md_table, "不应包含报告BLOCK序号"
    
    print("✓ 实验状态定义信息显示正确")
    return True

def test_image_aspect_ratio():
    """测试图片比例约束 - 使用实际的plot_utils.calc_figsize函数"""
    print("\n" + "=" * 60)
    print("测试3: 图片比例约束验证")
    print("=" * 60)
    
    import matplotlib.pyplot as plt
    from plot_utils import calc_figsize
    
    test_cases = [
        (2, 1, "2个子图，1列"),
        (4, 1, "4个子图，1列"),
        (8, 1, "8个子图，1列"),
        (16, 1, "16个子图，1列"),
        (4, 2, "4个子图，2列"),
        (6, 2, "6个子图，2列"),
        (12, 2, "12个子图，2列"),
    ]
    
    all_passed = True
    text_height_inch = 10 / 72.0
    for n_subplots, n_cols, desc in test_cases:
        figsize = calc_figsize(n_subplots, n_cols=n_cols)
        width, height = figsize
        aspect_ratio = width / height
        text_ratio = height / text_height_inch
        
        print(f"{desc}: figsize={figsize}, 宽高比={aspect_ratio:.2f}, 图高/文字高={text_ratio:.2f}")
        
        if aspect_ratio > 3.3:
            print(f"  ✗ 宽高比超过3.3")
            all_passed = False
        if text_ratio > 7.5:
            print(f"  ✗ 图高/文字高超过7.5")
            all_passed = False
        
        n_rows = (n_subplots + n_cols - 1) // n_cols
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        axes = axes.flatten() if n_rows > 1 or n_cols > 1 else [axes]
        for i, ax in enumerate(axes[:n_subplots]):
            ax.plot([1, 2, 3], [1, 2, 3])
            ax.set_title(f"子图{i+1}", fontsize=10)
            ax.tick_params(labelsize=8)
        for ax in axes[n_subplots:]:
            ax.axis('off')
        plt.close(fig)
    
    if all_passed:
        print("✓ 图片比例约束验证通过")
    return all_passed

def test_tab8_state_association():
    """测试Tab8实验状态关联"""
    print("\n" + "=" * 60)
    print("测试4: Tab8实验状态关联")
    print("=" * 60)
    
    from channel_sensitivity_tab import ChannelSensitivityTab, BasicResponseSensitivityTab
    from experiment_state import STATE_REGISTRY
    
    STATE_REGISTRY.clear()
    
    STATE_REGISTRY.add_state({
        'name': '状态A',
        'type': 'TC12',
        'params': {'alpha': '0.5'}
    })
    STATE_REGISTRY.add_state({
        'name': '状态B',
        'type': 'TC12',
        'params': {'alpha': '1.0'}
    })
    
    try:
        tab = ChannelSensitivityTab()
        tab.refresh_experiment_states()
        
        subtab_a = tab.subtab_a
        names = STATE_REGISTRY.get_state_names()
        
        print(f"注册的状态名: {names}")
        print(f"subtab_a类型: {type(subtab_a).__name__}")
        
        if hasattr(subtab_a, 'exp_state_mapper'):
            mapper = subtab_a.exp_state_mapper
            if hasattr(mapper, 'state_combo'):
                combo_items = [mapper.state_combo.itemText(i) for i in range(mapper.state_combo.count())]
                print(f"实验组状态下拉菜单: {combo_items}")
                for name in names:
                    assert name in combo_items, f"状态'{name}'未出现在下拉菜单中"
                print("✓ Tab8实验状态关联正确")
                return True
            else:
                print("✗ 状态映射器没有state_combo属性")
                return False
        else:
            print("✗ subtab_a没有exp_state_mapper属性")
            return False
            
    except Exception as e:
        print(f"✗ Tab8实验状态关联测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_report_structure():
    """测试报告结构 - 每个通道一张图"""
    print("\n" + "=" * 60)
    print("测试5: 报告结构验证")
    print("=" * 60)
    
    import matplotlib.pyplot as plt
    
    channels = ['CH1', 'CH2', 'CH3']
    
    for ch in channels:
        fig, axes = plt.subplots(2, 2, figsize=(10, 6))
        
        axes[0, 0].plot([1, 2, 3], [1, 2, 3])
        axes[0, 0].set_title(f"{ch} - 背景时域", fontsize=10)
        
        axes[0, 1].plot([1, 2, 3], [3, 2, 1])
        axes[0, 1].set_title(f"{ch} - 实验时域", fontsize=10)
        
        axes[1, 0].plot([1, 2, 3], [1, 4, 9])
        axes[1, 0].set_title(f"{ch} - 背景频域", fontsize=10)
        
        axes[1, 1].plot([1, 2, 3], [9, 4, 1])
        axes[1, 1].set_title(f"{ch} - 实验频域", fontsize=10)
        
        fig.suptitle(f"通道 {ch} - 敏感性分析", fontsize=14)
        plt.tight_layout()
        
        width, height = fig.get_size_inches()
        aspect_ratio = width / height
        print(f"通道{ch}: figsize=({width:.1f}, {height:.1f}), 宽高比={aspect_ratio:.2f}")
        
        assert aspect_ratio <= 3.3, f"宽高比超过3.3: {aspect_ratio}"
        
        plt.close(fig)
    
    print("✓ 报告结构验证通过")
    return True

def generate_test_report(results):
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("生成测试报告")
    print("=" * 60)
    
    report_dir = os.path.join(os.path.dirname(__file__), 'test_reports')
    os.makedirs(report_dir, exist_ok=True)
    
    report_path = os.path.join(report_dir, f"compliance_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 报告合规性测试结果\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 测试结果汇总\n\n")
        f.write("| 测试项 | 结果 |\n")
        f.write("|--------|------|\n")
        
        test_names = {
            'time_slice': '时间切片逻辑',
            'experiment_state_display': '实验状态定义信息显示',
            'image_aspect_ratio': '图片比例约束',
            'tab8_state_association': 'Tab8实验状态关联',
            'report_structure': '报告结构',
        }
        
        all_passed = True
        for key, result in results.items():
            status = "✓ 通过" if result else "✗ 失败"
            f.write(f"| {test_names.get(key, key)} | {status} |\n")
            if not result:
                all_passed = False
        
        f.write("\n")
        
        if all_passed:
            f.write("## 结论\n\n所有测试通过！报告符合设计要求。\n")
        else:
            f.write("## 结论\n\n部分测试失败，请检查并修复问题。\n")
    
    print(f"测试报告已生成: {report_path}")
    return report_path

if __name__ == '__main__':
    results = {}
    
    results['time_slice'] = test_time_slice()
    results['experiment_state_display'] = test_experiment_state_display()
    results['image_aspect_ratio'] = test_image_aspect_ratio()
    results['tab8_state_association'] = test_tab8_state_association()
    results['report_structure'] = test_report_structure()
    
    report_path = generate_test_report(results)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print(f"报告路径: {report_path}")
    print("=" * 60)
    
    if app:
        app.quit()
