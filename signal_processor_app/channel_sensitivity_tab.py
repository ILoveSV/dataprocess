# -*- coding: utf-8 -*-
"""
Tab9: 通道敏感性分析
包含两个子Tab：
- 子Tab_A: 基础响应敏感性分析
- 子Tab_B: 方位差异敏感性分析
"""
import sys
import os
import numpy as np
from scipy import signal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QLabel, QPushButton, QComboBox, QFileDialog, QMessageBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QScrollArea, QAbstractItemView, QListWidget,
    QListWidgetItem, QFormLayout, QLineEdit
)
from PyQt5.QtCore import Qt

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_debug.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[ChannelSensitivityTab] {msg}\n")
    print(f"[ChannelSensitivityTab] {msg}", flush=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from file_reader import load_data, get_file_info
from shared_widgets import ExperimentStateMapper
from signal_processing import (
    get_spectrum, compute_time_similarity_batch, compute_freq_similarity_batch,
    TIME_DOMAIN_METHODS, FREQ_DOMAIN_METHODS, BACKGROUND_SUBTRACTION_METHODS,
    subtract_background
)
from visualization import create_canvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar


class BasicResponseSensitivityTab(QWidget):
    """子Tab_A: 基础响应敏感性分析"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.exp_data = None
        self.bg_data = None
        self.exp_meta = {}
        self.bg_meta = {}
        self.exp_sliced = None
        self.bg_sliced = None
        self.exp_freq = None
        self.bg_freq = None
        self.correlation_results = {}
        self.sensitivity_results = []
        self.channels = []
        self.fs = 1.0
        self.n_channels = 0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # 数据导入
        data_group = QGroupBox("数据导入")
        data_layout = QVBoxLayout(data_group)
        
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("实验组数据:"))
        self.exp_file_edit = QLineEdit()
        self.exp_file_edit.setReadOnly(True)
        exp_layout.addWidget(self.exp_file_edit, stretch=1)
        self.exp_browse_btn = QPushButton("浏览")
        self.exp_browse_btn.clicked.connect(self.load_exp_data)
        exp_layout.addWidget(self.exp_browse_btn)
        data_layout.addLayout(exp_layout)
        
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("背景组数据:"))
        self.bg_file_edit = QLineEdit()
        self.bg_file_edit.setReadOnly(True)
        bg_layout.addWidget(self.bg_file_edit, stretch=1)
        self.bg_browse_btn = QPushButton("浏览")
        self.bg_browse_btn.clicked.connect(self.load_bg_data)
        bg_layout.addWidget(self.bg_browse_btn)
        data_layout.addLayout(bg_layout)
        
        left_layout.addWidget(data_group)
        
        # 实验状态对应关系
        state_group = QGroupBox("实验状态对应关系")
        state_layout = QVBoxLayout(state_group)
        
        self.exp_state_mapper = ExperimentStateMapper("实验组对应的实验状态")
        state_layout.addWidget(self.exp_state_mapper)
        
        self.bg_state_mapper = ExperimentStateMapper("背景组对应的实验状态")
        state_layout.addWidget(self.bg_state_mapper)
        
        left_layout.addWidget(state_group)
        
        # 时间切片
        slice_group = QGroupBox("时间切片（一次切片）")
        slice_layout = QHBoxLayout(slice_group)
        slice_layout.addWidget(QLabel("起始时间:"))
        self.slice_start_spin = QDoubleSpinBox()
        self.slice_start_spin.setRange(0, 1000)
        self.slice_start_spin.setValue(0)
        self.slice_start_spin.setSuffix(" s")
        slice_layout.addWidget(self.slice_start_spin)
        
        slice_layout.addWidget(QLabel("结束时间:"))
        self.slice_end_spin = QDoubleSpinBox()
        self.slice_end_spin.setRange(0, 1000)
        self.slice_end_spin.setValue(1)
        self.slice_end_spin.setSuffix(" s")
        slice_layout.addWidget(self.slice_end_spin)
        
        self.apply_slice_btn = QPushButton("应用切片")
        self.apply_slice_btn.clicked.connect(self.apply_time_slice)
        self.apply_slice_btn.setEnabled(False)
        slice_layout.addWidget(self.apply_slice_btn)
        
        left_layout.addWidget(slice_group)
        
        # 第二时间切片（用于显示）
        second_slice_group = QGroupBox("第二时间切片（用于显示）")
        second_slice_layout = QHBoxLayout(second_slice_group)
        second_slice_layout.addWidget(QLabel("起始时间:"))
        self.second_slice_start_spin = QDoubleSpinBox()
        self.second_slice_start_spin.setRange(0, 100)
        self.second_slice_start_spin.setValue(0)
        self.second_slice_start_spin.setSuffix(" s")
        second_slice_layout.addWidget(self.second_slice_start_spin)
        
        second_slice_layout.addWidget(QLabel("结束时间:"))
        self.second_slice_end_spin = QDoubleSpinBox()
        self.second_slice_end_spin.setRange(0, 100)
        self.second_slice_end_spin.setValue(0.1)
        self.second_slice_end_spin.setSuffix(" s")
        second_slice_layout.addWidget(self.second_slice_end_spin)
        
        self.apply_second_slice_btn = QPushButton("应用显示切片")
        self.apply_second_slice_btn.clicked.connect(self.apply_second_time_slice)
        self.apply_second_slice_btn.setEnabled(False)
        second_slice_layout.addWidget(self.apply_second_slice_btn)
        
        left_layout.addWidget(second_slice_group)
        
        # 相关性算法选择
        corr_group = QGroupBox("相关性算法")
        corr_layout = QVBoxLayout(corr_group)
        
        self.corr_method_combo = QComboBox()
        all_methods = list(TIME_DOMAIN_METHODS.keys()) + list(FREQ_DOMAIN_METHODS.keys())
        self.corr_method_combo.addItems(all_methods)
        self.corr_method_combo.setCurrentText("皮尔逊相关系数")
        corr_layout.addWidget(self.corr_method_combo)
        
        self.compute_corr_btn = QPushButton("计算相关性")
        self.compute_corr_btn.clicked.connect(self.compute_correlation)
        self.compute_corr_btn.setEnabled(False)
        corr_layout.addWidget(self.compute_corr_btn)
        
        left_layout.addWidget(corr_group)
        
        # 报告操作
        report_layout = QHBoxLayout()
        
        self.browse_report_dir_btn = QPushButton("浏览报告保存位置")
        self.browse_report_dir_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 6px;")
        self.browse_report_dir_btn.clicked.connect(self.browse_report_dir)
        report_layout.addWidget(self.browse_report_dir_btn)
        
        self.add_report_block_btn = QPushButton("添加报告BLOCK")
        self.add_report_block_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;")
        self.add_report_block_btn.clicked.connect(self.add_report_block)
        self.add_report_block_btn.setEnabled(False)
        report_layout.addWidget(self.add_report_block_btn)
        
        self.gen_report_btn = QPushButton("生成报告")
        self.gen_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.gen_report_btn.clicked.connect(self.generate_report)
        self.gen_report_btn.setEnabled(False)
        report_layout.addWidget(self.gen_report_btn)
        
        left_layout.addLayout(report_layout)
        
        left_layout.addStretch()
        splitter.addWidget(left_panel)
        
        # 右侧面板：可视化子Tab
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.viz_tabs = QTabWidget()
        
        # 时域可视化
        self.time_viz_tab = QWidget()
        self.time_viz_layout = QVBoxLayout(self.time_viz_tab)
        self.time_canvas = create_canvas(self)
        self.time_toolbar = NavigationToolbar(self.time_canvas, self)
        self.time_viz_layout.addWidget(self.time_toolbar)
        self.time_viz_layout.addWidget(self.time_canvas, stretch=1)
        self.viz_tabs.addTab(self.time_viz_tab, "时域可视化")
        
        # 频域可视化
        self.freq_viz_tab = QWidget()
        self.freq_viz_layout = QVBoxLayout(self.freq_viz_tab)
        self.freq_canvas = create_canvas(self)
        self.freq_toolbar = NavigationToolbar(self.freq_canvas, self)
        self.freq_viz_layout.addWidget(self.freq_toolbar)
        self.freq_viz_layout.addWidget(self.freq_canvas, stretch=1)
        self.viz_tabs.addTab(self.freq_viz_tab, "频域可视化")
        
        # 时域相关性可视化
        self.time_corr_tab = QWidget()
        self.time_corr_layout = QVBoxLayout(self.time_corr_tab)
        self.time_corr_canvas = create_canvas(self)
        self.time_corr_toolbar = NavigationToolbar(self.time_corr_canvas, self)
        self.time_corr_layout.addWidget(self.time_corr_toolbar)
        self.time_corr_layout.addWidget(self.time_corr_canvas, stretch=1)
        self.viz_tabs.addTab(self.time_corr_tab, "时域相关性")
        
        # 频域相关性可视化
        self.freq_corr_tab = QWidget()
        self.freq_corr_layout = QVBoxLayout(self.freq_corr_tab)
        self.freq_corr_canvas = create_canvas(self)
        self.freq_corr_toolbar = NavigationToolbar(self.freq_corr_canvas, self)
        self.freq_corr_layout.addWidget(self.freq_corr_toolbar)
        self.freq_corr_layout.addWidget(self.freq_corr_canvas, stretch=1)
        self.viz_tabs.addTab(self.freq_corr_tab, "频域相关性")
        
        # 敏感性排序表
        self.sensitivity_tab = QWidget()
        self.sensitivity_layout = QVBoxLayout(self.sensitivity_tab)
        self.sensitivity_table = QTableWidget()
        self.sensitivity_table.setColumnCount(4)
        self.sensitivity_table.setHorizontalHeaderLabels(['通道', 'Ka (频域峰值差)', 'Kb (相关性系数)', '敏感性排名'])
        self.sensitivity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sensitivity_layout.addWidget(self.sensitivity_table)
        self.viz_tabs.addTab(self.sensitivity_tab, "敏感性排序")
        
        right_layout.addWidget(self.viz_tabs, stretch=1)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
    
    def _get_num_channels(self, data):
        data = np.asarray(data)
        if len(data.shape) == 1:
            return 1
        return data.shape[1]
    
    def load_exp_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择实验组数据文件", "", 
                                              "TDMS Files (*.tdms);;All Files (*)")
        if path:
            try:
                data, fs, meta = load_data(path)
                self.exp_data = data
                self.exp_meta = meta
                self.exp_meta['fs'] = fs
                self.fs = fs
                self.n_channels = self._get_num_channels(data)
                self.channels = [f"CH{i+1}" for i in range(self.n_channels)]
                self.exp_file_edit.setText(os.path.basename(path))
                self.exp_state_mapper.set_data(data)
                log(f"[Basic] 加载实验组数据: {len(data)} samples, {self.n_channels} channels, fs={self.fs}")
                self.check_data_ready()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载实验组数据失败: {e}")
    
    def load_bg_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择背景组数据文件", "", 
                                              "TDMS Files (*.tdms);;All Files (*)")
        if path:
            try:
                data, fs, meta = load_data(path)
                self.bg_data = data
                self.bg_meta = meta
                self.bg_meta['fs'] = fs
                if self.fs == 1.0:
                    self.fs = fs
                if self.n_channels == 0:
                    self.n_channels = self._get_num_channels(data)
                    self.channels = [f"CH{i+1}" for i in range(self.n_channels)]
                self.bg_file_edit.setText(os.path.basename(path))
                self.bg_state_mapper.set_data(data)
                log(f"[Basic] 加载背景组数据: {len(data)} samples, {self.n_channels} channels, fs={self.fs}")
                self.check_data_ready()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载背景组数据失败: {e}")
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.exp_state_mapper.refresh_states(names)
        self.bg_state_mapper.refresh_states(names)
    
    def check_data_ready(self):
        if self.exp_data is not None and self.bg_data is not None:
            n_exp_ch = self._get_num_channels(self.exp_data)
            n_bg_ch = self._get_num_channels(self.bg_data)
            fs_exp = self.exp_meta.get('fs', 1.0)
            fs_bg = self.bg_meta.get('fs', 1.0)
            
            if n_exp_ch != n_bg_ch:
                QMessageBox.warning(self, "错误", 
                    f"通道数不匹配！\n实验组: {n_exp_ch} 通道\n背景组: {n_bg_ch} 通道")
                self.apply_slice_btn.setEnabled(False)
                return
            
            if abs(fs_exp - fs_bg) / fs_exp > 1e-6:
                QMessageBox.warning(self, "错误", 
                    f"采样率不匹配！\n实验组: {fs_exp} Hz\n背景组: {fs_bg} Hz")
                self.apply_slice_btn.setEnabled(False)
                return
            
            self.apply_slice_btn.setEnabled(True)
    
    def apply_time_slice(self):
        start_time = self.slice_start_spin.value()
        end_time = self.slice_end_spin.value()
        
        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "结束时间必须大于起始时间")
            return
        
        fs = self.fs
        start_idx = int(start_time * fs)
        end_idx = int(end_time * fs)
        
        self.exp_sliced = self.exp_data[start_idx:end_idx]
        self.bg_sliced = self.bg_data[start_idx:end_idx]
        
        log(f"[Basic] 时间切片: {start_time}s - {end_time}s, {len(self.exp_sliced)} samples")
        
        self.compute_freq_domain()
        self.compute_corr_btn.setEnabled(True)
        self.gen_report_btn.setEnabled(True)
        
        QMessageBox.information(self, "完成", "时间切片已应用")
        self.apply_second_slice_btn.setEnabled(True)
    
    def apply_second_time_slice(self):
        rel_start_time = self.second_slice_start_spin.value()
        rel_end_time = self.second_slice_end_spin.value()
        
        if rel_start_time >= rel_end_time:
            QMessageBox.warning(self, "提示", "第二时间切片结束时间必须大于起始时间")
            return
        
        slice_start = self.slice_start_spin.value()
        slice_end = self.slice_end_spin.value()
        slice_duration = slice_end - slice_start
        
        if rel_start_time < 0 or rel_end_time > slice_duration:
            QMessageBox.warning(self, "提示", 
                f"第二时间切片必须在第一时间切片范围内！\n第一时间切片时长: {slice_duration:.2f}s\n"
                f"第二时间切片输入范围: 0 - {slice_duration:.2f}s")
            return
        
        self.display_slice_start = slice_start + rel_start_time
        self.display_slice_end = slice_start + rel_end_time
        
        log(f"[Basic] 第二时间切片: 相对[{rel_start_time:.3f}s - {rel_end_time:.3f}s], "
            f"绝对[{self.display_slice_start:.3f}s - {self.display_slice_end:.3f}s]")
        self.visualize_all()
    
    def compute_freq_domain(self):
        n_ch = self.n_channels
        self.exp_freq = []
        self.bg_freq = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                exp_ch_data = self.exp_sliced[:, ch].flatten()
                bg_ch_data = self.bg_sliced[:, ch].flatten()
            else:
                exp_ch_data = self.exp_sliced.flatten()
                bg_ch_data = self.bg_sliced.flatten()
            
            self.exp_freq.append(get_spectrum(exp_ch_data, self.fs))
            self.bg_freq.append(get_spectrum(bg_ch_data, self.fs))
    
    def compute_correlation(self):
        method = self.corr_method_combo.currentText()
        is_time_domain = method in TIME_DOMAIN_METHODS
        
        self.correlation_results = {}
        self.sensitivity_results = []
        
        for i, ch in enumerate(self.channels):
            if self.n_channels > 1:
                exp_ch_data = self.exp_sliced[:, i].flatten()
                bg_ch_data = self.bg_sliced[:, i].flatten()
            else:
                exp_ch_data = self.exp_sliced.flatten()
                bg_ch_data = self.bg_sliced.flatten()
            
            try:
                if is_time_domain:
                    result = compute_time_similarity_batch(exp_ch_data, bg_ch_data, [method], fs=self.fs)
                else:
                    result = compute_freq_similarity_batch(exp_ch_data, bg_ch_data, [method], fs=self.fs)
                
                kb = result[0]['value'] if result and result[0].get('ok', False) else 0.0
                
                exp_spectrum = self.exp_freq[i]
                bg_spectrum = self.bg_freq[i]
                max_idx = np.argmax(exp_spectrum)
                ka = exp_spectrum[max_idx] - bg_spectrum[max_idx]
                
                self.correlation_results[ch] = {
                    'Ka': ka,
                    'Kb': kb,
                    'exp_data': exp_ch_data,
                    'bg_data': bg_ch_data,
                    'exp_freq': exp_spectrum,
                    'bg_freq': bg_spectrum
                }
                
                self.sensitivity_results.append({
                    'channel': ch,
                    'Ka': ka,
                    'Kb': kb,
                    'index': i
                })
                
            except Exception as e:
                log(f"[Basic] 通道 {ch} 相关性计算失败: {e}")
                self.correlation_results[ch] = {'Ka': 0, 'Kb': 0}
        
        self.sensitivity_results.sort(key=lambda x: x['Kb'])
        
        self.display_sensitivity_table()
        self.visualize_all()
    
    def display_sensitivity_table(self):
        self.sensitivity_table.setRowCount(len(self.sensitivity_results))
        
        for row, item in enumerate(self.sensitivity_results):
            self.sensitivity_table.setItem(row, 0, QTableWidgetItem(item['channel']))
            self.sensitivity_table.setItem(row, 1, QTableWidgetItem(f"{item['Ka']:.6f}"))
            self.sensitivity_table.setItem(row, 2, QTableWidgetItem(f"{item['Kb']:.6f}"))
            self.sensitivity_table.setItem(row, 3, QTableWidgetItem(str(row + 1)))
    
    def find_secondary_slice(self):
        all_spectra = self.exp_freq
        if not all_spectra:
            return 0, 100
        
        avg_spectrum = np.mean(all_spectra, axis=0)
        max_idx = np.argmax(avg_spectrum)
        freq_step = self.fs / len(avg_spectrum)
        peak_freq = max_idx * freq_step
        
        if peak_freq > 0:
            cycle_period = 1 / peak_freq
            window_duration = 7 * cycle_period
        else:
            window_duration = 0.1
        
        n_samples = len(self.exp_sliced)
        max_start = max(0, n_samples - int(window_duration * self.fs))
        start_sample = max_start // 2
        
        return start_sample, start_sample + int(window_duration * self.fs)
    
    def visualize_all(self):
        self.visualize_time_domain()
        self.visualize_freq_domain()
        self.visualize_time_correlation()
        self.visualize_freq_correlation()
    
    def visualize_time_domain(self):
        if hasattr(self, 'display_slice_start'):
            start_time = self.display_slice_start
            end_time = self.display_slice_end
        else:
            start_idx, end_idx = self.find_secondary_slice()
            start_time = start_idx / self.fs
            end_time = end_idx / self.fs
        
        slice_start = self.slice_start_spin.value()
        offset_start = int((start_time - slice_start) * self.fs)
        offset_end = int((end_time - slice_start) * self.fs)
        
        fig = self.time_canvas.figure
        fig.clear()
        
        n_rows = self.n_channels
        n_cols = 2
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        for i in range(n_rows):
            for j in range(n_cols):
                ax = fig.add_subplot(gs[i, j])
                if j == 0:
                    if self.n_channels > 1:
                        data = self.bg_sliced[offset_start:offset_end, i].flatten()
                    else:
                        data = self.bg_sliced[offset_start:offset_end].flatten()
                    t = np.linspace(start_time, end_time, len(data))
                    ax.plot(t, data, linewidth=1.0, color='#FF9800')
                else:
                    if self.n_channels > 1:
                        data = self.exp_sliced[offset_start:offset_end, i].flatten()
                    else:
                        data = self.exp_sliced[offset_start:offset_end].flatten()
                    t = np.linspace(start_time, end_time, len(data))
                    ax.plot(t, data, linewidth=1.0, color='#2196F3')
                
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, self.channels[i], transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel("信号值", fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel("时间(s)", fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
        
        gs_top = fig.add_gridspec(1, n_cols, top=0.98, bottom=0.95)
        ax_bg_title = fig.add_subplot(gs_top[0, 0])
        ax_bg_title.text(0.5, 0.5, '背景组', ha='center', va='center', fontsize=12, fontweight='bold', color='#E65100')
        ax_bg_title.set_axis_off()
        
        ax_exp_title = fig.add_subplot(gs_top[0, 1])
        ax_exp_title.text(0.5, 0.5, '实验组', ha='center', va='center', fontsize=12, fontweight='bold', color='#1565C0')
        ax_exp_title.set_axis_off()
        
        fig.suptitle(f"时域对比（第二时间切片: {start_time:.3f}s - {end_time:.3f}s）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.time_canvas.draw()
    
    def visualize_freq_domain(self):
        fig = self.freq_canvas.figure
        fig.clear()
        
        n_rows = self.n_channels
        n_cols = 2
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        for i in range(n_rows):
            for j in range(n_cols):
                ax = fig.add_subplot(gs[i, j])
                if j == 0:
                    data = self.bg_freq[i]
                    f = np.linspace(0, self.fs/2, len(data))
                    ax.semilogy(f, data, linewidth=1.0, color='#FF9800')
                else:
                    data = self.exp_freq[i]
                    f = np.linspace(0, self.fs/2, len(data))
                    ax.semilogy(f, data, linewidth=1.0, color='#2196F3')
                
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_xlim(0, self.fs/2)
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, self.channels[i], transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel("功率谱密度", fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel("频率(Hz)", fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
        
        gs_top = fig.add_gridspec(1, n_cols, top=0.98, bottom=0.95)
        ax_bg_title = fig.add_subplot(gs_top[0, 0])
        ax_bg_title.text(0.5, 0.5, '背景组', ha='center', va='center', fontsize=12, fontweight='bold', color='#E65100')
        ax_bg_title.set_axis_off()
        
        ax_exp_title = fig.add_subplot(gs_top[0, 1])
        ax_exp_title.text(0.5, 0.5, '实验组', ha='center', va='center', fontsize=12, fontweight='bold', color='#1565C0')
        ax_exp_title.set_axis_off()
        
        fig.suptitle("频域对比", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.freq_canvas.draw()
    
    def visualize_time_correlation(self):
        fig = self.time_corr_canvas.figure
        fig.clear()
        
        if not self.sensitivity_results:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("时域相关性", fontsize=14)
            self.time_corr_canvas.draw()
            return
        
        sorted_channels = [r['channel'] for r in self.sensitivity_results]
        n_channels = len(sorted_channels)
        n_cols = 2
        n_rows = (n_channels + n_cols - 1) // n_cols
        
        if n_channels == 0:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("时域相关性", fontsize=14)
            self.time_corr_canvas.draw()
            return
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        idx = 0
        for i in range(n_rows):
            for j in range(n_cols):
                if idx >= n_channels:
                    break
                ch = sorted_channels[idx]
                ax = fig.add_subplot(gs[i, j])
                
                result = self.correlation_results.get(ch, {})
                exp_data = result.get('exp_data', [])
                bg_data = result.get('bg_data', [])
                
                if len(exp_data) > 0 and len(bg_data) > 0:
                    ax.scatter(exp_data[:500], bg_data[:500], s=3, alpha=0.4, color='#2196F3')
                
                kb = result.get('Kb', 0)
                ka = result.get('Ka', 0)
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, f"{ch}", transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                ax.text(0.02, 0.02, f"Kb={kb:.4f}\nKa={ka:.4f}", 
                        transform=ax.transAxes, 
                        ha='left', va='bottom', fontsize=6,
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel('背景组', fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel('实验组', fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
                
                idx += 1
        
        fig.suptitle(f"时域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.time_corr_canvas.draw()
    
    def visualize_freq_correlation(self):
        fig = self.freq_corr_canvas.figure
        fig.clear()
        
        if not self.sensitivity_results:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("频域相关性", fontsize=14)
            self.freq_corr_canvas.draw()
            return
        
        sorted_channels = [r['channel'] for r in self.sensitivity_results]
        n_channels = len(sorted_channels)
        n_cols = 2
        n_rows = (n_channels + n_cols - 1) // n_cols
        
        if n_channels == 0:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("频域相关性", fontsize=14)
            self.freq_corr_canvas.draw()
            return
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        idx = 0
        for i in range(n_rows):
            for j in range(n_cols):
                if idx >= n_channels:
                    break
                ch = sorted_channels[idx]
                ax = fig.add_subplot(gs[i, j])
                
                result = self.correlation_results.get(ch, {})
                exp_freq = result.get('exp_freq', [])
                bg_freq = result.get('bg_freq', [])
                
                if len(exp_freq) > 0 and len(bg_freq) > 0:
                    ax.scatter(exp_freq, bg_freq, s=3, alpha=0.4, color='#2196F3')
                
                kb = result.get('Kb', 0)
                ka = result.get('Ka', 0)
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, f"{ch}", transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                ax.text(0.02, 0.02, f"Kb={kb:.4f}\nKa={ka:.4f}", 
                        transform=ax.transAxes, 
                        ha='left', va='bottom', fontsize=6,
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel('背景组频谱', fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel('实验组频谱', fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
                
                idx += 1
        
        fig.suptitle(f"频域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.freq_corr_canvas.draw()
    
    def browse_report_dir(self):
        from PyQt5.QtWidgets import QFileDialog
        from experiment_state import REPORT_MANAGER
        
        dir_path = QFileDialog.getExistingDirectory(self, "选择报告保存目录")
        if dir_path:
            REPORT_MANAGER.set_report_dir(dir_path)
            log(f"[Basic/Azimuth] 报告目录已设置: {dir_path}")
    
    def refresh_experiment_states(self):
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        if hasattr(self, 'exp_state_mapper'):
            self.exp_state_mapper.refresh_states(names)
            self.bg_state_mapper.refresh_states(names)
        elif hasattr(self, 'exp1_state_mapper'):
            self.exp1_state_mapper.refresh_states(names)
            self.bg1_state_mapper.refresh_states(names)
            self.exp2_state_mapper.refresh_states(names)
            self.bg2_state_mapper.refresh_states(names)
    
    def push_experiment_state(self, state_name):
        if hasattr(self, 'exp_state_mapper'):
            self.exp_state_mapper.set_state(state_name)
        elif hasattr(self, 'exp1_state_mapper'):
            self.exp1_state_mapper.set_state(state_name)
        log(f"[Basic/Azimuth] 接收推送的实验状态: {state_name}")
    
    def check_experiment_state_associated(self):
        if hasattr(self, 'exp_state_mapper'):
            exp_state = self.exp_state_mapper.get_selected_state()
            bg_state = self.bg_state_mapper.get_selected_state()
            if not exp_state or not bg_state:
                QMessageBox.warning(self, "提示", 
                    "请为实验组和背景组关联实验状态！\n\n" +
                    f"实验组状态: {'已关联' if exp_state else '未关联'}\n" +
                    f"背景组状态: {'已关联' if bg_state else '未关联'}\n\n" +
                    "请在实验状态定义Tab中定义实验状态，并通过推送或下拉菜单关联。")
                return False
        elif hasattr(self, 'exp1_state_mapper'):
            exp1_state = self.exp1_state_mapper.get_selected_state()
            bg1_state = self.bg1_state_mapper.get_selected_state()
            exp2_state = self.exp2_state_mapper.get_selected_state()
            bg2_state = self.bg2_state_mapper.get_selected_state()
            if not exp1_state or not bg1_state or not exp2_state or not bg2_state:
                QMessageBox.warning(self, "提示", 
                    "请为所有实验组和背景组关联实验状态！\n\n" +
                    f"实验组1状态: {'已关联' if exp1_state else '未关联'}\n" +
                    f"背景组1状态: {'已关联' if bg1_state else '未关联'}\n" +
                    f"实验组2状态: {'已关联' if exp2_state else '未关联'}\n" +
                    f"背景组2状态: {'已关联' if bg2_state else '未关联'}\n\n" +
                    "请在实验状态定义Tab中定义实验状态，并通过推送或下拉菜单关联。")
                return False
        return True
    
    def add_report_block(self):
        if not self.sensitivity_results:
            QMessageBox.warning(self, "提示", "请先计算相关性")
            return
        
        if not self.check_experiment_state_associated():
            return
        
        try:
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import save_figure_to_file
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            md_content = f"## 敏感性分析报告\n\n"
            md_content += "### 1. 实验状态定义\n\n"
            
            from experiment_state import STATE_REGISTRY
            state_names = []
            exp_state_name = self.exp_state_mapper.get_state_name()
            bg_state_name = self.bg_state_mapper.get_state_name()
            if exp_state_name:
                state_names.append(exp_state_name)
            if bg_state_name and bg_state_name != exp_state_name:
                state_names.append(bg_state_name)
            
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"| 参数 | 值 |\n"
            md_content += f"|------|----|\n"
            md_content += f"| 采样率 | {self.fs:.0f} Hz |\n"
            md_content += f"| 通道数 | {self.n_channels} |\n"
            md_content += f"| 时间切片 | {self.slice_start_spin.value():.2f}s - {self.slice_end_spin.value():.2f}s |\n"
            md_content += f"| 相关性算法 | {self.corr_method_combo.currentText()} |\n\n"
            
            md_content += "### 2. 通道敏感性分析（左背景右实验）\n\n"
            md_content += "> **左列**: 背景数据 | **右列**: 实验数据\n\n"
            
            from plot_utils import calc_figsize
            import matplotlib.pyplot as plt
            
            all_images = []
            
            if hasattr(self, 'display_slice_start'):
                start_time = self.display_slice_start
                end_time = self.display_slice_end
            else:
                start_idx, end_idx = self.find_secondary_slice()
                start_time = start_idx / self.fs
                end_time = end_idx / self.fs
            
            slice_start = self.slice_start_spin.value()
            offset_start = int((start_time - slice_start) * self.fs)
            offset_end = int((end_time - slice_start) * self.fs)
            
            for i, channel_name in enumerate(self.channels):
                n_subplots = 3
                n_cols = 2
                figsize = calc_figsize(n_subplots * 2, n_cols=n_cols)
                fig, axes = plt.subplots(n_subplots, n_cols, figsize=figsize)
                
                t = np.linspace(start_time, end_time, 
                               len(self.bg_sliced[offset_start:offset_end, i].flatten()) 
                               if self.n_channels > 1 else len(self.bg_sliced[offset_start:offset_end].flatten()))
                
                if self.n_channels > 1:
                    bg_data = self.bg_sliced[offset_start:offset_end, i].flatten()
                    exp_data = self.exp_sliced[offset_start:offset_end, i].flatten()
                else:
                    bg_data = self.bg_sliced[offset_start:offset_end].flatten()
                    exp_data = self.exp_sliced[offset_start:offset_end].flatten()
                
                axes[0, 0].plot(t, bg_data, linewidth=1.0, color='orange')
                axes[0, 0].set_title(f"背景组", fontsize=10)
                axes[0, 0].tick_params(axis='both', labelsize=8)
                
                axes[0, 1].plot(t, exp_data, linewidth=1.0)
                axes[0, 1].set_title(f"实验组", fontsize=10)
                axes[0, 1].tick_params(axis='both', labelsize=8)
                
                from scipy import signal
                f_bg, Pxx_bg = signal.welch(bg_data, fs=self.fs, nperseg=min(len(bg_data), 1024))
                f_exp, Pxx_exp = signal.welch(exp_data, fs=self.fs, nperseg=min(len(exp_data), 1024))
                
                axes[1, 0].semilogy(f_bg, Pxx_bg, linewidth=1.0, color='orange')
                axes[1, 0].set_title(f"背景组频谱", fontsize=10)
                axes[1, 0].set_xlim(0, self.fs/2)
                axes[1, 0].tick_params(axis='both', labelsize=8)
                
                axes[1, 1].semilogy(f_exp, Pxx_exp, linewidth=1.0)
                axes[1, 1].set_title(f"实验组频谱", fontsize=10)
                axes[1, 1].set_xlim(0, self.fs/2)
                axes[1, 1].tick_params(axis='both', labelsize=8)
                
                corr_value = self.sensitivity_results[i].get('Kb', 0)
                axes[2, 0].text(0.5, 0.5, f"相关性系数\nKb = {corr_value:.6f}", 
                               ha='center', va='center', fontsize=10)
                axes[2, 0].set_axis_off()
                
                axes[2, 1].text(0.5, 0.5, f"敏感性排名\n第{i+1}名", 
                               ha='center', va='center', fontsize=10)
                axes[2, 1].set_axis_off()
                
                fig.suptitle(f"通道 {channel_name} - 敏感性分析", fontsize=12)
                fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])
                
                path = os.path.join(report_dir, f"sensitivity_{channel_name}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                all_images.append(path)
                
                md_content += f"#### 通道 {channel_name}\n\n"
                md_content += f"![通道 {channel_name}](sensitivity_{channel_name}.png)\n\n"
            
            md_content += "### 3. 敏感性排序\n\n"
            md_content += f"> **敏感性判断**: 相关性越小(Kb越小)，敏感性越高。\n\n"
            
            if hasattr(self.sensitivity_results[0], 'Ka'):
                md_content += f"| 排名 | 通道 | Ka (频域峰值差) | Kb (相关性系数) |\n"
                md_content += f"|------|------|----------------|----------------|\n"
                for rank, item in enumerate(self.sensitivity_results, 1):
                    md_content += f"| {rank} | {item['channel']} | {item['Ka']:.6f} | {item['Kb']:.6f} |\n"
            else:
                md_content += f"| 排名 | 通道 | Kb (相关性系数) |\n"
                md_content += f"|------|------|----------------|\n"
                for rank, item in enumerate(self.sensitivity_results, 1):
                    md_content += f"| {rank} | {item['channel']} | {item['Kb']:.6f} |\n"
            md_content += "\n"
            
            block = ReportBlock(
                title=f"敏感性分析 - {self.exp_state_mapper.get_state_name()}",
                content=md_content,
                images=all_images
            )
            
            REPORT_MANAGER.add_block(block)
            QMessageBox.information(self, "成功", 
                f"已添加报告BLOCK到Markdown报告Tab\n标题: {block.title}")
            
        except Exception as e:
            log(f"[Basic/Azimuth] 添加报告BLOCK失败: {e}")
            import traceback
            log(f"[Basic/Azimuth] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}")
    
    def generate_report(self):
        try:
            from experiment_state import REPORT_MANAGER
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先在报告Tab设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            md_content = f"## 基础响应敏感性分析报告\n\n"
            
            md_content += "### 1. 实验状态定义\n\n"
            
            from experiment_state import STATE_REGISTRY
            state_names = []
            exp_state_name = self.exp_state_mapper.get_state_name()
            bg_state_name = self.bg_state_mapper.get_state_name()
            if exp_state_name:
                state_names.append(exp_state_name)
            if bg_state_name and bg_state_name != exp_state_name:
                state_names.append(bg_state_name)
            
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"| 参数 | 值 |\n"
            md_content += f"|------|----|\n"
            md_content += f"| 采样率 | {self.fs:.0f} Hz |\n"
            md_content += f"| 通道数 | {self.n_channels} |\n"
            md_content += f"| 时间切片 | {self.slice_start_spin.value():.2f}s - {self.slice_end_spin.value():.2f}s |\n"
            md_content += f"| 相关性算法 | {self.corr_method_combo.currentText()} |\n\n"
            
            md_content += "### 2. 可视化结果\n\n"
            
            md_content += "#### 2.1 时域二次切片对比\n\n"
            md_content += f"![时域对比](basic_time_viz.png)\n\n"
            md_content += f"**说明**: 显示各通道背景组与实验组的时域信号对比，二次切片范围为 {self.find_secondary_slice()[0]/self.fs:.3f}s - {self.find_secondary_slice()[1]/self.fs:.3f}s。\n\n"
            
            md_content += "#### 2.2 频域对比\n\n"
            md_content += f"![频域对比](basic_freq_viz.png)\n\n"
            md_content += "**说明**: 显示各通道背景组与实验组的频域频谱对比。\n\n"
            
            md_content += "#### 2.3 时域相关性\n\n"
            md_content += f"![时域相关性](basic_time_corr.png)\n\n"
            md_content += "**说明**: 各通道实验组与背景组的时域散点图，按敏感性(Kb)降序排列。\n\n"
            
            md_content += "#### 2.4 频域相关性\n\n"
            md_content += f"![频域相关性](basic_freq_corr.png)\n\n"
            md_content += "**说明**: 各通道实验组与背景组的频域散点图，按敏感性(Kb)降序排列。\n\n"
            
            md_content += "### 3. 敏感性排序\n\n"
            md_content += f"> **敏感性判断**: 实验组与背景组越不相关(Kb越小)，通道越敏感。\n\n"
            md_content += f"| 排名 | 通道 | Ka (频域峰值差) | Kb (相关性系数) |\n"
            md_content += f"|------|------|----------------|----------------|\n"
            
            for rank, item in enumerate(self.sensitivity_results, 1):
                md_content += f"| {rank} | {item['channel']} | {item['Ka']:.6f} | {item['Kb']:.6f} |\n"
            
            md_content += "\n"
            
            report_path = os.path.join(report_dir, "basic_response_sensitivity_report.md")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            from report_manager import save_figure_to_file
            save_figure_to_file(self.time_canvas.figure, os.path.join(report_dir, "basic_time_viz.png"))
            save_figure_to_file(self.freq_canvas.figure, os.path.join(report_dir, "basic_freq_viz.png"))
            save_figure_to_file(self.time_corr_canvas.figure, os.path.join(report_dir, "basic_time_corr.png"))
            save_figure_to_file(self.freq_corr_canvas.figure, os.path.join(report_dir, "basic_freq_corr.png"))
            
            QMessageBox.information(self, "完成", f"报告已生成: {report_path}")
            
        except Exception as e:
            log(f"[Basic] 生成报告失败: {e}")
            QMessageBox.warning(self, "错误", f"生成报告失败: {e}")


class AzimuthDiffSensitivityTab(QWidget):
    """子Tab_B: 方位差异敏感性分析"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.exp1_data = None
        self.exp2_data = None
        self.bg1_data = None
        self.bg2_data = None
        self.exp1_meta = {}
        self.exp2_meta = {}
        self.bg1_meta = {}
        self.bg2_meta = {}
        self.exp1_sliced = None
        self.exp2_sliced = None
        self.bg1_sliced = None
        self.bg2_sliced = None
        self.dbg1_data = None
        self.dbg2_data = None
        self.dbg1_freq = None
        self.dbg2_freq = None
        self.correlation_results = {}
        self.sensitivity_results = []
        self.channels = []
        self.fs = 1.0
        self.n_channels = 0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # 数据导入
        data_group = QGroupBox("数据导入")
        data_layout = QVBoxLayout(data_group)
        
        exp1_layout = QHBoxLayout()
        exp1_layout.addWidget(QLabel("实验组1数据:"))
        self.exp1_file_edit = QLineEdit()
        self.exp1_file_edit.setReadOnly(True)
        exp1_layout.addWidget(self.exp1_file_edit, stretch=1)
        self.exp1_browse_btn = QPushButton("浏览")
        self.exp1_browse_btn.clicked.connect(lambda: self.load_data('exp1'))
        exp1_layout.addWidget(self.exp1_browse_btn)
        data_layout.addLayout(exp1_layout)
        
        bg1_layout = QHBoxLayout()
        bg1_layout.addWidget(QLabel("背景组1数据:"))
        self.bg1_file_edit = QLineEdit()
        self.bg1_file_edit.setReadOnly(True)
        bg1_layout.addWidget(self.bg1_file_edit, stretch=1)
        self.bg1_browse_btn = QPushButton("浏览")
        self.bg1_browse_btn.clicked.connect(lambda: self.load_data('bg1'))
        bg1_layout.addWidget(self.bg1_browse_btn)
        data_layout.addLayout(bg1_layout)
        
        exp2_layout = QHBoxLayout()
        exp2_layout.addWidget(QLabel("实验组2数据:"))
        self.exp2_file_edit = QLineEdit()
        self.exp2_file_edit.setReadOnly(True)
        exp2_layout.addWidget(self.exp2_file_edit, stretch=1)
        self.exp2_browse_btn = QPushButton("浏览")
        self.exp2_browse_btn.clicked.connect(lambda: self.load_data('exp2'))
        exp2_layout.addWidget(self.exp2_browse_btn)
        data_layout.addLayout(exp2_layout)
        
        bg2_layout = QHBoxLayout()
        bg2_layout.addWidget(QLabel("背景组2数据:"))
        self.bg2_file_edit = QLineEdit()
        self.bg2_file_edit.setReadOnly(True)
        bg2_layout.addWidget(self.bg2_file_edit, stretch=1)
        self.bg2_browse_btn = QPushButton("浏览")
        self.bg2_browse_btn.clicked.connect(lambda: self.load_data('bg2'))
        bg2_layout.addWidget(self.bg2_browse_btn)
        data_layout.addLayout(bg2_layout)
        
        left_layout.addWidget(data_group)
        
        # 实验状态对应关系
        state_group = QGroupBox("实验状态对应关系")
        state_layout = QVBoxLayout(state_group)
        
        self.exp1_state_mapper = ExperimentStateMapper("实验组1对应的实验状态")
        state_layout.addWidget(self.exp1_state_mapper)
        
        self.bg1_state_mapper = ExperimentStateMapper("背景组1对应的实验状态")
        state_layout.addWidget(self.bg1_state_mapper)
        
        self.exp2_state_mapper = ExperimentStateMapper("实验组2对应的实验状态")
        state_layout.addWidget(self.exp2_state_mapper)
        
        self.bg2_state_mapper = ExperimentStateMapper("背景组2对应的实验状态")
        state_layout.addWidget(self.bg2_state_mapper)
        
        left_layout.addWidget(state_group)
        
        # 时间切片
        slice_group = QGroupBox("时间切片（一次切片）")
        slice_layout = QHBoxLayout(slice_group)
        slice_layout.addWidget(QLabel("起始时间:"))
        self.slice_start_spin = QDoubleSpinBox()
        self.slice_start_spin.setRange(0, 1000)
        self.slice_start_spin.setValue(0)
        self.slice_start_spin.setSuffix(" s")
        slice_layout.addWidget(self.slice_start_spin)
        
        slice_layout.addWidget(QLabel("结束时间:"))
        self.slice_end_spin = QDoubleSpinBox()
        self.slice_end_spin.setRange(0, 1000)
        self.slice_end_spin.setValue(1)
        self.slice_end_spin.setSuffix(" s")
        slice_layout.addWidget(self.slice_end_spin)
        
        self.apply_slice_btn = QPushButton("应用切片")
        self.apply_slice_btn.clicked.connect(self.apply_time_slice)
        self.apply_slice_btn.setEnabled(False)
        slice_layout.addWidget(self.apply_slice_btn)
        
        left_layout.addWidget(slice_group)
        
        # 背景对消算法
        bg_sub_group = QGroupBox("背景对消算法")
        bg_sub_layout = QVBoxLayout(bg_sub_group)
        
        self.bg_method_combo = QComboBox()
        self.bg_method_combo.addItems(BACKGROUND_SUBTRACTION_METHODS)
        self.bg_method_combo.setCurrentText("直接相减")
        bg_sub_layout.addWidget(self.bg_method_combo)
        
        self.apply_bg_btn = QPushButton("执行背景对消")
        self.apply_bg_btn.clicked.connect(self.apply_background_subtraction)
        self.apply_bg_btn.setEnabled(False)
        bg_sub_layout.addWidget(self.apply_bg_btn)
        
        left_layout.addWidget(bg_sub_group)
        
        # 相关性算法选择
        corr_group = QGroupBox("相关性算法")
        corr_layout = QVBoxLayout(corr_group)
        
        self.corr_method_combo = QComboBox()
        all_methods = list(TIME_DOMAIN_METHODS.keys()) + list(FREQ_DOMAIN_METHODS.keys())
        self.corr_method_combo.addItems(all_methods)
        self.corr_method_combo.setCurrentText("皮尔逊相关系数")
        corr_layout.addWidget(self.corr_method_combo)
        
        self.compute_corr_btn = QPushButton("计算相关性")
        self.compute_corr_btn.clicked.connect(self.compute_correlation)
        self.compute_corr_btn.setEnabled(False)
        corr_layout.addWidget(self.compute_corr_btn)
        
        left_layout.addWidget(corr_group)
        
        # 报告操作
        report_layout = QHBoxLayout()
        
        self.browse_report_dir_btn = QPushButton("浏览报告保存位置")
        self.browse_report_dir_btn.setStyleSheet("background-color: #9C27B0; color: white; padding: 6px;")
        self.browse_report_dir_btn.clicked.connect(self.browse_report_dir)
        report_layout.addWidget(self.browse_report_dir_btn)
        
        self.add_report_block_btn = QPushButton("添加报告BLOCK")
        self.add_report_block_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;")
        self.add_report_block_btn.clicked.connect(self.add_report_block)
        self.add_report_block_btn.setEnabled(False)
        report_layout.addWidget(self.add_report_block_btn)
        
        self.gen_report_btn = QPushButton("生成报告")
        self.gen_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.gen_report_btn.clicked.connect(self.generate_report)
        self.gen_report_btn.setEnabled(False)
        report_layout.addWidget(self.gen_report_btn)
        
        left_layout.addLayout(report_layout)
        
        left_layout.addStretch()
        splitter.addWidget(left_panel)
        
        # 右侧面板：可视化子Tab
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.viz_tabs = QTabWidget()
        
        # 时域可视化
        self.time_viz_tab = QWidget()
        self.time_viz_layout = QVBoxLayout(self.time_viz_tab)
        self.time_canvas = create_canvas(self)
        self.time_toolbar = NavigationToolbar(self.time_canvas, self)
        self.time_viz_layout.addWidget(self.time_toolbar)
        self.time_viz_layout.addWidget(self.time_canvas, stretch=1)
        self.viz_tabs.addTab(self.time_viz_tab, "时域可视化")
        
        # 频域可视化
        self.freq_viz_tab = QWidget()
        self.freq_viz_layout = QVBoxLayout(self.freq_viz_tab)
        self.freq_canvas = create_canvas(self)
        self.freq_toolbar = NavigationToolbar(self.freq_canvas, self)
        self.freq_viz_layout.addWidget(self.freq_toolbar)
        self.freq_viz_layout.addWidget(self.freq_canvas, stretch=1)
        self.viz_tabs.addTab(self.freq_viz_tab, "频域可视化")
        
        # 时域相关性可视化
        self.time_corr_tab = QWidget()
        self.time_corr_layout = QVBoxLayout(self.time_corr_tab)
        self.time_corr_canvas = create_canvas(self)
        self.time_corr_toolbar = NavigationToolbar(self.time_corr_canvas, self)
        self.time_corr_layout.addWidget(self.time_corr_toolbar)
        self.time_corr_layout.addWidget(self.time_corr_canvas, stretch=1)
        self.viz_tabs.addTab(self.time_corr_tab, "时域相关性")
        
        # 频域相关性可视化
        self.freq_corr_tab = QWidget()
        self.freq_corr_layout = QVBoxLayout(self.freq_corr_tab)
        self.freq_corr_canvas = create_canvas(self)
        self.freq_corr_toolbar = NavigationToolbar(self.freq_corr_canvas, self)
        self.freq_corr_layout.addWidget(self.freq_corr_toolbar)
        self.freq_corr_layout.addWidget(self.freq_corr_canvas, stretch=1)
        self.viz_tabs.addTab(self.freq_corr_tab, "频域相关性")
        
        # 敏感性排序表
        self.sensitivity_tab = QWidget()
        self.sensitivity_layout = QVBoxLayout(self.sensitivity_tab)
        self.sensitivity_table = QTableWidget()
        self.sensitivity_table.setColumnCount(3)
        self.sensitivity_table.setHorizontalHeaderLabels(['通道', 'Kb (相关性系数)', '敏感性排名'])
        self.sensitivity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sensitivity_layout.addWidget(self.sensitivity_table)
        self.viz_tabs.addTab(self.sensitivity_tab, "敏感性排序")
        
        right_layout.addWidget(self.viz_tabs, stretch=1)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])
        
        main_layout.addWidget(splitter)
    
    def _get_num_channels(self, data):
        data = np.asarray(data)
        if len(data.shape) == 1:
            return 1
        return data.shape[1]
    
    def load_data(self, data_type):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{data_type}数据文件", "", 
                                              "TDMS Files (*.tdms);;All Files (*)")
        if path:
            try:
                data, fs, meta = load_data(path)
                meta['fs'] = fs
                if data_type == 'exp1':
                    self.exp1_data = data
                    self.exp1_meta = meta
                    self.exp1_file_edit.setText(os.path.basename(path))
                    self.exp1_state_mapper.set_data(data)
                elif data_type == 'exp2':
                    self.exp2_data = data
                    self.exp2_meta = meta
                    self.exp2_file_edit.setText(os.path.basename(path))
                    self.exp2_state_mapper.set_data(data)
                elif data_type == 'bg1':
                    self.bg1_data = data
                    self.bg1_meta = meta
                    self.bg1_file_edit.setText(os.path.basename(path))
                    self.bg1_state_mapper.set_data(data)
                elif data_type == 'bg2':
                    self.bg2_data = data
                    self.bg2_meta = meta
                    self.bg2_file_edit.setText(os.path.basename(path))
                    self.bg2_state_mapper.set_data(data)
                
                log(f"[Azimuth] 加载{data_type}数据: {len(data)} samples, {self._get_num_channels(data)} channels, fs={fs}")
                self.check_data_ready()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载{data_type}数据失败: {e}")
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.exp1_state_mapper.refresh_states(names)
        self.bg1_state_mapper.refresh_states(names)
        self.exp2_state_mapper.refresh_states(names)
        self.bg2_state_mapper.refresh_states(names)
    
    def check_data_ready(self):
        all_data = [self.exp1_data, self.exp2_data, self.bg1_data, self.bg2_data]
        if all(d is not None for d in all_data):
            n_chs = [self._get_num_channels(d) for d in all_data]
            fss = [
                self.exp1_meta.get('fs', 1.0),
                self.exp2_meta.get('fs', 1.0),
                self.bg1_meta.get('fs', 1.0),
                self.bg2_meta.get('fs', 1.0)
            ]
            
            if len(set(n_chs)) != 1:
                QMessageBox.warning(self, "错误", 
                    f"通道数不匹配！\n实验组1: {n_chs[0]} 通道\n实验组2: {n_chs[1]} 通道\n背景组1: {n_chs[2]} 通道\n背景组2: {n_chs[3]} 通道")
                self.apply_slice_btn.setEnabled(False)
                return
            
            fs_ref = fss[0]
            fs_mismatch = False
            for i, fs in enumerate(fss):
                if abs(fs - fs_ref) / fs_ref > 1e-6:
                    fs_mismatch = True
                    break
            if fs_mismatch:
                QMessageBox.warning(self, "错误", 
                    f"采样率不匹配！\n实验组1: {fss[0]} Hz\n实验组2: {fss[1]} Hz\n背景组1: {fss[2]} Hz\n背景组2: {fss[3]} Hz")
                self.apply_slice_btn.setEnabled(False)
                return
            
            self.fs = fss[0]
            self.n_channels = n_chs[0]
            self.channels = [f"CH{i+1}" for i in range(self.n_channels)]
            self.apply_slice_btn.setEnabled(True)
    
    def apply_time_slice(self):
        start_time = self.slice_start_spin.value()
        end_time = self.slice_end_spin.value()
        
        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "结束时间必须大于起始时间")
            return
        
        fs = self.fs
        start_idx = int(start_time * fs)
        end_idx = int(end_time * fs)
        
        self.exp1_sliced = self.exp1_data[start_idx:end_idx]
        self.exp2_sliced = self.exp2_data[start_idx:end_idx]
        self.bg1_sliced = self.bg1_data[start_idx:end_idx]
        self.bg2_sliced = self.bg2_data[start_idx:end_idx]
        
        log(f"[Azimuth] 时间切片: {start_time}s - {end_time}s, {len(self.exp1_sliced)} samples")
        self.apply_bg_btn.setEnabled(True)
    
    def apply_background_subtraction(self):
        method = self.bg_method_combo.currentText()
        
        self.dbg1_data = []
        self.dbg2_data = []
        
        for ch in range(self.n_channels):
            if self.n_channels > 1:
                exp1_ch = self.exp1_sliced[:, ch].flatten()
                exp2_ch = self.exp2_sliced[:, ch].flatten()
                bg1_ch = self.bg1_sliced[:, ch].flatten()
                bg2_ch = self.bg2_sliced[:, ch].flatten()
            else:
                exp1_ch = self.exp1_sliced.flatten()
                exp2_ch = self.exp2_sliced.flatten()
                bg1_ch = self.bg1_sliced.flatten()
                bg2_ch = self.bg2_sliced.flatten()
            
            min_len1 = min(len(exp1_ch), len(bg1_ch))
            min_len2 = min(len(exp2_ch), len(bg2_ch))
            
            exp1_ch = exp1_ch[:min_len1]
            bg1_ch = bg1_ch[:min_len1]
            exp2_ch = exp2_ch[:min_len2]
            bg2_ch = bg2_ch[:min_len2]
            
            dbg1 = subtract_background(exp1_ch, bg1_ch, method)
            dbg2 = subtract_background(exp2_ch, bg2_ch, method)
            
            self.dbg1_data.append(dbg1)
            self.dbg2_data.append(dbg2)
        
        if self.n_channels > 1:
            self.dbg1_data = np.column_stack(self.dbg1_data)
            self.dbg2_data = np.column_stack(self.dbg2_data)
        else:
            self.dbg1_data = np.array(self.dbg1_data[0])
            self.dbg2_data = np.array(self.dbg2_data[0])
        
        self.compute_freq_domain()
        self.compute_corr_btn.setEnabled(True)
        self.gen_report_btn.setEnabled(True)
        
        QMessageBox.information(self, "完成", "背景对消已完成")
    
    def compute_freq_domain(self):
        n_ch = self.n_channels
        self.dbg1_freq = []
        self.dbg2_freq = []
        
        for ch in range(n_ch):
            if n_ch > 1:
                dbg1_ch = self.dbg1_data[:, ch].flatten()
                dbg2_ch = self.dbg2_data[:, ch].flatten()
            else:
                dbg1_ch = self.dbg1_data.flatten()
                dbg2_ch = self.dbg2_data.flatten()
            
            self.dbg1_freq.append(get_spectrum(dbg1_ch, self.fs))
            self.dbg2_freq.append(get_spectrum(dbg2_ch, self.fs))
    
    def compute_correlation(self):
        method = self.corr_method_combo.currentText()
        is_time_domain = method in TIME_DOMAIN_METHODS
        
        self.correlation_results = {}
        self.sensitivity_results = []
        
        for i, ch in enumerate(self.channels):
            if self.n_channels > 1:
                dbg1_ch = self.dbg1_data[:, i].flatten()
                dbg2_ch = self.dbg2_data[:, i].flatten()
            else:
                dbg1_ch = self.dbg1_data.flatten()
                dbg2_ch = self.dbg2_data.flatten()
            
            try:
                if is_time_domain:
                    result = compute_time_similarity_batch(dbg1_ch, dbg2_ch, [method], fs=self.fs)
                else:
                    result = compute_freq_similarity_batch(dbg1_ch, dbg2_ch, [method], fs=self.fs)
                
                kb = result[0]['value'] if result and result[0].get('ok', False) else 0.0
                
                self.correlation_results[ch] = {
                    'Kb': kb,
                    'dbg1_data': dbg1_ch,
                    'dbg2_data': dbg2_ch,
                    'dbg1_freq': self.dbg1_freq[i],
                    'dbg2_freq': self.dbg2_freq[i]
                }
                
                self.sensitivity_results.append({
                    'channel': ch,
                    'Kb': kb,
                    'index': i
                })
                
            except Exception as e:
                log(f"[Azimuth] 通道 {ch} 相关性计算失败: {e}")
                self.correlation_results[ch] = {'Kb': 0}
        
        self.sensitivity_results.sort(key=lambda x: x['Kb'])
        
        self.display_sensitivity_table()
        self.visualize_all()
    
    def display_sensitivity_table(self):
        self.sensitivity_table.setRowCount(len(self.sensitivity_results))
        
        for row, item in enumerate(self.sensitivity_results):
            self.sensitivity_table.setItem(row, 0, QTableWidgetItem(item['channel']))
            self.sensitivity_table.setItem(row, 1, QTableWidgetItem(f"{item['Kb']:.6f}"))
            self.sensitivity_table.setItem(row, 2, QTableWidgetItem(str(row + 1)))
    
    def find_secondary_slice(self):
        all_spectra = self.dbg1_freq + self.dbg2_freq
        if not all_spectra:
            return 0, 100
        
        avg_spectrum = np.mean(all_spectra, axis=0)
        max_idx = np.argmax(avg_spectrum)
        freq_step = self.fs / len(avg_spectrum)
        peak_freq = max_idx * freq_step
        
        if peak_freq > 0:
            cycle_period = 1 / peak_freq
            window_duration = 7 * cycle_period
        else:
            window_duration = 0.1
        
        n_samples = len(self.dbg1_data)
        max_start = max(0, n_samples - int(window_duration * self.fs))
        start_sample = max_start // 2
        
        return start_sample, start_sample + int(window_duration * self.fs)
    
    def visualize_all(self):
        self.visualize_time_domain()
        self.visualize_freq_domain()
        self.visualize_time_correlation()
        self.visualize_freq_correlation()
    
    def visualize_time_domain(self):
        start_idx, end_idx = self.find_secondary_slice()
        
        fig = self.time_canvas.figure
        fig.clear()
        
        n_rows = self.n_channels
        n_cols = 2
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        for i in range(n_rows):
            for j in range(n_cols):
                ax = fig.add_subplot(gs[i, j])
                if j == 0:
                    if self.n_channels > 1:
                        data = self.dbg1_data[start_idx:end_idx, i].flatten()
                    else:
                        data = self.dbg1_data[start_idx:end_idx].flatten()
                    t = np.linspace(start_idx/self.fs, end_idx/self.fs, len(data))
                    ax.plot(t, data, linewidth=1.0, color='#FF9800')
                else:
                    if self.n_channels > 1:
                        data = self.dbg2_data[start_idx:end_idx, i].flatten()
                    else:
                        data = self.dbg2_data[start_idx:end_idx].flatten()
                    t = np.linspace(start_idx/self.fs, end_idx/self.fs, len(data))
                    ax.plot(t, data, linewidth=1.0, color='#2196F3')
                
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, self.channels[i], transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel("信号值", fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel("时间(s)", fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
        
        gs_top = fig.add_gridspec(1, n_cols, top=0.98, bottom=0.95)
        ax_bg_title = fig.add_subplot(gs_top[0, 0])
        ax_bg_title.text(0.5, 0.5, '去背景状态1', ha='center', va='center', fontsize=12, fontweight='bold', color='#E65100')
        ax_bg_title.set_axis_off()
        
        ax_exp_title = fig.add_subplot(gs_top[0, 1])
        ax_exp_title.text(0.5, 0.5, '去背景状态2', ha='center', va='center', fontsize=12, fontweight='bold', color='#1565C0')
        ax_exp_title.set_axis_off()
        
        fig.suptitle(f"去背景时域二次切片对比（时间范围: {start_idx/self.fs:.3f}s - {end_idx/self.fs:.3f}s）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.time_canvas.draw()
    
    def visualize_freq_domain(self):
        fig = self.freq_canvas.figure
        fig.clear()
        
        n_rows = self.n_channels
        n_cols = 2
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        for i in range(n_rows):
            for j in range(n_cols):
                ax = fig.add_subplot(gs[i, j])
                if j == 0:
                    data = self.dbg1_freq[i]
                    f = np.linspace(0, self.fs/2, len(data))
                    ax.semilogy(f, data, linewidth=1.0, color='#FF9800')
                else:
                    data = self.dbg2_freq[i]
                    f = np.linspace(0, self.fs/2, len(data))
                    ax.semilogy(f, data, linewidth=1.0, color='#2196F3')
                
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_xlim(0, self.fs/2)
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, self.channels[i], transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel("功率谱密度", fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel("频率(Hz)", fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
        
        gs_top = fig.add_gridspec(1, n_cols, top=0.98, bottom=0.95)
        ax_bg_title = fig.add_subplot(gs_top[0, 0])
        ax_bg_title.text(0.5, 0.5, '去背景状态1', ha='center', va='center', fontsize=12, fontweight='bold', color='#E65100')
        ax_bg_title.set_axis_off()
        
        ax_exp_title = fig.add_subplot(gs_top[0, 1])
        ax_exp_title.text(0.5, 0.5, '去背景状态2', ha='center', va='center', fontsize=12, fontweight='bold', color='#1565C0')
        ax_exp_title.set_axis_off()
        
        fig.suptitle("去背景频域对比", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.freq_canvas.draw()
    
    def visualize_time_correlation(self):
        fig = self.time_corr_canvas.figure
        fig.clear()
        
        if not self.sensitivity_results:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("时域相关性", fontsize=14)
            self.time_corr_canvas.draw()
            return
        
        sorted_channels = [r['channel'] for r in self.sensitivity_results]
        n_channels = len(sorted_channels)
        n_cols = 2
        n_rows = (n_channels + n_cols - 1) // n_cols
        
        if n_channels == 0:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("时域相关性", fontsize=14)
            self.time_corr_canvas.draw()
            return
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        idx = 0
        for i in range(n_rows):
            for j in range(n_cols):
                if idx >= n_channels:
                    break
                ch = sorted_channels[idx]
                ax = fig.add_subplot(gs[i, j])
                
                result = self.correlation_results.get(ch, {})
                dbg1_data = result.get('dbg1_data', [])
                dbg2_data = result.get('dbg2_data', [])
                
                if len(dbg1_data) > 0 and len(dbg2_data) > 0:
                    ax.scatter(dbg1_data[:500], dbg2_data[:500], s=3, alpha=0.4, color='#2196F3')
                
                kb = result.get('Kb', 0)
                ka = result.get('Ka', 0)
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, f"{ch}", transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                ax.text(0.02, 0.02, f"Kb={kb:.4f}\nKa={ka:.4f}", 
                        transform=ax.transAxes, 
                        ha='left', va='bottom', fontsize=6,
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel('去背景状态2', fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel('去背景状态1', fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
                
                idx += 1
        
        fig.suptitle(f"时域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.time_corr_canvas.draw()
    
    def visualize_freq_correlation(self):
        fig = self.freq_corr_canvas.figure
        fig.clear()
        
        if not self.sensitivity_results:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("频域相关性", fontsize=14)
            self.freq_corr_canvas.draw()
            return
        
        sorted_channels = [r['channel'] for r in self.sensitivity_results]
        n_channels = len(sorted_channels)
        n_cols = 2
        n_rows = (n_channels + n_cols - 1) // n_cols
        
        if n_channels == 0:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, '请先计算相关性', ha='center', va='center')
            ax.set_axis_off()
            fig.suptitle("频域相关性", fontsize=14)
            self.freq_corr_canvas.draw()
            return
        
        fig_height = n_rows * 2.8
        fig_width = 16.0
        if fig_height > 40:
            fig_height = 40
        fig.set_size_inches(fig_width, fig_height)
        
        gs = fig.add_gridspec(n_rows, n_cols, hspace=0.6, wspace=0.5)
        
        idx = 0
        for i in range(n_rows):
            for j in range(n_cols):
                if idx >= n_channels:
                    break
                ch = sorted_channels[idx]
                ax = fig.add_subplot(gs[i, j])
                
                result = self.correlation_results.get(ch, {})
                dbg1_freq = result.get('dbg1_freq', [])
                dbg2_freq = result.get('dbg2_freq', [])
                
                if len(dbg1_freq) > 0 and len(dbg2_freq) > 0:
                    ax.scatter(dbg1_freq, dbg2_freq, s=3, alpha=0.4, color='#2196F3')
                
                kb = result.get('Kb', 0)
                ka = result.get('Ka', 0)
                ax.tick_params(axis='both', labelsize=6, pad=3)
                ax.grid(True, alpha=0.2, linestyle='--')
                ax.set_facecolor('#f8f9fa')
                ax.text(0.98, 0.98, f"{ch}", transform=ax.transAxes,
                        ha='right', va='top', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                  edgecolor='#ccc', alpha=0.9))
                ax.text(0.02, 0.02, f"Kb={kb:.4f}\nKa={ka:.4f}", 
                        transform=ax.transAxes, 
                        ha='left', va='bottom', fontsize=6,
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
                
                if j == 0:
                    ax.set_ylabel('去背景状态2频谱', fontsize=7, labelpad=4)
                else:
                    ax.set_yticklabels([])
                
                if i == n_rows - 1:
                    ax.set_xlabel('去背景状态1频谱', fontsize=7, labelpad=4)
                else:
                    ax.set_xticklabels([])
                
                idx += 1
        
        fig.suptitle(f"频域相关性（按Kb升序排列，相关性越小敏感性越高）", fontsize=14, fontweight='bold', y=1.02)
        fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.98, hspace=0.6, wspace=0.5)
        self.freq_corr_canvas.draw()
    
    def browse_report_dir(self):
        from PyQt5.QtWidgets import QFileDialog
        from experiment_state import REPORT_MANAGER
        
        dir_path = QFileDialog.getExistingDirectory(self, "选择报告保存目录")
        if dir_path:
            REPORT_MANAGER.set_report_dir(dir_path)
            log(f"[Basic/Azimuth] 报告目录已设置: {dir_path}")
    
    def refresh_experiment_states(self):
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        if hasattr(self, 'exp_state_mapper'):
            self.exp_state_mapper.refresh_states(names)
            self.bg_state_mapper.refresh_states(names)
        elif hasattr(self, 'exp1_state_mapper'):
            self.exp1_state_mapper.refresh_states(names)
            self.bg1_state_mapper.refresh_states(names)
            self.exp2_state_mapper.refresh_states(names)
            self.bg2_state_mapper.refresh_states(names)
    
    def push_experiment_state(self, state_name):
        if hasattr(self, 'exp_state_mapper'):
            self.exp_state_mapper.set_state(state_name)
        elif hasattr(self, 'exp1_state_mapper'):
            self.exp1_state_mapper.set_state(state_name)
        log(f"[Basic/Azimuth] 接收推送的实验状态: {state_name}")
    
    def check_experiment_state_associated(self):
        if hasattr(self, 'exp_state_mapper'):
            exp_state = self.exp_state_mapper.get_selected_state()
            bg_state = self.bg_state_mapper.get_selected_state()
            if not exp_state or not bg_state:
                QMessageBox.warning(self, "提示", 
                    "请为实验组和背景组关联实验状态！\n\n" +
                    f"实验组状态: {'已关联' if exp_state else '未关联'}\n" +
                    f"背景组状态: {'已关联' if bg_state else '未关联'}\n\n" +
                    "请在实验状态定义Tab中定义实验状态，并通过推送或下拉菜单关联。")
                return False
        elif hasattr(self, 'exp1_state_mapper'):
            exp1_state = self.exp1_state_mapper.get_selected_state()
            bg1_state = self.bg1_state_mapper.get_selected_state()
            exp2_state = self.exp2_state_mapper.get_selected_state()
            bg2_state = self.bg2_state_mapper.get_selected_state()
            if not exp1_state or not bg1_state or not exp2_state or not bg2_state:
                QMessageBox.warning(self, "提示", 
                    "请为所有实验组和背景组关联实验状态！\n\n" +
                    f"实验组1状态: {'已关联' if exp1_state else '未关联'}\n" +
                    f"背景组1状态: {'已关联' if bg1_state else '未关联'}\n" +
                    f"实验组2状态: {'已关联' if exp2_state else '未关联'}\n" +
                    f"背景组2状态: {'已关联' if bg2_state else '未关联'}\n\n" +
                    "请在实验状态定义Tab中定义实验状态，并通过推送或下拉菜单关联。")
                return False
        return True
    
    def add_report_block(self):
        if not self.sensitivity_results:
            QMessageBox.warning(self, "提示", "请先计算相关性")
            return
        
        if not self.check_experiment_state_associated():
            return
        
        try:
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import save_figure_to_file
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            md_content = f"## 敏感性分析报告\n\n"
            md_content += "### 1. 实验状态定义\n\n"
            
            from experiment_state import STATE_REGISTRY
            state_names = []
            exp_state_name = self.exp_state_mapper.get_state_name()
            bg_state_name = self.bg_state_mapper.get_state_name()
            if exp_state_name:
                state_names.append(exp_state_name)
            if bg_state_name and bg_state_name != exp_state_name:
                state_names.append(bg_state_name)
            
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"| 参数 | 值 |\n"
            md_content += f"|------|----|\n"
            md_content += f"| 采样率 | {self.fs:.0f} Hz |\n"
            md_content += f"| 通道数 | {self.n_channels} |\n"
            md_content += f"| 时间切片 | {self.slice_start_spin.value():.2f}s - {self.slice_end_spin.value():.2f}s |\n"
            md_content += f"| 相关性算法 | {self.corr_method_combo.currentText()} |\n\n"
            
            md_content += "### 2. 通道敏感性分析（左背景右实验）\n\n"
            md_content += "> **左列**: 背景数据 | **右列**: 实验数据\n\n"
            
            from plot_utils import calc_figsize
            import matplotlib.pyplot as plt
            
            all_images = []
            
            if hasattr(self, 'display_slice_start'):
                start_time = self.display_slice_start
                end_time = self.display_slice_end
            else:
                start_idx, end_idx = self.find_secondary_slice()
                start_time = start_idx / self.fs
                end_time = end_idx / self.fs
            
            slice_start = self.slice_start_spin.value()
            offset_start = int((start_time - slice_start) * self.fs)
            offset_end = int((end_time - slice_start) * self.fs)
            
            for i, channel_name in enumerate(self.channels):
                n_subplots = 3
                n_cols = 2
                figsize = calc_figsize(n_subplots * 2, n_cols=n_cols)
                fig, axes = plt.subplots(n_subplots, n_cols, figsize=figsize)
                
                t = np.linspace(start_time, end_time, 
                               len(self.bg_sliced[offset_start:offset_end, i].flatten()) 
                               if self.n_channels > 1 else len(self.bg_sliced[offset_start:offset_end].flatten()))
                
                if self.n_channels > 1:
                    bg_data = self.bg_sliced[offset_start:offset_end, i].flatten()
                    exp_data = self.exp_sliced[offset_start:offset_end, i].flatten()
                else:
                    bg_data = self.bg_sliced[offset_start:offset_end].flatten()
                    exp_data = self.exp_sliced[offset_start:offset_end].flatten()
                
                axes[0, 0].plot(t, bg_data, linewidth=1.0, color='orange')
                axes[0, 0].set_title(f"背景组", fontsize=10)
                axes[0, 0].tick_params(axis='both', labelsize=8)
                
                axes[0, 1].plot(t, exp_data, linewidth=1.0)
                axes[0, 1].set_title(f"实验组", fontsize=10)
                axes[0, 1].tick_params(axis='both', labelsize=8)
                
                from scipy import signal
                f_bg, Pxx_bg = signal.welch(bg_data, fs=self.fs, nperseg=min(len(bg_data), 1024))
                f_exp, Pxx_exp = signal.welch(exp_data, fs=self.fs, nperseg=min(len(exp_data), 1024))
                
                axes[1, 0].semilogy(f_bg, Pxx_bg, linewidth=1.0, color='orange')
                axes[1, 0].set_title(f"背景组频谱", fontsize=10)
                axes[1, 0].set_xlim(0, self.fs/2)
                axes[1, 0].tick_params(axis='both', labelsize=8)
                
                axes[1, 1].semilogy(f_exp, Pxx_exp, linewidth=1.0)
                axes[1, 1].set_title(f"实验组频谱", fontsize=10)
                axes[1, 1].set_xlim(0, self.fs/2)
                axes[1, 1].tick_params(axis='both', labelsize=8)
                
                corr_value = self.sensitivity_results[i].get('Kb', 0)
                axes[2, 0].text(0.5, 0.5, f"相关性系数\nKb = {corr_value:.6f}", 
                               ha='center', va='center', fontsize=10)
                axes[2, 0].set_axis_off()
                
                axes[2, 1].text(0.5, 0.5, f"敏感性排名\n第{i+1}名", 
                               ha='center', va='center', fontsize=10)
                axes[2, 1].set_axis_off()
                
                fig.suptitle(f"通道 {channel_name} - 敏感性分析", fontsize=12)
                fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])
                
                path = os.path.join(report_dir, f"sensitivity_{channel_name}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                all_images.append(path)
                
                md_content += f"#### 通道 {channel_name}\n\n"
                md_content += f"![通道 {channel_name}](sensitivity_{channel_name}.png)\n\n"
            
            md_content += "### 3. 敏感性排序\n\n"
            md_content += f"> **敏感性判断**: 相关性越小(Kb越小)，敏感性越高。\n\n"
            
            if hasattr(self.sensitivity_results[0], 'Ka'):
                md_content += f"| 排名 | 通道 | Ka (频域峰值差) | Kb (相关性系数) |\n"
                md_content += f"|------|------|----------------|----------------|\n"
                for rank, item in enumerate(self.sensitivity_results, 1):
                    md_content += f"| {rank} | {item['channel']} | {item['Ka']:.6f} | {item['Kb']:.6f} |\n"
            else:
                md_content += f"| 排名 | 通道 | Kb (相关性系数) |\n"
                md_content += f"|------|------|----------------|\n"
                for rank, item in enumerate(self.sensitivity_results, 1):
                    md_content += f"| {rank} | {item['channel']} | {item['Kb']:.6f} |\n"
            md_content += "\n"
            
            block = ReportBlock(
                title=f"敏感性分析 - {self.exp_state_mapper.get_state_name()}",
                content=md_content,
                images=all_images
            )
            
            REPORT_MANAGER.add_block(block)
            QMessageBox.information(self, "成功", 
                f"已添加报告BLOCK到Markdown报告Tab\n标题: {block.title}")
            
        except Exception as e:
            log(f"[Basic/Azimuth] 添加报告BLOCK失败: {e}")
            import traceback
            log(f"[Basic/Azimuth] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}")
    
    def generate_report(self):
        try:
            from experiment_state import REPORT_MANAGER
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先在报告Tab设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            md_content = f"## 方位差异敏感性分析报告\n\n"
            
            md_content += "### 1. 实验状态定义\n\n"
            
            from experiment_state import STATE_REGISTRY
            state_names = []
            
            exp1_state_name = self.exp1_state_mapper.get_state_name()
            bg1_state_name = self.bg1_state_mapper.get_state_name()
            exp2_state_name = self.exp2_state_mapper.get_state_name()
            bg2_state_name = self.bg2_state_mapper.get_state_name()
            
            for name in [exp1_state_name, bg1_state_name, exp2_state_name, bg2_state_name]:
                if name and name not in state_names:
                    state_names.append(name)
            
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"| 参数 | 值 |\n"
            md_content += f"|------|----|\n"
            md_content += f"| 采样率 | {self.fs:.0f} Hz |\n"
            md_content += f"| 通道数 | {self.n_channels} |\n"
            md_content += f"| 时间切片 | {self.slice_start_spin.value():.2f}s - {self.slice_end_spin.value():.2f}s |\n"
            md_content += f"| 背景对消算法 | {self.bg_method_combo.currentText()} |\n"
            md_content += f"| 相关性算法 | {self.corr_method_combo.currentText()} |\n\n"
            
            md_content += "### 2. 可视化结果\n\n"
            
            md_content += "#### 2.1 去背景时域二次切片对比\n\n"
            md_content += f"![时域对比](azimuth_time_viz.png)\n\n"
            md_content += f"**说明**: 显示各通道去背景实验状态1与状态2的时域信号对比，二次切片范围为 {self.find_secondary_slice()[0]/self.fs:.3f}s - {self.find_secondary_slice()[1]/self.fs:.3f}s。\n\n"
            
            md_content += "#### 2.2 去背景频域对比\n\n"
            md_content += f"![频域对比](azimuth_freq_viz.png)\n\n"
            md_content += "**说明**: 显示各通道去背景实验状态1与状态2的频域频谱对比。\n\n"
            
            md_content += "#### 2.3 时域相关性\n\n"
            md_content += f"![时域相关性](azimuth_time_corr.png)\n\n"
            md_content += "**说明**: 各通道去背景实验状态1与状态2的时域散点图，按敏感性(Kb)降序排列。\n\n"
            
            md_content += "#### 2.4 频域相关性\n\n"
            md_content += f"![频域相关性](azimuth_freq_corr.png)\n\n"
            md_content += "**说明**: 各通道去背景实验状态1与状态2的频域散点图，按敏感性(Kb)降序排列。\n\n"
            
            md_content += "### 3. 敏感性排序\n\n"
            md_content += f"> **敏感性判断**: 去背景实验状态1与状态2越不相关(Kb越小)，通道对方位差异越敏感。\n\n"
            md_content += f"| 排名 | 通道 | Kb (相关性系数) |\n"
            md_content += f"|------|------|----------------|\n"
            
            for rank, item in enumerate(self.sensitivity_results, 1):
                md_content += f"| {rank} | {item['channel']} | {item['Kb']:.6f} |\n"
            
            md_content += "\n"
            
            report_path = os.path.join(report_dir, "azimuth_diff_sensitivity_report.md")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            from report_manager import save_figure_to_file
            save_figure_to_file(self.time_canvas.figure, os.path.join(report_dir, "azimuth_time_viz.png"))
            save_figure_to_file(self.freq_canvas.figure, os.path.join(report_dir, "azimuth_freq_viz.png"))
            save_figure_to_file(self.time_corr_canvas.figure, os.path.join(report_dir, "azimuth_time_corr.png"))
            save_figure_to_file(self.freq_corr_canvas.figure, os.path.join(report_dir, "azimuth_freq_corr.png"))
            
            QMessageBox.information(self, "完成", f"报告已生成: {report_path}")
            
        except Exception as e:
            log(f"[Azimuth] 生成报告失败: {e}")
            QMessageBox.warning(self, "错误", f"生成报告失败: {e}")


class ChannelSensitivityTab(QWidget):
    """Tab9: 通道敏感性分析"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.subtabs = QTabWidget()
        
        self.subtab_a = BasicResponseSensitivityTab()
        self.subtabs.addTab(self.subtab_a, "基础响应敏感性分析")
        
        self.subtab_b = AzimuthDiffSensitivityTab()
        self.subtabs.addTab(self.subtab_b, "方位差异敏感性分析")
        
        main_layout.addWidget(self.subtabs)
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态（供主窗口调用）"""
        self.subtab_a.refresh_experiment_states()
        self.subtab_b.refresh_experiment_states()
