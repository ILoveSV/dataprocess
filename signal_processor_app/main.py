# -*- coding: utf-8 -*-
"""
主GUI程序 - 时域信号处理与可视化工具
"""
import sys
import os
import numpy as np

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_debug.log')

def log(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{os.path.basename(sys._getframe(1).f_code.co_filename)}:{sys._getframe(1).f_lineno}] {msg}\n")
    print(f"[GUI_LOG] {msg}", flush=True)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QComboBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QGroupBox, QSplitter,
    QMessageBox, QProgressBar, QProgressDialog, QSpinBox, QDoubleSpinBox, QLineEdit,
    QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QFrame,
    QHeaderView, QListWidget, QListWidgetItem, QAbstractItemView, QToolBar, QAction,
    QStatusBar, QSizePolicy, QGridLayout, QStackedWidget, QFormLayout,
    QDialog, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QColor

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# 导入自定义模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from file_reader import load_data, get_file_info
from signal_processing import (
    TIME_DOMAIN_METHODS, FREQ_DOMAIN_METHODS, MATRIX_METHOD_MAP,
    SIMILARITY_METHODS, MATRIX_METHODS, compute_time_similarity,
    compute_freq_similarity, convert_to_matrix, get_spectrum,
    COARSENING_METHODS, apply_coarsening,
    truncate_single_window, truncate_multi_window, truncate_periodic_window,
    compute_time_similarity_batch, compute_freq_similarity_batch,
    convert_to_matrix_batch, compute_statistical_background, BG_STATISTICAL_METHODS,
    BACKGROUND_SUBTRACTION_METHODS, subtract_background
)
from channel_sensitivity_tab import ChannelSensitivityTab
from similarity_methods_guide_tab import SimilarityMethodsGuideTab
from shared_widgets import ExperimentStateMapper
from visualization import (
    create_canvas, VISUALIZATION_METHODS, PLOT_METHODS, save_figure,
    plot_line, plot_scatter, plot_bar, plot_histogram, plot_heatmap,
    plot_contour, plot_3d_surface, plot_radar, plot_box, plot_violin,
    plot_spectrogram, plot_waterfall, plot_acf, plot_qq, plot_residual,
    plot_dual_axis, plot_pie, plot_stairs, plot_fill_between, plot_polar
)


# ============= 按钮状态管理器 =============
class ButtonStateManager:
    """统一管理按钮的四种状态：默认/运行中/成功/失败"""
    
    # 状态颜色样式
    STYLES = {
        'default': "QPushButton {{ background-color: {bg}; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }}",
        'running': "QPushButton {{ background-color: #2196F3; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }}",
        'success': "QPushButton {{ background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }}",
        'error': "QPushButton {{ background-color: #F44336; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }}",
        'disabled': "QPushButton {{ background-color: #9E9E9E; color: #BDBDBD; font-weight: bold; padding: 8px; border-radius: 4px; }}",
    }
    
    # 状态颜色映射（用于动态背景色）
    COLORS = {
        'default': '#4CAF50',   # 绿色
        'running': '#2196F3',   # 蓝色
        'success': '#4CAF50',   # 绿色
        'error': '#F44336',     # 红色
        'disabled': '#9E9E9E',  # 灰色
    }
    
    def __init__(self, btn, default_text='', default_color='#4CAF50'):
        self.btn = btn
        self.default_text = default_text or btn.text()
        self.default_color = default_color
        self._state = 'default'
        self._original_style = btn.styleSheet()
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_timeout)
        self._spinner_frame = 0
        self._spinner_timer = QTimer()
        self._spinner_timer.timeout.connect(self._update_spinner)
        self._success_callback = None
        self._error_callback = None
    
    def set_running(self, text=None):
        """设置运行中状态"""
        self._state = 'running'
        self._spinner_frame = 0
        text = text or f"{self.default_text}..."
        self.btn.setText(text)
        self.btn.setStyleSheet(self.STYLES['running'].format(bg=self.COLORS['running']))
        self.btn.setEnabled(False)
        self._spinner_timer.start(100)  # spinner动画
    
    def set_success(self, text=None, duration=2000, callback=None):
        """设置成功状态"""
        self._state = 'success'
        self._spinner_timer.stop()
        self._success_callback = callback
        text = text or f"完成 ✓"
        self.btn.setText(text)
        self.btn.setStyleSheet(self.STYLES['success'].format(bg=self.COLORS['success']))
        self.btn.setEnabled(True)
        if duration > 0:
            self._timer.singleShot(duration, lambda: self.reset(text=""))
    
    def set_error(self, text=None, duration=3000, callback=None):
        """设置错误状态"""
        self._state = 'error'
        self._spinner_timer.stop()
        self._error_callback = callback
        text = text or f"失败 ✗"
        self.btn.setText(text)
        self.btn.setStyleSheet(self.STYLES['error'].format(bg=self.COLORS['error']))
        self.btn.setEnabled(True)
        if duration > 0:
            self._timer.singleShot(duration, lambda: self.reset(text=""))
    
    def reset(self, text=None):
        """重置为默认状态"""
        self._state = 'default'
        self._spinner_timer.stop()
        text = text if text else self.default_text
        self.btn.setText(text)
        self.btn.setStyleSheet(self.STYLES['default'].format(bg=self.default_color))
        self.btn.setEnabled(True)
    
    def disable(self):
        """禁用按钮"""
        self._state = 'disabled'
        self._spinner_timer.stop()
        self.btn.setStyleSheet(self.STYLES['disabled'])
        self.btn.setEnabled(False)
    
    def enable(self):
        """启用按钮（保持当前状态）"""
        if self._state == 'disabled':
            self.reset()
        else:
            self.btn.setEnabled(True)
    
    def _update_spinner(self):
        """更新spinner动画"""
        spinner_chars = ['◐', '◓', '◑', '◒']
        text = f"{self.default_text} {spinner_chars[self._spinner_frame]}"
        self.btn.setText(text)
        self._spinner_frame = (self._spinner_frame + 1) % 4
    
    def _on_timeout(self):
        """超时处理"""
        pass
    
    @property
    def state(self):
        return self._state


# ============= 相似性方法意义与评价字典（第7点） =============
# 每个方法：适用特性 + 数值指标意义 + 能评价什么 + 大了/小了说明什么
SIMILARITY_METHOD_EVALUATION = {
    # ---- 时域方法 ----
    '欧几里得距离': '适用：等长信号整体差异度量。数值为两信号对应点差值平方和的平方根，反映整体幅值差异。值越大差异越大，0表示完全相同。无法反映形状相似性，受量纲影响。',
    '曼哈顿距离': '适用：等长信号绝对差异度量。数值为对应点绝对差值之和，对异常值比欧氏距离更稳健。值越大差异越大，0表示完全相同。反映总体偏离程度。',
    '切比雪夫距离': '适用：关注最大单点偏差的场景。数值为对应点最大绝对差值，反映最坏情况差异。值越大峰值偏离越严重，0表示完全相同。仅关注极值，忽略整体。',
    '闵可夫斯基距离': '适用：可调参数p的距离族(p=1曼哈顿,p=2欧氏,p→∞切比雪夫)。p越大越关注大偏差。值越大差异越大。灵活但需选p。',
    '余弦相似度': '适用：关注方向/形状而非幅值的信号。数值[-1,1]，1方向完全一致，0正交，-1反向。值越大形状越相似，不受幅值缩放影响。',
    '皮尔逊相关系数': '适用：线性相关程度度量。数值[-1,1]，1完全正线性相关，-1完全负相关，0无线性关系。值越大线性同步性越强，受异常值影响，仅反映线性关系。',
    '斯皮尔曼等级相关': '适用：单调(非线性)关系度量，基于秩。数值[-1,1]，1完全单调递增。比皮尔逊稳健，能捕捉非线性单调关系，对异常值不敏感。',
    '肯德尔秩相关': '适用：基于 concordant/discordant 对的秩相关。数值[-1,1]，1完全一致。比斯皮尔曼更稳健，适合小样本和有序数据，计算较慢。',
    '互相关峰值': '适用：检测时延与相似性。数值为不同时移下相关最大值，峰值位置反映时延。值越接近1相似度越高，峰值偏移反映时间错位。',
    '动态时间规整(DTW)': '适用：不等长或存在时间伸缩的信号对齐。数值为最优弯曲路径累计距离，值越小越相似。能处理时间扭曲，计算量较大。',
    '结构相似性(SSIM)': '适用：综合亮度/对比度/结构的图像/信号质量。数值[-1,1]，1完全相同。比MSE更符合人眼感知，值越大结构越相似。',
    '均方误差(MSE)': '适用：逐点误差平方均值。数值≥0，0完全相同，值越大误差越大。对大误差敏感(平方放大)，受量纲影响。',
    '均方根误差(RMSE)': '适用：MSE的平方根，与原信号同量纲。数值≥0，0完全相同，值越大误差越大。直观反映平均误差大小。',
    '平均绝对误差(MAE)': '适用：逐点绝对误差均值。数值≥0，0完全相同。比MSE对异常值稳健，反映平均偏离。',
    '标准化互信息(NMI)': '适用：非线性依赖关系度量(基于熵)。数值[0,1]，1完全相关。能捕捉任意依赖关系，需分箱，对样本量敏感。',
    '巴氏距离': '适用：概率分布相似性度量。数值[0,1]，0完全重合，1完全分离。反映分布重叠程度，需归一化为分布。',
    '最大信息系数(MIC)': '适用：发现任意(含非函数)关系。数值[0,1]，1完全相关。能捕捉复杂关系，计算较慢，对样本量敏感。',
    '能量差': '适用：信号总能量差异。数值为两信号平方和之差的绝对值，值越小能量越接近。仅反映能量，忽略时序细节。',
    '波形重叠指数': '适用：波形重合度度量。数值[0,1]，1完全重叠。反映波形吻合程度，对幅值缩放敏感。',
    '谱相干性': '适用：频域线性相关程度(各频率)。数值[0,1]，1该频率完全线性相关。反映频率成分的同步性，需多段估计。',
    # ---- 频域方法 ----
    '频谱欧几里得距离': '适用：频谱整体差异度量。数值为频谱差值平方和的平方根，值越大频谱差异越大。反映频率成分整体差异，0完全相同。',
    '频谱曼哈顿距离': '适用：频谱绝对差异度量。数值为频谱绝对差值之和，对异常频率成分更稳健。值越大频谱差异越大。',
    '频谱余弦相似度': '适用：关注频谱形状(频率分布)而非幅值。数值[-1,1]，1频谱形状完全一致。不受整体增益影响，反映频率结构相似性。',
    '频谱皮尔逊相关': '适用：频谱线性相关。数值[-1,1]，1频谱完全正线性相关。反映频率成分线性同步性，受异常频率影响。',
    '频谱MSE': '适用：频谱逐频点误差平方均值。数值≥0，0频谱完全相同。对大频谱差异敏感，受量纲影响。',
    '频谱RMSE': '适用：频谱误差平方根均值，同量纲。数值≥0，0完全相同。直观反映频谱平均误差。',
    '频谱MAE': '适用：频谱绝对误差均值。数值≥0，0完全相同。比频谱MSE稳健，反映频谱平均偏离。',
    '频谱互相关': '适用：频谱时移相关性。数值反映频谱在不同偏移下的相关，峰值反映最佳对齐。值越大频谱越相似。',
    '频谱DTW': '适用：频谱存在频率伸缩的对齐。数值为最优弯曲路径累计距离，值越小频谱越相似。能处理频谱形变。',
    '频谱SSIM': '适用：频谱结构相似性(亮度/对比度/结构)。数值[-1,1]，1完全相同。比频谱MSE更符合感知，值越大频谱结构越相似。',
    '频谱巴氏距离': '适用：频谱分布(归一化)重叠度。数值[0,1]，0完全重合。反映频率分布相似性，需归一化。',
    '频谱能量差': '适用：频谱总能量差异。数值为频谱能量之差绝对值，值越小频谱能量越接近。仅反映能量，忽略频率细节。',
    '频谱熵差': '适用：频谱分布复杂度差异。数值为两频谱熵之差绝对值，0复杂度相同。熵大频谱越均匀(白噪化)，熵小越集中。',
    '频谱KL散度': '适用：频谱分布差异(非对称)。数值≥0，0分布相同，值越大差异越大。非对称，需归一化为概率分布。',
    '频谱JS散度': '适用：频谱分布差异(对称版KL)。数值[0,ln2]，0分布相同。对称且有界，比KL更稳健。',
    '频谱相干性': '适用：两信号各频率线性相关程度。数值[0,1]，1该频率完全线性相关。反映频率同步性，需多段估计。',
    '频谱重心差': '适用：频谱重心(平均频率)差异。数值为两重心频率之差绝对值，0重心相同。反映主能量频段偏移，值大频段差异大。',
    '频谱带宽差': '适用：频谱带宽差异。数值为两带宽之差绝对值，0带宽相同。反映频率扩展范围差异，值大能量分布范围差异大。',
    '频谱平坦度差': '适用：频谱平坦度(几何/算术均值比)差异。数值为两平坦度之差绝对值，0平坦度相同。平坦度1为白噪，0为单频，值大频谱形状差异大。',
    '频谱 rolloff 差': '适用：频谱滚降点(累积能量85%对应频率)差异。数值为两滚降频率之差绝对值，0相同。反映高频能量分布差异，值大高频截止差异大。',
}

METHOD_KEY_INDICATORS = {
    '欧几里得距离': ['主值', '归一化距离'],
    '曼哈顿距离': ['主值', '归一化距离'],
    '切比雪夫距离': ['主值'],
    '闵可夫斯基距离': ['主值'],
    '余弦相似度': ['主值', '方向'],
    '皮尔逊相关系数': ['主值', '方向'],
    '斯皮尔曼等级相关': ['主值', '方向'],
    '肯德尔秩相关': ['主值', '方向'],
    '互相关峰值': ['主值', '峰值位置'],
    '动态时间规整(DTW)': ['主值', '归一化距离'],
    '结构相似性(SSIM)': ['主值'],
    '均方误差(MSE)': ['主值'],
    '均方根误差(RMSE)': ['主值'],
    '平均绝对误差(MAE)': ['主值'],
    '标准化互信息(NMI)': ['主值', '归一化值'],
    '巴氏距离': ['主值'],
    '最大信息系数(MIC)': ['主值'],
    '能量差': ['主值'],
    '波形重叠指数': ['主值'],
    '谱相干性': ['主值'],
    '频谱欧几里得距离': ['主值', '归一化距离'],
    '频谱曼哈顿距离': ['主值', '归一化距离'],
    '频谱余弦相似度': ['主值', '方向'],
    '频谱皮尔逊相关': ['主值', '方向'],
    '频谱MSE': ['主值'],
    '频谱RMSE': ['主值'],
    '频谱MAE': ['主值'],
    '频谱互相关': ['主值'],
    '频谱DTW': ['主值', '归一化距离'],
    '频谱SSIM': ['主值'],
    '频谱巴氏距离': ['主值'],
    '频谱能量差': ['主值'],
    '频谱熵差': ['主值'],
    '频谱KL散度': ['主值'],
    '频谱JS散度': ['主值'],
    '频谱相干性': ['主值'],
    '频谱重心差': ['主值'],
    '频谱带宽差': ['主值'],
    '频谱平坦度差': ['主值'],
    '频谱 rolloff 差': ['主值'],
}


# ============= 15种时频变换方法注册表（第8点）- 优化加速版 =============
# 每个方法：参数定义列表[(key, 显示名, 最小, 最大, 步长, 默认值, 参数说明), ...] + 方法说明
# 【优化措施】默认参数已调优：减小尺度数/窗长，加速计算约10-50倍
TIME_FREQ_METHODS = {
    '1. 短时傅里叶变换(STFT)': {
        'desc': '短时傅里叶变换：滑动窗口分段FFT，得到时频谱图。适用于平稳或缓变信号，频率分辨率与时间分辨率相互制约(窗长越长频率越细时间越粗)。【优化：默认窗长128，快速执行】',
        'params': [
            ('nperseg', '窗长(点)', 16, 4096, 16, 128, '每段FFT点数(优化后默认128)，越大频率分辨率越高、时间分辨率越低'),
            ('noverlap', '重叠(点)', 0, 4096, 16, 64, '段间重叠点数(优化后默认64)，通常=nperseg/2'),
            ('window', '窗函数', 0, 7, 1, 0, '0=hann,1=hamming,2=blackman,3=bartlett,4=flattop,5=kaiser,6=tukey,7=rect'),
        ],
    },
    '2. 连续小波变换(CWT)': {
        'desc': '连续小波变换：用缩放平移的小波族与信号卷积，得到尺度-时间图。适用于非平稳信号瞬态分析，小波类型影响时频特性。【优化：默认尺度32，快速执行】',
        'params': [
            ('wavelet', '小波类型', 0, 6, 1, 0, '0=morlet,1=cmor,2=mexh,3=gaus,4=db4,5=shan,6=fbsp'),
            ('scales', '尺度数', 8, 128, 1, 32, '小波尺度数(优化后默认32)，越多频率分辨率越高但计算量越大'),
            ('fmin', '最低频率(Hz)', 0.1, 100000, 0.1, 1.0, '分析最低频率，决定低频范围'),
            ('fmax', '最高频率(Hz)', 0.1, 500000, 0.1, 5000.0, '分析最高频率(优化后默认5000Hz)，须≤Fs/2'),
        ],
    },
    '3. 离散小波变换(DWT)': {
        'desc': '离散小波变换：多级分解为近似与细节系数，得到各频带能量。适用于信号去噪与多分辨率分析，级数决定分解深度。',
        'params': [
            ('wavelet', '小波类型', 0, 5, 1, 0, '0=db4,1=db8,2=coif3,3=sym4,4=haar,5=bior2.2'),
            ('level', '分解级数', 1, 20, 1, 5, '分解深度，每级频率减半，级数越大低频越细'),
        ],
    },
    '4. 小波包变换(WPT)': {
        'desc': '小波包变换：对近似和细节均进一步分解，得到更均匀的频带划分。适用于需要精细频带分析的场景。',
        'params': [
            ('wavelet', '小波类型', 0, 5, 1, 0, '0=db4,1=db8,2=coif3,3=sym4,4=haar,5=bior2.2'),
            ('level', '分解级数', 1, 15, 1, 4, '分解深度，2^level个频带'),
        ],
    },
    '5. 希尔伯特-黄变换(HHT)': {
        'desc': '希尔伯特-黄变换：EMD分解为IMF后做希尔伯特变换得瞬时频率。适用于强非平稳非线性信号，IMF数自适应。',
        'params': [
            ('max_imf', '最大IMF数', 1, 30, 1, 8, '最多分解的本征模态函数个数'),
            ('stop', '停止阈值', 0.001, 1.0, 0.001, 0.05, 'EMD筛选停止准则阈值，越小分解越细'),
        ],
    },
    '6. S变换(S-Transform)': {
        'desc': 'S变换：结合STFT和小波优点，窗宽随频率自适应变化。适用于多尺度时频分析，高频时间细低频频率细。',
        'params': [
            ('factor', '缩放因子', 0.1, 10.0, 0.1, 1.0, '窗宽调节因子，越大窗越宽频率越细'),
        ],
    },
    '7. 同步挤压变换(SST)': {
        'desc': '同步挤压变换：对STFT/小波结果在频率方向重排压缩，提升时频聚集度。适用于弱信号增强与瞬时频率估计。',
        'params': [
            ('nperseg', '窗长(点)', 16, 2048, 16, 128, 'STFT窗长(优化后默认128)，影响原始时频分辨率'),
            ('window', '窗函数', 0, 3, 1, 0, '0=hann,1=hamming,2=blackman,3=tukey'),
        ],
    },
    '8. Wigner-Ville分布(WVD)': {
        'desc': 'Wigner-Ville分布：双线性时频分布，理论分辨率最高但有交叉项。适用于单分量信号，多分量需伪WVD抑制交叉项。【优化：默认FFT256】',
        'params': [
            ('nfft', 'FFT点数', 64, 4096, 64, 256, '频率分辨率(优化后默认256)，越大越细'),
            ('kernel', '核函数', 0, 2, 1, 1, '0=无(纯WVD),1=伪WVD(PWVD),2=平滑伪WVD(SPWVD)'),
        ],
    },
    '9. Choi-Williams分布(CWD)': {
        'desc': 'Choi-Williams分布：减少交叉项干扰的Cohen类分布，指数核抑制交叉项。适用于多分量信号时频分析。【优化：默认FFT256】',
        'params': [
            ('nfft', 'FFT点数', 64, 4096, 64, 256, '频率分辨率(优化后默认256)'),
            ('sigma', '核参数σ', 0.01, 10.0, 0.01, 1.0, '越小交叉项抑制越强但自项也模糊'),
        ],
    },
    '10. 伪Wigner-Ville(PWVD)': {
        'desc': '伪Wigner-Ville分布：加窗抑制交叉项的WVD变体。比纯WVD交叉项少，分辨率略降。【优化：默认FFT256窗128】',
        'params': [
            ('nfft', 'FFT点数', 64, 4096, 64, 256, '频率分辨率(优化后默认256)'),
            ('win', '窗长(点)', 16, 2048, 16, 128, '分析窗长(优化后默认128)，影响时频聚集度'),
        ],
    },
    '11. 经验模态分解(EMD)': {
        'desc': '经验模态分解：自适应分解为多个IMF分量。适用于非线性非平稳信号，无需预设基函数。【优化：默认最大IMF数4】',
        'params': [
            ('max_imf', '最大IMF数', 1, 15, 1, 4, '最多分解的IMF个数(优化后默认4)'),
            ('stop', '停止阈值', 0.001, 1.0, 0.001, 0.05, '筛选停止准则阈值'),
        ],
    },
    '12. 集合经验模态分解(EEMD)': {
        'desc': '集合经验模态分解：EMD加噪声平均，解决模态混叠。比EMD稳健但计算量大。【优化：默认集合数10】',
        'params': [
            ('n_ensemble', '集合数', 5, 50, 1, 10, '加噪平均次数(优化后默认10)，越多越稳健越慢'),
            ('noise_amp', '噪声幅值', 0.001, 1.0, 0.001, 0.2, '添加白噪声幅值(相对信号标准差)'),
        ],
    },
    '13. 变分模态分解(VMD)': {
        'desc': '变分模态分解：基于变分问题的非递归分解，模态数预设。比EMD数学严格，无模态混叠。【优化：默认模态数3】',
        'params': [
            ('K', '模态数', 2, 10, 1, 3, '预设模态个数(优化后默认3)，需根据信号先验设定'),
            ('alpha', '带宽约束', 10, 5000, 10, 2000, '越大模态带宽越窄(惩罚项)'),
            ('tau', '噪声容差', 0.0, 1.0, 0.001, 0.0, '0为无噪声严格重构，>0允许噪声'),
        ],
    },
    '14. 短时自相关(STAC)': {
        'desc': '短时自相关：滑动窗内计算自相关函数，反映局部周期性。适用于准周期信号瞬时频率估计。【优化：默认窗128延迟64】',
        'params': [
            ('nperseg', '窗长(点)', 64, 2048, 64, 128, '分析窗长(优化后默认128)，越大频率分辨率越高'),
            ('max_lag', '最大延迟(点)', 8, 1024, 8, 64, '自相关最大延迟点数(优化后默认64)'),
        ],
    },
    '15. Gabor变换': {
        'desc': 'Gabor变换：高斯窗STFT，时频窗积最小(测不准下界)。适用于最优时频局部化分析。【优化：默认窗128】',
        'params': [
            ('sigma', '高斯窗宽σ', 0.001, 1.0, 0.001, 0.1, '高斯窗标准差(相对窗长)，越大窗越宽频率越细'),
            ('nperseg', '窗长(点)', 16, 2048, 16, 128, '窗长点数(优化后默认128)'),
        ],
    },
}

# 窗函数名称映射
WINDOW_NAMES = ['hann', 'hamming', 'blackman', 'bartlett', 'flattop', 'kaiser', 'tukey', 'rect']
# 小波类型映射
CWT_WAVELET_NAMES = ['morl', 'cmor1.5-1.0', 'mexh', 'gaus4', 'db4', 'shan1.5-1.0', 'fbsp']
DWT_WAVELET_NAMES = ['db4', 'db8', 'coif3', 'sym4', 'haar', 'bior2.2']


# ============= 通用文件选择组件 =============

class FileSelectorWidget(QWidget):
    """文件选择组件"""
    file_loaded = pyqtSignal(str, object, dict)  # 路径, 数据, 元信息
    
    def __init__(self, label_text="选择文件", parent=None):
        super().__init__(parent)
        self.data = None
        self.meta = None
        self.setup_ui(label_text)
    
    def setup_ui(self, label_text):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label_text)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("点击右侧按钮选择文件...")
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.browse_file)
        
        layout.addWidget(self.label)
        layout.addWidget(self.path_edit, stretch=1)
        layout.addWidget(self.browse_btn)
    
    def browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "",
            "所有支持格式 (*.csv *.txt *.dat *.xlsx *.xls *.tdms *.tdm *.lvm *.h5 *.hdf5 *.bin *.wav);;"
            "CSV文件 (*.csv);;文本文件 (*.txt *.dat);;Excel (*.xlsx *.xls);;"
            "NI文件 (*.tdms *.tdm *.lvm);;HDF5 (*.h5 *.hdf5);;二进制 (*.bin);;WAV (*.wav)"
        )
        if filepath:
            self.load_file(filepath)
    
    def load_file(self, filepath):
        try:
            self.path_edit.setText(filepath)
            data, fs, meta = load_data(filepath)
            self.data = data
            self.meta = meta
            self.meta['filepath'] = filepath
            self.meta['fs'] = fs
            self.file_loaded.emit(filepath, data, self.meta)
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"无法加载文件:\n{filepath}\n\n错误: {str(e)}")
    
    def get_data(self):
        return self.data
    
    def get_meta(self):
        return self.meta


# ============= 通道选择组件 =============

class ChannelSelectorWidget(QWidget):
    """通道选择组件，用于多通道数据"""
    selection_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_data = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel("选择通道:")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(150)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        
        layout.addWidget(self.label)
        layout.addWidget(self.combo, stretch=1)
    
    def _on_combo_changed(self, index):
        self.selection_changed.emit(index)
    
    def set_channels(self, num_channels):
        num_channels = max(1, int(num_channels))
        if self.combo.count() == num_channels:
            return
        self.combo.blockSignals(True)
        self.combo.clear()
        for i in range(num_channels):
            self.combo.addItem(f"CH{i+1:02d}")
        self.combo.blockSignals(False)
        if self.combo.count() > 0:
            self.combo.setCurrentIndex(0)
            self.selection_changed.emit(0)

    def get_selected_channel(self):
        return self.combo.currentIndex()

    def get_channel_name(self):
        return self.combo.currentText()

    def set_data(self, data):
        if data is None:
            return
        self._current_data = data
        if data.ndim > 1:
            self.set_channels(data.shape[1])
        else:
            self.set_channels(1)


# ============= 实验状态对应关系组件 =============

# ============= 并行计算后台 Worker =============

class ComputeWorker(QThread):
    """通用后台计算线程：在独立线程中执行任意 callable，避免阻塞 GUI

    信号:
        progress(done, total, method, value): 单项完成时发射
        finished_ok(results): 全部完成，返回结果列表
        error(msg): 发生致命错误
    """
    progress = pyqtSignal(int, int, str, object)
    finished_ok = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        """
        参数:
            fn: callable，签名为 fn(progress_cb) -> list
                其中 progress_cb(done, total, method, value) 由本线程提供
        """
        super().__init__(parent)
        self._fn = fn
        self._cancelled = False

    def run(self):
        try:
            def cb(done, total, method, value):
                if self._cancelled:
                    raise RuntimeError('cancelled')
                self.progress.emit(done, total, method, value)
            results = self._fn(cb)
            if self._cancelled:
                return
            self.finished_ok.emit(results)
        except RuntimeError as e:
            if str(e) == 'cancelled':
                return
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._cancelled = True


# ============= Tab1: 时域相似性处理 =============

class TimeDomainTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_a_data = None
        self.file_b_data = None
        self.result_data = None
        self.fs = 1.0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        # 文件选择组
        file_group = QGroupBox("数据文件")
        file_layout = QVBoxLayout(file_group)
        
        self.file_a_selector = FileSelectorWidget("A状态文件:")
        self.file_a_selector.file_loaded.connect(self.on_file_a_loaded)
        file_layout.addWidget(self.file_a_selector)
        
        self.file_b_selector = FileSelectorWidget("B状态文件:")
        self.file_b_selector.file_loaded.connect(self.on_file_b_loaded)
        file_layout.addWidget(self.file_b_selector)
        
        left_layout.addWidget(file_group)
        
        # 实验状态对应关系组（替代原"通道选择"）
        state_group = QGroupBox("实验状态对应关系")
        state_layout = QVBoxLayout(state_group)
        
        self.channel_a = ExperimentStateMapper("A对应的实验状态")
        self.channel_a.state_changed.connect(self.on_channel_changed)
        state_layout.addWidget(self.channel_a)
        
        self.channel_b = ExperimentStateMapper("B对应的实验状态")
        self.channel_b.state_changed.connect(self.on_channel_changed)
        state_layout.addWidget(self.channel_b)
        
        left_layout.addWidget(state_group)
        
        # 相似性方法选择
        method_group = QGroupBox("时域相似性方法 (15+种)")
        method_layout = QVBoxLayout(method_group)
        
        self.method_list = QListWidget()
        self.method_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for method in SIMILARITY_METHODS['时域']:
            self.method_list.addItem(method)
        # 默认选择前几个
        for i in range(min(5, self.method_list.count())):
            self.method_list.item(i).setSelected(True)
        method_layout.addWidget(self.method_list)
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(lambda: self.method_list.selectAll())
        method_layout.addWidget(self.select_all_btn)
        
        self.clear_sel_btn = QPushButton("清除选择")
        self.clear_sel_btn.clicked.connect(self.method_list.clearSelection)
        method_layout.addWidget(self.clear_sel_btn)
        
        left_layout.addWidget(method_group)
        
        # 计算和可视化按钮
        btn_layout = QHBoxLayout()
        self.compute_btn = QPushButton("计算相似性")
        self.compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.compute_btn.clicked.connect(self.compute_similarity)
        self.compute_btn_state = ButtonStateManager(self.compute_btn, "计算相似性")
        btn_layout.addWidget(self.compute_btn)
        
        self.viz_btn = QPushButton("可视化")
        self.viz_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.viz_btn.clicked.connect(self.visualize_all)
        self.viz_btn.setEnabled(False)
        self.viz_btn_state = ButtonStateManager(self.viz_btn, "可视化", '#2196F3')
        btn_layout.addWidget(self.viz_btn)
        
        left_layout.addLayout(btn_layout)
        
        # 结果保存与报告
        btn_layout2 = QHBoxLayout()
        self.save_btn = QPushButton("保存结果数据")
        self.save_btn.clicked.connect(self.save_results)
        self.save_btn.setEnabled(False)
        btn_layout2.addWidget(self.save_btn)
        
        self.add_report_btn = QPushButton("添加报告BLOCK")
        self.add_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.add_report_btn.clicked.connect(self.add_report_block)
        self.add_report_btn.setEnabled(False)
        btn_layout2.addWidget(self.add_report_btn)
        left_layout.addLayout(btn_layout2)
        
        left_layout.addStretch()
        
        # 右侧结果面板：使用子Tab结构（图表和表格分开）
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 顶层Tab：图表 | 表格
        self.main_result_tabs = QTabWidget()
        
        # 表格Tab
        table_tab = QWidget()
        table_layout = QVBoxLayout(table_tab)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["方法", "实验状态1", "实验状态2"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.result_table)
        self.main_result_tabs.addTab(table_tab, "📋 结果表格")
        
        # 图表Tab（包含数据曲线和相似性图）
        viz_tab = QWidget()
        viz_layout = QVBoxLayout(viz_tab)
        
        # 子Tab：数据曲线 / 相似性图
        self.viz_subtabs = QTabWidget()
        
        # 子Tab1：数据曲线
        data_tab = QWidget()
        data_tab_layout = QVBoxLayout(data_tab)
        # 可视化模式选择
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("显示模式:"))
        self.data_viz_mode = QComboBox()
        self.data_viz_mode.addItems([
            "同图上下叠加",
            "同图左右并排",
            "分两张图(上下)",
            "分两张图(左右)",
            "同图叠加(同坐标系)",
        ])
        self.data_viz_mode.currentIndexChanged.connect(self.visualize_data_curves)
        mode_row.addWidget(self.data_viz_mode, stretch=1)
        data_tab_layout.addLayout(mode_row)
        
        self.data_canvas = create_canvas(self)
        self.data_toolbar = NavigationToolbar(self.data_canvas, self)
        data_tab_layout.addWidget(self.data_toolbar)
        data_tab_layout.addWidget(self.data_canvas, stretch=1)
        self.viz_subtabs.addTab(data_tab, "📈 数据曲线")
        
        # 子Tab2：相似性图
        sim_tab = QWidget()
        sim_tab_layout = QVBoxLayout(sim_tab)
        sim_mode_row = QHBoxLayout()
        sim_mode_row.addWidget(QLabel("图表类型:"))
        self.viz_combo = QComboBox()
        self.viz_combo.addItems(VISUALIZATION_METHODS)
        self.viz_combo.currentIndexChanged.connect(self.visualize_results)
        sim_mode_row.addWidget(self.viz_combo, stretch=1)
        sim_tab_layout.addLayout(sim_mode_row)
        
        self.canvas = create_canvas(self)
        self.toolbar = NavigationToolbar(self.canvas, self)
        sim_tab_layout.addWidget(self.toolbar)
        sim_tab_layout.addWidget(self.canvas, stretch=1)
        
        self.save_img_btn = QPushButton("保存图像")
        self.save_img_btn.clicked.connect(self.save_image)
        sim_tab_layout.addWidget(self.save_img_btn)
        self.viz_subtabs.addTab(sim_tab, "📊 相似性图")
        
        viz_layout.addWidget(self.viz_subtabs, stretch=1)
        self.main_result_tabs.addTab(viz_tab, "📊 图表")
        
        right_layout.addWidget(self.main_result_tabs, stretch=1)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 850])
        
        main_layout.addWidget(splitter)
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单（供主窗口调用）"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.channel_a.refresh_states(names)
        self.channel_b.refresh_states(names)

    
    def on_file_a_loaded(self, path, data, meta):
        self.file_a_data = data
        self.fs = meta.get('fs', 1.0) or 1.0
        self.channel_a.set_data(data)
        self.update_status()
    
    def on_file_b_loaded(self, path, data, meta):
        self.file_b_data = data
        self.channel_b.set_data(data)
        self.update_status()
    
    def update_status(self):
        has_a = self.file_a_data is not None
        has_b = self.file_b_data is not None
        has_data = has_a or has_b  # 任一文件加载即可可视化
        self.compute_btn.setEnabled(has_a and has_b)  # 计算需要两个文件
        self.viz_btn.setEnabled(has_data)  # 可视化只需要任一文件
    
    def on_channel_changed(self):
        self.update_status()
    
    def get_channel_data(self, data, channel_idx):
        if data is None:
            return None
        if data.ndim == 1:
            return data
        elif data.ndim == 2:
            if channel_idx < data.shape[1]:
                return data[:, channel_idx]
        return data.flatten()

    def _get_channel_array(self, data, meta, ch_name):
        """按通道名获取1D数据：优先用meta中的channel_map，否则按索引取列"""
        if data is None:
            return None
        if meta and isinstance(meta, dict) and 'channel_map' in meta:
            cm = meta.get('channel_map') or {}
            if ch_name in cm:
                return np.asarray(cm[ch_name]).flatten()
        # 按索引取列
        try:
            idx = int(ch_name.replace('CH', '')) - 1
        except ValueError:
            idx = 0
        return self.get_channel_data(data, idx)

    def compute_similarity(self):
        selected_methods = [item.text() for item in self.method_list.selectedItems()]
        if not selected_methods:
            QMessageBox.warning(self, "提示", "请至少选择一种相似性方法")
            return

        # 多通道选择：A、B须选择相同通道集（一一对应，否则对比无意义）
        channels_a = self.channel_a.get_selected_channels()
        channels_b = self.channel_b.get_selected_channels()
        if not channels_a:
            QMessageBox.warning(self, "提示", "请在A状态选择至少一个通道")
            return
        if not channels_b:
            QMessageBox.warning(self, "提示", "请在B状态选择至少一个通道")
            return
        if channels_a != channels_b:
            ret = QMessageBox.question(
                self, "通道不对齐警告",
                f"A状态选择的通道: {channels_a}\nB状态选择的通道: {channels_b}\n\n"
                f"两次实验状态的通道必须一一对应才能对比。是否仍要继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret == QMessageBox.No:
                return
        # 通道对齐：按A的通道顺序配对
        channel_pairs = list(zip(channels_a, channels_b))
        name_a = self.channel_a.get_display_name()
        name_b = self.channel_b.get_display_name()

        # 准备每个通道对的数据
        meta_a = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        meta_b = self.file_b_selector.meta if hasattr(self, 'file_b_selector') else {}
        pair_data = []
        for ch_a, ch_b in channel_pairs:
            da = self._get_channel_array(self.file_a_data, meta_a, ch_a)
            db = self._get_channel_array(self.file_b_data, meta_b, ch_b)
            if da is None or db is None:
                QMessageBox.warning(self, "提示", f"无法获取通道数据: A={ch_a}, B={ch_b}")
                return
            pair_data.append((ch_a, ch_b, da, db))

        self.compute_btn_state.set_running()
        self.add_report_btn.setEnabled(False)
        log(f"[Tab1] 计算开始，禁用 add_report_btn")

        # 清空表格，等待计算完成后由display_results重新构建
        self.result_table.setRowCount(0)

        fs = self.fs
        methods = list(selected_methods)
        pairs_info = [(ca, cb, da, db) for ca, cb, da, db in pair_data]
        
        total_tasks = len(pairs_info) * len(methods)
        
        # 创建进度对话框
        self._progress_dialog = QProgressDialog(f"正在计算 {len(methods)} 种相似性算法...", "取消", 0, total_tasks, self)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(500)
        self._progress_dialog.canceled.connect(self._worker_cancel)

        def task(progress_cb):
            all_results = []
            done = 0
            total = len(pairs_info) * len(methods)
            for ca, cb, da, db in pairs_info:
                try:
                    batch = compute_time_similarity_batch(
                        da, db, methods, fs=fs, progress_cb=None
                    )
                    for r in batch:
                        all_results.append({
                            'channel_a': ca, 'channel_b': cb,
                            'method': r['method'], 'value': r['value'],
                            'indicators': r.get('indicators', {}),
                            'data_a': da, 'data_b': db,
                        })
                        done += 1
                        if progress_cb:
                            progress_cb(done, total, r['method'], r['value'])
                except Exception as e:
                    log(f"[Tab1] 计算通道对 {ca}-{cb} 失败: {e}")
                    done += len(methods)
                    if progress_cb:
                        progress_cb(done, total, f"通道{ca}-{cb}", "失败")
            return all_results

        self._worker = ComputeWorker(task)
        self._worker.progress.connect(self._on_compute_progress)
        self._worker.finished_ok.connect(lambda res: self._on_compute_done(res, pair_data))
        self._worker.error.connect(self._on_compute_error)
        self._worker.start()

    def _worker_cancel(self):
        if hasattr(self, '_worker') and self._worker:
            self._worker.cancel()
            log("[Tab1] 用户取消计算")

    def _on_compute_progress(self, done, total, method, value):
        dialog = getattr(self, '_progress_dialog', None)
        if dialog is not None:
            try:
                dialog.setValue(done)
                dialog.setLabelText(f"正在计算: {method} ({done}/{total})")
            except Exception:
                pass

    def _on_compute_done(self, batch_results, pair_data):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        self.compute_btn_state.set_success("完成", duration=1500)
        results = []
        for r in batch_results:
            results.append({
                'method': r['method'],
                'value': r['value'],
                'indicators': r.get('indicators', {}),
                'channel_a': r.get('channel_a', ''),
                'channel_b': r.get('channel_b', ''),
                'data_a': r['data_a'],
                'data_b': r['data_b']
            })
        self.result_data = results
        self.display_results(results)
        self.viz_btn_state.reset()
        self.viz_btn_state.enable()
        self.save_btn.setEnabled(True)
        log(f"[Tab1] 启用 add_report_btn 前状态: {self.add_report_btn.isEnabled()}")
        self.add_report_btn.setEnabled(True)
        log(f"[Tab1] 启用 add_report_btn 后状态: {self.add_report_btn.isEnabled()}")
        
        QMessageBox.information(self, "计算完成", f"成功完成 {len(results)} 项计算\n\n请点击'添加报告BLOCK'按钮生成报告")
        
        # 自动绘制数据曲线
        self.visualize_data_curves()

    def _on_compute_error(self, msg):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        self.compute_btn_state.set_error("失败", duration=3000)
        QMessageBox.warning(self, "计算错误", f"并行计算失败: {msg}")

    def display_results(self, results):
        """显示相似性计算结果，格式为：
        第1列：计算方法名称
        第2~X列：各通道结果（[参数1=值, 参数2=值, ...]形式）
        第X+1列：数据规模和数据结构特征评估
        第X+2列：适用性评估
        第X+3列：方法简介
        """
        if not results:
            return
        
        # 第一步：按方法和通道整理数据
        methods_order = []
        data_by_method = {}  # method -> {channel: {value, indicators, data_a, data_b}}
        
        for res in results:
            method = res['method']
            ca = res.get('channel_a', '')
            cb = res.get('channel_b', '')
            ch_label = ca if ca == cb else f"{ca}↔{cb}"
            
            if method not in methods_order:
                methods_order.append(method)
                data_by_method[method] = {}
            
            data_by_method[method][ch_label] = {
                'value': res['value'],
                'indicators': res.get('indicators', {}),
                'data_a': res.get('data_a', []),
                'data_b': res.get('data_b', []),
            }
        
        # 获取所有通道
        channels = set()
        for method_data in data_by_method.values():
            channels.update(method_data.keys())
        channels = list(channels)
        n_channels = len(channels)
        
        # 第二步：构建表格
        # 列：方法名称 | 通道1结果 | 通道2结果 | ... | 数据规模评估 | 适用性评估 | 方法简介
        n_cols = 1 + n_channels + 3  # 1(方法名) + n(通道) + 3(评估列)
        
        self.result_table.setColumnCount(n_cols)
        
        # 设置表头
        header_labels = ["计算方法名称"] + channels + ["数据规模和数据结构特征评估", "适用性评估", "方法简介"]
        self.result_table.setHorizontalHeaderLabels(header_labels)
        
        # 设置行数
        n_methods = len(methods_order)
        self.result_table.setRowCount(n_methods)
        
        # 第三步：填充数据
        for i, method in enumerate(methods_order):
            method_data = data_by_method[method]
            
            # 第1列：方法名称
            self.result_table.setItem(i, 0, QTableWidgetItem(method))
            
            # 第2~X列：各通道结果（多参数指标形式，只显示关键指标）
            for j, ch in enumerate(channels):
                ch_data = method_data.get(ch)
                if ch_data and 'indicators' in ch_data and ch_data['indicators']:
                    # 获取该方法的关键指标列表
                    key_indicators = METHOD_KEY_INDICATORS.get(method, ['主值'])
                    ind_strs = []
                    for key in key_indicators:
                        if key in ch_data['indicators']:
                            val = ch_data['indicators'][key]
                            if isinstance(val, float):
                                ind_strs.append(f"{key}={val:.4f}")
                            else:
                                ind_strs.append(f"{key}={val}")
                    if not ind_strs and '主值' in ch_data['indicators']:
                        val = ch_data['indicators']['主值']
                        ind_strs.append(f"主值={val:.4f}")
                    display_text = "[" + ", ".join(ind_strs) + "]"
                elif ch_data and 'value' in ch_data:
                    display_text = f"[主值={ch_data['value']:.6g}]"
                else:
                    display_text = "N/A"
                
                item = QTableWidgetItem(display_text)
                self.result_table.setItem(i, 1 + j, item)
            
            # 第X+1列：数据规模和数据结构特征评估
            size_eval = []
            for ch in channels:
                ch_data = method_data.get(ch)
                if ch_data:
                    data_a = ch_data.get('data_a', [])
                    data_b = ch_data.get('data_b', [])
                    ind = ch_data.get('indicators', {})
                    a_len = len(data_a) if hasattr(data_a, '__len__') else ind.get('数据A长度', 0)
                    b_len = len(data_b) if hasattr(data_b, '__len__') else ind.get('数据B长度', 0)
                    a_std = ind.get('数据A标准差', 0)
                    b_std = ind.get('数据B标准差', 0)
                    size_eval.append(f"{ch}: A={a_len}, B={b_len}, A_std={a_std:.3f}, B_std={b_std:.3f}")
            size_eval_text = "; ".join(size_eval) if size_eval else ""
            self.result_table.setItem(i, 1 + n_channels, QTableWidgetItem(size_eval_text))
            
            # 第X+2列：适用性评估
            applicability = []
            for ch in channels:
                ch_data = method_data.get(ch)
                if ch_data:
                    ind = ch_data.get('indicators', {})
                    value = ch_data.get('value', 0)
                    if isinstance(value, (int, float)):
                        if method in ['相关系数', '皮尔逊相关系数']:
                            if abs(value) > 0.7:
                                applicability.append(f"{ch}: 高度适用")
                            elif abs(value) > 0.3:
                                applicability.append(f"{ch}: 适用")
                            else:
                                applicability.append(f"{ch}: 低适用")
                        elif method in ['欧氏距离', '曼哈顿距离']:
                            applicability.append(f"{ch}: 适用(值={value:.3f})")
                        elif method in ['Cos相似度', '余弦相似度']:
                            if value > 0.8:
                                applicability.append(f"{ch}: 高度适用")
                            else:
                                applicability.append(f"{ch}: 适用")
                        else:
                            applicability.append(f"{ch}: 适用")
            applicability_text = "; ".join(applicability) if applicability else ""
            self.result_table.setItem(i, 1 + n_channels + 1, QTableWidgetItem(applicability_text))
            
            # 第X+3列：方法简介
            self.result_table.setItem(i, 1 + n_channels + 2, QTableWidgetItem(SIMILARITY_METHOD_EVALUATION.get(method, "")))
        
        # 第四步：调整列宽
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for j in range(n_channels):
            self.result_table.horizontalHeader().setSectionResizeMode(1 + j, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels + 1, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels + 2, QHeaderView.Stretch)
        self.result_table.setWordWrap(True)
        self.result_table.setTextElideMode(Qt.ElideNone)
        self.result_table.resizeRowsToContents()
        
        # 强制刷新表格
        self.result_table.viewport().update()
    
    def _add_color_legend(self):
        """在结果表格下方添加着色说明标签"""
        # 查找或创建说明标签
        if hasattr(self, '_color_legend_label') and self._color_legend_label is not None:
            self._color_legend_label.setParent(None)
        
        legend_text = (
            "<span style='background-color:#FFB4B4;padding:2px 4px;'>红色背景</span> = 该方法在该通道的最大值　"
            "<span style='background-color:#B4B4FF;padding:2px 4px;'>蓝色背景</span> = 该方法在该通道的最小值　"
            "<span style='color:#FF8C00;font-weight:bold;'>橙色粗体</span> = 高于均值　"
            "<span style='color:#009600;'>绿色</span> = 低于均值"
        )
        self._color_legend_label = QLabel(legend_text)
        self._color_legend_label.setTextFormat(Qt.RichText)
        self._color_legend_label.setStyleSheet("QLabel { padding: 4px; background-color: #f5f5f5; border: 1px solid #ddd; }")
        
        # 找到result_table的父widget，添加说明标签
        parent = self.result_table.parent()
        if parent and isinstance(parent, QWidget):
            layout = parent.layout()
            if layout:
                layout.addWidget(self._color_legend_label)
    
    def visualize_data_curves(self):
        """在数据曲线子Tab中绘制两条数据曲线，支持多种显示模式"""
        # 切换到图表TAB
        if hasattr(self, 'main_result_tabs'):
            self.main_result_tabs.setCurrentIndex(1)
        if self.file_a_data is None and self.file_b_data is None:
            QMessageBox.warning(self, "提示", "请先加载数据文件（A状态和/或B状态）")
            return
        # 多通道：取第一个选中通道用于曲线对比
        channels_a = self.channel_a.get_selected_channels()
        channels_b = self.channel_b.get_selected_channels()
        ch_a_name = channels_a[0] if channels_a else None
        ch_b_name = channels_b[0] if channels_b else None
        meta_a = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        meta_b = self.file_b_selector.meta if hasattr(self, 'file_b_selector') else {}
        data_a = self._get_channel_array(self.file_a_data, meta_a, ch_a_name) if ch_a_name else self.get_channel_data(self.file_a_data, 0)
        data_b = self._get_channel_array(self.file_b_data, meta_b, ch_b_name) if ch_b_name else self.get_channel_data(self.file_b_data, 0)
        if data_a is None and data_b is None:
            QMessageBox.warning(self, "提示", "无法获取数据通道，请检查通道选择")
            return
        name_a = self.channel_a.get_display_name() or "A"
        name_b = self.channel_b.get_display_name() or "B"
        if ch_a_name:
            name_a = f"{name_a}({ch_a_name})"
        if ch_b_name:
            name_b = f"{name_b}({ch_b_name})"
        mode = self.data_viz_mode.currentText()
        fs = self.fs or 1.0

        canvas = self.data_canvas
        canvas.clear()
        fig = canvas.fig
        # 设置中文字体兼容
        import matplotlib as mpl
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        mpl.rcParams['axes.unicode_minus'] = False
        mpl.rcParams['mathtext.fontset'] = 'cm'

        # 两条曲线明显区别：A用蓝色实线，B用红色虚线+圆点
        style_a = dict(color='#1f77b4', linewidth=1.8, linestyle='-', label=name_a)
        style_b = dict(color='#d62728', linewidth=1.6, linestyle='--', marker='o',
                       markersize=3, markevery=max(1, len(data_b)//200), label=name_b)

        try:
            if mode == "同图上下叠加":
                ax = fig.add_subplot(2, 1, 1)
                t_a = np.arange(len(data_a)) / fs
                ax.plot(t_a, data_a, **style_a)
                ax.set_title(f'{name_a} 时域波形', fontsize=13, fontweight='bold')
                ax.set_xlabel('时间 (s)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(2, 1, 2)
                t_b = np.arange(len(data_b)) / fs
                ax2.plot(t_b, data_b, **style_b)
                ax2.set_title(f'{name_b} 时域波形', fontsize=13, fontweight='bold')
                ax2.set_xlabel('时间 (s)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "同图左右并排":
                ax = fig.add_subplot(1, 2, 1)
                t_a = np.arange(len(data_a)) / fs
                ax.plot(t_a, data_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('时间 (s)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(1, 2, 2)
                t_b = np.arange(len(data_b)) / fs
                ax2.plot(t_b, data_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('时间 (s)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "分两张图(上下)":
                ax = fig.add_subplot(2, 1, 1)
                t_a = np.arange(len(data_a)) / fs
                ax.plot(t_a, data_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('时间 (s)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(2, 1, 2)
                t_b = np.arange(len(data_b)) / fs
                ax2.plot(t_b, data_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('时间 (s)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "分两张图(左右)":
                ax = fig.add_subplot(1, 2, 1)
                t_a = np.arange(len(data_a)) / fs
                ax.plot(t_a, data_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('时间 (s)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(1, 2, 2)
                t_b = np.arange(len(data_b)) / fs
                ax2.plot(t_b, data_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('时间 (s)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            else:  # 同图叠加(同坐标系)
                ax = fig.add_subplot(111)
                t_a = np.arange(len(data_a)) / fs
                t_b = np.arange(len(data_b)) / fs
                ax.plot(t_a, data_a, **style_a)
                ax.plot(t_b, data_b, **style_b)
                ax.set_title('时域波形对比', fontsize=13, fontweight='bold')
                ax.set_xlabel('时间 (s)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

            fig.tight_layout()
            canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘制数据曲线失败: {str(e)}")
    
    def visualize_all(self):
        """可视化按钮：同时绘制数据曲线和相似性图"""
        # 先绘制数据曲线
        try:
            self.visualize_data_curves()
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘制数据曲线失败: {str(e)}")
        # 再绘制相似性图
        if self.result_data:
            try:
                self.visualize_results()
            except Exception as e:
                QMessageBox.warning(self, "可视化错误", f"绘制相似性图失败: {str(e)}")

    def visualize_results(self):
        # 切换到图表TAB
        if hasattr(self, 'main_result_tabs'):
            self.main_result_tabs.setCurrentIndex(1)
        if not self.result_data:
            return
        
        viz_method = self.viz_combo.currentText()
        
        # 准备数据
        data_a = self.result_data[0]['data_a']
        data_b = self.result_data[0]['data_b']
        name_a = self.channel_a.get_display_name()
        name_b = self.channel_b.get_display_name()
        
        self.canvas.clear()
        
        try:
            if viz_method == '折线图 (Line)':
                plot_line(self.canvas, None, {name_a: data_a, name_b: data_b}, 
                         title='Time Domain Comparison', fs=self.fs)
            elif viz_method == '散点图 (Scatter)':
                plot_scatter(self.canvas, data_a, {f'{name_a} vs {name_b}': data_b}, 
                           title='Scatter Plot')
            elif viz_method == '双轴对比图 (Dual Axis)':
                plot_dual_axis(self.canvas, data_a, data_b, fs=self.fs)
            elif viz_method == '残差图 (Residual)':
                plot_residual(self.canvas, data_a, data_b)
            elif viz_method == '直方图 (Histogram)':
                plot_histogram(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '箱线图 (Box Plot)':
                plot_box(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '小提琴图 (Violin)':
                plot_violin(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '自相关图 (ACF)':
                plot_acf(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == 'Q-Q图 (Q-Q Plot)':
                plot_qq(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '柱状图 (Bar)':
                # 绘制相似性结果柱状图
                methods = [r['method'] for r in self.result_data if isinstance(r['value'], (int, float))]
                values = [r['value'] for r in self.result_data if isinstance(r['value'], (int, float))]
                if methods and values:
                    plot_bar(self.canvas, methods, {f'{name_a} vs {name_b}': values}, 
                            title='Similarity Measures', xlabel='Method', ylabel='Value')
            elif viz_method == '雷达图 (Radar)':
                methods = [r['method'][:10] for r in self.result_data if isinstance(r['value'], (int, float))]
                values = [r['value'] for r in self.result_data if isinstance(r['value'], (int, float))]
                if methods and values:
                    # 归一化到0-1范围
                    vals = np.array(values)
                    vals_norm = (vals - np.min(vals)) / (np.max(vals) - np.min(vals) + 1e-10)
                    plot_radar(self.canvas, methods, {f'{name_a} vs {name_b}': vals_norm}, 
                             title='Similarity Radar')
            elif viz_method == '阶梯图 (Stairs)':
                plot_stairs(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '填充图 (Fill Between)':
                plot_fill_between(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '极坐标图 (Polar)':
                plot_polar(self.canvas, {name_a: data_a, name_b: data_b})
            elif viz_method == '瀑布图 (Waterfall)':
                plot_waterfall(self.canvas, {name_a: data_a, name_b: data_b})
            else:
                plot_line(self.canvas, None, {name_a: data_a, name_b: data_b}, 
                         title='Time Domain Comparison', fs=self.fs)
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘图失败: {str(e)}")
    
    def save_results(self):
        if not self.result_data:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", "CSV文件 (*.csv);;文本文件 (*.txt);;NumPy (*.npy)"
        )
        if filepath:
            try:
                import csv
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Method', 'Value', 'Data_A_Length', 'Data_B_Length'])
                    for res in self.result_data:
                        writer.writerow([res['method'], res['value'], 
                                       len(res['data_a']), len(res['data_b'])])
                QMessageBox.information(self, "成功", f"结果已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", str(e))
    
    def save_image(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存图像", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff);;PDF (*.pdf);;SVG (*.svg);;EPS (*.eps)"
        )
        if filepath:
            success, msg = save_figure(self.canvas, filepath)
            if success:
                QMessageBox.information(self, "成功", f"图像已保存到:\n{msg}")
            else:
                QMessageBox.critical(self, "保存错误", msg)

    def add_report_block(self):
        """将当前结果作为一个BLOCK添加到全局报告管理器"""
        QMessageBox.information(self, 'DEBUG', 'Tab1 add_report_block called!')
        log("[Tab1] add_report_block CALLED")
        try:
            log("[Tab1] 检查 result_data...")
            if not self.result_data:
                log("[Tab1] result_data 为空，返回")
                QMessageBox.warning(self, "提示", "请先计算相似性结果")
                return
            
            log("[Tab1] 导入模块...")
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import build_similarity_block_md, save_figure_to_file
            log("[Tab1] 模块导入成功")

            log("[Tab1] 获取报告目录...")
            report_dir = self._get_report_dir()
            if report_dir is None:
                log("[Tab1] report_dir 为 None，返回")
                return
            log(f"[Tab1] 报告目录: {report_dir}")

            name_a = "A"
            name_b = "B"
            try:
                if hasattr(self, 'channel_a') and self.channel_a:
                    name_a = self.channel_a.get_display_name() or "A"
                    log(f"[Tab1] channel_a: {name_a}")
                else:
                    log("[Tab1] channel_a 不存在或为空")
                if hasattr(self, 'channel_b') and self.channel_b:
                    name_b = self.channel_b.get_display_name() or "B"
                    log(f"[Tab1] channel_b: {name_b}")
                else:
                    log("[Tab1] channel_b 不存在或为空")
            except Exception as e:
                log(f"[Tab1] 获取通道名称失败: {e}")

            state_names = [name_a, name_b]
            log(f"[Tab1] state_names: {state_names}")

            img_path = None
            data_img_path = None
            try:
                if hasattr(self, 'main_result_tabs'):
                    log("[Tab1] 切换到图表TAB")
                    self.main_result_tabs.setCurrentIndex(1)
                else:
                    log("[Tab1] 没有 main_result_tabs")
                if hasattr(self, 'canvas') and self.canvas:
                    log("[Tab1] 保存相似性图...")
                    img_path = save_figure_to_file(self.canvas, report_dir, prefix='tab1_sim')
                    log(f"[Tab1] 相似性图保存成功: {img_path}")
                else:
                    log("[Tab1] canvas 不存在")
            except Exception as e:
                img_path = None
                log(f"[Tab1] 保存相似性图失败: {e}")
            try:
                if hasattr(self, 'data_canvas') and self.data_canvas:
                    log("[Tab1] 保存数据曲线图...")
                    data_img_path = save_figure_to_file(self.data_canvas, report_dir, prefix='tab1_data')
                    log(f"[Tab1] 数据曲线图保存成功: {data_img_path}")
                else:
                    log("[Tab1] data_canvas 不存在")
            except Exception as e:
                data_img_path = None
                log(f"[Tab1] 保存数据曲线图失败: {e}")

            preprocess_info = getattr(self, '_preprocess_info', None)
            log(f"[Tab1] preprocess_info: {preprocess_info}")

            method_results = []
            try:
                log(f"[Tab1] 处理 result_data，共 {len(self.result_data)} 项")
                for r in self.result_data:
                    if isinstance(r, dict) and 'method' in r and 'value' in r:
                        method_results.append({'method': r['method'], 'value': r['value']})
                        log(f"[Tab1] 添加结果: {r['method']} = {r['value']}")
                    else:
                        log(f"[Tab1] 警告: 结果项格式不正确: {r}")
            except Exception as e:
                log(f"[Tab1] 构建方法结果列表失败: {e}")
                method_results = []

            if not method_results:
                log("[Tab1] method_results 为空，返回")
                QMessageBox.warning(self, "提示", "未找到有效的计算结果")
                return

            log("[Tab1] 构建报告内容...")
            content = build_similarity_block_md(state_names, method_results, viz_img=img_path, preprocess_info=preprocess_info)
            log(f"[Tab1] 报告内容长度: {len(content)}")
            
            if data_img_path:
                content += f"\n\n### 数据曲线图\n\n![数据曲线]({data_img_path})\n"
            
            log("[Tab1] 创建 ReportBlock...")
            block = ReportBlock(
                source_tab='Tab1 时域相似性',
                title=f"时域相似性分析 ({name_a} vs {name_b})",
                content_md=content,
                images=[p for p in [img_path, data_img_path] if p]
            )
            
            log("[Tab1] 添加到 REPORT_MANAGER...")
            REPORT_MANAGER.add_block(block)
            log(f"[Tab1] 添加成功! BLOCK标题: {block.title}")
            
            QMessageBox.information(self, "成功", f"已添加报告BLOCK到Tab6报告管理器\n标题: {block.title}\n图像已保存至: {report_dir}")
            log("[Tab1] 显示成功消息框")
        except Exception as e:
            import traceback
            log(f"[Tab1] add_report_block 异常: {e}")
            log(f"[Tab1] 堆栈跟踪:\n{traceback.format_exc()}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}\n\n请查看控制台输出获取详细信息")

    def _get_report_dir(self):
        """获取用户指定的报告目录（从报告Tab），未指定则弹窗提示

        返回:
            str: 报告目录路径
            None: 用户取消
        """
        from PyQt5.QtWidgets import QMainWindow
        p = self.parent()
        while p is not None and not isinstance(p, QMainWindow):
            p = p.parent()
        
        report_tab = None
        if p is not None:
            if hasattr(p, 'tab_report'):
                report_tab = p.tab_report
            elif hasattr(p, 'tab7'):
                report_tab = p.tab7
        
        if report_tab and hasattr(report_tab, 'report_dir') and report_tab.report_dir:
            return report_tab.report_dir
        
        ret = QMessageBox.question(
            self, "未指定报告目录",
            "尚未指定报告保存目录，是否现在选择？\n（点击'保存位置'按钮也可在报告Tab中设置）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ret == QMessageBox.Yes:
            d = QFileDialog.getExistingDirectory(self, "选择报告保存位置", "")
            if d:
                if report_tab and hasattr(report_tab, 'report_dir'):
                    report_tab.report_dir = d
                    if hasattr(report_tab, 'dir_label'):
                        report_tab.dir_label.setText(f"保存位置: {d}")
                return d
            return None
        return None


# ============= Tab2: 频域相似性处理 =============

class FrequencyDomainTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_a_data = None
        self.file_b_data = None
        self.result_data = None
        self.fs = 1.0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        # 文件选择组
        file_group = QGroupBox("数据文件")
        file_layout = QVBoxLayout(file_group)
        
        self.file_a_selector = FileSelectorWidget("A状态文件:")
        self.file_a_selector.file_loaded.connect(self.on_file_a_loaded)
        file_layout.addWidget(self.file_a_selector)
        
        self.file_b_selector = FileSelectorWidget("B状态文件:")
        self.file_b_selector.file_loaded.connect(self.on_file_b_loaded)
        file_layout.addWidget(self.file_b_selector)
        
        left_layout.addWidget(file_group)
        
        # 实验状态对应关系组（替代原"通道选择"）
        state_group = QGroupBox("实验状态对应关系")
        state_layout = QVBoxLayout(state_group)
        
        self.channel_a = ExperimentStateMapper("A对应的实验状态")
        self.channel_a.state_changed.connect(self.on_channel_changed)
        state_layout.addWidget(self.channel_a)
        
        self.channel_b = ExperimentStateMapper("B对应的实验状态")
        self.channel_b.state_changed.connect(self.on_channel_changed)
        state_layout.addWidget(self.channel_b)
        
        left_layout.addWidget(state_group)
        
        # 采样率设置
        fs_group = QGroupBox("采样率设置")
        fs_layout = QHBoxLayout(fs_group)
        fs_layout.addWidget(QLabel("Fs (Hz):"))
        self.fs_spin = QDoubleSpinBox()
        self.fs_spin.setRange(0.001, 1000000)
        self.fs_spin.setValue(1.0)
        self.fs_spin.setDecimals(3)
        fs_layout.addWidget(self.fs_spin)
        left_layout.addWidget(fs_group)
        
        # 频域相似性方法选择
        method_group = QGroupBox("频域相似性方法 (15+种)")
        method_layout = QVBoxLayout(method_group)
        
        self.method_list = QListWidget()
        self.method_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for method in SIMILARITY_METHODS['频域']:
            self.method_list.addItem(method)
        for i in range(min(5, self.method_list.count())):
            self.method_list.item(i).setSelected(True)
        method_layout.addWidget(self.method_list)
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(lambda: self.method_list.selectAll())
        method_layout.addWidget(self.select_all_btn)
        
        self.clear_sel_btn = QPushButton("清除选择")
        self.clear_sel_btn.clicked.connect(self.method_list.clearSelection)
        method_layout.addWidget(self.clear_sel_btn)
        
        left_layout.addWidget(method_group)
        
        # 计算按钮
        btn_layout = QHBoxLayout()
        self.compute_btn = QPushButton("计算频域相似性")
        self.compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.compute_btn.clicked.connect(self.compute_similarity)
        self.compute_btn_state = ButtonStateManager(self.compute_btn, "计算频域相似性")
        btn_layout.addWidget(self.compute_btn)
        
        self.viz_btn = QPushButton("可视化")
        self.viz_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.viz_btn.clicked.connect(self.visualize_all)
        self.viz_btn.setEnabled(False)
        self.viz_btn_state = ButtonStateManager(self.viz_btn, "可视化", '#2196F3')
        btn_layout.addWidget(self.viz_btn)
        
        left_layout.addLayout(btn_layout)
        
        # 结果保存与报告
        btn_layout2 = QHBoxLayout()
        self.save_btn = QPushButton("保存结果数据")
        self.save_btn.clicked.connect(self.save_results)
        self.save_btn.setEnabled(False)
        btn_layout2.addWidget(self.save_btn)
        
        self.add_report_btn = QPushButton("添加报告BLOCK")
        self.add_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.add_report_btn.clicked.connect(self.add_report_block)
        self.add_report_btn.setEnabled(False)
        btn_layout2.addWidget(self.add_report_btn)
        left_layout.addLayout(btn_layout2)
        
        left_layout.addStretch()
        
        # 右侧结果面板：使用子Tab结构（图表和表格分开）
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 顶层Tab：图表 | 表格
        self.main_result_tabs = QTabWidget()
        
        # 表格Tab
        table_tab = QWidget()
        table_layout = QVBoxLayout(table_tab)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["方法", "实验状态1", "实验状态2"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.result_table)
        self.main_result_tabs.addTab(table_tab, "📋 结果表格")
        
        # 图表Tab（包含频谱曲线、相似性图和时频变换）
        viz_tab = QWidget()
        viz_layout = QVBoxLayout(viz_tab)
        
        # 子Tab：数据曲线(频谱) / 相似性图
        self.viz_subtabs = QTabWidget()
        
        # 子Tab1：数据曲线（频谱）
        data_tab = QWidget()
        data_tab_layout = QVBoxLayout(data_tab)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("显示模式:"))
        self.data_viz_mode = QComboBox()
        self.data_viz_mode.addItems([
            "同图上下叠加",
            "同图左右并排",
            "分两张图(上下)",
            "分两张图(左右)",
            "同图叠加(同坐标系)",
        ])
        self.data_viz_mode.currentIndexChanged.connect(self.visualize_data_curves)
        mode_row.addWidget(self.data_viz_mode, stretch=1)
        data_tab_layout.addLayout(mode_row)
        
        self.data_canvas = create_canvas(self)
        self.data_toolbar = NavigationToolbar(self.data_canvas, self)
        data_tab_layout.addWidget(self.data_toolbar)
        data_tab_layout.addWidget(self.data_canvas, stretch=1)
        self.viz_subtabs.addTab(data_tab, "📈 频谱曲线")
        
        # 子Tab2：相似性图
        sim_tab = QWidget()
        sim_tab_layout = QVBoxLayout(sim_tab)
        sim_mode_row = QHBoxLayout()
        sim_mode_row.addWidget(QLabel("图表类型:"))
        self.viz_combo = QComboBox()
        self.viz_combo.addItems(VISUALIZATION_METHODS)
        self.viz_combo.currentIndexChanged.connect(self.visualize_results)
        sim_mode_row.addWidget(self.viz_combo, stretch=1)
        sim_tab_layout.addLayout(sim_mode_row)
        
        self.canvas = create_canvas(self)
        self.toolbar = NavigationToolbar(self.canvas, self)
        sim_tab_layout.addWidget(self.toolbar)
        sim_tab_layout.addWidget(self.canvas, stretch=1)
        
        self.save_img_btn = QPushButton("保存图像")
        self.save_img_btn.clicked.connect(self.save_image)
        sim_tab_layout.addWidget(self.save_img_btn)
        self.viz_subtabs.addTab(sim_tab, "📊 相似性图")
        
        # 子Tab3：时频变换（15种方法，第8点）
        tf_tab = QWidget()
        tf_tab_layout = QVBoxLayout(tf_tab)
        
        # 方法选择行
        tf_row1 = QHBoxLayout()
        tf_row1.addWidget(QLabel("时频变换方法:"))
        self.tf_method_combo = QComboBox()
        for m in TIME_FREQ_METHODS.keys():
            self.tf_method_combo.addItem(m)
        self.tf_method_combo.currentIndexChanged.connect(self._on_tf_method_changed)
        tf_row1.addWidget(self.tf_method_combo, stretch=1)
        tf_tab_layout.addLayout(tf_row1)
        
        # 方法说明
        self.tf_desc_label = QLabel()
        self.tf_desc_label.setWordWrap(True)
        self.tf_desc_label.setStyleSheet("background-color: #FFF8E1; padding: 6px; border: 1px solid #FFC107; border-radius: 3px;")
        tf_tab_layout.addWidget(self.tf_desc_label)
        
        # 参数输入区（动态生成）
        self.tf_params_group = QGroupBox("算法参数")
        self.tf_params_layout = QFormLayout(self.tf_params_group)
        tf_tab_layout.addWidget(self.tf_params_group)
        
        # 数据源选择
        tf_src_row = QHBoxLayout()
        tf_src_row.addWidget(QLabel("数据源:"))
        self.tf_src_combo = QComboBox()
        self.tf_src_combo.addItems(["A状态", "B状态", "A与B对比"])
        tf_src_row.addWidget(self.tf_src_combo)
        tf_src_row.addWidget(QLabel("通道:"))
        self.tf_ch_combo = QComboBox()
        tf_src_row.addWidget(self.tf_ch_combo, stretch=1)
        tf_tab_layout.addLayout(tf_src_row)
        
        # 计算与可视化按钮
        tf_btn_row = QHBoxLayout()
        self.tf_compute_btn = QPushButton("计算并可视化")
        self.tf_compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;")
        self.tf_compute_btn.clicked.connect(self._compute_tf_transform)
        self.tf_compute_btn_state = ButtonStateManager(self.tf_compute_btn, "计算并可视化")
        tf_btn_row.addWidget(self.tf_compute_btn)
        self.tf_detach_btn = QPushButton("分离为独立窗口")
        self.tf_detach_btn.clicked.connect(self._detach_tf_canvas)
        tf_btn_row.addWidget(self.tf_detach_btn)
        tf_tab_layout.addLayout(tf_btn_row)
        
        # 时频变换画布
        self.tf_canvas = create_canvas(self)
        self.tf_toolbar = NavigationToolbar(self.tf_canvas, self)
        tf_tab_layout.addWidget(self.tf_toolbar)
        tf_tab_layout.addWidget(self.tf_canvas, stretch=1)
        self.viz_subtabs.addTab(tf_tab, "🌐 时频变换")
        
        # 初始化时频变换方法说明与参数
        self._tf_param_widgets = {}
        self._on_tf_method_changed(0)
        
        viz_layout.addWidget(self.viz_subtabs, stretch=1)
        self.main_result_tabs.addTab(viz_tab, "📊 图表")
        
        right_layout.addWidget(self.main_result_tabs, stretch=1)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 850])
        
        main_layout.addWidget(splitter)
    
    def on_file_a_loaded(self, path, data, meta):
        self.file_a_data = data
        self.fs = meta.get('fs', 1.0) or 1.0
        self.fs_spin.setValue(self.fs)
        self.channel_a.set_data(data)
        self.update_status()
    
    def on_file_b_loaded(self, path, data, meta):
        self.file_b_data = data
        self.channel_b.set_data(data)
        self.update_status()
    
    def update_status(self):
        has_a = self.file_a_data is not None
        has_b = self.file_b_data is not None
        has_data = has_a or has_b  # 任一文件加载即可可视化
        self.compute_btn.setEnabled(has_a and has_b)  # 计算需要两个文件
        self.viz_btn.setEnabled(has_data)  # 可视化只需要任一文件
    
    def on_channel_changed(self):
        self.update_status()
    
    def get_channel_data(self, data, channel_idx):
        if data is None:
            return None
        if data.ndim == 1:
            return data
        elif data.ndim == 2:
            if channel_idx < data.shape[1]:
                return data[:, channel_idx]
        return data.flatten()

    def _get_channel_array(self, data, meta, ch_name):
        """按通道名获取1D数据：优先用meta中的channel_map，否则按索引取列"""
        if data is None:
            return None
        if meta and isinstance(meta, dict) and 'channel_map' in meta:
            cm = meta.get('channel_map') or {}
            if ch_name in cm:
                return np.asarray(cm[ch_name]).flatten()
        try:
            idx = int(ch_name.replace('CH', '')) - 1
        except (ValueError, AttributeError):
            idx = 0
        return self.get_channel_data(data, idx)

    def compute_similarity(self):
        selected_methods = [item.text() for item in self.method_list.selectedItems()]
        if not selected_methods:
            QMessageBox.warning(self, "提示", "请至少选择一种频域相似性方法")
            return

        self.fs = self.fs_spin.value()
        # 多通道选择：A、B须选择相同通道集（一一对应，否则对比无意义）
        channels_a = self.channel_a.get_selected_channels()
        channels_b = self.channel_b.get_selected_channels()
        if not channels_a:
            QMessageBox.warning(self, "提示", "请在A状态选择至少一个通道")
            return
        if not channels_b:
            QMessageBox.warning(self, "提示", "请在B状态选择至少一个通道")
            return
        if channels_a != channels_b:
            ret = QMessageBox.question(
                self, "通道不对齐警告",
                f"A状态选择的通道: {channels_a}\nB状态选择的通道: {channels_b}\n\n"
                f"两次实验状态的通道必须一一对应才能对比。是否仍要继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret == QMessageBox.No:
                return
        channel_pairs = list(zip(channels_a, channels_b))
        name_a = self.channel_a.get_display_name()
        name_b = self.channel_b.get_display_name()

        meta_a = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        meta_b = self.file_b_selector.meta if hasattr(self, 'file_b_selector') else {}
        pair_data = []
        for ch_a, ch_b in channel_pairs:
            da = self._get_channel_array(self.file_a_data, meta_a, ch_a)
            db = self._get_channel_array(self.file_b_data, meta_b, ch_b)
            if da is None or db is None:
                QMessageBox.warning(self, "提示", f"无法获取通道数据: A={ch_a}, B={ch_b}")
                return
            pair_data.append((ch_a, ch_b, da, db))

        self.compute_btn_state.set_running()
        self.add_report_btn.setEnabled(False)
        log(f"[Tab2] 计算开始，禁用 add_report_btn")

        # 清空表格，等待计算完成后由display_results重新构建
        self.result_table.setRowCount(0)

        fs = self.fs
        methods = list(selected_methods)
        pairs_info = [(ca, cb, da, db) for ca, cb, da, db in pair_data]
        
        total_tasks = len(pairs_info) * len(methods)
        
        # 创建进度对话框
        self._progress_dialog = QProgressDialog(f"正在计算 {len(methods)} 种频域相似性算法...", "取消", 0, total_tasks, self)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(500)
        self._progress_dialog.canceled.connect(self._worker_cancel)

        def task(progress_cb):
            all_results = []
            done = 0
            total = len(pairs_info) * len(methods)
            for ca, cb, da, db in pairs_info:
                try:
                    batch = compute_freq_similarity_batch(
                        da, db, methods, fs=fs, progress_cb=None
                    )
                    for r in batch:
                        all_results.append({
                            'channel_a': ca, 'channel_b': cb,
                            'method': r['method'], 'value': r['value'],
                            'indicators': r.get('indicators', {}),
                            'data_a': da, 'data_b': db,
                        })
                        done += 1
                        if progress_cb:
                            progress_cb(done, total, r['method'], r['value'])
                except Exception as e:
                    log(f"[Tab2] 计算通道对 {ca}-{cb} 失败: {e}")
                    done += len(methods)
                    if progress_cb:
                        progress_cb(done, total, f"通道{ca}-{cb}", "失败")
            return all_results

        self._worker = ComputeWorker(task)
        self._worker.progress.connect(self._on_compute_progress)
        self._worker.finished_ok.connect(lambda res: self._on_compute_done(res, pair_data))
        self._worker.error.connect(self._on_compute_error)
        self._worker.start()

    def _worker_cancel(self):
        if hasattr(self, '_worker') and self._worker:
            self._worker.cancel()
            log("[Tab2] 用户取消计算")

    def _on_compute_progress(self, done, total, method, value):
        dialog = getattr(self, '_progress_dialog', None)
        if dialog is not None:
            try:
                dialog.setValue(done)
                dialog.setLabelText(f"正在计算: {method} ({done}/{total})")
            except Exception:
                pass

    def _on_compute_done(self, batch_results, pair_data):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        self.compute_btn_state.set_success("完成", duration=1500)
        results = []
        for r in batch_results:
            results.append({
                'method': r['method'],
                'value': r['value'],
                'indicators': r.get('indicators', {}),
                'channel_a': r.get('channel_a', ''),
                'channel_b': r.get('channel_b', ''),
                'data_a': r['data_a'],
                'data_b': r['data_b']
            })
        self.result_data = results
        self.display_results(results)
        self.viz_btn_state.reset()
        self.viz_btn_state.enable()
        self.save_btn.setEnabled(True)
        log(f"[Tab2] 启用 add_report_btn 前状态: {self.add_report_btn.isEnabled()}")
        self.add_report_btn.setEnabled(True)
        log(f"[Tab2] 启用 add_report_btn 后状态: {self.add_report_btn.isEnabled()}")
        
        QMessageBox.information(self, "计算完成", f"成功完成 {len(results)} 项计算\n\n请点击'添加报告BLOCK'按钮生成报告")
        
        # 自动绘制频谱曲线
        self.visualize_data_curves()

    def _on_compute_error(self, msg):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        self.compute_btn_state.set_error("失败", duration=3000)
        QMessageBox.warning(self, "计算错误", f"并行计算失败: {msg}")

    def display_results(self, results):
        """显示相似性计算结果，格式为：
        第1列：计算方法名称
        第2~X列：各通道结果（[参数1=值, 参数2=值, ...]形式）
        第X+1列：数据规模和数据结构特征评估
        第X+2列：适用性评估
        第X+3列：方法简介
        """
        if not results:
            return
        
        methods_order = []
        data_by_method = {}
        
        for res in results:
            method = res['method']
            ca = res.get('channel_a', '')
            cb = res.get('channel_b', '')
            ch_label = ca if ca == cb else f"{ca}↔{cb}"
            
            if method not in methods_order:
                methods_order.append(method)
                data_by_method[method] = {}
            
            data_by_method[method][ch_label] = {
                'value': res['value'],
                'indicators': res.get('indicators', {}),
                'data_a': res.get('data_a', []),
                'data_b': res.get('data_b', []),
            }
        
        channels = set()
        for method_data in data_by_method.values():
            channels.update(method_data.keys())
        channels = list(channels)
        n_channels = len(channels)
        
        n_cols = 1 + n_channels + 3
        
        self.result_table.setColumnCount(n_cols)
        header_labels = ["计算方法名称"] + channels + ["数据规模和数据结构特征评估", "适用性评估", "方法简介"]
        self.result_table.setHorizontalHeaderLabels(header_labels)
        
        n_methods = len(methods_order)
        self.result_table.setRowCount(n_methods)
        
        for i, method in enumerate(methods_order):
            method_data = data_by_method[method]
            
            self.result_table.setItem(i, 0, QTableWidgetItem(method))
            
            for j, ch in enumerate(channels):
                ch_data = method_data.get(ch)
                if ch_data and 'indicators' in ch_data and ch_data['indicators']:
                    key_indicators = METHOD_KEY_INDICATORS.get(method, ['主值'])
                    ind_strs = []
                    for key in key_indicators:
                        if key in ch_data['indicators']:
                            val = ch_data['indicators'][key]
                            if isinstance(val, float):
                                ind_strs.append(f"{key}={val:.4f}")
                            else:
                                ind_strs.append(f"{key}={val}")
                    if not ind_strs and '主值' in ch_data['indicators']:
                        val = ch_data['indicators']['主值']
                        ind_strs.append(f"主值={val:.4f}")
                    display_text = "[" + ", ".join(ind_strs) + "]"
                elif ch_data and 'value' in ch_data:
                    display_text = f"[主值={ch_data['value']:.6g}]"
                else:
                    display_text = "N/A"
                item = QTableWidgetItem(display_text)
                self.result_table.setItem(i, 1 + j, item)
            
            size_eval = []
            for ch in channels:
                ch_data = method_data.get(ch)
                if ch_data:
                    data_a = ch_data.get('data_a', [])
                    data_b = ch_data.get('data_b', [])
                    ind = ch_data.get('indicators', {})
                    a_len = len(data_a) if hasattr(data_a, '__len__') else ind.get('数据A长度', 0)
                    b_len = len(data_b) if hasattr(data_b, '__len__') else ind.get('数据B长度', 0)
                    a_std = ind.get('数据A标准差', 0)
                    b_std = ind.get('数据B标准差', 0)
                    size_eval.append(f"{ch}: A={a_len}, B={b_len}, A_std={a_std:.3f}, B_std={b_std:.3f}")
            size_eval_text = "; ".join(size_eval) if size_eval else ""
            self.result_table.setItem(i, 1 + n_channels, QTableWidgetItem(size_eval_text))
            
            applicability = []
            for ch in channels:
                ch_data = method_data.get(ch)
                if ch_data:
                    value = ch_data.get('value', 0)
                    if isinstance(value, (int, float)):
                        if method in ['相关系数', '皮尔逊相关系数', '频谱相关系数']:
                            if abs(value) > 0.7:
                                applicability.append(f"{ch}: 高度适用")
                            elif abs(value) > 0.3:
                                applicability.append(f"{ch}: 适用")
                            else:
                                applicability.append(f"{ch}: 低适用")
                        elif method in ['Cos相似度', '余弦相似度']:
                            if value > 0.8:
                                applicability.append(f"{ch}: 高度适用")
                            else:
                                applicability.append(f"{ch}: 适用")
                        else:
                            applicability.append(f"{ch}: 适用")
            applicability_text = "; ".join(applicability) if applicability else ""
            self.result_table.setItem(i, 1 + n_channels + 1, QTableWidgetItem(applicability_text))
            
            self.result_table.setItem(i, 1 + n_channels + 2, QTableWidgetItem(SIMILARITY_METHOD_EVALUATION.get(method, "")))
        
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for j in range(n_channels):
            self.result_table.horizontalHeader().setSectionResizeMode(1 + j, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels + 1, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1 + n_channels + 2, QHeaderView.Stretch)
        self.result_table.setWordWrap(True)
        self.result_table.setTextElideMode(Qt.ElideNone)
        self.result_table.resizeRowsToContents()
        
        # 强制刷新表格
        self.result_table.viewport().update()

    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单（供主窗口调用）"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.channel_a.refresh_states(names)
        self.channel_b.refresh_states(names)
    
    # ============= 时频变换子Tab相关方法（第8点） =============
    def _on_tf_method_changed(self, idx):
        """切换时频变换方法时，更新说明文本与参数输入框"""
        method_name = self.tf_method_combo.currentText()
        info = TIME_FREQ_METHODS.get(method_name, {})
        desc = info.get('desc', '')
        params = info.get('params', [])
        self.tf_desc_label.setText(f"【{method_name}】\n{desc}")
        # 清空旧参数控件
        while self.tf_params_layout.rowCount():
            self.tf_params_layout.removeRow(0)
        self._tf_param_widgets = {}
        for pkey, plabel, pmin, pmax, pstep, pdefault, pdesc in params:
            if pkey == 'window' or pkey == 'wavelet' or pkey == 'kernel':
                combo = QComboBox()
                if pkey == 'window':
                    items = ['hann', 'hamming', 'blackman', 'bartlett', 'flattop', 'kaiser', 'tukey', 'rect'][:int(pmax)+1]
                elif pkey == 'wavelet':
                    if 'CWT' in method_name:
                        items = CWT_WAVELET_NAMES[:int(pmax)+1]
                    else:
                        items = DWT_WAVELET_NAMES[:int(pmax)+1]
                else:
                    items = ['无(纯WVD)', '伪WVD(PWVD)', '平滑伪WVD(SPWVD)'][:int(pmax)+1]
                combo.addItems(items)
                combo.setCurrentIndex(int(pdefault))
                combo.setToolTip(pdesc)
                self._tf_param_widgets[pkey] = combo
                self.tf_params_layout.addRow(f"{plabel}:", combo)
            else:
                if pkey in ('sigma', 'factor', 'tau', 'noise_amp', 'stop'):
                    spin = QDoubleSpinBox()
                    spin.setDecimals(4)
                else:
                    spin = QSpinBox()
                spin.setRange(pmin, pmax)
                spin.setSingleStep(pstep)
                spin.setValue(pdefault)
                spin.setToolTip(pdesc)
                self._tf_param_widgets[pkey] = spin
                self.tf_params_layout.addRow(f"{plabel}:", spin)
            # 添加参数说明行
            desc_label = QLabel(pdesc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666; font-size: 10px;")
            self.tf_params_layout.addRow("", desc_label)
        
        # 添加降采样预处理选项（可选项）
        downsamp_row = QHBoxLayout()
        self.tf_downsamp_check = QCheckBox("启用降采样预处理")
        self.tf_downsamp_check.setToolTip("启用后将对长信号进行降采样以加速计算（可能影响精度）")
        downsamp_row.addWidget(self.tf_downsamp_check)
        
        self.tf_downsamp_combo = QComboBox()
        self.tf_downsamp_combo.addItems(["5000点", "10000点", "20000点", "50000点", "100000点"])
        self.tf_downsamp_combo.setCurrentIndex(1)  # 默认10000点
        self.tf_downsamp_combo.setEnabled(False)
        downsamp_row.addWidget(self.tf_downsamp_combo)
        downsamp_row.addStretch()
        
        self.tf_downsamp_check.stateChanged.connect(lambda state: self.tf_downsamp_combo.setEnabled(state == 2))
        self.tf_params_layout.addRow("降采样:", downsamp_row)
        
        # 刷新通道下拉
        self._refresh_tf_channels()
    
    def _refresh_tf_channels(self):
        """刷新时频变换的通道下拉菜单"""
        self.tf_ch_combo.clear()
        meta = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        if meta and isinstance(meta, dict) and 'channel_map' in meta:
            for ch in meta['channel_map'].keys():
                self.tf_ch_combo.addItem(ch)
        elif self.file_a_data is not None and self.file_a_data.ndim == 2:
            n = self.file_a_data.shape[1]
            for i in range(n):
                self.tf_ch_combo.addItem(f"CH{i+1:02d}")
        else:
            self.tf_ch_combo.addItem("CH01")
    
    def _get_tf_params(self):
        """收集当前时频变换参数"""
        params = {}
        for k, w in self._tf_param_widgets.items():
            if isinstance(w, QComboBox):
                params[k] = w.currentText()
            else:
                params[k] = w.value()
        return params
    
    def _get_tf_data(self):
        """获取时频变换用数据"""
        src = self.tf_src_combo.currentText()
        ch = self.tf_ch_combo.currentText()
        meta_a = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        meta_b = self.file_b_selector.meta if hasattr(self, 'file_b_selector') else {}
        da = self._get_channel_array(self.file_a_data, meta_a, ch) if self.file_a_data is not None else None
        db = self._get_channel_array(self.file_b_data, meta_b, ch) if self.file_b_data is not None else None
        if src == "A状态":
            return [(da, "A状态")] if da is not None else []
        elif src == "B状态":
            return [(db, "B状态")] if db is not None else []
        else:
            res = []
            if da is not None:
                res.append((da, "A状态"))
            if db is not None:
                res.append((db, "B状态"))
            return res
    
    def _compute_tf_transform(self):
        """执行选定的时频变换并可视化"""
        data_list = self._get_tf_data()
        if not data_list:
            self.tf_compute_btn_state.set_error("无数据", duration=2000)
            QMessageBox.warning(self, "提示", "无可用数据，请先加载数据文件")
            return
        method_name = self.tf_method_combo.currentText()
        params = self._get_tf_params()
        fs = self.fs_spin.value()
        self.tf_canvas.clear()
        n_data = len(data_list)
        fig = self.tf_canvas.figure
        if n_data == 1:
            axes = [fig.add_subplot(111)]
        else:
            axes = [fig.add_subplot(n_data, 1, i+1) for i in range(n_data)]
        # 获取降采样选项
        use_downsamp = self.tf_downsamp_check.isChecked()
        downsamp_points = [5000, 10000, 20000, 50000, 100000][self.tf_downsamp_combo.currentIndex()]
        
        self.tf_compute_btn_state.set_running("计算中")
        
        try:
            for ax, (arr, label) in zip(axes, data_list):
                self._plot_tf_result(ax, arr, label, method_name, params, fs, use_downsamp, downsamp_points)
            fig.tight_layout()
            self.tf_canvas.draw()
            self.tf_compute_btn_state.set_success("完成", duration=1500)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.tf_compute_btn_state.set_error("失败", duration=3000)
            try:
                QMessageBox.critical(self, "计算错误", f"时频变换执行失败:\n{e}\n\n请检查参数设置与依赖库(如PyWavelets、scipy)。")
            except Exception:
                pass
    
    def _plot_tf_result(self, ax, arr, label, method_name, params, fs, use_downsamp=False, max_points=10000):
        """根据方法类型绘制时频变换结果（优化版）
        
        参数:
            use_downsamp: 是否启用降采样预处理（默认False）
            max_points: 降采样最大点数（默认10000）
        """
        arr = np.asarray(arr, dtype=float).flatten()
        # 去趋势和去直流分量（防止近零Hz出现异常大值）
        arr = arr - np.mean(arr)  # 去直流
        if len(arr) > 10:
            from scipy.signal import detrend
            arr = detrend(arr)  # 去线性趋势
        
        # 降采样预处理（可选）：信号过长时降采样加速
        if use_downsamp:
            N_orig = len(arr)
            if N_orig > max_points:
                down_factor = N_orig // max_points
                arr = arr[::down_factor]  # 简单降采样
                fs = fs / down_factor  # 调整采样率
        
        N = len(arr)
        t = np.arange(N) / fs
        if method_name.startswith('1.'):
            from scipy.signal import spectrogram
            # 优化：限制窗长
            nperseg = min(int(params['nperseg']), N//4, 512)
            noverlap = min(int(params['noverlap']), nperseg-1) if params['noverlap'] > 0 else nperseg//2
            win = params['window']
            f, tt, Sxx = spectrogram(arr, fs=fs, window=win, nperseg=nperseg, noverlap=noverlap)
            ax.pcolormesh(tt, f, 10*np.log10(Sxx+1e-12), shading='gouraud')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - STFT 谱图 (优化)')
        elif method_name.startswith('2.'):
            import pywt
            wav = params['wavelet']
            # 优化：限制尺度数
            scales_n = min(int(params['scales']), 64)
            fmin = float(params['fmin']); fmax = min(float(params['fmax']), fs/2)
            scales = np.linspace(fs/fmax, fs/fmin, scales_n) if fmax > fmin else np.arange(1, scales_n+1)
            coef, freqs = pywt.cwt(arr, scales, wav, sampling_period=1.0/fs)
            ax.pcolormesh(t, freqs, np.abs(coef), shading='gouraud')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - CWT 谱图 (优化)')
        elif method_name.startswith('3.'):
            import pywt
            wav = params['wavelet']; level = min(int(params['level']), pywt.dwt_max_level(N, wav))
            coeffs = pywt.wavedec(arr, wav, level=level)
            energy = [np.sum(c**2) for c in coeffs]
            labels = [f'A{level}'] + [f'D{i}' for i in range(level, 0, -1)]
            ax.bar(labels, energy)
            ax.set_ylabel('能量'); ax.set_xlabel('频带')
            ax.set_title(f'{label} - DWT 各频带能量 (优化)')
        elif method_name.startswith('4.'):
            import pywt
            # 优化：限制分解层数
            wav = params['wavelet']; level = min(int(params['level']), 4)
            wp = pywt.WaveletPacket(data=arr, wavelet=wav, mode='symmetric', maxlevel=level)
            nodes = [node.path for node in wp.get_level(level, 'freq')]
            energy = [np.sum(wp[node].data**2) for node in nodes]
            ax.bar(range(len(energy)), energy)
            ax.set_ylabel('能量'); ax.set_xlabel('频带索引')
            ax.set_title(f'{label} - WPT 各频带能量 (优化)')
        elif method_name.startswith('5.'):
            from scipy.signal import hilbert
            # 优化：限制IMF数
            imfs = self._emd_decompose(arr, min(int(params['max_imf']), 4), float(params['stop']))
            for i, imf in enumerate(imfs):
                analytic = hilbert(imf)
                inst_freq = np.diff(np.unwrap(np.angle(analytic))) / (2*np.pi) * fs
                ax.plot(t[:len(inst_freq)], inst_freq, label=f'IMF{i+1}')
            ax.set_ylabel('瞬时频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - HHT 瞬时频率 (优化)'); ax.legend(fontsize=8)
        elif method_name.startswith('6.'):
            S = self._stransform(arr, fs, float(params['factor']))
            ax.pcolormesh(t, np.fft.rfftfreq(N, 1/fs), np.abs(S).T, shading='gouraud')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - S变换 谱图')
        elif method_name.startswith('7.'):
            from scipy.signal import spectrogram
            # 优化：限制窗长
            nperseg = min(int(params['nperseg']), N//4, 256)
            win = params['window']
            f, tt, Sxx = spectrogram(arr, fs=fs, window=win, nperseg=nperseg)
            Sxx_sst = self._synchrosqueeze(Sxx, f, tt)
            ax.pcolormesh(tt, f, 10*np.log10(Sxx_sst+1e-12), shading='gouraud')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - SST 同步挤压谱图 (优化)')
        elif method_name.startswith('8.'):
            # 优化：限制FFT点数
            nfft = min(int(params['nfft']), 1024)
            kernel_val = params['kernel']
            kernel = kernel_val if isinstance(kernel_val, int) else (0 if '无' in str(kernel_val) else (1 if '伪' in str(kernel_val) and '平滑' not in str(kernel_val) else 2))
            wvd = self._wigner_ville(arr, nfft, kernel)
            f = np.fft.fftshift(np.fft.fftfreq(nfft, 1/fs))
            tt = np.arange(wvd.shape[1]) / fs
            mag = np.fft.fftshift(np.abs(wvd), axes=0)
            ax.pcolormesh(tt, f, mag, shading='nearest', cmap='viridis')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - WVD (优化)')
        elif method_name.startswith('9.'):
            # 优化：限制FFT点数
            nfft = min(int(params['nfft']), 1024); sigma = float(params['sigma'])
            cwd = self._choi_williams(arr, nfft, sigma, fs)
            f = np.fft.fftshift(np.fft.fftfreq(nfft, 1/fs))
            tt = np.arange(cwd.shape[1]) / fs
            mag = np.fft.fftshift(np.abs(cwd), axes=0)
            ax.pcolormesh(tt, f, mag, shading='nearest', cmap='viridis')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - CWD (优化)')
        elif method_name.startswith('10.'):
            # 优化：限制FFT点数和窗长
            nfft = min(int(params['nfft']), 1024); win = min(int(params['win']), N//4, 256)
            pwvd = self._pseudo_wvd(arr, nfft, win)
            f = np.fft.fftshift(np.fft.fftfreq(nfft, 1/fs))
            tt = np.arange(pwvd.shape[1]) / fs
            mag = np.fft.fftshift(np.abs(pwvd), axes=0)
            ax.pcolormesh(tt, f, mag, shading='nearest', cmap='viridis')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - PWVD 谱图 (优化)')
        elif method_name.startswith('11.'):
            # 优化：限制IMF数
            imfs = self._emd_decompose(arr, min(int(params['max_imf']), 4), float(params['stop']))
            for i, imf in enumerate(imfs):
                ax.plot(t, imf, label=f'IMF{i+1}')
            ax.set_ylabel('幅值'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - EMD 分解 (优化)'); ax.legend(fontsize=8)
        elif method_name.startswith('12.'):
            # 优化：限制集合数
            imfs = self._eemd_decompose(arr, min(int(params['n_ensemble']), 10), float(params['noise_amp']))
            for i, imf in enumerate(imfs):
                ax.plot(t, imf, label=f'IMF{i+1}')
            ax.set_ylabel('幅值'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - EEMD 分解 (优化)'); ax.legend(fontsize=8)
        elif method_name.startswith('13.'):
            imfs = self._vmd_decompose(arr, int(params['K']), float(params['alpha']), float(params['tau']))
            for i, imf in enumerate(imfs):
                ax.plot(t, imf, label=f'Mode{i+1}')
            ax.set_ylabel('幅值'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - VMD 分解 (优化)'); ax.legend(fontsize=8)
        elif method_name.startswith('14.'):
            # 优化：限制窗口和延迟
            nperseg = min(int(params['nperseg']), N//4, 256); max_lag = min(int(params['max_lag']), nperseg//2, 128)
            n_seg = max(1, N // nperseg)
            acf_mat = np.zeros((max_lag, n_seg))
            for s in range(n_seg):
                seg = arr[s*nperseg:(s+1)*nperseg]
                if len(seg) < max_lag+1:
                    continue
                acf = np.correlate(seg-seg.mean(), seg-seg.mean(), 'full')[len(seg)-1:len(seg)-1+max_lag]
                acf_mat[:, s] = acf / (acf[0]+1e-12)
            ax.pcolormesh(np.arange(n_seg)/fs, np.arange(max_lag)/fs, acf_mat, shading='gouraud')
            ax.set_ylabel('延迟 [sec]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - 短时自相关 (优化)')
        elif method_name.startswith('15.'):
            # 优化：限制窗长
            nperseg = min(int(params['nperseg']), N//4, 256); sigma = float(params['sigma'])
            n_seg = max(1, N // nperseg)
            S = np.zeros((nperseg//2+1, n_seg), dtype=complex)
            win_len = nperseg
            gauss = np.exp(-0.5*((np.arange(win_len)-win_len/2)/(sigma*win_len))**2)
            for s in range(n_seg):
                seg = arr[s*nperseg:(s+1)*nperseg]
                if len(seg) < nperseg:
                    seg = np.pad(seg, (0, nperseg-len(seg)))
                S[:, s] = np.fft.rfft(seg*gauss)[:nperseg//2+1]
            f = np.fft.rfftfreq(nperseg, 1/fs)
            tt = np.arange(n_seg)*nperseg/fs
            ax.pcolormesh(tt, f, 10*np.log10(np.abs(S)**2+1e-12), shading='gouraud')
            ax.set_ylabel('频率 [Hz]'); ax.set_xlabel('时间 [sec]')
            ax.set_title(f'{label} - Gabor变换 (优化)')
    
    # ---- 时频变换辅助算法 ----
    def _emd_decompose(self, arr, max_imf, stop):
        """简化EMD分解（优化版）"""
        imfs = []
        residual = arr.copy()
        for _ in range(max_imf):
            h = residual.copy()
            for _ in range(50):
                from scipy.signal import find_peaks
                max_idx, _ = find_peaks(h)
                min_idx, _ = find_peaks(-h)
                if len(max_idx) < 2 or len(min_idx) < 2:
                    break
                t_max = np.concatenate([[0], max_idx, [len(h)-1]])
                t_min = np.concatenate([[0], min_idx, [len(h)-1]])
                upper = np.interp(np.arange(len(h)), t_max, h[t_max])
                lower = np.interp(np.arange(len(h)), t_min, h[t_min])
                mean = (upper + lower) / 2
                prev = h.copy()
                h = h - mean
                if np.sum((prev-h)**2) / (np.sum(prev**2)+1e-12) < stop:
                    break
            if np.sum(h**2) < 1e-10 * np.sum(arr**2):
                break
            imfs.append(h)
            residual = residual - h
        if len(imfs) == 0:
            imfs = [arr]
        return imfs
    
    def _eemd_decompose(self, arr, n_ensemble, noise_amp):
        """简化EEMD分解"""
        std = np.std(arr)
        all_imfs = None
        for _ in range(n_ensemble):
            noisy = arr + noise_amp * std * np.random.randn(len(arr))
            imfs = self._emd_decompose(noisy, 10, 0.05)
            if all_imfs is None:
                all_imfs = [imf.copy() for imf in imfs]
            else:
                while len(all_imfs) < len(imfs):
                    all_imfs.append(np.zeros_like(arr))
                while len(imfs) < len(all_imfs):
                    imfs.append(np.zeros_like(arr))
                for i in range(len(all_imfs)):
                    all_imfs[i] += imfs[i]
        return [imf/n_ensemble for imf in all_imfs]
    
    def _vmd_decompose(self, arr, K, alpha, tau):
        """简化VMD分解（基于迭代，参考Dragomiretskiy 2014）"""
        N = len(arr)
        fs = 1.0
        T = N
        t = np.arange(1, T+1) / T
        freqs = t - 0.5 - 1/T
        alpha_k = alpha
        u = np.zeros((K, T))
        u_hat = np.zeros((K, T), dtype=complex)
        u_hat_prev = np.zeros((K, T), dtype=complex)
        omega = np.zeros(K)
        lambda_hat = np.zeros(T, dtype=complex)
        arr_hat = np.fft.fftshift(np.fft.fft(arr))
        max_iter = 100
        for _ in range(max_iter):
            u_hat_prev = u_hat.copy()
            for k in range(K):
                sum_u = np.sum(u_hat, axis=0) - u_hat[k]
                residual = arr_hat - sum_u - lambda_hat/2
                u_hat[k] = residual / (1 + alpha_k * (freqs - omega[k])**2)
                if k == K-1:
                    omega[k] = 0
                else:
                    omega[k] = np.sum(freqs[T//2:] * np.abs(u_hat[k, T//2:])**2) / (np.sum(np.abs(u_hat[k, T//2:])**2) + 1e-12)
            lambda_hat = lambda_hat + tau * (arr_hat - np.sum(u_hat, axis=0))
            if np.sum(np.abs(u_hat - u_hat_prev)**2) / (np.sum(np.abs(u_hat_prev)**2)+1e-12) < 1e-6:
                break
        for k in range(K):
            u[k] = np.real(np.fft.ifft(np.fft.ifftshift(u_hat[k])))
        return list(u)
    
    def _stransform(self, arr, fs, factor):
        """简化S变换"""
        N = len(arr)
        f = np.fft.rfftfreq(N, 1/fs)
        S = np.zeros((N, len(f)), dtype=complex)
        X = np.fft.fft(arr)
        for j, freq in enumerate(f):
            if freq == 0:
                S[:, j] = np.mean(arr)
                continue
            sigma = factor / abs(freq)
            gauss_win = np.exp(-2j*np.pi*freq*np.arange(N)) * np.exp(-np.pi**2*sigma**2*np.arange(N)**2/N)
            S[:, j] = np.fft.ifft(X * np.fft.fft(gauss_win))
        return S
    
    def _synchrosqueeze(self, Sxx, f, tt):
        """简化同步挤压（稳健版，避免越界）"""
        if Sxx.size == 0 or len(f) < 3:
            return Sxx
        Sxx_sst = np.zeros_like(Sxx)
        dt = (tt[1] - tt[0]) if len(tt) > 1 else 1.0
        for j in range(Sxx.shape[1]):
            for i in range(1, Sxx.shape[0]-1):
                if abs(Sxx[i-1, j]) < 1e-12 or abs(Sxx[i+1, j]) < 1e-12:
                    continue
                dphi = np.angle(Sxx[i+1, j]) - np.angle(Sxx[i-1, j])
                omega = f[i] + dphi / (2*np.pi*dt)
                idx = int(np.argmin(np.abs(f - omega)))
                if 0 <= idx < Sxx.shape[0]:
                    Sxx_sst[idx, j] += np.abs(Sxx[i, j])
        return Sxx_sst
    
    def _wigner_ville(self, arr, nfft, kernel):
        """Wigner-Ville分布"""
        N = len(arr)
        wvd = np.zeros((nfft, N), dtype=complex)
        for n in range(N):
            tau_max = min(n, N-1-n, nfft//2 - 1)
            if tau_max < 1:
                continue
            taus = np.arange(-tau_max, tau_max+1)
            seg = arr[n+taus] * np.conj(arr[n-taus])
            if kernel == 1:
                win = np.hanning(len(seg))
                seg = seg * win
            elif kernel == 2:
                win = np.hanning(len(seg))
                seg = seg * win
            padded = np.zeros(nfft, dtype=complex)
            start = nfft//2 - tau_max
            padded[start:start+len(seg)] = seg
            wvd[:, n] = np.fft.fftshift(np.fft.fft(padded))
        return wvd
    
    def _pseudo_wvd(self, arr, nfft, win_len):
        """伪Wigner-Ville分布"""
        N = len(arr)
        wvd = np.zeros((nfft, N), dtype=complex)
        win = np.hanning(win_len)
        for n in range(N):
            tau_max = min(win_len//2 - 1, n, N-1-n, nfft//2 - 1)
            if tau_max < 1:
                continue
            taus = np.arange(-tau_max, tau_max+1)
            win_seg = win[win_len//2 - tau_max : win_len//2 + tau_max + 1]
            seg = arr[n+taus] * np.conj(arr[n-taus]) * win_seg
            padded = np.zeros(nfft, dtype=complex)
            start = nfft//2 - tau_max
            padded[start:start+len(seg)] = seg
            wvd[:, n] = np.fft.fftshift(np.fft.fft(padded))
        return wvd
    
    def _choi_williams(self, arr, nfft, sigma, fs):
        """Choi-Williams分布（简化）"""
        N = len(arr)
        cwd = np.zeros((nfft, N), dtype=complex)
        for n in range(N):
            tau_max = min(n, N-1-n, nfft//2 - 1)
            if tau_max < 1:
                continue
            taus = np.arange(-tau_max, tau_max+1)
            kernel = np.exp(-(taus**2) / sigma)
            seg = arr[n+taus] * np.conj(arr[n-taus]) * kernel
            padded = np.zeros(nfft, dtype=complex)
            start = nfft//2 - tau_max
            padded[start:start+len(seg)] = seg
            cwd[:, n] = np.fft.fftshift(np.fft.fft(padded))
        return cwd
    
    def _detach_tf_canvas(self):
        """将时频变换画布分离为独立窗口"""
        self._detach_canvas_generic(self.tf_canvas, "时频变换可视化")
    
    def _detach_canvas_generic(self, canvas, title):
        """通用画布分离方法"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 600)
        layout = QVBoxLayout(dlg)
        new_canvas = create_canvas(dlg)
        new_toolbar = NavigationToolbar(new_canvas, dlg)
        layout.addWidget(new_toolbar)
        layout.addWidget(new_canvas, stretch=1)
        new_canvas.figure = canvas.figure
        new_canvas.draw()
        dlg.exec_()
    
    def visualize_data_curves(self):
        """在频谱曲线子Tab中绘制两条频谱曲线，支持多种显示模式"""
        # 切换到图表TAB
        if hasattr(self, 'main_result_tabs'):
            self.main_result_tabs.setCurrentIndex(1)
        if self.file_a_data is None and self.file_b_data is None:
            return
        # 多通道：取第一个选中通道用于频谱对比
        channels_a = self.channel_a.get_selected_channels()
        channels_b = self.channel_b.get_selected_channels()
        ch_a_name = channels_a[0] if channels_a else None
        ch_b_name = channels_b[0] if channels_b else None
        meta_a = self.file_a_selector.meta if hasattr(self, 'file_a_selector') else {}
        meta_b = self.file_b_selector.meta if hasattr(self, 'file_b_selector') else {}
        data_a = self._get_channel_array(self.file_a_data, meta_a, ch_a_name) if ch_a_name else self.get_channel_data(self.file_a_data, 0)
        data_b = self._get_channel_array(self.file_b_data, meta_b, ch_b_name) if ch_b_name else self.get_channel_data(self.file_b_data, 0)
        if data_a is None and data_b is None:
            return
        name_a = self.channel_a.get_display_name() or "A"
        name_b = self.channel_b.get_display_name() or "B"
        if ch_a_name:
            name_a = f"{name_a}({ch_a_name})"
        if ch_b_name:
            name_b = f"{name_b}({ch_b_name})"
        mode = self.data_viz_mode.currentText()
        fs = self.fs or 1.0

        spec_a = get_spectrum(data_a, fs)
        spec_b = get_spectrum(data_b, fs)
        freqs_a = np.fft.rfftfreq(len(data_a), d=1/fs)
        freqs_b = np.fft.rfftfreq(len(data_b), d=1/fs)

        canvas = self.data_canvas
        canvas.clear()
        fig = canvas.fig
        import matplotlib as mpl
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        mpl.rcParams['axes.unicode_minus'] = False
        mpl.rcParams['mathtext.fontset'] = 'cm'

        style_a = dict(color='#1f77b4', linewidth=1.8, linestyle='-', label=name_a)
        style_b = dict(color='#d62728', linewidth=1.6, linestyle='--', label=name_b)

        try:
            if mode == "同图上下叠加":
                ax = fig.add_subplot(2, 1, 1)
                ax.plot(freqs_a, spec_a, **style_a)
                ax.set_title(f'{name_a} 频谱', fontsize=13, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(2, 1, 2)
                ax2.plot(freqs_b, spec_b, **style_b)
                ax2.set_title(f'{name_b} 频谱', fontsize=13, fontweight='bold')
                ax2.set_xlabel('频率 (Hz)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "同图左右并排":
                ax = fig.add_subplot(1, 2, 1)
                ax.plot(freqs_a, spec_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(1, 2, 2)
                ax2.plot(freqs_b, spec_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('频率 (Hz)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "分两张图(上下)":
                ax = fig.add_subplot(2, 1, 1)
                ax.plot(freqs_a, spec_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(2, 1, 2)
                ax2.plot(freqs_b, spec_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('频率 (Hz)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            elif mode == "分两张图(左右)":
                ax = fig.add_subplot(1, 2, 1)
                ax.plot(freqs_a, spec_a, **style_a)
                ax.set_title(f'{name_a}', fontsize=13, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

                ax2 = fig.add_subplot(1, 2, 2)
                ax2.plot(freqs_b, spec_b, **style_b)
                ax2.set_title(f'{name_b}', fontsize=13, fontweight='bold')
                ax2.set_xlabel('频率 (Hz)', fontsize=11)
                ax2.set_ylabel('幅值', fontsize=11)
                ax2.grid(True, alpha=0.3)
                ax2.legend(loc='best', fontsize=10)

            else:  # 同图叠加(同坐标系)
                ax = fig.add_subplot(111)
                ax.plot(freqs_a, spec_a, **style_a)
                ax.plot(freqs_b, spec_b, **style_b)
                ax.set_title('频谱对比', fontsize=13, fontweight='bold')
                ax.set_xlabel('频率 (Hz)', fontsize=11)
                ax.set_ylabel('幅值', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)

            fig.tight_layout()
            canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘制频谱曲线失败: {str(e)}")
    
    def visualize_all(self):
        """可视化按钮：同时绘制频谱曲线和相似性图"""
        try:
            self.visualize_data_curves()
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘制频谱曲线失败: {str(e)}")
        if self.result_data:
            try:
                self.visualize_results()
            except Exception as e:
                QMessageBox.warning(self, "可视化错误", f"绘制相似性图失败: {str(e)}")

    def visualize_results(self):
        # 切换到图表TAB
        if hasattr(self, 'main_result_tabs'):
            self.main_result_tabs.setCurrentIndex(1)
        if not self.result_data:
            return
        
        viz_method = self.viz_combo.currentText()
        data_a = self.result_data[0]['data_a']
        data_b = self.result_data[0]['data_b']
        name_a = self.channel_a.get_display_name()
        name_b = self.channel_b.get_display_name()
        
        self.canvas.clear()
        
        try:
            if viz_method == '折线图 (Line)':
                # 绘制频谱
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                freqs = np.fft.rfftfreq(len(data_a), d=1/self.fs)
                plot_line(self.canvas, None, {f'{name_a} 频谱': spec_a, f'{name_b} 频谱': spec_b}, 
                         title='Frequency Spectrum', xlabel='Frequency (Hz)', ylabel='Magnitude', fs=1.0)
            elif viz_method == '散点图 (Scatter)':
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_scatter(self.canvas, spec_a, {f'{name_b} 频谱': spec_b}, 
                           title='Spectrum Scatter', xlabel=f'{name_a} 频谱', ylabel=f'{name_b} 频谱')
            elif viz_method == '双轴对比图 (Dual Axis)':
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_dual_axis(self.canvas, spec_a, spec_b, fs=1.0, 
                             title='Spectrum Comparison', xlabel='Frequency Bin')
            elif viz_method == '残差图 (Residual)':
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_residual(self.canvas, spec_a, spec_b, 
                            title='Spectrum Residual', xlabel='Frequency Bin')
            elif viz_method == '柱状图 (Bar)':
                methods = [r['method'] for r in self.result_data if isinstance(r['value'], (int, float))]
                values = [r['value'] for r in self.result_data if isinstance(r['value'], (int, float))]
                if methods and values:
                    plot_bar(self.canvas, methods, {f'{name_a} vs {name_b}': values}, 
                            title='Frequency Domain Similarity', xlabel='Method', ylabel='Value')
            elif viz_method == '雷达图 (Radar)':
                methods = [r['method'][:10] for r in self.result_data if isinstance(r['value'], (int, float))]
                values = [r['value'] for r in self.result_data if isinstance(r['value'], (int, float))]
                if methods and values:
                    vals = np.array(values)
                    vals_norm = (vals - np.min(vals)) / (np.max(vals) - np.min(vals) + 1e-10)
                    plot_radar(self.canvas, methods, {f'{name_a} vs {name_b}': vals_norm}, 
                             title='Frequency Similarity Radar')
            elif viz_method == '直方图 (Histogram)':
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_histogram(self.canvas, {f'{name_a} 频谱': spec_a, f'{name_b} 频谱': spec_b})
            elif viz_method == '时频图 (Spectrogram)':
                plot_spectrogram(self.canvas, data_a, fs=self.fs, title=f'{name_a} Spectrogram')
            elif viz_method == '箱线图 (Box Plot)':
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_box(self.canvas, {f'{name_a} 频谱': spec_a, f'{name_b} 频谱': spec_b})
            elif viz_method == '热力图 (Heatmap)':
                # STFT热力图
                from signal_processing import stft_matrix
                mat_a = stft_matrix(data_a, self.fs)
                plot_heatmap(self.canvas, mat_a, title=f'STFT of {name_a}')
            else:
                spec_a = get_spectrum(data_a, self.fs)
                spec_b = get_spectrum(data_b, self.fs)
                plot_line(self.canvas, None, {f'{name_a} 频谱': spec_a, f'{name_b} 频谱': spec_b}, 
                         title='Frequency Spectrum', xlabel='Frequency (Hz)', ylabel='Magnitude', fs=1.0)
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘图失败: {str(e)}")
    
    def save_results(self):
        if not self.result_data:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", "CSV文件 (*.csv);;文本文件 (*.txt);;NumPy (*.npy)"
        )
        if filepath:
            try:
                import csv
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Method', 'Value', 'Data_A_Length', 'Data_B_Length', 'Fs'])
                    for res in self.result_data:
                        writer.writerow([res['method'], res['value'], 
                                       len(res['data_a']), len(res['data_b']), self.fs])
                QMessageBox.information(self, "成功", f"结果已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", str(e))
    
    def save_image(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存图像", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff);;PDF (*.pdf);;SVG (*.svg);;EPS (*.eps)"
        )
        if filepath:
            success, msg = save_figure(self.canvas, filepath)
            if success:
                QMessageBox.information(self, "成功", f"图像已保存到:\n{msg}")
            else:
                QMessageBox.critical(self, "保存错误", msg)

    def add_report_block(self):
        """将当前结果作为一个BLOCK添加到全局报告管理器"""
        QMessageBox.information(self, 'DEBUG', 'Tab2 add_report_block called!')
        log("[Tab2] add_report_block CALLED")
        try:
            log("[Tab2] 检查 result_data...")
            if not self.result_data:
                log("[Tab2] result_data 为空，返回")
                QMessageBox.warning(self, "提示", "请先计算频域相似性结果")
                return
            
            log("[Tab2] 导入模块...")
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import build_similarity_block_md, save_figure_to_file
            log("[Tab2] 模块导入成功")

            log("[Tab2] 获取报告目录...")
            report_dir = self._get_report_dir()
            if report_dir is None:
                log("[Tab2] report_dir 为 None，返回")
                return
            log(f"[Tab2] 报告目录: {report_dir}")

            name_a = "A"
            name_b = "B"
            try:
                if hasattr(self, 'channel_a') and self.channel_a:
                    name_a = self.channel_a.get_display_name() or "A"
                    log(f"[Tab2] channel_a: {name_a}")
                else:
                    log("[Tab2] channel_a 不存在或为空")
                if hasattr(self, 'channel_b') and self.channel_b:
                    name_b = self.channel_b.get_display_name() or "B"
                    log(f"[Tab2] channel_b: {name_b}")
                else:
                    log("[Tab2] channel_b 不存在或为空")
            except Exception as e:
                log(f"[Tab2] 获取通道名称失败: {e}")

            state_names = [name_a, name_b]
            log(f"[Tab2] state_names: {state_names}")

            img_path = None
            data_img_path = None
            try:
                if hasattr(self, 'main_result_tabs'):
                    log("[Tab2] 切换到图表TAB")
                    self.main_result_tabs.setCurrentIndex(1)
                else:
                    log("[Tab2] 没有 main_result_tabs")
                if hasattr(self, 'canvas') and self.canvas:
                    log("[Tab2] 保存相似性图...")
                    img_path = save_figure_to_file(self.canvas, report_dir, prefix='tab2_sim')
                    log(f"[Tab2] 相似性图保存成功: {img_path}")
                else:
                    log("[Tab2] canvas 不存在")
            except Exception as e:
                img_path = None
                log(f"[Tab2] 保存相似性图失败: {e}")
            try:
                if hasattr(self, 'data_canvas') and self.data_canvas:
                    log("[Tab2] 保存频谱曲线图...")
                    data_img_path = save_figure_to_file(self.data_canvas, report_dir, prefix='tab2_data')
                    log(f"[Tab2] 频谱曲线图保存成功: {data_img_path}")
                else:
                    log("[Tab2] data_canvas 不存在")
            except Exception as e:
                data_img_path = None
                log(f"[Tab2] 保存频谱曲线图失败: {e}")

            preprocess_info = getattr(self, '_preprocess_info', None)
            log(f"[Tab2] preprocess_info: {preprocess_info}")

            method_results = []
            try:
                log(f"[Tab2] 处理 result_data，共 {len(self.result_data)} 项")
                for r in self.result_data:
                    if isinstance(r, dict) and 'method' in r and 'value' in r:
                        method_results.append({'method': r['method'], 'value': r['value']})
                        log(f"[Tab2] 添加结果: {r['method']} = {r['value']}")
                    else:
                        log(f"[Tab2] 警告: 结果项格式不正确: {r}")
            except Exception as e:
                log(f"[Tab2] 构建方法结果列表失败: {e}")
                method_results = []

            if not method_results:
                log("[Tab2] method_results 为空，返回")
                QMessageBox.warning(self, "提示", "未找到有效的计算结果")
                return

            log("[Tab2] 构建报告内容...")
            content = build_similarity_block_md(state_names, method_results, viz_img=img_path, preprocess_info=preprocess_info)
            log(f"[Tab2] 报告内容长度: {len(content)}")
            
            if data_img_path:
                content += f"\n\n### 频谱曲线图\n\n![频谱曲线]({data_img_path})\n"
            
            log("[Tab2] 创建 ReportBlock...")
            block = ReportBlock(
                source_tab='Tab2 频域相似性',
                title=f"频域相似性分析 ({name_a} vs {name_b})",
                content_md=content,
                images=[p for p in [img_path, data_img_path] if p]
            )
            
            log("[Tab2] 添加到 REPORT_MANAGER...")
            REPORT_MANAGER.add_block(block)
            log(f"[Tab2] 添加成功! BLOCK标题: {block.title}")
            
            QMessageBox.information(self, "成功", f"已添加报告BLOCK到Tab6报告管理器\n标题: {block.title}\n图像已保存至: {report_dir}")
            log("[Tab2] 显示成功消息框")
        except Exception as e:
            import traceback
            log(f"[Tab2] add_report_block 异常: {e}")
            log(f"[Tab2] 堆栈跟踪:\n{traceback.format_exc()}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}\n\n请查看控制台输出获取详细信息")

    def _get_report_dir(self):
        """获取用户指定的报告目录（从报告Tab），未指定则弹窗提示"""
        from PyQt5.QtWidgets import QMainWindow
        p = self.parent()
        while p is not None and not isinstance(p, QMainWindow):
            p = p.parent()
        
        report_tab = None
        if p is not None:
            if hasattr(p, 'tab_report'):
                report_tab = p.tab_report
            elif hasattr(p, 'tab7'):
                report_tab = p.tab7
        
        if report_tab and hasattr(report_tab, 'report_dir') and report_tab.report_dir:
            return report_tab.report_dir
        
        ret = QMessageBox.question(
            self, "未指定报告目录",
            "尚未指定报告保存目录，是否现在选择？\n（点击'保存位置'按钮也可在报告Tab中设置）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ret == QMessageBox.Yes:
            d = QFileDialog.getExistingDirectory(self, "选择报告保存位置", "")
            if d:
                if report_tab and hasattr(report_tab, 'report_dir'):
                    report_tab.report_dir = d
                    if hasattr(report_tab, 'dir_label'):
                        report_tab.dir_label.setText(f"保存位置: {d}")
                return d
            return None
        return None


# ============= Tab3: 矩阵转换 =============

class MatrixTransformTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_data = None
        self.matrix_result = None
        self.fs = 1.0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        # 文件选择
        file_group = QGroupBox("数据文件")
        file_layout = QVBoxLayout(file_group)
        
        self.file_selector = FileSelectorWidget("选择时域数据文件:")
        self.file_selector.file_loaded.connect(self.on_file_loaded)
        file_layout.addWidget(self.file_selector)
        
        left_layout.addWidget(file_group)
        
        # 通道选择
        channel_group = QGroupBox("通道选择")
        channel_layout = QVBoxLayout(channel_group)
        self.channel_sel = ChannelSelectorWidget()
        channel_layout.addWidget(self.channel_sel)
        left_layout.addWidget(channel_group)
        
        # 采样率设置
        fs_group = QGroupBox("采样率设置")
        fs_layout = QHBoxLayout(fs_group)
        fs_layout.addWidget(QLabel("Fs (Hz):"))
        self.fs_spin = QDoubleSpinBox()
        self.fs_spin.setRange(0.001, 1000000)
        self.fs_spin.setValue(1.0)
        self.fs_spin.setDecimals(3)
        fs_layout.addWidget(self.fs_spin)
        left_layout.addWidget(fs_group)
        
        # 矩阵转换方法选择
        method_group = QGroupBox("矩阵转换方法 (15+种)")
        method_layout = QVBoxLayout(method_group)
        
        self.method_list = QListWidget()
        self.method_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for method in MATRIX_METHODS:
            self.method_list.addItem(method)
        for i in range(min(3, self.method_list.count())):
            self.method_list.item(i).setSelected(True)
        method_layout.addWidget(self.method_list)
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(lambda: self.method_list.selectAll())
        method_layout.addWidget(self.select_all_btn)
        
        self.clear_sel_btn = QPushButton("清除选择")
        self.clear_sel_btn.clicked.connect(self.method_list.clearSelection)
        method_layout.addWidget(self.clear_sel_btn)
        
        left_layout.addWidget(method_group)
        
        # 可视化方法选择
        viz_group = QGroupBox("可视化方法")
        viz_layout = QVBoxLayout(viz_group)
        self.viz_combo = QComboBox()
        self.viz_combo.addItems(VISUALIZATION_METHODS)
        viz_layout.addWidget(self.viz_combo)
        left_layout.addWidget(viz_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.compute_btn = QPushButton("生成矩阵")
        self.compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.compute_btn.clicked.connect(self.compute_matrix)
        btn_layout.addWidget(self.compute_btn)
        
        self.viz_btn = QPushButton("可视化")
        self.viz_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.viz_btn.clicked.connect(self.visualize_matrix)
        self.viz_btn.setEnabled(False)
        btn_layout.addWidget(self.viz_btn)
        
        left_layout.addLayout(btn_layout)
        
        self.save_matrix_btn = QPushButton("保存矩阵数据")
        self.save_matrix_btn.clicked.connect(self.save_matrix)
        self.save_matrix_btn.setEnabled(False)
        left_layout.addWidget(self.save_matrix_btn)
        
        self.add_report_btn = QPushButton("添加报告BLOCK")
        self.add_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.add_report_btn.clicked.connect(self.add_report_block)
        self.add_report_btn.setEnabled(False)
        left_layout.addWidget(self.add_report_btn)
        
        left_layout.addStretch()
        
        # 右侧结果面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 矩阵信息
        self.matrix_info = QLabel("矩阵信息: 未生成")
        self.matrix_info.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        right_layout.addWidget(self.matrix_info)
        
        # 可视化区域
        viz_group = QGroupBox("可视化")
        viz_layout = QVBoxLayout(viz_group)
        
        self.canvas = create_canvas(self)
        self.toolbar = NavigationToolbar(self.canvas, self)
        viz_layout.addWidget(self.toolbar)
        viz_layout.addWidget(self.canvas, stretch=1)
        
        self.save_img_btn = QPushButton("保存图像")
        self.save_img_btn.clicked.connect(self.save_image)
        viz_layout.addWidget(self.save_img_btn)
        
        right_layout.addWidget(viz_group, stretch=1)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 850])
        
        main_layout.addWidget(splitter)
    
    def on_file_loaded(self, path, data, meta):
        self.file_data = data
        self.fs = meta.get('fs', 1.0) or 1.0
        self.fs_spin.setValue(self.fs)
        self.channel_sel.set_data(data)
        self.compute_btn.setEnabled(True)
    
    def get_channel_data(self, data, channel_idx):
        if data is None:
            return None
        if data.ndim == 1:
            return data
        elif data.ndim == 2:
            if channel_idx < data.shape[1]:
                return data[:, channel_idx]
        return data.flatten()
    
    def compute_matrix(self):
        selected_methods = [item.text() for item in self.method_list.selectedItems()]
        if not selected_methods:
            QMessageBox.warning(self, "提示", "请至少选择一种矩阵转换方法")
            return
        
        self.fs = self.fs_spin.value()
        ch = self.channel_sel.get_selected_channel()
        data = self.get_channel_data(self.file_data, ch)
        
        if data is None:
            QMessageBox.warning(self, "提示", "请先加载数据文件")
            return
        
        # 防止重复点击
        self.compute_btn.setEnabled(False)
        self.compute_btn.setText("计算中...")
        self.matrix_info.setText("并行计算中...")
        
        fs = self.fs
        
        def task(progress_cb):
            return convert_to_matrix_batch(
                data, selected_methods, fs=fs, progress_cb=progress_cb
            )
        
        self._worker = ComputeWorker(task)
        self._worker.progress.connect(self._on_matrix_progress)
        self._worker.finished_ok.connect(self._on_matrix_done)
        self._worker.error.connect(self._on_matrix_error)
        self._worker.start()
    
    def _on_matrix_progress(self, done, total, method, result):
        self.matrix_info.setText(f"并行计算中... {done}/{total} ({method})")
    
    def _on_matrix_done(self, batch_results):
        self.compute_btn.setEnabled(True)
        self.compute_btn.setText("计算矩阵转换")
        results = []
        errors = []
        for r in batch_results:
            if r['ok']:
                results.append({
                    'method': r['method'],
                    'matrix': r['matrix'],
                    'shape': r['shape']
                })
            else:
                errors.append(f"{r['method']}: {r['error']}")
        if errors:
            QMessageBox.warning(self, "部分方法失败", "\n".join(errors))
        if results:
            self.matrix_result = results
            self.display_matrix_info()
            self.viz_btn.setEnabled(True)
            self.save_matrix_btn.setEnabled(True)
            self.add_report_btn.setEnabled(True)
        elif not errors:
            self.matrix_info.setText("无有效结果")
    
    def _on_matrix_error(self, msg):
        self.compute_btn.setEnabled(True)
        self.compute_btn.setText("计算矩阵转换")
        QMessageBox.warning(self, "计算错误", f"并行计算失败: {msg}")
    
    def display_matrix_info(self):
        if not self.matrix_result:
            return
        info = []
        for res in self.matrix_result:
            info.append(f"{res['method']}: shape={res['shape']}, min={np.min(res['matrix']):.4f}, max={np.max(res['matrix']):.4f}")
        self.matrix_info.setText("矩阵信息:\n" + "\n".join(info))
    
    def visualize_matrix(self):
        if not self.matrix_result:
            return
        
        viz_method = self.viz_combo.currentText()
        self.canvas.clear()
        
        # 默认显示第一个矩阵，或者所有矩阵的汇总
        current_matrix = self.matrix_result[0]['matrix']
        method_name = self.matrix_result[0]['method']
        
        try:
            if viz_method == '热力图 (Heatmap)':
                plot_heatmap(self.canvas, current_matrix, title=f'{method_name} Heatmap')
            elif viz_method == '等高线图 (Contour)':
                plot_contour(self.canvas, current_matrix, title=f'{method_name} Contour')
            elif viz_method == '3D曲面图 (3D Surface)':
                plot_3d_surface(self.canvas, current_matrix, title=f'{method_name} 3D Surface')
            elif viz_method == '折线图 (Line)':
                # 显示矩阵的行
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(10, current_matrix.shape[0]))}
                plot_line(self.canvas, None, data_dict, title=f'{method_name} Line Plot', fs=1.0)
            elif viz_method == '柱状图 (Bar)':
                # 显示矩阵每行的均值
                labels = [f'R{i}' for i in range(current_matrix.shape[0])]
                values = np.mean(current_matrix, axis=1)
                plot_bar(self.canvas, labels, {'Mean': values}, title=f'{method_name} Bar Chart')
            elif viz_method == '箱线图 (Box Plot)':
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(10, current_matrix.shape[0]))}
                plot_box(self.canvas, data_dict, title=f'{method_name} Box Plot')
            elif viz_method == '小提琴图 (Violin)':
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(10, current_matrix.shape[0]))}
                plot_violin(self.canvas, data_dict, title=f'{method_name} Violin Plot')
            elif viz_method == '直方图 (Histogram)':
                plot_histogram(self.canvas, {'Matrix': current_matrix.flatten()}, title=f'{method_name} Histogram')
            elif viz_method == '散点图 (Scatter)':
                if current_matrix.shape[1] >= 2:
                    plot_scatter(self.canvas, current_matrix[:, 0], {'Col1 vs Col2': current_matrix[:, 1]}, 
                               title=f'{method_name} Scatter')
                else:
                    plot_scatter(self.canvas, range(len(current_matrix)), {'Values': current_matrix.flatten()}, 
                               title=f'{method_name} Scatter')
            elif viz_method == '雷达图 (Radar)':
                labels = [f'Col{i}' for i in range(min(10, current_matrix.shape[1]))]
                values = np.mean(current_matrix[:min(10, current_matrix.shape[0]), :min(10, current_matrix.shape[1])], axis=0)
                plot_radar(self.canvas, labels, {'Mean': values}, title=f'{method_name} Radar')
            elif viz_method == '瀑布图 (Waterfall)':
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(10, current_matrix.shape[0]))}
                plot_waterfall(self.canvas, data_dict, title=f'{method_name} Waterfall')
            elif viz_method == '极坐标图 (Polar)':
                data_dict = {'Matrix': current_matrix.flatten()[:min(360, current_matrix.size)]}
                plot_polar(self.canvas, data_dict, title=f'{method_name} Polar')
            elif viz_method == '阶梯图 (Stairs)':
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(5, current_matrix.shape[0]))}
                plot_stairs(self.canvas, data_dict, title=f'{method_name} Stairs')
            elif viz_method == '填充图 (Fill Between)':
                data_dict = {f'Row {i}': current_matrix[i, :] for i in range(min(2, current_matrix.shape[0]))}
                plot_fill_between(self.canvas, data_dict, title=f'{method_name} Fill')
            elif viz_method == '时频图 (Spectrogram)':
                if current_matrix.ndim == 2 and current_matrix.shape[0] > 10 and current_matrix.shape[1] > 10:
                    plot_heatmap(self.canvas, current_matrix, title=f'{method_name} Spectrogram-like')
                else:
                    plot_spectrogram(self.canvas, self.get_channel_data(self.file_data, self.channel_sel.get_selected_channel()), 
                                 fs=self.fs, title='Original Signal Spectrogram')
            else:
                plot_heatmap(self.canvas, current_matrix, title=f'{method_name}')
        except Exception as e:
            QMessageBox.warning(self, "可视化错误", f"绘图失败: {str(e)}")
    
    def save_matrix(self):
        if not self.matrix_result:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存矩阵", "", "NumPy (*.npy);;CSV (*.csv);;MAT文件 (*.mat)"
        )
        if filepath:
            try:
                if filepath.endswith('.npy'):
                    # 保存所有矩阵
                    np.save(filepath, self.matrix_result[0]['matrix'])
                elif filepath.endswith('.csv'):
                    np.savetxt(filepath, self.matrix_result[0]['matrix'], delimiter=',')
                elif filepath.endswith('.mat'):
                    from scipy.io import savemat
                    savemat(filepath, {'matrix': self.matrix_result[0]['matrix']})
                QMessageBox.information(self, "成功", f"矩阵已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", str(e))
    
    def save_image(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存图像", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff);;PDF (*.pdf);;SVG (*.svg);;EPS (*.eps)"
        )
        if filepath:
            success, msg = save_figure(self.canvas, filepath)
            if success:
                QMessageBox.information(self, "成功", f"图像已保存到:\n{msg}")
            else:
                QMessageBox.critical(self, "保存错误", msg)

    def add_report_block(self):
        """将当前矩阵转换结果作为一个BLOCK添加到全局报告管理器"""
        if not self.matrix_result:
            QMessageBox.warning(self, "提示", "请先生成矩阵")
            return
        from experiment_state import ReportBlock, REPORT_MANAGER
        from report_manager import build_matrix_block_md, save_figure_to_file

        # 获取用户指定的报告目录（Tab6），未指定则弹窗提示
        report_dir = self._get_report_dir()
        if report_dir is None:
            return

        state_name = self.channel_sel.get_channel_name() if hasattr(self.channel_sel, 'get_channel_name') else "数据"

        img_path = None
        try:
            img_path = save_figure_to_file(self.canvas, report_dir, prefix='tab3_matrix')
        except Exception:
            img_path = None

        preprocess_info = getattr(self, '_preprocess_info', None)
        content = build_matrix_block_md(state_name, self.matrix_result, viz_img=img_path, preprocess_info=preprocess_info)
        block = ReportBlock(
            source_tab='Tab3 矩阵转换',
            title=f"矩阵转换分析 ({state_name})",
            content_md=content,
            images=[img_path] if img_path else []
        )
        REPORT_MANAGER.add_block(block)
        QMessageBox.information(self, "成功", f"已添加报告BLOCK到Tab6报告管理器\n标题: {block.title}\n图像已保存至: {report_dir}")

    def _get_report_dir(self):
        """获取用户指定的报告目录（从报告Tab），未指定则弹窗提示"""
        from PyQt5.QtWidgets import QMainWindow
        p = self.parent()
        while p is not None and not isinstance(p, QMainWindow):
            p = p.parent()
        
        report_tab = None
        if p is not None:
            if hasattr(p, 'tab_report'):
                report_tab = p.tab_report
            elif hasattr(p, 'tab7'):
                report_tab = p.tab7
        
        if report_tab and hasattr(report_tab, 'report_dir') and report_tab.report_dir:
            return report_tab.report_dir
        
        ret = QMessageBox.question(
            self, "未指定报告目录",
            "尚未指定报告保存目录，是否现在选择？\n（点击'保存位置'按钮也可在报告Tab中设置）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ret == QMessageBox.Yes:
            d = QFileDialog.getExistingDirectory(self, "选择报告保存位置", "")
            if d:
                if report_tab and hasattr(report_tab, 'report_dir'):
                    report_tab.report_dir = d
                    if hasattr(report_tab, 'dir_label'):
                        report_tab.dir_label.setText(f"保存位置: {d}")
                return d
            return None
        return None


# ============= 批量参数对比Tab =============

class BatchCompareTab(QWidget):
    """批量参数对比Tab：支持N组数据的全排列相似性对比
    
    功能：
    1. 加载N组数据（KW1~KWN），每组有标签
    2. 共享预处理：相同的切片/粗粒化方法
    3. 自动计算N×N两两相似性
    4. 结果显示：排序表格 + N×N热力图
    5. 可视化：下拉菜单分通道显示N组波形竖排对比图
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []  # 每组: {'label': 'KW1', 'filepath': '', 'data': None, 'meta': {}, 'fs': 1.0}
        self.result_data = None
        self.heatmap_results = {}  # {algorithm: N×N矩阵}
        self._tf_param_widgets = {}
        self.setup_ui()
        self._on_tf_method_changed(0)
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板（带滚动区域）
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # 数据组管理
        group_box = QGroupBox("数据组管理")
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(6)
        
        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.group_list.setMinimumHeight(100)
        self.group_list.setMaximumHeight(150)
        group_layout.addWidget(self.group_list)
        
        btn_layout = QHBoxLayout()
        self.add_group_btn = QPushButton("添加数据组")
        self.add_group_btn.clicked.connect(self.add_data_group)
        btn_layout.addWidget(self.add_group_btn)
        
        self.remove_group_btn = QPushButton("移除选中")
        self.remove_group_btn.clicked.connect(self.remove_selected_groups)
        btn_layout.addWidget(self.remove_group_btn)
        
        self.clear_groups_btn = QPushButton("清空")
        self.clear_groups_btn.clicked.connect(self.clear_all_groups)
        btn_layout.addWidget(self.clear_groups_btn)
        
        group_layout.addLayout(btn_layout)
        
        # 标签编辑
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("标签:"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("如: KW1")
        label_layout.addWidget(self.label_edit)
        self.update_label_btn = QPushButton("更新标签")
        self.update_label_btn.clicked.connect(self.update_group_label)
        label_layout.addWidget(self.update_label_btn)
        group_layout.addLayout(label_layout)
        
        # 实验状态关联（下拉菜单选择自动关联）
        state_layout = QHBoxLayout()
        state_layout.addWidget(QLabel("关联实验状态:"))
        self.exp_state_combo = QComboBox()
        self.exp_state_combo.addItem("（未关联）", "")
        self.exp_state_combo.setEnabled(False)
        self.exp_state_combo.currentIndexChanged.connect(self.associate_experiment_state)
        state_layout.addWidget(self.exp_state_combo, stretch=1)
        group_layout.addLayout(state_layout)
        
        left_layout.addWidget(group_box)
        
        # 预处理设置
        proc_box = QGroupBox("共享预处理")
        proc_layout = QVBoxLayout(proc_box)
        proc_layout.setSpacing(6)
        
        # 切片设置
        slice_layout = QHBoxLayout()
        self.slice_start_spin = QDoubleSpinBox()
        self.slice_start_spin.setRange(0, 100)
        self.slice_start_spin.setSuffix(" s")
        slice_layout.addWidget(QLabel("起始时间:"))
        slice_layout.addWidget(self.slice_start_spin)
        
        self.slice_end_spin = QDoubleSpinBox()
        self.slice_end_spin.setRange(0, 100)
        self.slice_end_spin.setSuffix(" s")
        self.slice_end_spin.setValue(1.0)
        slice_layout.addWidget(QLabel("结束时间:"))
        slice_layout.addWidget(self.slice_end_spin)
        proc_layout.addLayout(slice_layout)
        
        # 降采样
        down_layout = QHBoxLayout()
        self.downsample_check = QCheckBox("启用降采样")
        self.downsample_check.setChecked(False)
        self.downsample_check.stateChanged.connect(self.on_downsample_toggle)
        down_layout.addWidget(self.downsample_check)
        
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(100, 100000000)
        self.max_points_spin.setValue(10000)
        self.max_points_spin.setEnabled(False)
        down_layout.addWidget(QLabel("降采样点数:"))
        down_layout.addWidget(self.max_points_spin)
        down_layout.addStretch()
        proc_layout.addLayout(down_layout)
        
        # 第二时间切片（用于显示的时间范围）
        second_slice_layout = QHBoxLayout()
        self.second_slice_start_spin = QDoubleSpinBox()
        self.second_slice_start_spin.setRange(0, 100)
        self.second_slice_start_spin.setSuffix(" s")
        second_slice_layout.addWidget(QLabel("第二时间切片起始:"))
        second_slice_layout.addWidget(self.second_slice_start_spin)
        
        self.second_slice_end_spin = QDoubleSpinBox()
        self.second_slice_end_spin.setRange(0, 100)
        self.second_slice_end_spin.setSuffix(" s")
        self.second_slice_end_spin.setValue(0.1)
        second_slice_layout.addWidget(QLabel("第二时间切片结束:"))
        second_slice_layout.addWidget(self.second_slice_end_spin)
        
        self.apply_second_slice_btn = QPushButton("应用显示切片")
        self.apply_second_slice_btn.clicked.connect(self.apply_second_time_slice)
        self.apply_second_slice_btn.setEnabled(False)
        second_slice_layout.addWidget(self.apply_second_slice_btn)
        proc_layout.addLayout(second_slice_layout)
        
        self.apply_proc_btn = QPushButton("应用预处理")
        self.apply_proc_btn.clicked.connect(self.apply_preprocessing)
        proc_layout.addWidget(self.apply_proc_btn)
        
        left_layout.addWidget(proc_box)
        
        # 算法选择
        method_box = QGroupBox("相似性算法")
        method_layout = QVBoxLayout(method_box)
        method_layout.setSpacing(6)
        
        # 计算类型选择
        calc_type_layout = QHBoxLayout()
        self.calc_type_combo = QComboBox()
        self.calc_type_combo.addItems(["时域", "频域", "时域+频域"])
        calc_type_layout.addWidget(QLabel("计算类型:"))
        calc_type_layout.addWidget(self.calc_type_combo)
        calc_type_layout.addStretch()
        method_layout.addLayout(calc_type_layout)
        
        # 时域算法列表
        time_method_box = QGroupBox("时域算法")
        time_method_layout = QVBoxLayout(time_method_box)
        self.time_method_list = QListWidget()
        self.time_method_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.time_method_list.setMinimumHeight(80)
        self.time_method_list.setMaximumHeight(120)
        self.time_method_list.addItems([
            '互相关系数', '互相关峰值', '协方差', '皮尔逊相关系数',
            '斯皮尔曼等级相关', '动态时间规整(DTW)', '最大信息系数(MIC)',
            '归一化互相关'
        ])
        self.time_method_list.selectAll()
        time_method_layout.addWidget(self.time_method_list)
        method_layout.addWidget(time_method_box)
        
        # 频域算法列表
        freq_method_box = QGroupBox("频域算法")
        freq_method_layout = QVBoxLayout(freq_method_box)
        self.freq_method_list = QListWidget()
        self.freq_method_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.freq_method_list.setMinimumHeight(120)
        self.freq_method_list.setMaximumHeight(180)
        self.freq_method_list.addItems([
            '频谱欧几里得距离', '频谱曼哈顿距离', '频谱余弦相似度',
            '频谱皮尔逊相关', '频谱MSE', '频谱RMSE', '频谱MAE',
            '频谱互相关', '频谱DTW', '频谱SSIM', '频谱巴氏距离',
            '频谱能量差', '频谱熵差', '频谱KL散度', '频谱JS散度',
            '频谱相干性', '频谱重心差', '频谱带宽差', '频谱平坦度差',
            '频谱 rolloff 差'
        ])
        self.freq_method_list.selectAll()
        freq_method_layout.addWidget(self.freq_method_list)
        method_layout.addWidget(freq_method_box)
        
        left_layout.addWidget(method_box)
        
        # 频域变换设置
        tf_box = QGroupBox("频域变换设置")
        tf_layout = QVBoxLayout(tf_box)
        tf_layout.setSpacing(6)
        
        tf_row1 = QHBoxLayout()
        tf_row1.addWidget(QLabel("时频变换方法:"))
        self.tf_method_combo = QComboBox()
        for m in TIME_FREQ_METHODS.keys():
            self.tf_method_combo.addItem(m)
        self.tf_method_combo.currentIndexChanged.connect(self._on_tf_method_changed)
        tf_row1.addWidget(self.tf_method_combo, stretch=1)
        tf_layout.addLayout(tf_row1)
        
        self.tf_desc_label = QLabel()
        self.tf_desc_label.setWordWrap(True)
        self.tf_desc_label.setMinimumHeight(40)
        self.tf_desc_label.setStyleSheet("background-color: #FFF8E1; padding: 6px; border: 1px solid #FFC107; border-radius: 3px;")
        tf_layout.addWidget(self.tf_desc_label)
        
        self.tf_params_group = QGroupBox("算法参数")
        self.tf_params_layout = QFormLayout(self.tf_params_group)
        self.tf_params_group.setMinimumHeight(60)
        tf_layout.addWidget(self.tf_params_group)
        
        left_layout.addWidget(tf_box)
        
        # 计算按钮
        self.compute_btn = QPushButton("计算全部两两相似性")
        self.compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.compute_btn.clicked.connect(self.compute_all_pairs)
        self.compute_btn.setEnabled(False)
        left_layout.addWidget(self.compute_btn)
        
        # 添加报告按钮
        self.add_report_btn = QPushButton("添加报告BLOCK")
        self.add_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.add_report_btn.clicked.connect(self.add_report_block)
        self.add_report_btn.setEnabled(False)
        left_layout.addWidget(self.add_report_btn)
        
        left_layout.addStretch()
        
        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 结果子Tab
        self.result_tabs = QTabWidget()
        
        # 表格结果（包含时域和频域两个子Tab）
        table_main_tab = QWidget()
        table_main_layout = QVBoxLayout(table_main_tab)
        self.table_subtabs = QTabWidget()
        
        # 时域表格
        time_table_tab = QWidget()
        time_table_layout = QVBoxLayout(time_table_tab)
        self.time_result_table = QTableWidget()
        self.time_result_table.setAlternatingRowColors(True)
        time_table_layout.addWidget(self.time_result_table)
        self.table_subtabs.addTab(time_table_tab, "时域结果")
        
        # 频域表格
        freq_table_tab = QWidget()
        freq_table_layout = QVBoxLayout(freq_table_tab)
        self.freq_result_table = QTableWidget()
        self.freq_result_table.setAlternatingRowColors(True)
        freq_table_layout.addWidget(self.freq_result_table)
        self.table_subtabs.addTab(freq_table_tab, "频域结果")
        
        # 合并表格（显示所有结果）
        merged_table_tab = QWidget()
        merged_table_layout = QVBoxLayout(merged_table_tab)
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        merged_table_layout.addWidget(self.result_table)
        self.table_subtabs.addTab(merged_table_tab, "合并结果")
        
        # 通道相关性指标排序表格
        corr_ranking_tab = QWidget()
        corr_ranking_layout = QVBoxLayout(corr_ranking_tab)
        self.corr_ranking_table = QTableWidget()
        self.corr_ranking_table.setAlternatingRowColors(True)
        corr_ranking_layout.addWidget(self.corr_ranking_table)
        self.table_subtabs.addTab(corr_ranking_tab, "通道相关性排序")
        
        table_main_layout.addWidget(self.table_subtabs)
        self.result_tabs.addTab(table_main_tab, "排序表格")
        
        # 热力图结果
        heatmap_tab = QWidget()
        heatmap_layout = QVBoxLayout(heatmap_tab)
        
        heatmap_top_layout = QHBoxLayout()
        self.heatmap_alg_combo = QComboBox()
        heatmap_top_layout.addWidget(QLabel("选择算法:"))
        heatmap_top_layout.addWidget(self.heatmap_alg_combo)
        heatmap_top_layout.addStretch()
        heatmap_layout.addLayout(heatmap_top_layout)
        
        self.heatmap_canvas = create_canvas(heatmap_tab)
        self.heatmap_toolbar = NavigationToolbar(self.heatmap_canvas, heatmap_tab)
        heatmap_layout.addWidget(self.heatmap_toolbar)
        heatmap_layout.addWidget(self.heatmap_canvas)
        self.result_tabs.addTab(heatmap_tab, "热力图")
        
        # 波形对比可视化
        viz_tab = QWidget()
        viz_layout = QVBoxLayout(viz_tab)
        
        viz_top_layout = QHBoxLayout()
        self.channel_combo = QComboBox()
        viz_top_layout.addWidget(QLabel("选择通道:"))
        viz_top_layout.addWidget(self.channel_combo)
        
        self.waveform_mode_combo = QComboBox()
        self.waveform_mode_combo.addItems(["时域波形", "频域波形"])
        self.waveform_mode_combo.currentIndexChanged.connect(self.visualize_waveforms)
        viz_top_layout.addWidget(QLabel("显示模式:"))
        viz_top_layout.addWidget(self.waveform_mode_combo)
        
        self.downsample_display_check = QCheckBox("显示粗粒化")
        self.downsample_display_check.setChecked(False)
        self.downsample_display_check.stateChanged.connect(self.visualize_waveforms)
        viz_top_layout.addWidget(self.downsample_display_check)
        
        self.downsample_display_spin = QSpinBox()
        self.downsample_display_spin.setRange(100, 10000)
        self.downsample_display_spin.setValue(1000)
        self.downsample_display_spin.setEnabled(False)
        viz_top_layout.addWidget(QLabel("粗粒化点数:"))
        viz_top_layout.addWidget(self.downsample_display_spin)
        
        viz_top_layout.addStretch()
        viz_layout.addLayout(viz_top_layout)
        
        self.waveform_canvas = create_canvas(viz_tab)
        self.waveform_toolbar = NavigationToolbar(self.waveform_canvas, viz_tab)
        viz_layout.addWidget(self.waveform_toolbar)
        viz_layout.addWidget(self.waveform_canvas)
        self.result_tabs.addTab(viz_tab, "波形对比")
        
        right_layout.addWidget(self.result_tabs)
        splitter.addWidget(right_panel)
        
        main_layout.addWidget(splitter)
    
    def _on_downsample_display_toggle(self, state):
        self.downsample_display_spin.setEnabled(state == Qt.Checked)
    
    def _on_tf_method_changed(self, index):
        method_name = self.tf_method_combo.currentText()
        info = TIME_FREQ_METHODS.get(method_name, {})
        
        self.tf_desc_label.setText(info.get('desc', ''))
        
        while self.tf_params_layout.rowCount() > 0:
            self.tf_params_layout.removeRow(0)
        
        self._tf_param_widgets = {}
        for pname, pdesc, pmin, pmax, pstep, pdefault, phelp in info.get('params', []):
            spin = QDoubleSpinBox()
            spin.setRange(pmin, pmax)
            spin.setSingleStep(pstep)
            spin.setValue(pdefault)
            spin.setToolTip(phelp)
            self.tf_params_layout.addRow(f"{pname} ({pdesc}):", spin)
            self._tf_param_widgets[pname] = spin
    
    def get_tf_params(self):
        params = {}
        for pname, widget in self._tf_param_widgets.items():
            try:
                params[pname] = float(widget.value())
            except:
                params[pname] = 0
        return params
    
    def add_data_group(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择数据文件（可按住Ctrl多选）", "",
            "TDMS文件 (*.tdms);;NPY文件 (*.npy);;CSV文件 (*.csv)"
        )
        if not files:
            return
        
        success_count = 0
        fail_count = 0
        failed_files = []
        
        for filepath in files:
            if not os.path.exists(filepath):
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
                continue
            
            try:
                data, meta, fs = self._load_file(filepath)
                if data is None:
                    fail_count += 1
                    failed_files.append(os.path.basename(filepath))
                    continue
                
                label = f"KW{len(self.groups) + 1}"
                
                # 获取当前选中的实验状态
                selected_state = self.exp_state_combo.currentData()
                
                group_data = {
                    'label': label,
                    'filepath': filepath,
                    'data': data,
                    'meta': meta,
                    'fs': fs,
                    'proc_data': None,
                    'proc_meta': None
                }
                
                # 如果当前有选中的实验状态，自动关联
                if selected_state:
                    group_data['experiment_state'] = selected_state
                    item = QListWidgetItem(f"{label}[{selected_state}]: {os.path.basename(filepath)}")
                    log(f"[Batch] 添加数据组: {label}, 自动关联实验状态: {selected_state}")
                else:
                    item = QListWidgetItem(f"{label}: {os.path.basename(filepath)}")
                    log(f"[Batch] 添加数据组: {label}")
                
                self.groups.append(group_data)
                self.group_list.addItem(item)
                success_count += 1
            except Exception as e:
                log(f"[Batch] 加载文件失败: {filepath}, {e}")
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
        
        self.update_ui_state()
        self.update_channel_combo()
        
        # 显示导入结果
        if success_count > 0:
            msg = f"成功导入 {success_count} 个数据文件"
            if fail_count > 0:
                msg += f"\n\n失败 {fail_count} 个文件:\n" + "\n".join(failed_files)
            QMessageBox.information(self, "导入完成", msg)
    
    def _load_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.tdms':
            try:
                from file_reader import load_data
                data, fs, meta = load_data(filepath)
                return data, meta, fs
            except Exception as e:
                log(f"[Batch] TDMS加载错误: {e}")
                return None, None, 1.0
        elif ext == '.npy':
            data = np.load(filepath)
            return data, {}, 1.0
        elif ext == '.csv':
            data = np.loadtxt(filepath, delimiter=',')
            return data, {}, 1.0
        return None, None, 1.0
    
    def remove_selected_groups(self):
        rows = sorted([self.group_list.row(i) for i in self.group_list.selectedItems()], reverse=True)
        for row in rows:
            self.group_list.takeItem(row)
            del self.groups[row]
        self.update_ui_state()
        self.update_channel_combo()
    
    def clear_all_groups(self):
        if QMessageBox.question(self, "确认", "确定清空所有数据组？") == QMessageBox.Yes:
            self.groups.clear()
            self.group_list.clear()
            self.result_data = None
            self.heatmap_results = {}
            self.update_ui_state()
    
    def update_group_label(self):
        row = self.group_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个数据组")
            return
        
        label = self.label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "提示", "标签不能为空")
            return
        
        self.groups[row]['label'] = label
        item = self.group_list.item(row)
        item.setText(f"{label}: {os.path.basename(self.groups[row]['filepath'])}")
        log(f"[Batch] 更新标签: {label}")
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.exp_state_combo.blockSignals(True)
        self.exp_state_combo.clear()
        self.exp_state_combo.addItem("（未关联）", "")
        for n in names:
            self.exp_state_combo.addItem(n, n)
        self.exp_state_combo.blockSignals(False)
        self.exp_state_combo.setEnabled(len(names) > 0)
    
    def associate_experiment_state(self):
        """下拉菜单选择自动关联实验状态"""
        row = self.group_list.currentRow()
        if row < 0:
            return
        
        state_name = self.exp_state_combo.currentData()
        
        if state_name:
            self.groups[row]['experiment_state'] = state_name
            item = self.group_list.item(row)
            filepath = os.path.basename(self.groups[row]['filepath'])
            label = self.groups[row]['label']
            item.setText(f"{label}[{state_name}]: {filepath}")
            log(f"[Batch] 数据组 {label} 关联实验状态: {state_name}")
        else:
            if 'experiment_state' in self.groups[row]:
                del self.groups[row]['experiment_state']
            item = self.group_list.item(row)
            filepath = os.path.basename(self.groups[row]['filepath'])
            label = self.groups[row]['label']
            item.setText(f"{label}: {filepath}")
    
    def push_experiment_state(self, state_name):
        """接收从实验状态定义Tab推送的实验状态，并自动关联到未关联的数据组"""
        self.exp_state_combo.blockSignals(True)
        idx = self.exp_state_combo.findData(state_name)
        if idx >= 0:
            self.exp_state_combo.setCurrentIndex(idx)
        self.exp_state_combo.blockSignals(False)
        
        # 自动将推送的实验状态关联到所有未关联的数据组
        for i, group in enumerate(self.groups):
            if 'experiment_state' not in group or not group['experiment_state']:
                group['experiment_state'] = state_name
                item = self.group_list.item(i)
                filepath = os.path.basename(group['filepath'])
                label = group['label']
                item.setText(f"{label}[{state_name}]: {filepath}")
                log(f"[Batch] 数据组 {label} 自动关联实验状态: {state_name}")
        
        log(f"[Batch] 接收推送的实验状态: {state_name}")
    
    def check_experiment_state_associated(self):
        """检查是否所有数据组都关联了实验状态"""
        unassociated = []
        for i, group in enumerate(self.groups):
            if 'experiment_state' not in group or not group['experiment_state']:
                unassociated.append(group.get('label', f"组{i+1}"))
        
        if unassociated:
            QMessageBox.warning(self, "提示", 
                f"以下数据组未关联实验状态:\n" + "\n".join(unassociated) + 
                f"\n\n请在实验状态定义Tab中定义实验状态，并关联到各数据组。")
            return False
        return True
    
    def on_downsample_toggle(self, state):
        """降采样复选框状态切换"""
        self.max_points_spin.setEnabled(state == Qt.Checked)
    
    def apply_preprocessing(self):
        if len(self.groups) == 0:
            QMessageBox.warning(self, "提示", "请先添加数据组")
            return
        
        start_time = self.slice_start_spin.value()
        end_time = self.slice_end_spin.value()
        use_downsample = self.downsample_check.isChecked()
        max_points = self.max_points_spin.value()
        
        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "结束时间必须大于起始时间")
            return
        
        log(f"[Batch] 应用预处理: 切片[{start_time}-{end_time}s], 降采样={use_downsample}")
        
        for i, group in enumerate(self.groups):
            data = group['data']
            fs = group['fs']
            
            start_idx = int(start_time * fs)
            end_idx = int(end_time * fs)
            
            if start_idx >= len(data):
                log(f"[Batch] 组 {group['label']} 起始索引超出范围")
                continue
            
            end_idx = min(end_idx, len(data))
            sliced_data = data[start_idx:end_idx]
            
            if use_downsample and len(sliced_data) > max_points:
                from scipy import signal
                sliced_data = signal.resample(sliced_data, max_points)
            
            group['proc_data'] = sliced_data
            group['proc_meta'] = {
                'fs': fs,
                'slice_start': start_time,
                'slice_end': end_time,
                'downsampled': use_downsample,
                'original_length': len(data),
                'processed_length': len(sliced_data),
                'channel_map': group['meta'].get('channel_map', {})
            }
        
        QMessageBox.information(self, "完成", f"已对 {len(self.groups)} 组数据应用预处理")
        self.compute_btn.setEnabled(True)
        self.apply_second_slice_btn.setEnabled(True)
        self.update_channel_combo()
        self.visualize_waveforms()
    
    def apply_second_time_slice(self):
        start_time = self.second_slice_start_spin.value()
        end_time = self.second_slice_end_spin.value()
        
        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "第二时间切片结束时间必须大于起始时间")
            return
        
        for group in self.groups:
            proc_meta = group.get('proc_meta', {})
            original_start = proc_meta.get('slice_start', 0)
            
            display_start_time = original_start + start_time
            display_end_time = original_start + end_time
            
            group['display_slice_start'] = display_start_time
            group['display_slice_end'] = display_end_time
        
        log(f"[Batch] 应用第二时间切片: {start_time}s - {end_time}s")
        self.visualize_waveforms()
    
    def update_channel_combo(self):
        self.channel_combo.clear()
        if len(self.groups) > 0:
            meta = self.groups[0].get('proc_meta') or self.groups[0].get('meta') or {}
            channel_map = meta.get('channel_map', {})
            if channel_map:
                channels = sorted(channel_map.keys())
            else:
                channels = [f"CH{i+1}" for i in range(self._get_num_channels())]
            self.channel_combo.addItems(channels)
            self.channel_combo.currentIndexChanged.connect(self.visualize_waveforms)
    
    def _get_num_channels(self):
        if len(self.groups) == 0:
            return 0
        data = self.groups[0].get('proc_data', self.groups[0].get('data'))
        if data is None:
            return 0
        return data.shape[1] if len(data.shape) > 1 else 1
    
    def get_channel_data(self, group, channel_name):
        data = group.get('proc_data', group.get('data'))
        if data is None:
            return None
        
        meta = group.get('proc_meta') or group.get('meta') or {}
        if isinstance(meta, dict) and 'channel_map' in meta:
            cm = meta.get('channel_map') or {}
            if channel_name in cm:
                return np.asarray(cm[channel_name]).flatten()
        
        try:
            idx = int(channel_name.replace('CH', '')) - 1
            if len(data.shape) > 1 and idx < data.shape[1]:
                return data[:, idx].flatten()
        except (ValueError, AttributeError):
            pass
        
        return data.flatten()
    
    def get_all_channels(self):
        if hasattr(self, '_channels') and self._channels:
            return self._channels
        
        if not self.groups:
            return []
        
        group = self.groups[0]
        data = group.get('proc_data', group.get('data'))
        
        if data is not None and len(data.shape) > 1:
            n_channels = data.shape[1]
            return [f'CH{i+1}' for i in range(n_channels)]
        
        return ['CH1']
    
    def update_ui_state(self):
        has_data = len(self.groups) >= 2
        has_results = self.result_data is not None
        
        self.compute_btn.setEnabled(has_data)
        self.add_report_btn.setEnabled(has_results)
        self.apply_proc_btn.setEnabled(len(self.groups) > 0)
    
    def compute_all_pairs(self):
        n_groups = len(self.groups)
        if n_groups < 2:
            QMessageBox.warning(self, "提示", "至少需要2组数据")
            return
        
        calc_type = self.calc_type_combo.currentText()
        
        time_methods = [item.text() for item in self.time_method_list.selectedItems()]
        freq_methods = [item.text() for item in self.freq_method_list.selectedItems()]
        
        if calc_type == "时域":
            selected_methods = time_methods
            domain = "time"
        elif calc_type == "频域":
            selected_methods = freq_methods
            domain = "freq"
        else:
            selected_methods = time_methods + freq_methods
            domain = "both"
        
        if not selected_methods:
            QMessageBox.warning(self, "提示", "请至少选择一种算法")
            return
        
        log(f"[Batch] 开始计算 {n_groups}×{n_groups} 两两相似性 (类型: {calc_type})")
        
        self.compute_btn.setEnabled(False)
        self.add_report_btn.setEnabled(False)
        
        total_tasks = n_groups * n_groups * len(selected_methods)
        self._progress_dialog = QProgressDialog(
            f"正在计算 {len(selected_methods)} 种算法的 {n_groups}×{n_groups} 组合...",
            "取消", 0, total_tasks, self
        )
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(500)
        
        channels = []
        if self.channel_combo.count() > 0:
            channels = [self.channel_combo.itemText(i) for i in range(self.channel_combo.count())]
        else:
            n_ch = self._get_num_channels()
            channels = [f"CH{i+1}" for i in range(n_ch)]
        
        if not channels:
            QMessageBox.warning(self, "提示", "未找到通道数据")
            return
        
        tf_method = self.tf_method_combo.currentText()
        tf_params = self.get_tf_params()
        
        def task(progress_cb):
            all_results = []
            heatmap_results = {}
            
            for method in selected_methods:
                heatmap_results[method] = np.eye(n_groups)
            
            done = 0
            total = n_groups * n_groups * len(selected_methods)
            
            for ch in channels:
                for i in range(n_groups):
                    for j in range(n_groups):
                        group_i = self.groups[i]
                        group_j = self.groups[j]
                        
                        data_i = self.get_channel_data(group_i, ch)
                        data_j = self.get_channel_data(group_j, ch)
                        
                        if data_i is None or data_j is None:
                            done += len(selected_methods)
                            continue
                        
                        for method in selected_methods:
                            try:
                                is_time_domain = method in time_methods
                                
                                if is_time_domain:
                                    from signal_processing import compute_time_similarity_batch
                                    result = compute_time_similarity_batch(
                                        data_i, data_j, [method], fs=group_i['fs']
                                    )
                                else:
                                    from signal_processing import compute_freq_similarity_batch
                                    result = compute_freq_similarity_batch(
                                        data_i, data_j, [method], fs=group_i['fs']
                                    )
                                
                                if result and len(result) > 0 and result[0].get('ok', False):
                                    value = result[0]['value']
                                    indicators = result[0].get('indicators', {})
                                    
                                    all_results.append({
                                        'method': method,
                                        'value': value,
                                        'indicators': indicators,
                                        'group_a': group_i['label'],
                                        'group_b': group_j['label'],
                                        'channel': ch,
                                        'data_a': data_i,
                                        'data_b': data_j,
                                        'fs': group_i['fs'],
                                        'domain': '时域' if is_time_domain else '频域'
                                    })
                                    
                                    if ch == channels[0]:
                                        heatmap_results[method][i, j] = value
                            except Exception as e:
                                log(f"[Batch] 计算 {ch}:{method}({group_i['label']}, {group_j['label']}) 失败: {e}")
                            
                            done += 1
                            if progress_cb:
                                progress_cb(done, total, method, f"{group_i['label']}-{group_j['label']}")
            
            return all_results, heatmap_results, channels, calc_type
        
        self._worker = ComputeWorker(task)
        self._worker.progress.connect(self._on_compute_progress)
        self._worker.finished_ok.connect(self._on_compute_done)
        self._worker.error.connect(self._on_compute_error)
        self._progress_dialog.canceled.connect(self._worker_cancel)
        self._worker.start()
    
    def _worker_cancel(self):
        if hasattr(self, '_worker') and self._worker:
            self._worker.cancel()
            log("[Batch] 用户取消计算")
    
    def _on_compute_progress(self, done, total, method, value):
        dialog = getattr(self, '_progress_dialog', None)
        if dialog is not None:
            try:
                dialog.setValue(done)
                dialog.setLabelText(f"正在计算: {method} ({done}/{total})")
            except Exception:
                pass
    
    def _on_compute_done(self, result):
        try:
            if result is None:
                log("[Batch] _on_compute_done: result is None")
                return
            
            if len(result) == 4:
                all_results, heatmap_results, channels, calc_type = result
            else:
                all_results, heatmap_results, channels = result
                calc_type = "时域"
            
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                try:
                    self._progress_dialog.close()
                except Exception:
                    pass
                self._progress_dialog = None
            
            if not isinstance(all_results, list):
                log(f"[Batch] _on_compute_done: all_results is not list, type={type(all_results)}")
                return
            
            self.result_data = all_results
            self.heatmap_results = heatmap_results if isinstance(heatmap_results, dict) else {}
            self._channels = channels if isinstance(channels, list) else []
            self._calc_type = calc_type
            
            self.display_results(all_results)
            self.update_heatmap_combo()
            self.update_ui_state()
            
            QMessageBox.information(self, "计算完成", 
                f"成功完成 {len(all_results)} 项计算\n\n"
                f"计算类型: {calc_type}\n"
                f"数据组数: {len(self.groups)}\n"
                f"算法数: {len(self.heatmap_results)}\n"
                f"通道数: {len(self._channels)}")
            
            self.visualize_waveforms()
        except Exception as e:
            log(f"[Batch] _on_compute_done 异常: {e}")
            import traceback
            log(f"[Batch] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "计算错误", f"处理结果时发生错误: {str(e)}")
    
    def _on_compute_error(self, msg):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        QMessageBox.warning(self, "计算错误", f"计算失败: {msg}")
        self.compute_btn.setEnabled(True)
    
    def display_results(self, results):
        try:
            if not results:
                return
            
            time_results = [r for r in results if r.get('domain') == '时域']
            freq_results = [r for r in results if r.get('domain') == '频域']
            
            def populate_table(table, data, domain_name):
                table.setRowCount(0)
                table.setColumnCount(6)
                table.setHorizontalHeaderLabels(['算法', '通道', '组A', '组B', '值', '指标'])
                
                sorted_data = sorted(data, key=lambda x: x.get('value', 0), reverse=True)
                
                for i, r in enumerate(sorted_data):
                    try:
                        table.insertRow(i)
                        table.setItem(i, 0, QTableWidgetItem(r.get('method', '')))
                        table.setItem(i, 1, QTableWidgetItem(r.get('channel', '')))
                        table.setItem(i, 2, QTableWidgetItem(r.get('group_a', '')))
                        table.setItem(i, 3, QTableWidgetItem(r.get('group_b', '')))
                        
                        value = r.get('value')
                        if isinstance(value, (int, float)):
                            table.setItem(i, 4, QTableWidgetItem(f"{value:.6f}"))
                        else:
                            table.setItem(i, 4, QTableWidgetItem(str(value)))
                        
                        indicators = r.get('indicators', {})
                        if indicators:
                            parts = []
                            for k, v in indicators.items():
                                if isinstance(v, (int, float)):
                                    parts.append(f"{k}={v:.4f}")
                                else:
                                    parts.append(f"{k}={v}")
                            indicator_str = "; ".join(parts)
                        else:
                            indicator_str = ""
                        table.setItem(i, 5, QTableWidgetItem(indicator_str))
                    except Exception as row_err:
                        log(f"[Batch] display_results {domain_name}行{i}错误: {row_err}")
                        continue
                
                table.resizeColumnsToContents()
            
            populate_table(self.time_result_table, time_results, "时域")
            populate_table(self.freq_result_table, freq_results, "频域")
            
            self.result_table.setRowCount(0)
            self.result_table.setColumnCount(7)
            self.result_table.setHorizontalHeaderLabels(['领域', '算法', '通道', '组A', '组B', '值', '指标'])
            
            sorted_all = sorted(results, key=lambda x: x.get('value', 0), reverse=True)
            
            for i, r in enumerate(sorted_all):
                try:
                    self.result_table.insertRow(i)
                    self.result_table.setItem(i, 0, QTableWidgetItem(r.get('domain', '时域')))
                    self.result_table.setItem(i, 1, QTableWidgetItem(r.get('method', '')))
                    self.result_table.setItem(i, 2, QTableWidgetItem(r.get('channel', '')))
                    self.result_table.setItem(i, 3, QTableWidgetItem(r.get('group_a', '')))
                    self.result_table.setItem(i, 4, QTableWidgetItem(r.get('group_b', '')))
                    
                    value = r.get('value')
                    if isinstance(value, (int, float)):
                        self.result_table.setItem(i, 5, QTableWidgetItem(f"{value:.6f}"))
                    else:
                        self.result_table.setItem(i, 5, QTableWidgetItem(str(value)))
                    
                    indicators = r.get('indicators', {})
                    if indicators:
                        parts = []
                        for k, v in indicators.items():
                            if isinstance(v, (int, float)):
                                parts.append(f"{k}={v:.4f}")
                            else:
                                parts.append(f"{k}={v}")
                        indicator_str = "; ".join(parts)
                    else:
                        indicator_str = ""
                    self.result_table.setItem(i, 6, QTableWidgetItem(indicator_str))
                except Exception as row_err:
                    log(f"[Batch] display_results 合并行{i}错误: {row_err}")
                    continue
            
            self.result_table.resizeColumnsToContents()
            
            self.update_corr_ranking_table()
        except Exception as e:
            log(f"[Batch] display_results 异常: {e}")
            import traceback
            log(f"[Batch] 堆栈跟踪:\n{traceback.format_exc()}")
    
    def update_corr_ranking_table(self):
        try:
            if not self.result_data:
                return
            
            channel_corr = {}
            
            for r in self.result_data:
                channel = r.get('channel', '')
                value = r.get('value', 0)
                if isinstance(value, (int, float)):
                    if channel not in channel_corr:
                        channel_corr[channel] = []
                    channel_corr[channel].append(value)
            
            ranking = []
            for channel, values in channel_corr.items():
                if values:
                    weighted_mean = sum(values) / len(values)
                    ranking.append({
                        'channel': channel,
                        'weighted_mean': weighted_mean,
                        'count': len(values)
                    })
            
            ranking.sort(key=lambda x: x['weighted_mean'], reverse=True)
            
            self.corr_ranking_table.setRowCount(len(ranking))
            self.corr_ranking_table.setColumnCount(3)
            self.corr_ranking_table.setHorizontalHeaderLabels(['排名', '通道', '加权均值'])
            
            for i, item in enumerate(ranking):
                self.corr_ranking_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.corr_ranking_table.setItem(i, 1, QTableWidgetItem(item['channel']))
                self.corr_ranking_table.setItem(i, 2, QTableWidgetItem(f"{item['weighted_mean']:.6f}"))
            
            self.corr_ranking_table.resizeColumnsToContents()
        except Exception as e:
            log(f"[Batch] update_corr_ranking_table 异常: {e}")
            import traceback
            log(f"[Batch] 堆栈跟踪:\n{traceback.format_exc()}")
    
    def update_heatmap_combo(self):
        self.heatmap_alg_combo.clear()
        for alg in self.heatmap_results.keys():
            self.heatmap_alg_combo.addItem(alg)
        self.heatmap_alg_combo.currentIndexChanged.connect(self.visualize_heatmap)
        if self.heatmap_alg_combo.count() > 0:
            self.visualize_heatmap(0)
    
    def visualize_heatmap(self, index):
        if index < 0 or not self.heatmap_results:
            return
        
        alg_name = self.heatmap_alg_combo.itemText(index)
        if alg_name not in self.heatmap_results:
            return
        
        matrix = self.heatmap_results[alg_name]
        labels = [g['label'] for g in self.groups]
        
        fig = self.heatmap_canvas.figure
        fig.clear()
        
        ax = fig.add_subplot(111)
        im = ax.imshow(matrix, cmap='viridis', interpolation='nearest', vmin=0, vmax=1)
        
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_yticklabels(labels)
        
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, f"{matrix[i, j]:.3f}", ha='center', va='center', 
                        color='white' if matrix[i, j] < 0.5 else 'black', fontsize=8)
        
        ax.set_title(f"{alg_name} - 相似度矩阵")
        ax.set_xlabel("组B")
        ax.set_ylabel("组A")
        
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        self.heatmap_canvas.draw()
    
    def visualize_waveforms(self):
        try:
            if len(self.groups) == 0:
                return
            
            mode = self.waveform_mode_combo.currentText()
            use_downsample = self.downsample_display_check.isChecked()
            downsample_points = self.downsample_display_spin.value()
            
            n_groups = len(self.groups)
            channels = self.get_all_channels()
            
            if not channels:
                return
            
            n_channels = len(channels)
            
            fig = self.waveform_canvas.figure
            fig.clear()
            fig.set_size_inches(16, 2 * n_channels)
            
            gs = fig.add_gridspec(n_channels, 1, hspace=0.3)
            axes = gs.subplots(sharex=True)
            
            if n_channels == 1:
                axes = [axes]
            
            for ch_idx, channel_name in enumerate(channels):
                ax = axes[ch_idx]
                
                all_data = []
                all_time_ranges = []
                
                for i, group in enumerate(self.groups):
                    data = self.get_channel_data(group, channel_name)
                    if data is not None:
                        proc_meta = group.get('proc_meta', {})
                        slice_start = proc_meta.get('slice_start', 0)
                        display_start = group.get('display_slice_start', slice_start)
                        display_end = group.get('display_slice_end', slice_start + len(data) / group['fs'])
                        
                        if display_start > slice_start:
                            offset_start = int((display_start - slice_start) * group['fs'])
                            offset_end = int((display_end - slice_start) * group['fs'])
                            data = data[offset_start:offset_end]
                        
                        all_data.append(data)
                        all_time_ranges.append((display_start, display_end))
                
                if not all_data:
                    continue
                
                for i, (group, data, (display_start, display_end)) in enumerate(zip(self.groups, all_data, all_time_ranges)):
                    if use_downsample and len(data) > downsample_points:
                        from scipy import signal
                        data = signal.resample(data, downsample_points)
                    
                    if mode == "频域波形":
                        from scipy import signal
                        fs = group['fs']
                        f, Pxx = signal.welch(data, fs=fs, nperseg=min(len(data), 1024))
                        ax.semilogy(f, Pxx, linewidth=1.0, label=group['label'])
                        ax.set_xlim(0, fs/2)
                    else:
                        t = np.linspace(display_start, display_end, len(data))
                        ax.plot(t, data, linewidth=1.0, label=group['label'])
                
                ax.set_ylabel(channel_name, rotation=0, labelpad=20, fontsize=10)
                ax.tick_params(axis='both', labelsize=8)
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
            
            axes[-1].set_xlabel("频率 (Hz)" if mode == "频域波形" else "时间 (s)", fontsize=10)
            
            domain_name = "频域" if mode == "频域波形" else "时域"
            fig.suptitle(f"{domain_name}对比（按通道组织，第二时间切片）", fontsize=16, y=0.99)
            fig.tight_layout(rect=[0.08, 0.02, 1, 0.96])
            self.waveform_canvas.draw()
        except Exception as e:
            log(f"[Batch] visualize_waveforms 异常: {e}")
            import traceback
            log(f"[Batch] 堆栈跟踪:\n{traceback.format_exc()}")
    
    def add_report_block(self):
        if not self.result_data:
            QMessageBox.warning(self, "提示", "请先计算相似性结果")
            return
        
        if not self.check_experiment_state_associated():
            return
        
        try:
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import save_figure_to_file
            import matplotlib.pyplot as plt
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先在报告Tab设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            labels = [g['label'] for g in self.groups]
            channels = self.get_all_channels()
            n_groups = len(self.groups)
            n_channels = len(channels)
            
            use_downsample = self.downsample_display_check.isChecked()
            downsample_points = self.downsample_display_spin.value()
            
            all_images = []
            
            # 为每个通道生成时域波形图
            md_content = f"## 批量参数对比报告\n\n"
            
            # 实验状态定义表 - 只显示当前Tab关联的实验状态
            from experiment_state import STATE_REGISTRY
            state_names = []
            for group in self.groups:
                state_name = group.get('experiment_state')
                if state_name and state_name not in state_names:
                    state_names.append(state_name)
            
            md_content += "### 实验状态定义\n\n"
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"**数据组数**: {len(labels)}\n\n"
            md_content += f"**参数标签**: {', '.join(labels)}\n\n"
            md_content += f"**计算类型**: {getattr(self, '_calc_type', '时域')}\n\n"
            md_content += f"**预处理设置**: 切片[{self.slice_start_spin.value():.2f}-{self.slice_end_spin.value():.2f}s], "
            md_content += f"降采样={'是' if self.downsample_check.isChecked() else '否'}\n\n"
            
            md_content += "### 通道波形对比\n\n"
            
            import itertools
            for ch_idx, channel_name in enumerate(channels):
                channel_results = [r for r in self.result_data if r.get('channel') == channel_name]
                pairs = list(itertools.combinations(labels, 2))
                n_pairs = len(pairs)
                
                n_rows = n_groups + n_groups + n_pairs + n_pairs
                n_cols = 1
                
                fig_height = n_rows * 1.8
                fig_width = 12.0
                if fig_height > 24:
                    fig_height = 24
                figsize = (fig_width, fig_height)
                
                fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
                
                row_idx = 0
                
                for i, group in enumerate(self.groups):
                    data = self.get_channel_data(group, channel_name)
                    if data is not None:
                        if use_downsample and len(data) > downsample_points:
                            from scipy import signal
                            data = signal.resample(data, downsample_points)
                        
                        display_start = group.get('display_slice_start', 0)
                        display_end = group.get('display_slice_end', len(data) / group['fs'])
                        t = np.linspace(display_start, display_end, len(data))
                        axes[row_idx].plot(t, data, linewidth=1.0)
                        axes[row_idx].set_title(f"时域 - {group['label']}", fontsize=10)
                        axes[row_idx].set_xlabel("时间(s)", fontsize=8)
                        axes[row_idx].tick_params(axis='both', labelsize=8)
                        axes[row_idx].grid(True, alpha=0.3)
                    row_idx += 1
                
                for i, group in enumerate(self.groups):
                    data = self.get_channel_data(group, channel_name)
                    if data is not None:
                        if use_downsample and len(data) > downsample_points:
                            from scipy import signal
                            data = signal.resample(data, downsample_points)
                        
                        fs = group['fs']
                        from scipy import signal
                        f, Pxx = signal.welch(data, fs=fs, nperseg=min(len(data), 1024))
                        axes[row_idx].semilogy(f, Pxx, linewidth=1.0)
                        axes[row_idx].set_xlim(0, fs/2)
                        axes[row_idx].set_title(f"频域 - {group['label']}", fontsize=10)
                        axes[row_idx].set_xlabel("频率(Hz)", fontsize=8)
                        axes[row_idx].tick_params(axis='both', labelsize=8)
                        axes[row_idx].grid(True, alpha=0.3)
                    row_idx += 1
                
                for (label_a, label_b) in pairs:
                    result = None
                    for r in channel_results:
                        if (r.get('group_a') == label_a and r.get('group_b') == label_b and r.get('domain') == '时域') or \
                           (r.get('group_a') == label_b and r.get('group_b') == label_a and r.get('domain') == '时域'):
                            result = r
                            break
                    
                    if result:
                        data_a = result.get('data_a')
                        data_b = result.get('data_b')
                        corr_value = result.get('value', 0)
                        
                        if data_a is not None and data_b is not None:
                            max_points = min(len(data_a), len(data_b), 500)
                            axes[row_idx].scatter(data_a[:max_points], data_b[:max_points], s=2, alpha=0.4)
                            axes[row_idx].set_title(f"时域相关性 - {label_a} vs {label_b}", fontsize=10)
                            axes[row_idx].set_xlabel(label_a, fontsize=8)
                            axes[row_idx].set_ylabel(label_b, fontsize=8)
                            axes[row_idx].tick_params(axis='both', labelsize=8)
                            axes[row_idx].grid(True, alpha=0.3)
                            axes[row_idx].text(0.05, 0.95, f"相关性系数: {corr_value:.4f}", 
                                              transform=axes[row_idx].transAxes, 
                                              ha='left', va='top', fontsize=8,
                                              bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                        else:
                            axes[row_idx].text(0.5, 0.5, 
                                              f"{label_a} vs {label_b}\n值: {corr_value:.6f}", 
                                              ha='center', va='center', fontsize=10)
                    else:
                        axes[row_idx].text(0.5, 0.5, f"{label_a} vs {label_b}\n无时域数据", 
                                          ha='center', va='center', fontsize=10)
                    row_idx += 1
                
                for (label_a, label_b) in pairs:
                    result = None
                    for r in channel_results:
                        if (r.get('group_a') == label_a and r.get('group_b') == label_b and r.get('domain') == '频域') or \
                           (r.get('group_a') == label_b and r.get('group_b') == label_a and r.get('domain') == '频域'):
                            result = r
                            break
                    
                    if result:
                        data_a = result.get('data_a')
                        data_b = result.get('data_b')
                        corr_value = result.get('value', 0)
                        
                        if data_a is not None and data_b is not None:
                            max_points = min(len(data_a), len(data_b), 500)
                            axes[row_idx].scatter(data_a[:max_points], data_b[:max_points], s=2, alpha=0.4)
                            axes[row_idx].set_title(f"频域相关性 - {label_a} vs {label_b}", fontsize=10)
                            axes[row_idx].set_xlabel(label_a, fontsize=8)
                            axes[row_idx].set_ylabel(label_b, fontsize=8)
                            axes[row_idx].tick_params(axis='both', labelsize=8)
                            axes[row_idx].grid(True, alpha=0.3)
                            axes[row_idx].text(0.05, 0.95, f"相关性系数: {corr_value:.4f}", 
                                              transform=axes[row_idx].transAxes, 
                                              ha='left', va='top', fontsize=8,
                                              bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                        else:
                            axes[row_idx].text(0.5, 0.5, 
                                              f"{label_a} vs {label_b}\n值: {corr_value:.6f}", 
                                              ha='center', va='center', fontsize=10)
                    else:
                        axes[row_idx].text(0.5, 0.5, f"{label_a} vs {label_b}\n无频域数据", 
                                          ha='center', va='center', fontsize=10)
                    row_idx += 1
                
                fig.suptitle(f"通道 {channel_name} - 综合分析", fontsize=12)
                fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])
                
                path = os.path.join(report_dir, f"batch_{channel_name}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                all_images.append(path)
                md_content += f"#### 通道 {channel_name}\n\n"
                md_content += f"![通道 {channel_name}](batch_{channel_name}.png)\n\n"
            
            md_content += "### 相似度矩阵\n\n"
            
            for ch_idx, channel_name in enumerate(channels):
                channel_results = [r for r in self.result_data if r.get('channel') == channel_name]
                
                time_matrix = np.eye(n_groups)
                freq_matrix = np.eye(n_groups)
                
                for i, label_a in enumerate(labels):
                    for j, label_b in enumerate(labels):
                        if i != j:
                            for r in channel_results:
                                if ((r.get('group_a') == label_a and r.get('group_b') == label_b) or \
                                    (r.get('group_a') == label_b and r.get('group_b') == label_a)):
                                    if r.get('domain') == '时域':
                                        time_matrix[i, j] = r.get('value', 0)
                                    elif r.get('domain') == '频域':
                                        freq_matrix[i, j] = r.get('value', 0)
                
                fig, axes = plt.subplots(1, 2, figsize=(12, 5))
                
                im = axes[0].imshow(time_matrix, cmap='viridis', aspect='auto')
                axes[0].set_title(f"{channel_name} - 时域相似度矩阵", fontsize=12)
                axes[0].set_xlabel("组B")
                axes[0].set_ylabel("组A")
                axes[0].set_xticks(range(n_groups))
                axes[0].set_yticks(range(n_groups))
                axes[0].set_xticklabels(labels)
                axes[0].set_yticklabels(labels)
                for i in range(n_groups):
                    for j in range(n_groups):
                        axes[0].text(j, i, f"{time_matrix[i, j]:.3f}", ha='center', va='center', 
                                    color='white' if time_matrix[i, j] < 0.5 else 'black', fontsize=8)
                fig.colorbar(im, ax=axes[0])
                
                im = axes[1].imshow(freq_matrix, cmap='viridis', aspect='auto')
                axes[1].set_title(f"{channel_name} - 频域相似度矩阵", fontsize=12)
                axes[1].set_xlabel("组B")
                axes[1].set_ylabel("组A")
                axes[1].set_xticks(range(n_groups))
                axes[1].set_yticks(range(n_groups))
                axes[1].set_xticklabels(labels)
                axes[1].set_yticklabels(labels)
                for i in range(n_groups):
                    for j in range(n_groups):
                        axes[1].text(j, i, f"{freq_matrix[i, j]:.3f}", ha='center', va='center', 
                                    color='white' if freq_matrix[i, j] < 0.5 else 'black', fontsize=8)
                fig.colorbar(im, ax=axes[1])
                
                fig.tight_layout()
                path = os.path.join(report_dir, f"matrix_{channel_name}.png")
                fig.savefig(path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                all_images.append(path)
                md_content += f"#### 通道 {channel_name} 相似度矩阵\n\n"
                md_content += f"![矩阵 {channel_name}](matrix_{channel_name}.png)\n\n"
            
            # 保存热力图
            md_content += "### 相似度热力图\n\n"
            for alg_name in self.heatmap_results.keys():
                idx = self.heatmap_alg_combo.findText(alg_name)
                if idx >= 0:
                    self.heatmap_alg_combo.setCurrentIndex(idx)
                    self.visualize_heatmap(idx)
                    path = save_figure_to_file(
                        self.heatmap_canvas.figure,
                        os.path.join(report_dir, f"batch_heatmap_{alg_name}.png")
                    )
                    if path:
                        all_images.append(path)
                        md_content += f"#### {alg_name}\n\n"
                        md_content += f"![{alg_name}热力图]({os.path.basename(path)})\n\n"
            
            # 通道相关性指标排序表格
            md_content += "### 通道相关性指标排序\n\n"
            md_content += "> 各通道中两两互相关系数（权重均匀）加权均值指标，由大到小排序\n\n"
            md_content += "| 排名 | 通道 | 加权均值 |\n"
            md_content += "|------|------|----------|\n"
            
            channel_corr = {}
            for r in self.result_data:
                channel = r.get('channel', '')
                value = r.get('value', 0)
                if isinstance(value, (int, float)):
                    if channel not in channel_corr:
                        channel_corr[channel] = []
                    channel_corr[channel].append(value)
            
            ranking = []
            for channel, values in channel_corr.items():
                if values:
                    weighted_mean = sum(values) / len(values)
                    ranking.append({
                        'channel': channel,
                        'weighted_mean': weighted_mean,
                        'count': len(values)
                    })
            
            ranking.sort(key=lambda x: x['weighted_mean'], reverse=True)
            
            for i, item in enumerate(ranking, 1):
                md_content += f"| {i} | {item['channel']} | {item['weighted_mean']:.6f} |\n"
            md_content += "\n"
            
            # 时域结果表格
            time_results = [r for r in self.result_data if r.get('domain') == '时域']
            if time_results:
                md_content += "### 时域相似性计算结果\n\n"
                md_content += "| 算法 | 通道 | 组A | 组B | 值 |\n"
                md_content += "|------|------|-----|-----|----|\n"
                for r in time_results:
                    val = r.get('value', 0)
                    if isinstance(val, (int, float)):
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                    else:
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                md_content += "\n"
            
            # 频域结果表格
            freq_results = [r for r in self.result_data if r.get('domain') == '频域']
            if freq_results:
                md_content += "### 频域相似性计算结果\n\n"
                md_content += "**频域变换算法**: Welch功率谱密度估计（使用FFT计算）\n\n"
                md_content += "| 算法 | 通道 | 组A | 组B | 值 |\n"
                md_content += "|------|------|-----|-----|----|\n"
                for r in freq_results:
                    val = r.get('value', 0)
                    if isinstance(val, (int, float)):
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                    else:
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                md_content += "\n"
            
            block = ReportBlock(
                source_tab='批量参数对比',
                title=f"批量对比-{', '.join(labels)}",
                content_md=md_content,
                images=all_images
            )
            REPORT_MANAGER.add_block(block)
            
            QMessageBox.information(self, "成功", 
                f"报告BLOCK已添加\n共生成 {len(all_images)} 张图片")
            log(f"[Batch] 报告BLOCK添加成功，图片数: {len(all_images)}")
            
        except Exception as e:
            import traceback
            log(f"[Batch] add_report_block 异常: {e}")
            log(f"[Batch] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}")


# ============= Tab6.5: 背景对消批处理 =============

class BackgroundSubtractionTab(QWidget):
    """背景对消批处理Tab：支持N组实验数据与背景数据的对消处理和相似性对比
    
    功能：
    1. 独立管理实验数据组和背景数据组
    2. 支持两种关联模式：所有实验组共用一组背景 / 每个实验组单独使用一组背景
    3. 支持两种背景来源模式：直接使用单一背景数据 / 多组数据统计平均
    4. 5种统计平均方法：均值平均、中位数平均、均方根平均、加权平均、剔除极值后均值
    5. 支持10种背景对消算法
    6. 自动检查通道数匹配（不匹配弹窗报错）
    7. 数据长度不一致时自动截取最短（不弹窗）
    8. 对消后的数据用于相似性计算和可视化
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        log("[BGSub] Initializing BackgroundSubtractionTab...")
        self.exp_groups = []  
        self.bg_groups = []
        self.bg_association_mode = 'shared'
        self.bg_source_mode = 'direct'
        self.bg_stat_method = '均值平均'
        self.result_data = None
        self.heatmap_results = {}
        self._tf_param_widgets = {}
        self._bg_combo_widgets = {}
        try:
            self.setup_ui()
            log("[BGSub] setup_ui completed")
            self._on_tf_method_changed(0)
            log("[BGSub] _on_tf_method_changed completed")
        except Exception as e:
            log(f"[BGSub] __init__ error: {e}")
            import traceback
            log(f"[BGSub] __init__ traceback:\n{traceback.format_exc()}")
    
    def showEvent(self, event):
        try:
            log("[BGSub] showEvent triggered")
            super().showEvent(event)
            log("[BGSub] showEvent completed")
        except Exception as e:
            log(f"[BGSub] showEvent error: {e}")
            import traceback
            log(f"[BGSub] showEvent traceback:\n{traceback.format_exc()}")
    
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(8, 8, 8, 8)
        
        # 数据组管理 - 实验数据
        exp_box = QGroupBox("实验数据组")
        exp_layout = QVBoxLayout(exp_box)
        exp_layout.setSpacing(6)
        
        self.exp_list = QListWidget()
        self.exp_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.exp_list.setMinimumHeight(100)
        self.exp_list.setMaximumHeight(150)
        exp_layout.addWidget(self.exp_list)
        
        exp_btn_layout = QHBoxLayout()
        self.add_exp_btn = QPushButton("添加实验数据")
        self.add_exp_btn.clicked.connect(self.add_exp_group)
        exp_btn_layout.addWidget(self.add_exp_btn)
        
        self.remove_exp_btn = QPushButton("移除选中")
        self.remove_exp_btn.clicked.connect(self.remove_selected_exp)
        exp_btn_layout.addWidget(self.remove_exp_btn)
        
        self.clear_exp_btn = QPushButton("清空")
        self.clear_exp_btn.clicked.connect(self.clear_all_exp)
        exp_btn_layout.addWidget(self.clear_exp_btn)
        
        exp_layout.addLayout(exp_btn_layout)
        
        exp_label_layout = QHBoxLayout()
        exp_label_layout.addWidget(QLabel("标签:"))
        self.exp_label_edit = QLineEdit()
        self.exp_label_edit.setPlaceholderText("如: KW1")
        exp_label_layout.addWidget(self.exp_label_edit)
        self.update_exp_label_btn = QPushButton("更新标签")
        self.update_exp_label_btn.clicked.connect(self.update_exp_label)
        exp_label_layout.addWidget(self.update_exp_label_btn)
        exp_layout.addLayout(exp_label_layout)
        
        exp_state_layout = QHBoxLayout()
        exp_state_layout.addWidget(QLabel("关联实验状态:"))
        self.exp_state_combo = QComboBox()
        self.exp_state_combo.addItem("（未关联）", "")
        self.exp_state_combo.setEnabled(False)
        exp_state_layout.addWidget(self.exp_state_combo, stretch=1)
        self.assoc_exp_state_btn = QPushButton("关联")
        self.assoc_exp_state_btn.clicked.connect(self.associate_exp_state)
        self.assoc_exp_state_btn.setEnabled(False)
        exp_state_layout.addWidget(self.assoc_exp_state_btn)
        exp_layout.addLayout(exp_state_layout)
        
        left_layout.addWidget(exp_box)
        
        # 数据组管理 - 背景数据
        bg_box = QGroupBox("背景数据组")
        bg_layout = QVBoxLayout(bg_box)
        bg_layout.setSpacing(6)
        
        self.bg_list = QListWidget()
        self.bg_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.bg_list.setMinimumHeight(80)
        self.bg_list.setMaximumHeight(120)
        bg_layout.addWidget(self.bg_list)
        
        bg_btn_layout = QHBoxLayout()
        self.add_bg_btn = QPushButton("添加背景数据")
        self.add_bg_btn.clicked.connect(self.add_bg_group)
        bg_btn_layout.addWidget(self.add_bg_btn)
        
        self.remove_bg_btn = QPushButton("移除选中")
        self.remove_bg_btn.clicked.connect(self.remove_selected_bg)
        bg_btn_layout.addWidget(self.remove_bg_btn)
        
        self.clear_bg_btn = QPushButton("清空")
        self.clear_bg_btn.clicked.connect(self.clear_all_bg)
        bg_btn_layout.addWidget(self.clear_bg_btn)
        
        bg_layout.addLayout(bg_btn_layout)
        
        bg_label_layout = QHBoxLayout()
        bg_label_layout.addWidget(QLabel("重命名:"))
        self.bg_label_edit = QLineEdit()
        self.bg_label_edit.setPlaceholderText("如: 背景组1")
        bg_label_layout.addWidget(self.bg_label_edit)
        self.update_bg_label_btn = QPushButton("重命名")
        self.update_bg_label_btn.clicked.connect(self.update_bg_label)
        bg_label_layout.addWidget(self.update_bg_label_btn)
        bg_layout.addLayout(bg_label_layout)
        
        left_layout.addWidget(bg_box)
        
        # 背景关联设置
        assoc_box = QGroupBox("背景关联设置")
        assoc_layout = QVBoxLayout(assoc_box)
        assoc_layout.setSpacing(6)
        
        assoc_row1 = QHBoxLayout()
        assoc_row1.addWidget(QLabel("关联模式:"))
        self.assoc_mode_combo = QComboBox()
        self.assoc_mode_combo.addItems(["所有实验组共用一组背景", "每个实验组单独使用一组背景"])
        self.assoc_mode_combo.currentIndexChanged.connect(self._on_assoc_mode_changed)
        assoc_row1.addWidget(self.assoc_mode_combo, stretch=1)
        assoc_layout.addLayout(assoc_row1)
        
        assoc_row2 = QHBoxLayout()
        assoc_row2.addWidget(QLabel("背景来源:"))
        self.bg_source_combo = QComboBox()
        self.bg_source_combo.addItems(["直接使用单一背景数据", "通过多组数据统计处理"])
        self.bg_source_combo.currentIndexChanged.connect(self._on_bg_source_changed)
        assoc_row2.addWidget(self.bg_source_combo, stretch=1)
        assoc_layout.addLayout(assoc_row2)
        
        self.stat_method_combo = QComboBox()
        from signal_processing import BG_STATISTICAL_METHODS
        self.stat_method_combo.addItems(BG_STATISTICAL_METHODS)
        self.stat_method_combo.setEnabled(False)
        assoc_layout.addWidget(QLabel("统计方法:"))
        assoc_layout.addWidget(self.stat_method_combo)
        
        shared_bg_row = QHBoxLayout()
        shared_bg_row.addWidget(QLabel("共用背景:"))
        self.shared_bg_combo = QComboBox()
        shared_bg_row.addWidget(self.shared_bg_combo, stretch=1)
        assoc_layout.addLayout(shared_bg_row)
        
        left_layout.addWidget(assoc_box)
        
        # 背景对消设置
        sub_box = QGroupBox("背景对消设置")
        sub_layout = QVBoxLayout(sub_box)
        sub_layout.setSpacing(6)
        
        self.bg_method_combo = QComboBox()
        from signal_processing import BACKGROUND_SUBTRACTION_METHODS
        self.bg_method_combo.addItems(BACKGROUND_SUBTRACTION_METHODS)
        sub_layout.addWidget(QLabel("对消算法:"))
        sub_layout.addWidget(self.bg_method_combo)
        
        self.apply_bg_btn = QPushButton("应用背景对消")
        self.apply_bg_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 6px;")
        self.apply_bg_btn.clicked.connect(self.apply_background_subtraction)
        self.apply_bg_btn.setEnabled(False)
        sub_layout.addWidget(self.apply_bg_btn)
        
        left_layout.addWidget(sub_box)
        
        # 预处理设置
        proc_box = QGroupBox("共享预处理")
        proc_layout = QVBoxLayout(proc_box)
        proc_layout.setSpacing(6)
        
        slice_layout = QHBoxLayout()
        self.slice_start_spin = QDoubleSpinBox()
        self.slice_start_spin.setRange(0, 100)
        self.slice_start_spin.setSuffix(" s")
        slice_layout.addWidget(QLabel("起始时间:"))
        slice_layout.addWidget(self.slice_start_spin)
        
        self.slice_end_spin = QDoubleSpinBox()
        self.slice_end_spin.setRange(0, 100)
        self.slice_end_spin.setSuffix(" s")
        self.slice_end_spin.setValue(1.0)
        slice_layout.addWidget(QLabel("结束时间:"))
        slice_layout.addWidget(self.slice_end_spin)
        proc_layout.addLayout(slice_layout)
        
        down_layout = QHBoxLayout()
        self.downsample_check = QCheckBox("启用降采样")
        self.downsample_check.setChecked(False)
        self.downsample_check.stateChanged.connect(self.on_downsample_toggle)
        down_layout.addWidget(self.downsample_check)
        
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(100, 100000000)
        self.max_points_spin.setValue(10000)
        self.max_points_spin.setEnabled(False)
        down_layout.addWidget(QLabel("降采样点数:"))
        down_layout.addWidget(self.max_points_spin)
        down_layout.addStretch()
        proc_layout.addLayout(down_layout)
        
        self.apply_proc_btn = QPushButton("应用预处理")
        self.apply_proc_btn.clicked.connect(self.apply_preprocessing)
        proc_layout.addWidget(self.apply_proc_btn)
        
        left_layout.addWidget(proc_box)
        
        # 算法选择
        method_box = QGroupBox("加入报告的相似性算法")
        method_layout = QVBoxLayout(method_box)
        method_layout.setSpacing(6)
        
        calc_type_layout = QHBoxLayout()
        self.calc_type_combo = QComboBox()
        self.calc_type_combo.addItems(["时域", "频域", "时域+频域"])
        calc_type_layout.addWidget(QLabel("计算类型:"))
        calc_type_layout.addWidget(self.calc_type_combo)
        calc_type_layout.addStretch()
        method_layout.addLayout(calc_type_layout)
        
        time_method_box = QGroupBox("时域算法")
        time_method_layout = QVBoxLayout(time_method_box)
        self.time_method_list = QListWidget()
        self.time_method_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.time_method_list.setMinimumHeight(80)
        self.time_method_list.setMaximumHeight(120)
        self.time_method_list.addItems([
            '互相关系数', '互相关峰值', '协方差', '皮尔逊相关系数',
            '斯皮尔曼等级相关', '动态时间规整(DTW)', '最大信息系数(MIC)',
            '归一化互相关'
        ])
        self.time_method_list.selectAll()
        time_method_layout.addWidget(self.time_method_list)
        method_layout.addWidget(time_method_box)
        
        freq_method_box = QGroupBox("频域算法")
        freq_method_layout = QVBoxLayout(freq_method_box)
        self.freq_method_list = QListWidget()
        self.freq_method_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.freq_method_list.setMinimumHeight(120)
        self.freq_method_list.setMaximumHeight(180)
        self.freq_method_list.addItems([
            '频谱欧几里得距离', '频谱曼哈顿距离', '频谱余弦相似度',
            '频谱皮尔逊相关', '频谱MSE', '频谱RMSE', '频谱MAE',
            '频谱互相关', '频谱DTW', '频谱SSIM', '频谱巴氏距离',
            '频谱能量差', '频谱熵差', '频谱KL散度', '频谱JS散度',
            '频谱相干性', '频谱重心差', '频谱带宽差', '频谱平坦度差',
            '频谱 rolloff 差'
        ])
        self.freq_method_list.selectAll()
        freq_method_layout.addWidget(self.freq_method_list)
        method_layout.addWidget(freq_method_box)
        
        left_layout.addWidget(method_box)
        
        # 频域变换设置
        tf_box = QGroupBox("频域变换设置")
        tf_layout = QVBoxLayout(tf_box)
        tf_layout.setSpacing(6)
        
        tf_row1 = QHBoxLayout()
        tf_row1.addWidget(QLabel("时频变换方法:"))
        self.tf_method_combo = QComboBox()
        for m in TIME_FREQ_METHODS.keys():
            self.tf_method_combo.addItem(m)
        self.tf_method_combo.currentIndexChanged.connect(self._on_tf_method_changed)
        tf_row1.addWidget(self.tf_method_combo, stretch=1)
        tf_layout.addLayout(tf_row1)
        
        self.tf_desc_label = QLabel()
        self.tf_desc_label.setWordWrap(True)
        self.tf_desc_label.setMinimumHeight(40)
        self.tf_desc_label.setStyleSheet("background-color: #FFF8E1; padding: 6px; border: 1px solid #FFC107; border-radius: 3px;")
        tf_layout.addWidget(self.tf_desc_label)
        
        self.tf_params_group = QGroupBox("算法参数")
        self.tf_params_layout = QFormLayout(self.tf_params_group)
        self.tf_params_group.setMinimumHeight(60)
        tf_layout.addWidget(self.tf_params_group)
        
        left_layout.addWidget(tf_box)
        
        # 计算按钮
        self.compute_btn = QPushButton("计算全部两两相似性（对消后）")
        self.compute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.compute_btn.clicked.connect(self.compute_all_pairs)
        self.compute_btn.setEnabled(False)
        left_layout.addWidget(self.compute_btn)
        
        # 添加报告按钮
        self.add_report_btn = QPushButton("添加报告BLOCK")
        self.add_report_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 6px;")
        self.add_report_btn.clicked.connect(self.add_report_block)
        self.add_report_btn.setEnabled(False)
        left_layout.addWidget(self.add_report_btn)
        
        left_layout.addStretch()
        
        left_scroll.setWidget(left_panel)
        splitter.addWidget(left_scroll)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.result_tabs = QTabWidget()
        
        table_main_tab = QWidget()
        table_main_layout = QVBoxLayout(table_main_tab)
        self.table_subtabs = QTabWidget()
        
        time_table_tab = QWidget()
        time_table_layout = QVBoxLayout(time_table_tab)
        self.time_result_table = QTableWidget()
        self.time_result_table.setAlternatingRowColors(True)
        time_table_layout.addWidget(self.time_result_table)
        self.table_subtabs.addTab(time_table_tab, "时域结果")
        
        freq_table_tab = QWidget()
        freq_table_layout = QVBoxLayout(freq_table_tab)
        self.freq_result_table = QTableWidget()
        self.freq_result_table.setAlternatingRowColors(True)
        freq_table_layout.addWidget(self.freq_result_table)
        self.table_subtabs.addTab(freq_table_tab, "频域结果")
        
        merged_table_tab = QWidget()
        merged_table_layout = QVBoxLayout(merged_table_tab)
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        merged_table_layout.addWidget(self.result_table)
        self.table_subtabs.addTab(merged_table_tab, "合并结果")
        
        table_main_layout.addWidget(self.table_subtabs)
        self.result_tabs.addTab(table_main_tab, "排序表格")
        
        # 热力图结果
        heatmap_tab = QWidget()
        heatmap_layout = QVBoxLayout(heatmap_tab)
        
        heatmap_top_layout = QHBoxLayout()
        self.heatmap_alg_combo = QComboBox()
        heatmap_top_layout.addWidget(QLabel("选择算法:"))
        heatmap_top_layout.addWidget(self.heatmap_alg_combo)
        heatmap_top_layout.addStretch()
        heatmap_layout.addLayout(heatmap_top_layout)
        
        self.heatmap_canvas = create_canvas(heatmap_tab)
        self.heatmap_toolbar = NavigationToolbar(self.heatmap_canvas, heatmap_tab)
        heatmap_layout.addWidget(self.heatmap_toolbar)
        heatmap_layout.addWidget(self.heatmap_canvas)
        self.result_tabs.addTab(heatmap_tab, "热力图")
        
        # 波形对比可视化
        viz_tab = QWidget()
        viz_layout = QVBoxLayout(viz_tab)
        
        viz_top_layout = QHBoxLayout()
        self.channel_combo = QComboBox()
        viz_top_layout.addWidget(QLabel("选择通道:"))
        viz_top_layout.addWidget(self.channel_combo)
        
        self.waveform_mode_combo = QComboBox()
        self.waveform_mode_combo.addItems(["时域波形", "频域波形"])
        self.waveform_mode_combo.currentIndexChanged.connect(self.visualize_waveforms)
        viz_top_layout.addWidget(QLabel("显示模式:"))
        viz_top_layout.addWidget(self.waveform_mode_combo)
        
        self.downsample_display_check = QCheckBox("显示粗粒化")
        self.downsample_display_check.setChecked(False)
        self.downsample_display_check.stateChanged.connect(self.visualize_waveforms)
        viz_top_layout.addWidget(self.downsample_display_check)
        
        self.downsample_display_spin = QSpinBox()
        self.downsample_display_spin.setRange(100, 10000)
        self.downsample_display_spin.setValue(1000)
        self.downsample_display_spin.setEnabled(False)
        viz_top_layout.addWidget(QLabel("粗粒化点数:"))
        viz_top_layout.addWidget(self.downsample_display_spin)
        
        viz_top_layout.addStretch()
        viz_layout.addLayout(viz_top_layout)
        
        self.waveform_canvas = create_canvas(viz_tab)
        self.waveform_toolbar = NavigationToolbar(self.waveform_canvas, viz_tab)
        viz_layout.addWidget(self.waveform_toolbar)
        viz_layout.addWidget(self.waveform_canvas)
        self.result_tabs.addTab(viz_tab, "波形对比")
        
        right_layout.addWidget(self.result_tabs)
        splitter.addWidget(right_panel)
        
        main_layout.addWidget(splitter)
    
    def _on_tf_method_changed(self, index):
        method_name = self.tf_method_combo.currentText()
        info = TIME_FREQ_METHODS.get(method_name, {})
        
        self.tf_desc_label.setText(info.get('desc', ''))
        
        while self.tf_params_layout.rowCount() > 0:
            self.tf_params_layout.removeRow(0)
        
        self._tf_param_widgets = {}
        for pname, pdesc, pmin, pmax, pstep, pdefault, phelp in info.get('params', []):
            spin = QDoubleSpinBox()
            spin.setRange(pmin, pmax)
            spin.setSingleStep(pstep)
            spin.setValue(pdefault)
            spin.setToolTip(phelp)
            self.tf_params_layout.addRow(f"{pname} ({pdesc}):", spin)
            self._tf_param_widgets[pname] = spin
    
    def _on_assoc_mode_changed(self, index):
        mode = 'shared' if index == 0 else 'per_group'
        self.bg_association_mode = mode
        self._update_bg_combo_widgets()
        self.update_ui_state()
    
    def _on_bg_source_changed(self, index):
        mode = 'direct' if index == 0 else 'statistical'
        self.bg_source_mode = mode
        self.stat_method_combo.setEnabled(mode == 'statistical')
        if mode == 'statistical':
            self.bg_stat_method = self.stat_method_combo.currentText()
        self.update_ui_state()
    
    def _update_bg_combo_widgets(self):
        for widget in self._bg_combo_widgets.values():
            widget.deleteLater()
        self._bg_combo_widgets.clear()
        
        bg_names = [bg['label'] for bg in self.bg_groups]
        
        if self.bg_association_mode == 'shared':
            self.shared_bg_combo.clear()
            self.shared_bg_combo.addItems(bg_names)
        else:
            for i, group in enumerate(self.exp_groups):
                row = self.exp_list.row(i)
                if row >= 0:
                    combo = QComboBox()
                    combo.addItems(bg_names)
                    if 'bg_label' in group and group['bg_label'] in bg_names:
                        combo.setCurrentText(group['bg_label'])
                    combo.currentTextChanged.connect(lambda text, idx=i: self._on_exp_bg_changed(idx, text))
                    item = self.exp_list.item(row)
                    self.exp_list.setItemWidget(item, combo)
                    self._bg_combo_widgets[i] = combo
    
    def _on_exp_bg_changed(self, exp_idx, bg_label):
        if exp_idx < len(self.exp_groups):
            self.exp_groups[exp_idx]['bg_label'] = bg_label
            self.update_ui_state()
    
    def get_tf_params(self):
        params = {}
        for pname, widget in self._tf_param_widgets.items():
            try:
                params[pname] = float(widget.value())
            except:
                params[pname] = 0
        return params
    
    def add_exp_group(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择实验数据文件（可按住Ctrl多选）", "",
            "TDMS文件 (*.tdms);;NPY文件 (*.npy);;CSV文件 (*.csv)"
        )
        if not files:
            return
        
        success_count = 0
        fail_count = 0
        failed_files = []
        
        for filepath in files:
            if not os.path.exists(filepath):
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
                continue
            
            try:
                data, meta, fs = self._load_file(filepath)
                if data is None:
                    fail_count += 1
                    failed_files.append(os.path.basename(filepath))
                    continue
                
                label = f"KW{len(self.exp_groups) + 1}"
                
                # 获取当前选中的实验状态
                selected_state = self.exp_state_combo.currentData()
                
                group_data = {
                    'label': label,
                    'filepath': filepath,
                    'data': data,
                    'meta': meta,
                    'fs': fs,
                    'bg_label': None,
                    'proc_data': None,
                    'proc_meta': None,
                    'subtracted_data': None
                }
                
                # 如果当前有选中的实验状态，自动关联
                if selected_state:
                    group_data['experiment_state'] = selected_state
                    item = QListWidgetItem(f"{label}[{selected_state}]: {os.path.basename(filepath)}")
                    log(f"[BGSub] 添加实验数据组: {label}, 自动关联实验状态: {selected_state}")
                else:
                    item = QListWidgetItem(f"{label}: {os.path.basename(filepath)}")
                    log(f"[BGSub] 添加实验数据组: {label}")
                
                self.exp_groups.append(group_data)
                self.exp_list.addItem(item)
                success_count += 1
            except Exception as e:
                log(f"[BGSub] 加载文件失败: {filepath}, {e}")
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
        
        self._update_bg_combo_widgets()
        self.update_ui_state()
        self.update_channel_combo()
        
        if success_count > 0:
            msg = f"成功导入 {success_count} 个实验数据文件"
            if fail_count > 0:
                msg += f"\n\n失败 {fail_count} 个文件:\n" + "\n".join(failed_files)
            QMessageBox.information(self, "导入完成", msg)
    
    def add_bg_group(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择背景数据文件（可按住Ctrl多选）", "",
            "TDMS文件 (*.tdms);;NPY文件 (*.npy);;CSV文件 (*.csv)"
        )
        if not files:
            return
        
        success_count = 0
        fail_count = 0
        failed_files = []
        
        for filepath in files:
            if not os.path.exists(filepath):
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
                continue
            
            try:
                data, meta, fs = self._load_file(filepath)
                if data is None:
                    fail_count += 1
                    failed_files.append(os.path.basename(filepath))
                    continue
                
                label = f"背景组{len(self.bg_groups) + 1}"
                
                # 获取当前选中的实验状态
                selected_state = self.exp_state_combo.currentData()
                
                group_data = {
                    'label': label,
                    'filepath': filepath,
                    'data': data,
                    'meta': meta,
                    'fs': fs
                }
                
                # 如果当前有选中的实验状态，自动关联
                if selected_state:
                    group_data['experiment_state'] = selected_state
                    item = QListWidgetItem(f"{label}[{selected_state}]: {os.path.basename(filepath)}")
                    log(f"[BGSub] 添加背景数据组: {label}, 自动关联实验状态: {selected_state}")
                else:
                    item = QListWidgetItem(f"{label}: {os.path.basename(filepath)}")
                    log(f"[BGSub] 添加背景数据组: {label}")
                
                self.bg_groups.append(group_data)
                self.bg_list.addItem(item)
                success_count += 1
            except Exception as e:
                log(f"[BGSub] 加载背景文件失败: {filepath}, {e}")
                fail_count += 1
                failed_files.append(os.path.basename(filepath))
        
        self._update_bg_combo_widgets()
        self.update_ui_state()
        
        if success_count > 0:
            msg = f"成功导入 {success_count} 个背景数据文件"
            if fail_count > 0:
                msg += f"\n\n失败 {fail_count} 个文件:\n" + "\n".join(failed_files)
            QMessageBox.information(self, "导入完成", msg)
    
    def _load_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.tdms':
            try:
                from file_reader import load_data
                data, fs, meta = load_data(filepath)
                return data, meta, fs
            except Exception as e:
                log(f"[BGSub] TDMS加载错误: {e}")
                return None, None, 1.0
        elif ext == '.npy':
            data = np.load(filepath)
            return data, {}, 1.0
        elif ext == '.csv':
            data = np.loadtxt(filepath, delimiter=',')
            return data, {}, 1.0
        return None, None, 1.0
    
    def _get_num_channels(self, group):
        data = group.get('proc_data', group.get('data'))
        if data is None:
            return 0
        return data.shape[1] if len(data.shape) > 1 else 1
    
    def remove_selected_exp(self):
        rows = sorted([self.exp_list.row(i) for i in self.exp_list.selectedItems()], reverse=True)
        for row in rows:
            self.exp_list.takeItem(row)
            del self.exp_groups[row]
        self._update_bg_combo_widgets()
        self.update_ui_state()
        self.update_channel_combo()
    
    def clear_all_exp(self):
        if QMessageBox.question(self, "确认", "确定清空所有实验数据组？") == QMessageBox.Yes:
            self.exp_groups.clear()
            self.exp_list.clear()
            self.result_data = None
            self.heatmap_results = {}
            self.update_ui_state()
    
    def remove_selected_bg(self):
        rows = sorted([self.bg_list.row(i) for i in self.bg_list.selectedItems()], reverse=True)
        for row in rows:
            bg_item = self.bg_list.item(row)
            bg_label = bg_item.text().split(':')[0].strip()
            self.bg_list.takeItem(row)
            del self.bg_groups[row]
            for exp_group in self.exp_groups:
                if exp_group.get('bg_label') == bg_label:
                    exp_group['bg_label'] = None
        self._update_bg_combo_widgets()
        self.update_ui_state()
    
    def clear_all_bg(self):
        if QMessageBox.question(self, "确认", "确定清空所有背景数据组？") == QMessageBox.Yes:
            self.bg_groups.clear()
            self.bg_list.clear()
            for exp_group in self.exp_groups:
                exp_group['bg_label'] = None
            self._update_bg_combo_widgets()
            self.update_ui_state()
    
    def update_exp_label(self):
        row = self.exp_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个实验数据组")
            return
        
        label = self.exp_label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "提示", "标签不能为空")
            return
        
        self.exp_groups[row]['label'] = label
        item = self.exp_list.item(row)
        exp_group = self.exp_groups[row]
        state = exp_group.get('experiment_state', '')
        if state:
            item.setText(f"{label}[{state}]: {os.path.basename(exp_group['filepath'])}")
        else:
            item.setText(f"{label}: {os.path.basename(exp_group['filepath'])}")
        log(f"[BGSub] 更新实验数据组标签: {label}")
    
    def refresh_experiment_states(self):
        """从全局注册表刷新实验状态下拉菜单"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        self.exp_state_combo.blockSignals(True)
        self.exp_state_combo.clear()
        self.exp_state_combo.addItem("（未关联）", "")
        for n in names:
            self.exp_state_combo.addItem(n, n)
        self.exp_state_combo.blockSignals(False)
        self.exp_state_combo.setEnabled(len(names) > 0)
    
    def associate_exp_state(self):
        """将选中的实验数据组关联到实验状态"""
        row = self.exp_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个实验数据组")
            return
        
        state_name = self.exp_state_combo.currentData()
        if not state_name:
            QMessageBox.warning(self, "提示", "请选择一个实验状态")
            return
        
        self.exp_groups[row]['experiment_state'] = state_name
        item = self.exp_list.item(row)
        exp_group = self.exp_groups[row]
        label = exp_group['label']
        item.setText(f"{label}[{state_name}]: {os.path.basename(exp_group['filepath'])}")
        log(f"[BGSub] 实验数据组 {label} 关联实验状态: {state_name}")
    
    def push_experiment_state(self, state_name):
        """接收从实验状态定义Tab推送的实验状态，并自动关联到未关联的数据组"""
        self.exp_state_combo.blockSignals(True)
        idx = self.exp_state_combo.findData(state_name)
        if idx >= 0:
            self.exp_state_combo.setCurrentIndex(idx)
        self.exp_state_combo.blockSignals(False)
        
        # 自动将推送的实验状态关联到所有未关联的实验组
        for i, group in enumerate(self.exp_groups):
            if 'experiment_state' not in group or not group['experiment_state']:
                group['experiment_state'] = state_name
                item = self.exp_list.item(i)
                filepath = os.path.basename(group['filepath'])
                label = group['label']
                item.setText(f"{label}[{state_name}]: {filepath}")
                log(f"[BGSub] 实验组 {label} 自动关联实验状态: {state_name}")
        
        # 自动将推送的实验状态关联到所有未关联的背景组
        for i, group in enumerate(self.bg_groups):
            if 'experiment_state' not in group or not group['experiment_state']:
                group['experiment_state'] = state_name
                item = self.bg_list.item(i)
                filepath = os.path.basename(group['filepath'])
                label = group['label']
                item.setText(f"{label}[{state_name}]: {filepath}")
                log(f"[BGSub] 背景组 {label} 自动关联实验状态: {state_name}")
        
        log(f"[BGSub] 接收推送的实验状态: {state_name}")
    
    def check_experiment_state_associated(self):
        """检查是否所有实验数据组都关联了实验状态"""
        unassociated = []
        for i, group in enumerate(self.exp_groups):
            if 'experiment_state' not in group or not group['experiment_state']:
                unassociated.append(group.get('label', f"实验数据组{i+1}"))
        
        if unassociated:
            QMessageBox.warning(self, "提示", 
                f"以下实验数据组未关联实验状态:\n" + "\n".join(unassociated) + 
                f"\n\n请在实验状态定义Tab中定义实验状态，并关联到各实验数据组。")
            return False
        return True
    
    def update_bg_label(self):
        row = self.bg_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个背景数据组")
            return
        
        label = self.bg_label_edit.text().strip()
        if not label:
            QMessageBox.warning(self, "提示", "标签不能为空")
            return
        
        old_label = self.bg_groups[row]['label']
        self.bg_groups[row]['label'] = label
        item = self.bg_list.item(row)
        bg_group = self.bg_groups[row]
        item.setText(f"{label}: {os.path.basename(bg_group['filepath'])}")
        
        for exp_group in self.exp_groups:
            if exp_group.get('bg_label') == old_label:
                exp_group['bg_label'] = label
        
        self._update_bg_combo_widgets()
        log(f"[BGSub] 更新背景数据组标签: {label}")
    
    def on_downsample_toggle(self, state):
        self.max_points_spin.setEnabled(state == Qt.Checked)
    
    def apply_preprocessing(self):
        if len(self.exp_groups) == 0:
            QMessageBox.warning(self, "提示", "请先添加实验数据组")
            return
        
        start_time = self.slice_start_spin.value()
        end_time = self.slice_end_spin.value()
        use_downsample = self.downsample_check.isChecked()
        max_points = self.max_points_spin.value()
        
        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "结束时间必须大于起始时间")
            return
        
        log(f"[BGSub] 应用预处理: 切片[{start_time}-{end_time}s], 降采样={use_downsample}")
        
        for i, group in enumerate(self.exp_groups):
            data = group['data']
            fs = group['fs']
            
            start_idx = int(start_time * fs)
            end_idx = int(end_time * fs)
            
            if start_idx >= len(data):
                log(f"[BGSub] 组 {group['label']} 起始索引超出范围")
                continue
            
            end_idx = min(end_idx, len(data))
            sliced_data = data[start_idx:end_idx]
            
            if use_downsample and len(sliced_data) > max_points:
                from scipy import signal
                sliced_data = signal.resample(sliced_data, max_points)
            
            group['proc_data'] = sliced_data
            group['proc_meta'] = {
                'fs': fs,
                'slice_start': start_time,
                'slice_end': end_time,
                'downsampled': use_downsample,
                'original_length': len(data),
                'processed_length': len(sliced_data),
                'channel_map': group['meta'].get('channel_map', {})
            }
        
        for bg_group in self.bg_groups:
            bg_data = bg_group['data']
            bg_fs = bg_group['fs']
            
            bg_start_idx = int(start_time * bg_fs)
            bg_end_idx = int(end_time * bg_fs)
            
            if bg_start_idx >= len(bg_data):
                continue
            
            bg_end_idx = min(bg_end_idx, len(bg_data))
            bg_sliced = bg_data[bg_start_idx:bg_end_idx]
            
            if use_downsample and len(bg_sliced) > max_points:
                from scipy import signal
                bg_sliced = signal.resample(bg_sliced, max_points)
            
            bg_group['proc_data'] = bg_sliced
        
        QMessageBox.information(self, "完成", f"已对 {len(self.exp_groups)} 组实验数据和 {len(self.bg_groups)} 组背景数据应用预处理")
        self.update_ui_state()
        self.update_channel_combo()
        self.visualize_waveforms()
    
    def apply_background_subtraction(self):
        if len(self.exp_groups) == 0:
            QMessageBox.warning(self, "提示", "请先添加实验数据组")
            return
        
        method = self.bg_method_combo.currentText()
        
        from signal_processing import subtract_background, compute_statistical_background
        
        shared_bg_label = self.shared_bg_combo.currentText() if self.bg_association_mode == 'shared' else None
        
        log(f"[BGSub] 应用背景对消: {method}, 关联模式={self.bg_association_mode}, 来源模式={self.bg_source_mode}")
        
        for exp_group in self.exp_groups:
            data = exp_group.get('proc_data', exp_group.get('data'))
            if data is None:
                continue
            
            if self.bg_association_mode == 'shared':
                bg_label = shared_bg_label
            else:
                bg_label = exp_group.get('bg_label')
            
            if not bg_label:
                continue
            
            bg_group = next((bg for bg in self.bg_groups if bg['label'] == bg_label), None)
            if bg_group is None:
                continue
            
            n_ch_exp = self._get_num_channels(exp_group)
            n_ch_bg = self._get_num_channels(bg_group)
            if n_ch_exp != n_ch_bg:
                QMessageBox.critical(self, "错误",
                    f"通道数不匹配！\n实验数据 {exp_group['label']}: {n_ch_exp} 通道\n背景数据 {bg_group['label']}: {n_ch_bg} 通道\n\n请修正后重新尝试。")
                return
            
            if self.bg_source_mode == 'direct':
                bg_data = bg_group.get('proc_data', bg_group.get('data'))
            else:
                bg_data_list = []
                for bg in self.bg_groups:
                    bg_d = bg.get('proc_data', bg.get('data'))
                    if bg_d is not None:
                        bg_data_list.append(bg_d)
                bg_data = compute_statistical_background(bg_data_list, self.stat_method_combo.currentText())
            
            if bg_data is None or len(bg_data) == 0:
                continue
            
            try:
                subtracted = subtract_background(data, bg_data, method)
                exp_group['subtracted_data'] = subtracted
                log(f"[BGSub] 对消完成: {exp_group['label']}")
            except Exception as e:
                log(f"[BGSub] 对消失败: {exp_group['label']}, {e}")
                QMessageBox.warning(self, "警告", f"数据组 {exp_group['label']} 对消失败: {e}")
        
        QMessageBox.information(self, "完成", f"背景对消处理完成\n对消算法: {method}")
        self.compute_btn.setEnabled(True)
        self.visualize_waveforms()
    
    def update_channel_combo(self):
        self.channel_combo.clear()
        if len(self.exp_groups) > 0:
            meta = self.exp_groups[0].get('proc_meta') or self.exp_groups[0].get('meta') or {}
            channel_map = meta.get('channel_map', {})
            if channel_map:
                channels = sorted(channel_map.keys())
            else:
                channels = [f"CH{i+1}" for i in range(self._get_num_channels(self.exp_groups[0]))]
            self.channel_combo.addItems(channels)
    
    def get_channel_data(self, group, channel_name):
        data = group.get('subtracted_data', group.get('proc_data', group.get('data')))
        if data is None:
            return None
        
        meta = group.get('proc_meta') or group.get('meta') or {}
        if isinstance(meta, dict) and 'channel_map' in meta:
            cm = meta.get('channel_map') or {}
            if channel_name in cm:
                return np.asarray(cm[channel_name]).flatten()
        
        try:
            idx = int(channel_name.replace('CH', '')) - 1
            if len(data.shape) > 1 and idx < data.shape[1]:
                return data[:, idx].flatten()
        except (ValueError, AttributeError):
            pass
        
        return data.flatten()
    
    def update_ui_state(self):
        has_data = len(self.exp_groups) >= 2
        has_bg_all = False
        if self.exp_groups:
            if self.bg_association_mode == 'shared':
                has_bg_all = self.shared_bg_combo.currentText() != ''
            else:
                has_bg_all = all(g.get('bg_label') is not None for g in self.exp_groups)
        has_results = self.result_data is not None
        
        self.apply_bg_btn.setEnabled(has_data and len(self.bg_groups) > 0)
        self.compute_btn.setEnabled(has_data and has_bg_all)
        self.add_report_btn.setEnabled(has_results)
        self.apply_proc_btn.setEnabled(len(self.exp_groups) > 0)
    
    def compute_all_pairs(self):
        n_groups = len(self.exp_groups)
        if n_groups < 2:
            QMessageBox.warning(self, "提示", "至少需要2组数据")
            return
        
        if self.bg_association_mode == 'shared':
            shared_bg_label = self.shared_bg_combo.currentText()
            if not shared_bg_label:
                QMessageBox.warning(self, "提示", "请先选择共用背景数据！")
                return
            bg_group = next((bg for bg in self.bg_groups if bg['label'] == shared_bg_label), None)
            if bg_group is None:
                QMessageBox.warning(self, "提示", "选择的背景数据组不存在！")
                return
        else:
            for i, group in enumerate(self.exp_groups):
                if group.get('bg_label') is None:
                    QMessageBox.warning(self, "提示", 
                        f"数据组 {group['label']} 缺少背景数据！\n\n"
                        f"请先为所有实验数据组添加背景数据后再启动计算。")
                    return
        
        calc_type = self.calc_type_combo.currentText()
        
        time_methods = [item.text() for item in self.time_method_list.selectedItems()]
        freq_methods = [item.text() for item in self.freq_method_list.selectedItems()]
        
        if calc_type == "时域":
            selected_methods = time_methods
        elif calc_type == "频域":
            selected_methods = freq_methods
        else:
            selected_methods = time_methods + freq_methods
        
        if not selected_methods:
            QMessageBox.warning(self, "提示", "请至少选择一种算法")
            return
        
        log(f"[BGSub] 开始计算 {n_groups}×{n_groups} 两两相似性 (类型: {calc_type})")
        
        self.compute_btn.setEnabled(False)
        self.add_report_btn.setEnabled(False)
        
        total_tasks = n_groups * n_groups * len(selected_methods)
        self._progress_dialog = QProgressDialog(
            f"正在计算 {len(selected_methods)} 种算法的 {n_groups}×{n_groups} 组合...",
            "取消", 0, total_tasks, self
        )
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(500)
        
        channels = []
        if self.channel_combo.count() > 0:
            channels = [self.channel_combo.itemText(i) for i in range(self.channel_combo.count())]
        else:
            n_ch = self._get_num_channels(self.exp_groups[0]) if self.exp_groups else 0
            channels = [f"CH{i+1}" for i in range(n_ch)]
        
        if not channels:
            QMessageBox.warning(self, "提示", "未找到通道数据")
            return
        
        tf_method = self.tf_method_combo.currentText()
        tf_params = self.get_tf_params()
        
        def task(progress_cb):
            all_results = []
            heatmap_results = {}
            
            for method in selected_methods:
                heatmap_results[method] = np.eye(n_groups)
            
            done = 0
            total = n_groups * n_groups * len(selected_methods)
            
            for ch in channels:
                for i in range(n_groups):
                    for j in range(n_groups):
                        group_i = self.exp_groups[i]
                        group_j = self.exp_groups[j]
                        
                        data_i = self.get_channel_data(group_i, ch)
                        data_j = self.get_channel_data(group_j, ch)
                        
                        if data_i is None or data_j is None:
                            done += len(selected_methods)
                            continue
                        
                        for method in selected_methods:
                            try:
                                is_time_domain = method in time_methods
                                
                                if is_time_domain:
                                    from signal_processing import compute_time_similarity_batch
                                    result = compute_time_similarity_batch(
                                        data_i, data_j, [method], fs=group_i['fs']
                                    )
                                else:
                                    from signal_processing import compute_freq_similarity_batch
                                    result = compute_freq_similarity_batch(
                                        data_i, data_j, [method], fs=group_i['fs']
                                    )
                                
                                if result and len(result) > 0 and result[0].get('ok', False):
                                    value = result[0]['value']
                                    indicators = result[0].get('indicators', {})
                                    
                                    all_results.append({
                                        'method': method,
                                        'value': value,
                                        'indicators': indicators,
                                        'group_a': group_i['label'],
                                        'group_b': group_j['label'],
                                        'channel': ch,
                                        'data_a': data_i,
                                        'data_b': data_j,
                                        'fs': group_i['fs'],
                                        'domain': '时域' if is_time_domain else '频域',
                                        'bg_method': self.bg_method_combo.currentText()
                                    })
                                    
                                    if ch == channels[0]:
                                        heatmap_results[method][i, j] = value
                            except Exception as e:
                                log(f"[BGSub] 计算 {ch}:{method}({group_i['label']}, {group_j['label']}) 失败: {e}")
                            
                            done += 1
                            if progress_cb:
                                progress_cb(done, total, method, f"{group_i['label']}-{group_j['label']}")
            
            return all_results, heatmap_results, channels, calc_type
        
        self._worker = ComputeWorker(task)
        self._worker.progress.connect(self._on_compute_progress)
        self._worker.finished_ok.connect(self._on_compute_done)
        self._worker.error.connect(self._on_compute_error)
        self._progress_dialog.canceled.connect(self._worker_cancel)
        self._worker.start()
    
    def _worker_cancel(self):
        if hasattr(self, '_worker') and self._worker:
            self._worker.cancel()
            log("[BGSub] 用户取消计算")
    
    def _on_compute_progress(self, done, total, method, value):
        dialog = getattr(self, '_progress_dialog', None)
        if dialog is not None:
            try:
                dialog.setValue(done)
                dialog.setLabelText(f"正在计算: {method} ({done}/{total})")
            except Exception:
                pass
    
    def _on_compute_done(self, result):
        try:
            if result is None:
                log("[BGSub] _on_compute_done: result is None")
                return
            
            if len(result) == 4:
                all_results, heatmap_results, channels, calc_type = result
            else:
                all_results, heatmap_results, channels = result
                calc_type = "时域"
            
            if hasattr(self, '_progress_dialog') and self._progress_dialog:
                try:
                    self._progress_dialog.close()
                except Exception:
                    pass
                self._progress_dialog = None
            
            if not isinstance(all_results, list):
                log(f"[BGSub] _on_compute_done: all_results is not list, type={type(all_results)}")
                return
            
            self.result_data = all_results
            self.heatmap_results = heatmap_results if isinstance(heatmap_results, dict) else {}
            self._channels = channels if isinstance(channels, list) else []
            self._calc_type = calc_type
            
            self.display_results(all_results)
            self.update_heatmap_combo()
            self.update_ui_state()
            
            QMessageBox.information(self, "计算完成", 
                f"成功完成 {len(all_results)} 项计算\n\n"
                f"计算类型: {calc_type}\n"
                f"数据组数: {len(self.exp_groups)}\n"
                f"算法数: {len(self.heatmap_results)}\n"
                f"通道数: {len(self._channels)}\n"
                f"背景对消算法: {self.bg_method_combo.currentText()}")
            
            self.visualize_waveforms()
        except Exception as e:
            log(f"[BGSub] _on_compute_done 异常: {e}")
            import traceback
            log(f"[BGSub] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "计算错误", f"处理结果时发生错误: {str(e)}")
    
    def _on_compute_error(self, msg):
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        QMessageBox.warning(self, "计算错误", f"计算失败: {msg}")
        self.compute_btn.setEnabled(True)
    
    def display_results(self, results):
        try:
            if not results:
                return
            
            time_results = [r for r in results if r.get('domain') == '时域']
            freq_results = [r for r in results if r.get('domain') == '频域']
            
            def populate_table(table, data, domain_name):
                table.setRowCount(0)
                table.setColumnCount(6)
                table.setHorizontalHeaderLabels(['算法', '通道', '组A', '组B', '值', '指标'])
                
                sorted_data = sorted(data, key=lambda x: x.get('value', 0), reverse=True)
                
                for i, r in enumerate(sorted_data):
                    try:
                        table.insertRow(i)
                        table.setItem(i, 0, QTableWidgetItem(r.get('method', '')))
                        table.setItem(i, 1, QTableWidgetItem(r.get('channel', '')))
                        table.setItem(i, 2, QTableWidgetItem(r.get('group_a', '')))
                        table.setItem(i, 3, QTableWidgetItem(r.get('group_b', '')))
                        
                        value = r.get('value')
                        if isinstance(value, (int, float)):
                            table.setItem(i, 4, QTableWidgetItem(f"{value:.6f}"))
                        else:
                            table.setItem(i, 4, QTableWidgetItem(str(value)))
                        
                        indicators = r.get('indicators', {})
                        if indicators:
                            parts = []
                            for k, v in indicators.items():
                                if isinstance(v, (int, float)):
                                    parts.append(f"{k}={v:.4f}")
                                else:
                                    parts.append(f"{k}={v}")
                            indicator_str = "; ".join(parts)
                        else:
                            indicator_str = ""
                        table.setItem(i, 5, QTableWidgetItem(indicator_str))
                    except Exception as row_err:
                        log(f"[BGSub] display_results {domain_name}行{i}错误: {row_err}")
                        continue
                
                table.resizeColumnsToContents()
            
            populate_table(self.time_result_table, time_results, "时域")
            populate_table(self.freq_result_table, freq_results, "频域")
            
            self.result_table.setRowCount(0)
            self.result_table.setColumnCount(8)
            self.result_table.setHorizontalHeaderLabels(['领域', '算法', '通道', '组A', '组B', '值', '指标', '对消方法'])
            
            sorted_all = sorted(results, key=lambda x: x.get('value', 0), reverse=True)
            
            for i, r in enumerate(sorted_all):
                try:
                    self.result_table.insertRow(i)
                    self.result_table.setItem(i, 0, QTableWidgetItem(r.get('domain', '时域')))
                    self.result_table.setItem(i, 1, QTableWidgetItem(r.get('method', '')))
                    self.result_table.setItem(i, 2, QTableWidgetItem(r.get('channel', '')))
                    self.result_table.setItem(i, 3, QTableWidgetItem(r.get('group_a', '')))
                    self.result_table.setItem(i, 4, QTableWidgetItem(r.get('group_b', '')))
                    
                    value = r.get('value')
                    if isinstance(value, (int, float)):
                        self.result_table.setItem(i, 5, QTableWidgetItem(f"{value:.6f}"))
                    else:
                        self.result_table.setItem(i, 5, QTableWidgetItem(str(value)))
                    
                    indicators = r.get('indicators', {})
                    if indicators:
                        parts = []
                        for k, v in indicators.items():
                            if isinstance(v, (int, float)):
                                parts.append(f"{k}={v:.4f}")
                            else:
                                parts.append(f"{k}={v}")
                        indicator_str = "; ".join(parts)
                    else:
                        indicator_str = ""
                    self.result_table.setItem(i, 6, QTableWidgetItem(indicator_str))
                    self.result_table.setItem(i, 7, QTableWidgetItem(r.get('bg_method', '')))
                except Exception as row_err:
                    log(f"[BGSub] display_results 合并行{i}错误: {row_err}")
                    continue
            
            self.result_table.resizeColumnsToContents()
        except Exception as e:
            log(f"[BGSub] display_results 异常: {e}")
            import traceback
            log(f"[BGSub] 堆栈跟踪:\n{traceback.format_exc()}")
    
    def update_heatmap_combo(self):
        self.heatmap_alg_combo.blockSignals(True)
        self.heatmap_alg_combo.clear()
        for alg in self.heatmap_results.keys():
            self.heatmap_alg_combo.addItem(alg)
        self.heatmap_alg_combo.blockSignals(False)
        if self.heatmap_alg_combo.count() > 0:
            self.visualize_heatmap(0)
    
    def visualize_heatmap(self, index):
        if index < 0 or not self.heatmap_results:
            return
        
        alg_name = self.heatmap_alg_combo.itemText(index)
        if alg_name not in self.heatmap_results:
            return
        
        matrix = self.heatmap_results[alg_name]
        labels = [g['label'] for g in self.exp_groups]
        
        fig = self.heatmap_canvas.figure
        fig.clear()
        
        ax = fig.add_subplot(111)
        im = ax.imshow(matrix, cmap='viridis', interpolation='nearest', vmin=0, vmax=1)
        
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_yticklabels(labels)
        
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, f"{matrix[i, j]:.3f}", ha='center', va='center', 
                        color='white' if matrix[i, j] < 0.5 else 'black', fontsize=8)
        
        ax.set_title(f"{alg_name} - 相似度矩阵（背景对消后）")
        ax.set_xlabel("组B")
        ax.set_ylabel("组A")
        
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        self.heatmap_canvas.draw()
    
    def visualize_waveforms(self):
        try:
            if len(self.exp_groups) == 0:
                return
            
            channel_name = self.channel_combo.currentText()
            if not channel_name:
                return
            
            mode = self.waveform_mode_combo.currentText()
            use_downsample = self.downsample_display_check.isChecked()
            downsample_points = self.downsample_display_spin.value()
            
            n_groups = len(self.exp_groups)
            fig = self.waveform_canvas.figure
            fig.clear()
            
            gs = fig.add_gridspec(n_groups, 1, hspace=0.05)
            axes = gs.subplots(sharex=True)
            
            all_data = []
            for i, group in enumerate(self.exp_groups):
                data = self.get_channel_data(group, channel_name)
                if data is not None:
                    all_data.append(data)
            
            if not all_data:
                return
            
            if mode == "频域波形":
                try:
                    from scipy import signal
                    
                    for i, (group, data) in enumerate(zip(self.exp_groups, all_data)):
                        ax = axes[i] if n_groups > 1 else axes
                        
                        fs = group['fs']
                        
                        if use_downsample and len(data) > downsample_points:
                            data = signal.resample(data, downsample_points)
                        
                        f, Pxx = signal.welch(data, fs=fs, nperseg=min(len(data), 1024))
                        
                        ax.semilogy(f, Pxx, linewidth=0.8)
                        ax.set_ylabel(group['label'], rotation=0, labelpad=20, fontsize=8)
                        
                        if i < n_groups - 1:
                            ax.set_xticks([])
                        
                        ax.grid(True, alpha=0.3)
                        ax.set_xlim(0, fs/2)
                    
                    if n_groups > 1:
                        axes[-1].set_xlabel("频率 (Hz)")
                    else:
                        axes.set_xlabel("频率 (Hz)")
                    
                    fig.suptitle(f"通道 {channel_name} - {n_groups} 组数据频域对比（背景对消后）", y=0.98)
                except Exception as freq_err:
                    log(f"[BGSub] 频域波形可视化失败: {freq_err}")
                    QMessageBox.warning(self, "提示", f"频域波形计算失败: {freq_err}")
                    return
            else:
                for i, (group, data) in enumerate(zip(self.exp_groups, all_data)):
                    ax = axes[i] if n_groups > 1 else axes
                    
                    if use_downsample and len(data) > downsample_points:
                        from scipy import signal
                        data = signal.resample(data, downsample_points)
                    
                    t = np.linspace(0, len(data) / group['fs'], len(data))
                    ax.plot(t, data, linewidth=0.8)
                    ax.set_ylabel(group['label'], rotation=0, labelpad=20, fontsize=8)
                    
                    if i < n_groups - 1:
                        ax.set_xticks([])
                    
                    ax.grid(True, alpha=0.3)
                
                if n_groups > 1:
                    axes[-1].set_xlabel("时间 (s)")
                else:
                    axes.set_xlabel("时间 (s)")
                
                fig.suptitle(f"通道 {channel_name} - {n_groups} 组数据时域对比（背景对消后）", y=0.98)
            
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            self.waveform_canvas.draw()
        except Exception as e:
            log(f"[BGSub] visualize_waveforms 异常: {e}")
            import traceback
            log(f"[BGSub] 堆栈跟踪:\n{traceback.format_exc()}")
    
    def add_report_block(self):
        if not self.result_data:
            QMessageBox.warning(self, "提示", "请先计算相似性结果")
            return
        
        if not self.check_experiment_state_associated():
            return
        
        try:
            from experiment_state import ReportBlock, REPORT_MANAGER
            from report_manager import build_similarity_block_md, save_figure_to_file
            
            report_dir = REPORT_MANAGER.get_report_dir()
            if not report_dir:
                QMessageBox.warning(self, "提示", "请先在报告Tab设置报告目录")
                return
            
            os.makedirs(report_dir, exist_ok=True)
            
            fig_path = None
            channel_name = ''
            if self.channel_combo.count() > 0:
                channel_name = self.channel_combo.currentText()
                fig_path = save_figure_to_file(
                    self.waveform_canvas.figure, 
                    os.path.join(report_dir, f"bg_sub_waveform_{channel_name}.png")
                )
                log(f"[BGSub] 波形图保存路径: {fig_path}")
            
            heatmap_paths = {}
            for alg_name in self.heatmap_results.keys():
                idx = self.heatmap_alg_combo.findText(alg_name)
                if idx >= 0:
                    self.heatmap_alg_combo.setCurrentIndex(idx)
                    self.visualize_heatmap(idx)
                    path = save_figure_to_file(
                        self.heatmap_canvas.figure,
                        os.path.join(report_dir, f"bg_sub_heatmap_{alg_name}.png")
                    )
                    if path:
                        heatmap_paths[alg_name] = path
                        log(f"[BGSub] 热力图保存路径: {alg_name} -> {path}")
            
            labels = [g['label'] for g in self.exp_groups]
            md_content = f"## 背景对消批量参数对比报告\n\n"
            
            # 实验状态定义表
            from experiment_state import STATE_REGISTRY
            state_names = []
            for group in self.exp_groups:
                state_name = group.get('experiment_state')
                if state_name and state_name not in state_names:
                    state_names.append(state_name)
            for group in self.bg_groups:
                state_name = group.get('experiment_state')
                if state_name and state_name not in state_names:
                    state_names.append(state_name)
            
            md_content += "### 实验状态定义\n\n"
            md_content += STATE_REGISTRY.to_markdown_table(names=state_names)
            md_content += "\n"
            
            md_content += f"**数据组数**: {len(labels)}\n\n"
            md_content += f"**参数标签**: {', '.join(labels)}\n\n"
            md_content += f"**计算类型**: {getattr(self, '_calc_type', '时域')}\n\n"
            md_content += f"**背景对消算法**: {self.bg_method_combo.currentText()}\n\n"
            
            # 实验状态列表
            md_content += "### 数据组列表\n\n"
            md_content += "| 编号 | 标签 | 实验数据文件 | 关联背景数据 | 采样率 |\n"
            md_content += "|------|------|--------------|--------------|--------|\n"
            for i, group in enumerate(self.exp_groups):
                bg_label = group.get('bg_label')
                bg_file = ''
                if bg_label:
                    bg_group = next((bg for bg in self.bg_groups if bg['label'] == bg_label), None)
                    if bg_group:
                        bg_file = os.path.basename(bg_group.get('filepath', ''))
                md_content += f"| {i+1} | {group['label']} | {os.path.basename(group['filepath'])} | {bg_file if bg_file else (bg_label if bg_label else '无')} | {group['fs']:.0f} Hz |\n"
            md_content += "\n"
            
            if fig_path:
                md_content += f"### 波形对比图（通道: {channel_name}，背景对消后）\n\n"
                md_content += f"![波形对比]({os.path.basename(fig_path)})\n\n"
            
            md_content += "### 相似度热力图（背景对消后）\n\n"
            for alg_name, path in heatmap_paths.items():
                md_content += f"#### {alg_name}\n\n"
                md_content += f"![{alg_name}热力图]({os.path.basename(path)})\n\n"
            
            time_results = [r for r in self.result_data if r.get('domain') == '时域']
            if time_results:
                md_content += "### 时域相似性计算结果（背景对消后）\n\n"
                md_content += "| 算法 | 通道 | 组A | 组B | 值 |\n"
                md_content += "|------|------|-----|-----|----|\n"
                for r in time_results:
                    val = r.get('value', 0)
                    if isinstance(val, (int, float)):
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                    else:
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                md_content += "\n"
            
            freq_results = [r for r in self.result_data if r.get('domain') == '频域']
            if freq_results:
                md_content += "### 频域相似性计算结果（背景对消后）\n\n"
                md_content += "**频域变换算法**: Welch功率谱密度估计（使用FFT计算）\n\n"
                md_content += "| 算法 | 通道 | 组A | 组B | 值 |\n"
                md_content += "|------|------|-----|-----|----|\n"
                for r in freq_results:
                    val = r.get('value', 0)
                    if isinstance(val, (int, float)):
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val:.6f} |\n"
                    else:
                        md_content += f"| {r.get('method', '')} | {r.get('channel', '')} | {r.get('group_a', '')} | {r.get('group_b', '')} | {val} |\n"
                md_content += "\n"
            
            all_images = []
            if fig_path:
                all_images.append(fig_path)
            all_images.extend(list(heatmap_paths.values()))
            
            block = ReportBlock(
                source_tab='背景对消批处理',
                title=f"背景对消对比-{', '.join(labels)}",
                content_md=md_content,
                images=all_images
            )
            REPORT_MANAGER.add_block(block)
            
            QMessageBox.information(self, "成功", "报告BLOCK已添加")
            log(f"[BGSub] 报告BLOCK添加成功")
            
        except Exception as e:
            import traceback
            log(f"[BGSub] add_report_block 异常: {e}")
            log(f"[BGSub] 堆栈跟踪:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"添加报告BLOCK失败:\n{str(e)}")


# ============= Tab4: 数据预处理（粗粒化与窗口截断） =============

class PreprocessTab(QWidget):
    """数据预处理Tab：粗粒化、单窗口/多窗口/周期性窗口截断。
    处理后的数据完全替换原始数据，供时域/频域/矩阵Tab使用。"""

    # 预处理类型
    PRESET_TYPES = ['粗粒化', '单窗口截断', '多窗口截断', '周期性窗口截断']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_data = None
        self.fs = 1.0
        self.processed_data = None
        self.processed_meta = None
        self.processed_desc = ''
        self.target_tabs = []  # 注册的目标Tab列表
        # 多通道分割：通道名 -> 1D数组（CH01~CH16），不产生新文件
        self.channel_map = {}        # 原始数据通道映射
        self.proc_channel_map = {}   # 预处理后通道映射
        self.n_channels = 0
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # ---------- 左侧：配置面板 ----------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)

        # 文件选择
        file_group = QGroupBox("数据文件")
        file_layout = QVBoxLayout(file_group)
        self.file_selector = FileSelectorWidget("选择数据文件:")
        self.file_selector.file_loaded.connect(self.on_file_loaded)
        file_layout.addWidget(self.file_selector)
        left_layout.addWidget(file_group)

        # 多通道TDMS分割配置（通道数 + 采样频率，与实验状态定义页CH1/CH2对应）
        chcfg_group = QGroupBox("通道配置（多通道TDMS分割）")
        chcfg_layout = QGridLayout(chcfg_group)
        chcfg_layout.addWidget(QLabel("通道数:"), 0, 0)
        self.ch_count_combo = QComboBox()
        self.ch_count_combo.addItems(['12', '16'])
        self.ch_count_combo.setToolTip("探测器物理通道数，须与实验状态定义页(Tab5)的CH1一致")
        chcfg_layout.addWidget(self.ch_count_combo, 0, 1)
        chcfg_layout.addWidget(QLabel("采样频率:"), 1, 0)
        self.ch_fs_combo = QComboBox()
        self.ch_fs_combo.addItems(['200K', '300K', '400K'])
        self.ch_fs_combo.setToolTip("探测系统采样频率，须与实验状态定义页(Tab5)的CH2一致")
        chcfg_layout.addWidget(self.ch_fs_combo, 1, 1)
        self.split_btn = QPushButton("分割赋值通道")
        self.split_btn.setStyleSheet("background-color: #009688; color: white; padding: 4px;")
        self.split_btn.clicked.connect(self.split_channels)
        chcfg_layout.addWidget(self.split_btn, 2, 0, 1, 2)
        self.split_info_label = QLabel("尚未分割")
        self.split_info_label.setWordWrap(True)
        self.split_info_label.setStyleSheet("color: #666; font-size: 9pt; padding: 2px;")
        chcfg_layout.addWidget(self.split_info_label, 3, 0, 1, 2)
        left_layout.addWidget(chcfg_group)

        # 通道选择（用于预处理目标通道）
        channel_group = QGroupBox("通道选择（预处理目标通道）")
        channel_layout = QVBoxLayout(channel_group)
        self.channel_sel = ChannelSelectorWidget()
        channel_layout.addWidget(self.channel_sel)
        left_layout.addWidget(channel_group)

        # 采样率
        fs_group = QGroupBox("采样率设置")
        fs_layout = QHBoxLayout(fs_group)
        fs_layout.addWidget(QLabel("Fs (Hz):"))
        self.fs_spin = QDoubleSpinBox()
        self.fs_spin.setRange(0.001, 1000000)
        self.fs_spin.setValue(1.0)
        self.fs_spin.setDecimals(3)
        fs_layout.addWidget(self.fs_spin)
        left_layout.addWidget(fs_group)

        # 预处理类型
        type_group = QGroupBox("预处理类型")
        type_layout = QVBoxLayout(type_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.PRESET_TYPES)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        left_layout.addWidget(type_group)

        # 参数容器（用StackedWidget切换不同类型的参数面板）
        self.param_stack = QStackedWidget()
        self.param_stack.addWidget(self._build_coarsening_panel())   # index 0
        self.param_stack.addWidget(self._build_single_window_panel())# index 1
        self.param_stack.addWidget(self._build_multi_window_panel()) # index 2
        self.param_stack.addWidget(self._build_periodic_panel())    # index 3
        left_layout.addWidget(self.param_stack, stretch=1)

        # 推送设置与操作按钮
        push_group = QGroupBox("推送设置")
        push_layout = QVBoxLayout(push_group)

        # 目标页面选择
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("目标页面:"))
        self.push_target_combo = QComboBox()
        self.push_target_combo.addItem("时域相似性处理", "tab1")
        self.push_target_combo.addItem("频域相似性处理", "tab2")
        self.push_target_combo.addItem("矩阵转换与可视化", "tab3")
        self.push_target_combo.addItem("全部页面", "all")
        self.push_target_combo.currentIndexChanged.connect(self._on_push_target_changed)
        target_row.addWidget(self.push_target_combo, stretch=1)
        push_layout.addLayout(target_row)

        # 实验状态选择（A/B 对应的实验状态，从全局注册表读取）
        state_row = QHBoxLayout()
        state_row.addWidget(QLabel("实验状态:"))
        self.push_state_combo = QComboBox()
        self.push_state_combo.addItem("实验状态1", "A")
        self.push_state_combo.addItem("实验状态2", "B")
        self.push_state_combo.addItem("实验状态1 和 实验状态2", "AB")
        self._on_push_target_changed(self.push_target_combo.currentIndex())
        state_row.addWidget(self.push_state_combo, stretch=1)

        # 实验状态A对应的具体状态（从注册表）
        state_row.addWidget(QLabel("A状态:"))
        self.push_state_a_combo = QComboBox()
        self.push_state_a_combo.setEnabled(False)
        state_row.addWidget(self.push_state_a_combo, stretch=1)
        # 实验状态B对应的具体状态（从注册表）
        state_row.addWidget(QLabel("B状态:"))
        self.push_state_b_combo = QComboBox()
        self.push_state_b_combo.setEnabled(False)
        state_row.addWidget(self.push_state_b_combo, stretch=1)

        self.refresh_state_btn = QPushButton("刷新状态")
        self.refresh_state_btn.clicked.connect(self.refresh_push_states)
        state_row.addWidget(self.refresh_state_btn)
        push_layout.addLayout(state_row)

        # 推送通道维度选择：全部通道 / 单通道 / 任意指定通道
        ch_push_row1 = QHBoxLayout()
        ch_push_row1.addWidget(QLabel("推送通道:"))
        self.push_ch_mode_combo = QComboBox()
        self.push_ch_mode_combo.addItem("全部通道", "all")
        self.push_ch_mode_combo.addItem("单通道", "single")
        self.push_ch_mode_combo.addItem("指定通道(多选)", "multi")
        self.push_ch_mode_combo.currentIndexChanged.connect(self._on_push_ch_mode_changed)
        ch_push_row1.addWidget(self.push_ch_mode_combo, stretch=1)
        push_layout.addLayout(ch_push_row1)

        # 单通道选择下拉
        self.push_ch_single_combo = QComboBox()
        push_layout.addWidget(self.push_ch_single_combo)
        # 多通道选择列表
        self.push_ch_multi_list = QListWidget()
        self.push_ch_multi_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.push_ch_multi_list.setMaximumHeight(90)
        push_layout.addWidget(self.push_ch_multi_list)
        self._on_push_ch_mode_changed()

        # 操作按钮行
        op_btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("执行预处理")
        self.apply_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.apply_btn.clicked.connect(self.apply_preprocess)
        op_btn_layout.addWidget(self.apply_btn)

        self.push_btn = QPushButton("推送")
        self.push_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.push_btn.clicked.connect(self.push_to_tabs)
        self.push_btn.setEnabled(False)
        op_btn_layout.addWidget(self.push_btn)
        push_layout.addLayout(op_btn_layout)

        left_layout.addWidget(push_group)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # ---------- 右侧：预览（子Tab结构） ----------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        info_group = QGroupBox("处理信息")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("尚未执行预处理")
        self.info_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        right_layout.addWidget(info_group)

        # 预处理结果预览区：子Tab1(表格) + 子Tab2(通道可视化) + 子Tab3(统计指标)
        self.preview_subtabs = QTabWidget()

        # 子Tab1：表格化显示分割赋值好的数据（同一文件内各通道）
        tab1_table = QWidget()
        tab1_layout = QVBoxLayout(tab1_table)
        tab1_top = QHBoxLayout()
        tab1_top.addWidget(QLabel("通道数据表格（显示各通道前N个采样点）:"))
        self.table_n_spin = QSpinBox()
        self.table_n_spin.setRange(10, 10000)
        self.table_n_spin.setValue(100)
        self.table_n_spin.setSuffix(" 点")
        tab1_top.addWidget(self.table_n_spin)
        self.table_refresh_btn = QPushButton("刷新表格")
        self.table_refresh_btn.clicked.connect(self._refresh_channel_table)
        tab1_top.addWidget(self.table_refresh_btn)
        tab1_layout.addLayout(tab1_top)
        self.channel_table = QTableWidget()
        self.channel_table.setColumnCount(0)
        self.channel_table.setRowCount(0)
        self.channel_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        tab1_layout.addWidget(self.channel_table, stretch=1)
        self.preview_subtabs.addTab(tab1_table, "📋 子Tab1: 通道数据表格")

        # 子Tab2：可视化显示用户指定通道的数据（多选列表+按钮）
        tab2_viz = QWidget()
        tab2_layout = QVBoxLayout(tab2_viz)
        tab2_top = QHBoxLayout()
        tab2_top.addWidget(QLabel("选择通道:"))
        # 改为多选列表，支持全部/单通道/指定通道多选
        self.viz_ch_mode_combo = QComboBox()
        self.viz_ch_mode_combo.addItem("全部通道", "all")
        self.viz_ch_mode_combo.addItem("单通道", "single")
        self.viz_ch_mode_combo.addItem("指定通道(多选)", "multi")
        self.viz_ch_mode_combo.currentIndexChanged.connect(self._on_viz_ch_mode_changed)
        tab2_top.addWidget(self.viz_ch_mode_combo)
        self.viz_ch_single_combo = QComboBox()
        self.viz_ch_single_combo.setMinimumWidth(100)
        tab2_top.addWidget(self.viz_ch_single_combo)
        self.viz_ch_multi_list = QListWidget()
        self.viz_ch_multi_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.viz_ch_multi_list.setMaximumHeight(80)
        tab2_layout.addWidget(self.viz_ch_multi_list)
        tab2_top.addWidget(QLabel("数据源:"))
        self.viz_src_combo = QComboBox()
        self.viz_src_combo.addItem("原始数据", "raw")
        self.viz_src_combo.addItem("预处理后数据", "proc")
        tab2_top.addWidget(self.viz_src_combo)
        self.viz_plot_btn = QPushButton("绘制")
        self.viz_plot_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 4px;")
        self.viz_plot_btn.clicked.connect(self._plot_selected_channel)
        tab2_top.addWidget(self.viz_plot_btn)
        self.viz_detach_btn = QPushButton("🖥 独立窗口")
        self.viz_detach_btn.setToolTip("将当前可视化分离为独立窗口，支持缩放和全屏")
        self.viz_detach_btn.clicked.connect(lambda: self._detach_canvas(self.channel_viz_canvas, "通道可视化"))
        tab2_top.addWidget(self.viz_detach_btn)
        tab2_layout.addLayout(tab2_top)
        self._on_viz_ch_mode_changed()  # 初始化通道选择控件的显示/隐藏
        
        # 时间门控制面板（第5点：鼠标拖动+输入框控制时间门宽窄）
        gate_group = QGroupBox("时间门控制 (鼠标拖动 / 输入框指定截断范围)")
        # ========== 整合的截断功能区（互锁模式） ==========
        gate_group = QGroupBox("📌 截断功能区（定义截断位置 - 用于预处理）")
        gate_group.setStyleSheet("QGroupBox { font-weight: bold; background-color: #f5f5f5; border: 2px solid #2196F3; border-radius: 5px; padding: 8px; }")
        gate_layout = QVBoxLayout(gate_group)
        
        # 截断类型选择（互斥）
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("截断方式:"))
        self.truncate_type_combo = QComboBox()
        self.truncate_type_combo.addItems(["不使用截断", "单窗口截断", "多窗口截断", "周期性窗口截断"])
        self.truncate_type_combo.currentIndexChanged.connect(self._on_truncate_type_changed)
        type_row.addWidget(self.truncate_type_combo, stretch=1)
        gate_layout.addLayout(type_row)
        
        # 单窗口截断参数面板
        self.sw_panel = QWidget()
        sw_layout = QFormLayout(self.sw_panel)
        sw_layout.setContentsMargins(5, 5, 5, 5)
        self.tr_sw_start = QDoubleSpinBox()
        self.tr_sw_start.setRange(0, 1e12)
        self.tr_sw_start.setDecimals(6)
        self.tr_sw_start.setValue(0.0)
        self.tr_sw_start.setToolTip("窗口起始时间(秒)，从信号起点算起")
        sw_layout.addRow("起始时间 T_start (秒):", self.tr_sw_start)
        
        self.tr_sw_end = QDoubleSpinBox()
        self.tr_sw_end.setRange(0, 1e12)
        self.tr_sw_end.setDecimals(6)
        self.tr_sw_end.setValue(1.0)
        self.tr_sw_end.setToolTip("窗口结束时间(秒)，必须大于起始时间")
        sw_layout.addRow("结束时间 T_end (秒):", self.tr_sw_end)
        
        sw_hint = QLabel("保留 [T_start, T_end] 时间段内的数据，其余部分丢弃。")
        sw_hint.setWordWrap(True)
        sw_hint.setStyleSheet("color: #666; font-size: 9pt;")
        sw_layout.addRow(sw_hint)
        gate_layout.addWidget(self.sw_panel)
        
        # 多窗口截断参数面板
        self.mw_panel = QWidget()
        mw_layout = QVBoxLayout(self.mw_panel)
        mw_layout.setContentsMargins(5, 5, 5, 5)
        mw_layout.addWidget(QLabel("多时段定义（每行：起始时间, 结束时间，单位秒）:"))
        self.mw_table = QTableWidget(0, 2)
        self.mw_table.setHorizontalHeaderLabels(["起始时间(秒)", "结束时间(秒)"])
        self.mw_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        mw_layout.addWidget(self.mw_table)
        mw_btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 添加时段")
        add_btn.clicked.connect(lambda: self._mw_add_row(0.0, 1.0))
        mw_btn_row.addWidget(add_btn)
        del_btn = QPushButton("- 删除选中")
        del_btn.clicked.connect(self._mw_del_row)
        mw_btn_row.addWidget(del_btn)
        clr_btn = QPushButton("清空")
        clr_btn.clicked.connect(lambda: self.mw_table.setRowCount(0))
        mw_btn_row.addWidget(clr_btn)
        mw_layout.addLayout(mw_btn_row)
        mw_hint = QLabel("所有时段数据按顺序拼接为一段。")
        mw_hint.setWordWrap(True)
        mw_hint.setStyleSheet("color: #666; font-size: 9pt;")
        mw_layout.addWidget(mw_hint)
        # 默认两行
        self._mw_add_row(0.0, 1.0)
        self._mw_add_row(2.0, 3.0)
        gate_layout.addWidget(self.mw_panel)
        
        # 周期性窗口截断参数面板
        self.pw_panel = QWidget()
        pw_layout = QFormLayout(self.pw_panel)
        pw_layout.setContentsMargins(5, 5, 5, 5)
        self.tr_pw_T0 = QDoubleSpinBox()
        self.tr_pw_T0.setRange(0, 1e12)
        self.tr_pw_T0.setDecimals(6)
        self.tr_pw_T0.setValue(0.0)
        self.tr_pw_T0.setToolTip("起始时间T0(秒)，第一个窗口从T0开始")
        pw_layout.addRow("起始时间 T0 (秒):", self.tr_pw_T0)
        
        self.tr_pw_T1 = QDoubleSpinBox()
        self.tr_pw_T1.setRange(1e-6, 1e12)
        self.tr_pw_T1.setDecimals(6)
        self.tr_pw_T1.setValue(1.0)
        self.tr_pw_T1.setToolTip("周期T1(秒)，每隔T1时间取一个窗口")
        pw_layout.addRow("周期 T1 (秒):", self.tr_pw_T1)
        
        self.tr_pw_T2 = QDoubleSpinBox()
        self.tr_pw_T2.setRange(1e-6, 1e12)
        self.tr_pw_T2.setDecimals(6)
        self.tr_pw_T2.setValue(0.3)
        self.tr_pw_T2.setToolTip("窗口时长T2(秒)，每个窗口取T2时长数据，必须≤T1")
        pw_layout.addRow("窗口时长 T2 (秒):", self.tr_pw_T2)
        
        pw_hint = QLabel("从T0开始，每隔T1秒取T2秒数据，所有窗口拼接。要求 T2 ≤ T1。")
        pw_hint.setWordWrap(True)
        pw_hint.setStyleSheet("color: #666; font-size: 9pt;")
        pw_layout.addRow(pw_hint)
        gate_layout.addWidget(self.pw_panel)
        
        # 起始时间归零选项
        tzero_row = QHBoxLayout()
        self.tzero_check = QCheckBox("截断后起始时间归零")
        self.tzero_check.setToolTip("勾选后，截断后的数据起始时间将从0秒开始")
        self.tzero_check.setChecked(True)
        tzero_row.addWidget(self.tzero_check)
        tzero_row.addStretch()
        gate_layout.addLayout(tzero_row)
        
        # 截断预览和清除按钮
        btn_row = QHBoxLayout()
        self.truncate_preview_btn = QPushButton("🔍 预览截断效果")
        self.truncate_preview_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 6px;")
        self.truncate_preview_btn.clicked.connect(self._preview_truncate)
        btn_row.addWidget(self.truncate_preview_btn)
        self.truncate_clear_btn = QPushButton("🗑 清除截断定义")
        self.truncate_clear_btn.setStyleSheet("background-color: #9E9E9E; color: white; padding: 6px;")
        self.truncate_clear_btn.clicked.connect(self._clear_truncate)
        btn_row.addWidget(self.truncate_clear_btn)
        gate_layout.addLayout(btn_row)
        
        # 提示
        gate_hint = QLabel("💡 提示：先选择截断方式并设置参数，点击「预览截断效果」观察效果。确认无误后，在左侧「预处理类型」中选择对应的截断方式，点击「执行预处理」进行实际处理。")
        gate_hint.setStyleSheet("color: #1565C0; font-size: 10px; background-color: #E3F2FD; padding: 5px; border-radius: 3px;")
        gate_hint.setWordWrap(True)
        gate_layout.addWidget(gate_hint)
        
        # 初始状态：所有截断面板隐藏
        self._on_truncate_type_changed(0)
        tab2_layout.addWidget(gate_group)
        
        self.channel_viz_canvas = create_canvas(self)
        self.channel_viz_toolbar = NavigationToolbar(self.channel_viz_canvas, self)
        tab2_layout.addWidget(self.channel_viz_toolbar)
        tab2_layout.addWidget(self.channel_viz_canvas, stretch=1)
        # 门控状态
        self.gate_regions = []  # [(start_s, end_s), ...]
        self._gate_dragging = False
        self._gate_drag_side = None  # 'start' or 'end'
        # 连接画布鼠标事件用于拖动门控
        self.channel_viz_canvas.mpl_connect('button_press_event', self._on_gate_mouse_press)
        self.channel_viz_canvas.mpl_connect('motion_notify_event', self._on_gate_mouse_motion)
        self.channel_viz_canvas.mpl_connect('button_release_event', self._on_gate_mouse_release)
        self.preview_subtabs.addTab(tab2_viz, "📈 子Tab2: 通道可视化")

        # 子Tab3：数据文件参数特征识别（总时长 + 20种统计指标）
        tab3_stat = QWidget()
        tab3_layout = QVBoxLayout(tab3_stat)
        tab3_top = QHBoxLayout()
        tab3_top.addWidget(QLabel("统计通道:"))
        # 改为多选列表，支持全部/单通道/指定通道多选
        self.stat_ch_mode_combo = QComboBox()
        self.stat_ch_mode_combo.addItem("全部通道", "all")
        self.stat_ch_mode_combo.addItem("单通道", "single")
        self.stat_ch_mode_combo.addItem("指定通道(多选)", "multi")
        self.stat_ch_mode_combo.currentIndexChanged.connect(self._on_stat_ch_mode_changed)
        tab3_top.addWidget(self.stat_ch_mode_combo)
        self.stat_ch_single_combo = QComboBox()
        self.stat_ch_single_combo.setMinimumWidth(100)
        tab3_top.addWidget(self.stat_ch_single_combo)
        self.stat_ch_multi_list = QListWidget()
        self.stat_ch_multi_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.stat_ch_multi_list.setMaximumHeight(80)
        tab3_layout.addWidget(self.stat_ch_multi_list)
        tab3_top.addWidget(QLabel("数据源:"))
        self.stat_src_combo = QComboBox()
        self.stat_src_combo.addItem("原始数据", "raw")
        self.stat_src_combo.addItem("预处理后数据", "proc")
        tab3_top.addWidget(self.stat_src_combo)
        self.stat_calc_btn = QPushButton("计算统计指标")
        self.stat_calc_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 4px;")
        self.stat_calc_btn.clicked.connect(self._calc_statistics)
        tab3_top.addWidget(self.stat_calc_btn)
        tab3_layout.addLayout(tab3_top)
        self._on_stat_ch_mode_changed()  # 初始化通道选择控件的显示/隐藏
        # 文件参数特征区
        self.file_feat_label = QLabel("文件参数特征：尚未计算")
        self.file_feat_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border: 1px solid #ddd; font-size: 9pt;")
        self.file_feat_label.setWordWrap(True)
        tab3_layout.addWidget(self.file_feat_label)
        # 统计指标表格
        self.stat_table = QTableWidget()
        self.stat_table.setColumnCount(3)
        self.stat_table.setHorizontalHeaderLabels(["统计指标", "数值", "说明"])
        self.stat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.stat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.stat_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tab3_layout.addWidget(self.stat_table, stretch=1)
        self.preview_subtabs.addTab(tab3_stat, "📊 子Tab3: 参数特征与统计")

        right_layout.addWidget(self.preview_subtabs, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter)

    # ---------- 参数面板构建 ----------
    def _build_coarsening_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 方法选择
        layout.addWidget(QLabel("粗粒化方法 (20种):"))
        self.coarse_method_combo = QComboBox()
        for name in COARSENING_METHODS.keys():
            self.coarse_method_combo.addItem(name)
        self.coarse_method_combo.currentIndexChanged.connect(self.on_coarse_method_changed)
        layout.addWidget(self.coarse_method_combo)

        # 方法说明（鼠标悬停tooltip在combo上）
        self.coarse_tooltip_label = QLabel()
        self.coarse_tooltip_label.setWordWrap(True)
        self.coarse_tooltip_label.setStyleSheet("padding: 5px; background-color: #fffde7; border: 1px solid #ffe082; font-size: 9pt;")
        layout.addWidget(self.coarse_tooltip_label)

        # 动态参数容器
        self.coarse_param_container = QWidget()
        self.coarse_param_layout = QGridLayout(self.coarse_param_container)
        self.coarse_param_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.coarse_param_container)
        layout.addStretch()

        # 初始化第一个方法的参数
        self._coarse_param_widgets = {}
        self.on_coarse_method_changed(0)
        return panel

    def _build_single_window_panel(self):
        """单窗口截断参数面板（已整合到右侧截断功能区）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("📌 单窗口截断参数已在右侧「截断功能区」定义。\n\n"
                      "请切换到子Tab2:通道可视化，在「截断功能区」中：\n"
                      "1. 选择「单窗口截断」方式\n"
                      "2. 设置起始/结束时间\n"
                      "3. 点击「预览截断效果」观察\n"
                      "4. 确认后点击左侧「执行预处理」")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #1565C0; font-size: 10pt; background-color: #E3F2FD; padding: 15px; border-radius: 5px;")
        layout.addWidget(hint)
        layout.addStretch()
        return panel

    def _build_multi_window_panel(self):
        """多窗口截断参数面板（已整合到右侧截断功能区）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("📌 多窗口截断参数已在右侧「截断功能区」定义。\n\n"
                      "请切换到子Tab2:通道可视化，在「截断功能区」中：\n"
                      "1. 选择「多窗口截断」方式\n"
                      "2. 添加/编辑时段\n"
                      "3. 点击「预览截断效果」观察\n"
                      "4. 确认后点击左侧「执行预处理」")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #1565C0; font-size: 10pt; background-color: #E3F2FD; padding: 15px; border-radius: 5px;")
        layout.addWidget(hint)
        layout.addStretch()
        return panel

    def _build_periodic_panel(self):
        """周期性窗口截断参数面板（已整合到右侧截断功能区）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        hint = QLabel("📌 周期性窗口截断参数已在右侧「截断功能区」定义。\n\n"
                      "请切换到子Tab2:通道可视化，在「截断功能区」中：\n"
                      "1. 选择「周期性窗口截断」方式\n"
                      "2. 设置T0/T1/T2参数\n"
                      "3. 点击「预览截断效果」观察\n"
                      "4. 确认后点击左侧「执行预处理」")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #1565C0; font-size: 10pt; background-color: #E3F2FD; padding: 15px; border-radius: 5px;")
        layout.addWidget(hint)
        layout.addStretch()
        return panel

    # ---------- 粗粒化方法切换 ----------
    def on_coarse_method_changed(self, idx):
        name = self.coarse_method_combo.currentText()
        if not name:
            return
        entry = COARSENING_METHODS.get(name)
        if not entry:
            return
        # 设置方法说明
        tooltip = entry['tooltip']
        self.coarse_method_combo.setToolTip(tooltip)
        self.coarse_tooltip_label.setText(f"【{name}】{tooltip}")

        # 清空旧参数控件
        for w in self._coarse_param_widgets.values():
            w.setParent(None)
            w.deleteLater()
        self._coarse_param_widgets.clear()

        # 重建参数控件
        params = entry['params']
        for row, p in enumerate(params):
            key, display, vmin, vmax, step, default, desc = p
            lbl = QLabel(display + ":")
            lbl.setToolTip(desc)
            if isinstance(default, float) or isinstance(step, float) or isinstance(vmin, float):
                spin = QDoubleSpinBox()
                spin.setDecimals(4)
            else:
                spin = QSpinBox()
            spin.setRange(vmin, vmax)
            spin.setSingleStep(step)
            spin.setValue(default)
            spin.setToolTip(desc)
            self.coarse_param_layout.addWidget(lbl, row, 0)
            self.coarse_param_layout.addWidget(spin, row, 1)
            # 参数说明标签
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #555; font-size: 8pt;")
            self.coarse_param_layout.addWidget(desc_lbl, row, 2)
            self._coarse_param_widgets[key] = spin

    def on_type_changed(self, idx):
        self.param_stack.setCurrentIndex(idx)

    # ---------- 多窗口表格操作 ----------
    def _mw_add_row(self, t0=0.0, t1=1.0):
        r = self.mw_table.rowCount()
        self.mw_table.insertRow(r)
        self.mw_table.setItem(r, 0, QTableWidgetItem(str(t0)))
        self.mw_table.setItem(r, 1, QTableWidgetItem(str(t1)))

    def _mw_del_row(self):
        rows = sorted(set(i.row() for i in self.mw_table.selectedItems()), reverse=True)
        for r in rows:
            self.mw_table.removeRow(r)

    def _mw_collect_windows(self):
        windows = []
        for r in range(self.mw_table.rowCount()):
            it0 = self.mw_table.item(r, 0)
            it1 = self.mw_table.item(r, 1)
            if it0 is None or it1 is None:
                continue
            try:
                t0 = float(it0.text()); t1 = float(it1.text())
            except ValueError:
                raise ValueError(f"第{r+1}行时间格式错误，请输入数字")
            if t1 <= t0:
                raise ValueError(f"第{r+1}行结束时间必须大于起始时间")
            windows.append((t0, t1))
        return windows

    # ---------- 文件加载 ----------
    def on_file_loaded(self, path, data, meta):
        self.file_data = data
        self.fs = meta.get('fs', 1.0) or 1.0
        self.fs_spin.setValue(self.fs)
        self.channel_sel.set_data(data)
        # 自动检测通道数并匹配通道配置下拉
        n_ch = data.shape[1] if data.ndim > 1 else 1
        self.n_channels = n_ch
        # 根据实际通道数自动选择12/16
        if n_ch in (12, 16):
            idx = self.ch_count_combo.findText(str(n_ch))
            if idx >= 0:
                self.ch_count_combo.setCurrentIndex(idx)
        # 根据采样率自动选择200K/300K/400K
        fs_khz = int(round(self.fs / 1000))
        if fs_khz in (200, 300, 400):
            idx = self.ch_fs_combo.findText(f"{fs_khz}K")
            if idx >= 0:
                self.ch_fs_combo.setCurrentIndex(idx)
        # 自动分割赋值通道
        self.split_channels(silent=True)
        total_time = (len(data) / self.fs) if self.fs > 0 else 0
        self.info_label.setText(
            f"已加载: {path}\n样本数: {len(data)} | 采样率: {self.fs} Hz | "
            f"通道数: {n_ch} | 总时长: {total_time:.3f} 秒"
        )

    def split_channels(self, silent=False):
        """将TDMS/多通道数据分割赋值给通道变量CH01~CH16（仅内存赋值，不产生新文件）"""
        if self.file_data is None:
            if not silent:
                QMessageBox.warning(self, "提示", "请先加载数据文件")
            return False
        data = self.file_data
        n_ch = data.shape[1] if data.ndim > 1 else 1
        # 校验：用户指定通道数须与文件实际通道数一致
        user_ch = int(self.ch_count_combo.currentText())
        if n_ch != user_ch:
            if not silent:
                QMessageBox.warning(
                    self, "通道数不匹配",
                    f"文件实际通道数为 {n_ch}，与指定通道数 {user_ch} 不一致。\n"
                    f"请确认通道数设置或重新选择文件。"
                )
            return False
        # 校验：与实验状态定义页(Tab5)的CH1一致性
        exp_ch = self._get_experiment_ch1()
        if exp_ch is not None and str(exp_ch) != str(user_ch):
            ret = QMessageBox.question(
                self, "通道数与实验状态定义不一致",
                f"本页指定通道数为 {user_ch}，但实验状态定义页(Tab5)记录的CH1(通道数)为 {exp_ch}。\n\n"
                f"通道数不一致会导致对比无意义。是否仍要继续？\n"
                f"（建议：先到Tab5修正CH1设置，或修改本页通道数使其一致）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret == QMessageBox.No:
                return False
        # 分割赋值：CH01~CH{nn}
        self.channel_map = {}
        for i in range(n_ch):
            ch_name = f"CH{i+1:02d}"
            self.channel_map[ch_name] = data[:, i] if data.ndim > 1 else data.flatten()
        self.n_channels = n_ch
        # 同步采样频率到fs_spin
        fs_khz = self.ch_fs_combo.currentText()
        fs_map = {'200K': 200000.0, '300K': 300000.0, '400K': 400000.0}
        if fs_khz in fs_map:
            self.fs = fs_map[fs_khz]
            self.fs_spin.setValue(self.fs)
        total_time = (len(data) / self.fs) if self.fs > 0 else 0
        ch_list = ', '.join(list(self.channel_map.keys()))
        self.split_info_label.setText(
            f"已分割 {n_ch} 通道: {ch_list}\n采样率: {self.fs} Hz | 总时长: {total_time:.3f} 秒"
        )
        # 刷新推送通道选择控件
        self._refresh_push_channel_selectors()
        if not silent:
            QMessageBox.information(
                self, "分割完成",
                f"已将数据分割赋值给 {n_ch} 个通道变量(CH01~CH{n_ch:02d})。\n"
                f"采样率: {self.fs} Hz | 总时长: {total_time:.3f} 秒\n"
                f"（仅在内存中赋值，未产生新文件）"
            )
        return True

    def _get_experiment_ch1(self):
        """从实验状态注册表获取最近一条实验状态的CH1(通道数)设置，无则返回None"""
        try:
            from experiment_state import STATE_REGISTRY
            states = STATE_REGISTRY.get_all_states()
            if not states:
                return None
            # 取最近一条有CH1参数的状态
            for s in reversed(states):
                ch1 = s.get('params', {}).get('CH1')
                if ch1:
                    return ch1
            return None
        except Exception:
            return None

    def _refresh_push_channel_selectors(self):
        """根据已分割的通道刷新推送通道选择控件"""
        ch_names = list(self.channel_map.keys()) if self.channel_map else []
        # 单通道下拉
        self.push_ch_single_combo.blockSignals(True)
        self.push_ch_single_combo.clear()
        for n in ch_names:
            self.push_ch_single_combo.addItem(n)
        self.push_ch_single_combo.blockSignals(False)
        # 多通道列表
        self.push_ch_multi_list.blockSignals(True)
        self.push_ch_multi_list.clear()
        for n in ch_names:
            self.push_ch_multi_list.addItem(n)
        self.push_ch_multi_list.blockSignals(False)
        # 同步子Tab2的通道下拉（单选和多选）
        self.viz_ch_single_combo.blockSignals(True)
        self.viz_ch_single_combo.clear()
        for n in ch_names:
            self.viz_ch_single_combo.addItem(n)
        self.viz_ch_single_combo.blockSignals(False)
        self.viz_ch_multi_list.blockSignals(True)
        self.viz_ch_multi_list.clear()
        for n in ch_names:
            item = QListWidgetItem(n)
            self.viz_ch_multi_list.addItem(item)
        self.viz_ch_multi_list.blockSignals(False)
        # 同步子Tab3的通道下拉（单选和多选）
        self.stat_ch_single_combo.blockSignals(True)
        self.stat_ch_single_combo.clear()
        for n in ch_names:
            self.stat_ch_single_combo.addItem(n)
        self.stat_ch_single_combo.blockSignals(False)
        self.stat_ch_multi_list.blockSignals(True)
        self.stat_ch_multi_list.clear()
        for n in ch_names:
            self.stat_ch_multi_list.addItem(n)
        self.stat_ch_multi_list.blockSignals(False)

    def _on_push_ch_mode_changed(self, *args):
        """切换推送通道模式时显示/隐藏对应控件"""
        mode = self.push_ch_mode_combo.currentData()
        is_single = (mode == 'single')
        is_multi = (mode == 'multi')
        self.push_ch_single_combo.setVisible(is_single)
        self.push_ch_multi_list.setVisible(is_multi)

    def _on_viz_ch_mode_changed(self, *args):
        """切换子Tab2通道模式时显示/隐藏对应控件"""
        mode = self.viz_ch_mode_combo.currentData()
        is_single = (mode == 'single')
        is_multi = (mode == 'multi')
        self.viz_ch_single_combo.setVisible(is_single)
        self.viz_ch_multi_list.setVisible(is_multi)

    def _on_stat_ch_mode_changed(self, *args):
        """切换子Tab3通道模式时显示/隐藏对应控件"""
        mode = self.stat_ch_mode_combo.currentData()
        is_single = (mode == 'single')
        is_multi = (mode == 'multi')
        self.stat_ch_single_combo.setVisible(is_single)
        self.stat_ch_multi_list.setVisible(is_multi)

    def _get_viz_channels(self):
        """获取子Tab2当前要可视化的通道名列表"""
        mode = self.viz_ch_mode_combo.currentData()
        ch_names = list(self.channel_map.keys()) if self.channel_map else []
        if mode == 'all':
            return ch_names
        elif mode == 'single':
            name = self.viz_ch_single_combo.currentText()
            return [name] if name else []
        elif mode == 'multi':
            return [it.text() for it in self.viz_ch_multi_list.selectedItems()]
        return []

    def _get_stat_channels(self):
        """获取子Tab3当前要计算统计的通道名列表"""
        mode = self.stat_ch_mode_combo.currentData()
        ch_names = list(self.channel_map.keys()) if self.channel_map else []
        if mode == 'all':
            return ch_names
        elif mode == 'single':
            name = self.stat_ch_single_combo.currentText()
            return [name] if name else []
        elif mode == 'multi':
            return [it.text() for it in self.stat_ch_multi_list.selectedItems()]
        return []

    def _get_push_channels(self):
        """获取当前要推送的通道名列表"""
        mode = self.push_ch_mode_combo.currentData()
        if mode == 'all':
            return list(self.channel_map.keys()) if self.channel_map else []
        elif mode == 'single':
            name = self.push_ch_single_combo.currentText()
            return [name] if name else []
        elif mode == 'multi':
            return [it.text() for it in self.push_ch_multi_list.selectedItems()]
        return []

    def _get_channel_data(self):
        if self.file_data is None:
            return None
        ch = self.channel_sel.get_selected_channel()
        data = self.file_data
        if data.ndim == 1:
            return data
        elif data.ndim == 2:
            if ch < data.shape[1]:
                return data[:, ch]
        return data.flatten()

    # ---------- 执行预处理 ----------
    def _process_one_channel(self, raw, ptype):
        """对单个通道数据执行指定类型的预处理，返回(结果数组, 描述)"""
        tzero = self.tzero_check.isChecked()  # 是否将起始时间归零
        if ptype == '粗粒化':
            method = self.coarse_method_combo.currentText()
            params = {}
            for k, w in self._coarse_param_widgets.items():
                params[k] = w.value()
            result = apply_coarsening(raw, method, fs=self.fs, **params)
            desc = f"粗粒化[{method}] 参数={params}"
            if tzero:
                result = result  # 粗粒化后时间轴从0开始
            desc += f"\n原始长度:{len(raw)} -> 处理后长度:{len(result)}"
        elif ptype == '单窗口截断':
            t0 = self.tr_sw_start.value(); t1 = self.tr_sw_end.value()
            # 验证参数有效性
            total_t = len(raw) / self.fs if self.fs > 0 else 1.0
            if t1 <= t0:
                raise ValueError(f"单窗口截断结束时间({t1})必须大于起始时间({t0})")
            if t0 < 0 or t1 > total_t:
                raise ValueError(f"单窗口截断参数超出数据范围 [0, {total_t}] 秒")
            result = truncate_single_window(raw, self.fs, t0, t1)
            desc = f"单窗口截断 [起始:{t0}s, 结束:{t1}s]"
            if tzero:
                desc += " (起始时间归零)"
            desc += f"\n原始长度:{len(raw)} -> 处理后长度:{len(result)}"
        elif ptype == '多窗口截断':
            windows = self._mw_collect_windows()
            result = truncate_multi_window(raw, self.fs, windows)
            desc = f"多窗口截断 {len(windows)}段"
            if tzero:
                desc += " (起始时间归零)"
            desc += f"\n原始长度:{len(raw)} -> 处理后长度:{len(result)}\n时段:{windows}"
        elif ptype == '周期性窗口截断':
            T0 = self.tr_pw_T0.value(); T1 = self.tr_pw_T1.value(); T2 = self.tr_pw_T2.value()
            if T2 > T1:
                raise ValueError(f"周期性窗口截断窗口时长(T2={T2})必须≤周期(T1={T1})")
            result = truncate_periodic_window(raw, self.fs, T0, T1, T2)
            n_win = len(result) // int(round(T2 * self.fs)) if T2 * self.fs > 0 else 0
            desc = f"周期窗口 T0={T0}, T1={T1}, T2={T2} 秒"
            if tzero:
                desc += " (起始时间归零)"
            desc += f"\n截取约{n_win}个窗口\n原始长度:{len(raw)} -> 处理后长度:{len(result)}"
        else:
            raise ValueError(f"未知预处理类型: {ptype}")
        return np.asarray(result).flatten(), desc

    def apply_preprocess(self):
        if self.file_data is None:
            QMessageBox.warning(self, "提示", "请先加载数据文件")
            return
        self.fs = self.fs_spin.value()
        ptype = self.type_combo.currentText()
        try:
            # 多通道模式：对channel_map中所有通道执行同一预处理
            if self.channel_map:
                self.proc_channel_map = {}
                first_desc = ''
                for ch_name, ch_arr in self.channel_map.items():
                    res, d = self._process_one_channel(ch_arr, ptype)
                    self.proc_channel_map[ch_name] = res
                    if not first_desc:
                        first_desc = d
                # processed_data 取当前选中通道的结果用于预览
                sel_ch = self.channel_sel.get_selected_channel()
                sel_name = f"CH{sel_ch+1:02d}" if sel_ch < len(self.channel_map) else list(self.channel_map.keys())[0]
                self.processed_data = self.proc_channel_map.get(sel_name, list(self.proc_channel_map.values())[0])
                n_ch = len(self.proc_channel_map)
                desc = f"[多通道预处理 {n_ch}通道: {', '.join(self.proc_channel_map.keys())}]\n" + first_desc
                self.processed_meta = {
                    'format': 'Preprocessed-' + ptype, 'fs': self.fs,
                    'raw_length': len(list(self.channel_map.values())[0]),
                    'channels': list(self.proc_channel_map.keys()),
                    'channel_map': dict(self.proc_channel_map),
                    'multi_channel': True,
                }
            else:
                raw = self._get_channel_data()
                if raw is None:
                    QMessageBox.warning(self, "提示", "无法获取通道数据")
                    return
                result, desc = self._process_one_channel(raw, ptype)
                self.processed_data = result
                self.processed_meta = {'format': 'Preprocessed-' + ptype, 'fs': self.fs, 'raw_length': len(raw)}
            self.processed_desc = desc.replace('\n', ' | ')
            self.info_label.setText(desc)
            self.push_btn.setEnabled(True)
            self._preview_result()
        except Exception as e:
            QMessageBox.critical(self, "预处理错误", str(e))

    def _preview_result(self):
        if self.processed_data is None:
            return
        # 在子Tab2的可视化画布上预览当前选中通道的预处理结果
        self.channel_viz_canvas.clear()
        try:
            sel_ch = self.channel_sel.get_selected_channel()
            sel_name = f"CH{sel_ch+1:02d}" if sel_ch < len(self.channel_map) else "预处理结果"
            arr = self.proc_channel_map.get(sel_name, self.processed_data) if self.proc_channel_map else self.processed_data
            plot_line(self.channel_viz_canvas, None, {sel_name: arr},
                     title=f'预处理结果预览 - {sel_name}', fs=self.fs)
        except Exception as e:
            QMessageBox.warning(self, "预览错误", f"绘图失败: {str(e)}")
        # 同时刷新通道数据表格
        self._refresh_channel_table()

    # ---------- 子Tab1：通道数据表格 ----------
    def _refresh_channel_table(self):
        """表格化显示分割赋值好的各通道数据（同一文件内）"""
        src_map = self.proc_channel_map if self.proc_channel_map else self.channel_map
        if not src_map:
            self.channel_table.setRowCount(0)
            self.channel_table.setColumnCount(0)
            return
        ch_names = list(src_map.keys())
        n_points = self.table_n_spin.value()
        # 列：采样点索引 + 各通道
        self.channel_table.setColumnCount(1 + len(ch_names))
        headers = ["采样点"] + ch_names
        self.channel_table.setHorizontalHeaderLabels(headers)
        # 行数：取所有通道最小长度的前n_points
        min_len = min(len(src_map[c]) for c in ch_names)
        show_n = min(n_points, min_len)
        self.channel_table.setRowCount(show_n)
        for i in range(show_n):
            self.channel_table.setItem(i, 0, QTableWidgetItem(str(i)))
            for j, cn in enumerate(ch_names):
                val = float(src_map[cn][i])
                self.channel_table.setItem(i, j + 1, QTableWidgetItem(f"{val:.6g}"))
        self.channel_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    # ---------- 子Tab2：通道可视化 ----------
    def _plot_selected_channel(self):
        """可视化显示用户指定的通道数据，支持多通道和时间门控截断"""
        ch_names = self._get_viz_channels()
        if not ch_names:
            QMessageBox.warning(self, "提示", "请先选择通道")
            return
        src = self.viz_src_combo.currentData()
        src_map = self.proc_channel_map if src == 'proc' else self.channel_map
        # 根据门控模式生成门控区域
        self._generate_gate_regions()
        self.channel_viz_canvas.clear()
        fig = self.channel_viz_canvas.figure
        ax = fig.add_subplot(111)
        fs = self.fs if self.fs > 0 else 1.0
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4', '#795548', '#607D8B']
        for i, ch_name in enumerate(ch_names):
            arr = src_map.get(ch_name)
            if arr is None:
                continue
            arr = np.asarray(arr)
            if arr.ndim > 1:
                arr = arr.flatten()
            t = np.arange(len(arr)) / fs
            color = colors[i % len(colors)]
            ax.plot(t, arr, color=color, linewidth=0.8, label=ch_name)
        ax.set_xlabel('时间 [秒]')
        ax.set_ylabel('幅值')
        src_label = '预处理后' if src == 'proc' else '原始'
        ax.set_title(f'通道数据 - {", ".join(ch_names)} ({src_label})')
        # 绘制门控区域（使用第一个通道的数据范围）
        if self.gate_regions and ch_names:
            first_ch = ch_names[0]
            arr0 = np.asarray(src_map.get(first_ch, []))
            if arr0.ndim > 1:
                arr0 = arr0.flatten()
            t0 = np.arange(len(arr0)) / fs
            from matplotlib.patches import Rectangle
            for gi, (gs, ge) in enumerate(self.gate_regions):
                ax.axvspan(gs, ge, alpha=0.25, color='#FF9800', label=f'门{gi+1}' if gi < 8 else None)
                ax.axvline(gs, color='#FF5722', linestyle='--', linewidth=0.8)
                ax.axvline(ge, color='#FF5722', linestyle='--', linewidth=0.8)
            # 截断数据高亮（仅对第一个通道）
            mask = np.zeros(len(arr0), dtype=bool)
            for gs, ge in self.gate_regions:
                mask |= (t0 >= gs) & (t0 <= ge)
            if mask.any():
                ax.plot(t0[mask], arr0[mask], '.', color='#F44336', markersize=2, label='门内数据')
            # 如果用户选择截断后起始时间归零，在图上标注
            if self.tzero_check.isChecked():
                ax.axvline(0, color='#4CAF50', linestyle=':', linewidth=2.0, label='截断后零点(T=0)')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        self.channel_viz_canvas.draw()
    
    def _on_truncate_type_changed(self, idx):
        """截断类型切换：显示/隐藏对应的参数面板"""
        truncate_type = self.truncate_type_combo.currentText()
        self.sw_panel.setVisible(truncate_type == "单窗口截断")
        self.mw_panel.setVisible(truncate_type == "多窗口截断")
        self.pw_panel.setVisible(truncate_type == "周期性窗口截断")
        self.truncate_preview_btn.setEnabled(truncate_type != "不使用截断")
    
    def _preview_truncate(self):
        """预览截断效果：在图上显示截断区域（仅可视化，不执行预处理）"""
        truncate_type = self.truncate_type_combo.currentText()
        if truncate_type == "不使用截断":
            self._clear_truncate()
            return
        
        # 获取当前选中的通道数据
        ch_names = self._get_viz_channels()
        if not ch_names:
            QMessageBox.warning(self, "提示", "请先选择通道")
            return
        src = self.viz_src_combo.currentData()
        src_map = self.proc_channel_map if src == 'proc' else self.channel_map
        arr = src_map.get(ch_names[0])
        if arr is None:
            QMessageBox.warning(self, "提示", "所选通道无数据")
            return
        arr = np.asarray(arr)
        if arr.ndim > 1:
            arr = arr.flatten()
        
        fs = self.fs if self.fs > 0 else 1.0
        total_t = len(arr) / fs
        
        # 根据截断类型生成门控区域
        self.gate_regions = []
        if truncate_type == "单窗口截断":
            gs = self.tr_sw_start.value()
            ge = self.tr_sw_end.value()
            if ge > gs and gs >= 0 and ge <= total_t:
                self.gate_regions = [(gs, ge)]
            else:
                QMessageBox.warning(self, "参数错误", f"单窗口截断参数无效：\n起始时间={gs}，结束时间={ge}\n有效范围: [0, {total_t}]")
                return
        elif truncate_type == "多窗口截断":
            try:
                windows = self._mw_collect_windows()
                for gs, ge in windows:
                    if gs >= 0 and ge <= total_t and ge > gs:
                        self.gate_regions.append((gs, ge))
                    else:
                        QMessageBox.warning(self, "参数错误", f"时段 [{gs}, {ge}] 超出数据范围 [0, {total_t}] 或结束时间<=起始时间")
                        return
            except ValueError as e:
                QMessageBox.warning(self, "参数错误", str(e))
                return
        elif truncate_type == "周期性窗口截断":
            T0 = self.tr_pw_T0.value()
            T1 = self.tr_pw_T1.value()
            T2 = self.tr_pw_T2.value()
            if T2 > T1:
                QMessageBox.warning(self, "参数错误", f"周期性窗口截断参数错误：\n窗口时长 T2={T2} 必须 ≤ 周期 T1={T1}")
                return
            if T0 < 0 or T0 >= total_t:
                QMessageBox.warning(self, "参数错误", f"起始时间 T0={T0} 超出有效范围 [0, {total_t}]")
                return
            t_start = T0
            while t_start < total_t:
                t_end = min(t_start + T2, total_t)
                self.gate_regions.append((t_start, t_end))
                t_start += T1
        
        # 在图上绘制截断区域
        self._plot_selected_channel()
        QMessageBox.information(self, "预览完成", 
            f"截断预览已显示。\n共定义 {len(self.gate_regions)} 个截断窗口。\n\n"
            f"注意：此为预览效果。\n"
            f"要执行实际预处理，请在左侧「预处理类型」中选择「{truncate_type}」，\n"
            f"然后点击「执行预处理」按钮。")
    
    def _clear_truncate(self):
        """清除截断定义"""
        self.truncate_type_combo.setCurrentIndex(0)
        self.gate_regions = []
        self._plot_selected_channel()
    
    def _generate_gate_regions(self):
        """根据截断类型生成门控区域列表（用于可视化）"""
        truncate_type = self.truncate_type_combo.currentText()
        if truncate_type == "不使用截断":
            self.gate_regions = []
            return
        
        fs = self.fs if self.fs > 0 else 1.0
        arr_len = 0
        # 获取当前选中的通道数据长度
        ch_names = self._get_viz_channels()
        if ch_names:
            src = self.viz_src_combo.currentData()
            src_map = self.proc_channel_map if src == 'proc' else self.channel_map
            arr = src_map.get(ch_names[0])
            if arr is not None:
                arr_len = len(arr)
        total_t = arr_len / fs if arr_len > 0 else 1.0
        
        if truncate_type == "单窗口截断":
            gs = self.tr_sw_start.value()
            ge = self.tr_sw_end.value()
            if ge > gs:
                self.gate_regions = [(gs, ge)]
            else:
                self.gate_regions = []
        elif truncate_type == "多窗口截断":
            try:
                windows = self._mw_collect_windows()
                self.gate_regions = [(s, min(e, total_t)) for s, e in windows if s < total_t and e > s]
            except:
                self.gate_regions = []
        elif truncate_type == "周期性窗口截断":
            T0 = self.tr_pw_T0.value()
            T1 = self.tr_pw_T1.value()
            T2 = self.tr_pw_T2.value()
            if T1 > 0:
                regions = []
                t_start = T0
                while t_start < total_t:
                    regions.append((t_start, min(t_start + T2, total_t)))
                    t_start += T1
                self.gate_regions = regions
            else:
                self.gate_regions = []
    
    def _redraw_gate_lines_only(self):
        """轻量重绘门控竖线（不重新计算数据）"""
        try:
            fig = self.channel_viz_canvas.figure
            ax = fig.axes[0] if fig.axes else None
            if ax is None:
                return
            # 移除旧的门控竖线和区域（按标签识别）
            for line in list(ax.lines):
                if getattr(line, '_is_gate_line', False):
                    line.remove()
            for patch in list(ax.patches):
                if getattr(patch, '_is_gate_patch', False):
                    patch.remove()
            for collection in list(ax.collections):
                if getattr(collection, '_is_gate_coll', False):
                    collection.remove()
            for gs, ge in self.gate_regions:
                span = ax.axvspan(gs, ge, alpha=0.25, color='#FF9800')
                span._is_gate_patch = True
                l1 = ax.axvline(gs, color='#FF5722', linestyle='--', linewidth=0.8)
                l1._is_gate_line = True
                l2 = ax.axvline(ge, color='#FF5722', linestyle='--', linewidth=0.8)
                l2._is_gate_line = True
            self.channel_viz_canvas.draw_idle()
        except Exception:
            pass
    
    def _clear_gates(self):
        """清除所有门控区域"""
        self.gate_regions = []
        self._plot_selected_channel()
    
    def _on_gate_mouse_press(self, event):
        """鼠标按下：判断是否点击在门控边界附近，开始拖动（仅单窗口截断模式有效）"""
        if event.inaxes is None or not self.gate_regions:
            return
        if event.button != 1:
            return
        x = event.xdata
        if x is None:
            return
        threshold = (self.tr_sw_end.maximum() - self.tr_sw_start.minimum()) * 0.005
        for i, (gs, ge) in enumerate(self.gate_regions):
            if abs(x - gs) < threshold:
                self._gate_dragging = True
                self._gate_drag_side = ('start', i)
                return
            if abs(x - ge) < threshold:
                self._gate_dragging = True
                self._gate_drag_side = ('end', i)
                return
    
    def _on_gate_mouse_motion(self, event):
        """鼠标移动：若正在拖动门控边界，实时更新（仅单窗口截断模式有效）"""
        if not self._gate_dragging or self._gate_drag_side is None:
            return
        if event.inaxes is None or event.xdata is None:
            return
        side, idx = self._gate_drag_side
        gs, ge = self.gate_regions[idx]
        new_x = max(0.0, event.xdata)
        if side == 'start':
            gs = min(new_x, ge - 1e-9)
            self.tr_sw_start.blockSignals(True)
            self.tr_sw_start.setValue(gs)
            self.tr_sw_start.blockSignals(False)
        else:
            ge = max(new_x, gs + 1e-9)
            self.tr_sw_end.blockSignals(True)
            self.tr_sw_end.setValue(ge)
            self.tr_sw_end.blockSignals(False)
        self.gate_regions[idx] = (gs, ge)
        self._redraw_gate_lines_only()
    
    def _on_gate_mouse_release(self, event):
        """鼠标释放：结束拖动"""
        self._gate_dragging = False
        self._gate_drag_side = None

    # ---------- 子Tab3：参数特征与统计指标 ----------
    def _calc_statistics(self):
        """计算数据文件参数特征 + 20种统计指标，支持多通道"""
        ch_names = self._get_stat_channels()
        if not ch_names:
            QMessageBox.warning(self, "提示", "请先选择统计通道")
            return
        src = self.stat_src_combo.currentData()
        src_map = self.proc_channel_map if src == 'proc' else self.channel_map
        
        # 收集所有通道的统计信息
        all_stats = []
        for ch_name in ch_names:
            arr = src_map.get(ch_name)
            if arr is None:
                continue
            arr = np.asarray(arr, dtype=float).flatten()
            n = len(arr)
            fs = self.fs if self.fs > 0 else 1.0
            total_time = n / fs
            
            # 计算该通道的20种统计指标
            stats = self._compute_20_statistics(arr, fs)
            all_stats.append((ch_name, n, fs, total_time, stats))
        
        if not all_stats:
            QMessageBox.warning(self, "提示", "所选通道均无数据")
            return
        
        # 文件参数特征（显示第一个通道的基本信息）
        first_ch, first_n, first_fs, first_total_time, _ = all_stats[0]
        self.file_feat_label.setText(
            f"文件参数特征（显示前{len(all_stats)}个通道的首个统计）：\n"
            f"  通道: {first_ch} | 数据源: {'预处理后' if src == 'proc' else '原始'}\n"
            f"  采样点数: {first_n} | 采样率: {first_fs} Hz | 总时长: {first_total_time:.6f} 秒 ({first_total_time:.3f} s)\n"
            f"  采样间隔: {1.0/first_fs*1e6:.3f} μs\n"
            f"  选中通道: {', '.join(ch_names)}"
        )

        # 显示所有通道的统计指标（按通道分组）
        self.stat_table.setRowCount(0)
        self.stat_table.setColumnCount(3)
        self.stat_table.setHorizontalHeaderLabels(["统计指标", "数值", "说明"])
        
        for ch_name, n, fs, total_time, stats in all_stats:
            # 添加通道分隔行
            row = self.stat_table.rowCount()
            self.stat_table.insertRow(row)
            ch_item = QTableWidgetItem(f"===== {ch_name} =====")
            ch_item.setBackground(QColor('#E3F2FD'))
            font = ch_item.font()
            font.setBold(True)
            ch_item.setFont(font)
            self.stat_table.setItem(row, 0, ch_item)
            self.stat_table.setItem(row, 1, QTableWidgetItem(f"n={n}, t={total_time:.3f}s"))
            self.stat_table.setItem(row, 2, QTableWidgetItem(""))
            
            for name, val, desc in stats:
                row = self.stat_table.rowCount()
                self.stat_table.insertRow(row)
                self.stat_table.setItem(row, 0, QTableWidgetItem(name))
                self.stat_table.setItem(row, 1, QTableWidgetItem(f"{val:.6g}" if isinstance(val, (int, float)) else str(val)))
                self.stat_table.setItem(row, 2, QTableWidgetItem(desc))

    def _compute_20_statistics(self, arr, fs):
        """计算20种统计指标，返回[(名称, 数值, 说明), ...]"""
        arr = np.asarray(arr, dtype=float).flatten()
        n = len(arr)
        mean = float(np.mean(arr))
        median = float(np.median(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        var = float(np.var(arr, ddof=1)) if n > 1 else 0.0
        mx = float(np.max(arr))
        mn = float(np.min(arr))
        rng = mx - mn
        ptp = rng
        rms = float(np.sqrt(np.mean(arr**2)))
        skew_val = float(PreprocessTab._skew(arr))
        kurt_val = float(PreprocessTab._kurtosis(arr))
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        cv = std / mean if mean != 0 else 0.0
        energy = float(np.sum(arr**2))
        # 峰值因子：峰值/RMS
        crest = mx / rms if rms != 0 else 0.0
        # 裕度因子：峰值/(方根幅值均值)^0.5
        sq_abs_mean = np.mean(np.sqrt(np.abs(arr)))**2
        margin = mx / np.sqrt(sq_abs_mean) if sq_abs_mean > 0 else 0.0
        # 峭度因子（无因次峭度）
        # 形状因子：RMS/绝对均值
        abs_mean = float(np.mean(np.abs(arr)))
        shape = rms / abs_mean if abs_mean != 0 else 0.0
        # 频域：主频
        try:
            spec = np.abs(np.fft.rfft(arr))
            freqs = np.fft.rfftfreq(n, d=1.0/fs)
            dom_freq = float(freqs[np.argmax(spec[1:]) + 1]) if len(spec) > 1 else 0.0
        except Exception:
            dom_freq = 0.0
        # 过零率
        zero_cross = float(np.sum(np.diff(np.sign(arr)) != 0) / n * fs)
        return [
            ("1. 均值 (Mean)", mean, "算术平均，反映信号直流分量/中心位置"),
            ("2. 中位数 (Median)", median, "排序中间值，对异常值不敏感，反映典型水平"),
            ("3. 标准差 (Std)", std, "离散程度，越大波动越剧烈"),
            ("4. 方差 (Variance)", var, "离散程度平方量纲，反映总体波动"),
            ("5. 最大值 (Max)", mx, "信号峰值，反映正向极值"),
            ("6. 最小值 (Min)", mn, "信号谷值，反映负向极值"),
            ("7. 极差 (Range)", rng, "Max-Min，反映信号幅值跨度"),
            ("8. 峰峰值 (Peak-to-Peak)", ptp, "峰谷差，评估动态范围"),
            ("9. 均方根 (RMS)", rms, "有效值，反映信号能量/强度"),
            ("10. 偏度 (Skewness)", skew_val, "分布不对称性，>0右偏<0左偏，0对称"),
            ("11. 峭度 (Kurtosis)", kurt_val, "分布尖峭/尾部厚度，3为正态，>3尖峰<3平缓"),
            ("12. 第1四分位数 (Q1)", q1, "25%分位点，反映下四分位水平"),
            ("13. 第3四分位数 (Q3)", q3, "75%分位点，反映上四分位水平"),
            ("14. 四分位距 (IQR)", iqr, "Q3-Q1，稳健离散度，抗异常值"),
            ("15. 变异系数 (CV)", cv, "标准差/均值，无量纲离散度，便于跨通道比较"),
            ("16. 总能量 (Energy)", energy, "平方和，反映信号总能量"),
            ("17. 峰值因子 (Crest Factor)", crest, "峰值/RMS，越大冲击性越强"),
            ("18. 裕度因子 (Margin Factor)", margin, "峰值/方根幅值，对冲击敏感"),
            ("19. 形状因子 (Shape Factor)", shape, "RMS/绝对均值，反映波形形状"),
            ("20. 主频 (Dominant Freq)", dom_freq, "频谱最大幅值对应频率，反映主导周期成分"),
        ]

    @staticmethod
    def _skew(arr):
        arr = np.asarray(arr, dtype=float).flatten()
        n = len(arr)
        if n < 3:
            return 0.0
        m = np.mean(arr); s = np.std(arr, ddof=1)
        if s == 0:
            return 0.0
        return float(np.mean(((arr - m) / s) ** 3))

    @staticmethod
    def _kurtosis(arr):
        arr = np.asarray(arr, dtype=float).flatten()
        n = len(arr)
        if n < 4:
            return 0.0
        m = np.mean(arr); s = np.std(arr, ddof=1)
        if s == 0:
            return 0.0
        return float(np.mean(((arr - m) / s) ** 4))

    # ---------- 可视化窗口分离为独立窗口 ----------
    def _detach_canvas(self, source_canvas, title):
        """将指定画布的内容分离到独立窗口显示（支持缩放和全屏）"""
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar
            from PyQt5.QtWidgets import QSizePolicy
            from PyQt5.QtCore import Qt
            
            dlg = QDialog(self)
            dlg.setWindowTitle(f"📊 独立窗口 - {title}")
            dlg.resize(1000, 700)
            dlg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
            main_layout = QVBoxLayout(dlg)
            main_layout.setContentsMargins(0, 0, 0, 0)
            
            # 创建画布（必须在引用它之前创建）
            new_canvas = create_canvas(dlg)
            
            # 创建工具栏
            toolbar = QToolBar()
            toolbar.setIconSize(QSizePolicy.Expanding, QSizePolicy.Minimum)
            
            # 重置视图按钮
            reset_btn = QPushButton("🔄 重置视图")
            reset_btn.clicked.connect(lambda: self._reset_detached_view(new_canvas))
            toolbar.addWidget(reset_btn)
            
            # 全屏切换按钮
            fullscreen_btn = QPushButton("⛶ 全屏")
            fullscreen_btn.setCheckable(True)
            fullscreen_btn.clicked.connect(lambda checked: self._toggle_fullscreen(dlg, fullscreen_btn, checked))
            toolbar.addWidget(fullscreen_btn)
            
            toolbar.addSeparator()
            
            # 添加默认的导航工具栏
            nav_toolbar = NavigationToolbar(new_canvas, dlg)
            toolbar.addWidget(nav_toolbar)
            
            main_layout.addWidget(toolbar)
            main_layout.addWidget(new_canvas, stretch=1)
            
            # 直接复制原图的figure到新画布（保持交互能力）
            new_canvas.figure = source_canvas.figure
            new_canvas.figure.canvas = new_canvas  # 更新canvas引用
            new_canvas.draw()
            
            # 添加工具栏按钮提示
            hint_label = QLabel("💡 提示：使用鼠标滚轮缩放，拖动平移，右键菜单还原视图")
            hint_label.setStyleSheet("color: #666; font-size: 9pt; padding: 2px; background-color: #f5f5f5;")
            main_layout.addWidget(hint_label)
            
            dlg.exec_()
        except Exception as e:
            import traceback
            QMessageBox.warning(self, "分离窗口错误", f"无法分离画布到独立窗口:\n{str(e)}\n\n{traceback.format_exc()}")
    
    def _reset_detached_view(self, canvas):
        """重置分离窗口的视图"""
        try:
            axes = canvas.figure.axes
            for ax in axes:
                ax.relim()
                ax.autoscale_view()
            canvas.draw()
        except Exception:
            pass
    
    def _toggle_fullscreen(self, dlg, btn, checked):
        """切换全屏模式"""
        if checked:
            dlg.showFullScreen()
            btn.setText("⛶ 退出全屏")
        else:
            dlg.showNormal()
            btn.setText("⛶ 全屏")

    # ---------- 推送到各业务Tab ----------
    def register_target_tab(self, tab):
        if tab not in self.target_tabs:
            self.target_tabs.append(tab)

    def refresh_push_states(self):
        """从全局注册表刷新A/B实验状态下拉菜单"""
        from experiment_state import STATE_REGISTRY
        names = STATE_REGISTRY.get_state_names()
        for combo in (self.push_state_a_combo, self.push_state_b_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("（未选择）", "")
            for n in names:
                combo.addItem(n, n)
            combo.blockSignals(False)
            combo.setEnabled(len(names) > 0)
        # 同时刷新目标Tab的实验状态下拉
        for tab in self.target_tabs:
            if hasattr(tab, 'refresh_experiment_states'):
                tab.refresh_experiment_states()

    def _on_push_target_changed(self, index):
        target_key = self.push_target_combo.currentData()
        is_matrix = (target_key == 'tab3')
        is_all = (target_key == 'all')
        prev_state = self.push_state_combo.currentData()
        self.push_state_combo.blockSignals(True)
        self.push_state_combo.clear()
        if is_matrix:
            self.push_state_combo.addItem("数据文件", "SINGLE")
        elif is_all:
            self.push_state_combo.addItem("实验状态1", "A")
            self.push_state_combo.addItem("实验状态2", "B")
            self.push_state_combo.addItem("实验状态1 和 实验状态2", "AB")
        else:
            self.push_state_combo.addItem("实验状态1", "A")
            self.push_state_combo.addItem("实验状态2", "B")
            self.push_state_combo.addItem("实验状态1 和 实验状态2", "AB")
        idx = self.push_state_combo.findData(prev_state)
        if idx >= 0:
            self.push_state_combo.setCurrentIndex(idx)
        self.push_state_combo.blockSignals(False)

    def _resolve_target_tabs(self):
        target_key = self.push_target_combo.currentData()
        tab_map = {}
        for tab in self.target_tabs:
            cls_name = type(tab).__name__
            if cls_name == 'TimeDomainTab':
                tab_map['tab1'] = tab
            elif cls_name == 'FrequencyDomainTab':
                tab_map['tab2'] = tab
            elif cls_name == 'MatrixTransformTab':
                tab_map['tab3'] = tab
        if target_key == 'all':
            return list(tab_map.values())
        elif target_key in tab_map:
            return [tab_map[target_key]]
        return []

    def push_to_tabs(self):
        if self.processed_data is None:
            QMessageBox.warning(self, "提示", "请先执行预处理")
            return
        target_tabs = self._resolve_target_tabs()
        if not target_tabs:
            QMessageBox.warning(self, "提示", "未找到目标页面")
            return
        # 获取推送通道选择
        push_channels = self._get_push_channels()
        if not push_channels:
            QMessageBox.warning(self, "提示", "请选择至少一个推送通道\n（在'推送通道'下拉中选择全部/单通道/指定通道）")
            return
        state_key = self.push_state_combo.currentData()
        # 推送A和B两种状态时，弹窗确认通道在两次实验状态中必须完全一致（一一对应）
        if state_key == 'AB':
            ret = QMessageBox.question(
                self, "通道一致性确认",
                f"您正在同时推送【实验状态A】和【实验状态B】两种状态的数据。\n\n"
                f"推送通道: {', '.join(push_channels)}\n\n"
                f"重要提示：A、B两次实验状态的通道设置必须完全一致（一一对应），\n"
                f"否则通道对比将无意义。\n\n"
                f"请确认两次实验状态下的探测器物理通道连接与编号完全相同？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if ret == QMessageBox.No:
                return
        target_name = self.push_target_combo.currentText()
        state_name = self.push_state_combo.currentText()
        pushed = 0
        details = []
        for tab in target_tabs:
            try:
                info = self._push_to_tab(tab, state_key, push_channels)
                pushed += 1
                details.append(info)
            except Exception as e:
                QMessageBox.warning(self, "推送错误", f"推送失败: {str(e)}")
        msg = f"已推送到 {pushed} 个页面\n目标: {target_name}\n状态: {state_name}\n推送通道: {', '.join(push_channels)}"
        if details:
            msg += "\n" + "\n".join(details)
        QMessageBox.information(self, "推送成功", msg)

    def _build_push_channel_data(self, push_channels):
        """根据推送通道列表构建2D数据数组和通道映射，返回(data_2d, channel_map)"""
        src_map = self.proc_channel_map if self.proc_channel_map else self.channel_map
        cols = []
        ch_map = {}
        for ch_name in push_channels:
            arr = src_map.get(ch_name)
            if arr is None:
                raise ValueError(f"通道 {ch_name} 不存在，请先分割赋值通道")
            cols.append(np.asarray(arr).flatten())
            ch_map[ch_name] = cols[-1]
        data_2d = np.column_stack(cols) if len(cols) > 1 else cols[0].reshape(-1, 1)
        return data_2d, ch_map

    def _push_to_tab(self, tab, state_key, push_channels):
        meta = dict(self.processed_meta) if self.processed_meta else {}
        desc = self.processed_desc or '预处理结果'
        # 构建通道感知数据
        data_2d, ch_map = self._build_push_channel_data(push_channels)
        display_text = f'<预处理结果 {desc}>'
        meta['filepath'] = display_text
        meta['fs'] = self.fs
        meta['channels'] = list(push_channels)
        meta['channel_map'] = ch_map
        meta['multi_channel'] = len(push_channels) > 1
        meta['n_channels'] = len(push_channels)
        # 记录预处理信息，供报告BLOCK使用
        meta['preprocess_info'] = desc
        info_parts = []
        cls_name = type(tab).__name__

        # 获取A/B对应的具体实验状态名
        state_a_name = self.push_state_a_combo.currentData() if hasattr(self, 'push_state_a_combo') else ""
        state_b_name = self.push_state_b_combo.currentData() if hasattr(self, 'push_state_b_combo') else ""

        if cls_name in ('TimeDomainTab', 'FrequencyDomainTab'):
            if state_key in ('A', 'AB'):
                tab.file_a_selector.data = data_2d
                tab.file_a_selector.meta = meta
                tab.file_a_selector.path_edit.setText(display_text)
                if hasattr(tab, 'on_file_a_loaded'):
                    tab.on_file_a_loaded(display_text, data_2d, meta)
                # 关联实验状态
                if state_a_name and hasattr(tab, 'channel_a') and hasattr(tab.channel_a, 'set_state'):
                    tab.channel_a.set_state(state_a_name)
                # 保存预处理信息到目标Tab
                if hasattr(tab, '_preprocess_info'):
                    tab._preprocess_info = f"预处理方法: {desc}"
                info_parts.append("实验状态1(A)" + (f"→{state_a_name}" if state_a_name else ""))
            if state_key in ('B', 'AB'):
                tab.file_b_selector.data = data_2d
                tab.file_b_selector.meta = meta
                tab.file_b_selector.path_edit.setText(display_text)
                if hasattr(tab, 'on_file_b_loaded'):
                    tab.on_file_b_loaded(display_text, data_2d, meta)
                if state_b_name and hasattr(tab, 'channel_b') and hasattr(tab.channel_b, 'set_state'):
                    tab.channel_b.set_state(state_b_name)
                if hasattr(tab, '_preprocess_info'):
                    tab._preprocess_info = f"预处理方法: {desc}"
                info_parts.append("实验状态2(B)" + (f"→{state_b_name}" if state_b_name else ""))

        elif cls_name == 'MatrixTransformTab':
            tab.file_selector.data = data_2d
            tab.file_selector.meta = meta
            tab.file_selector.path_edit.setText(display_text)
            if hasattr(tab, 'on_file_loaded'):
                tab.on_file_loaded(display_text, data_2d, meta)
            if hasattr(tab, '_preprocess_info'):
                tab._preprocess_info = f"预处理方法: {desc}"
            info_parts.append("数据文件")

        tab_label = {'TimeDomainTab': '时域', 'FrequencyDomainTab': '频域', 'MatrixTransformTab': '矩阵'}.get(cls_name, cls_name)
        return f"  → {tab_label}页: {', '.join(info_parts)} (通道: {', '.join(push_channels)})"


# ============= Tab5: 实验状态定义与记录 =============

class ExperimentStateTab(QWidget):
    """实验状态定义Tab：TC12/TC34 图示 + 参数录入 + 生成记录"""

    # TG2 选项
    TG2_OPTIONS = [
        '自制直流高压模块配芯片', '自制直流高压模块配针尖',
        '2025黑正高压配针尖', '2025白正高压配针尖',
        '东文负高压配针尖', 'TREK配针尖', 'SPELLMAN配针尖'
    ]
    # TG3 选项
    TG3_OPTIONS = [
        '不锈钢KQS金属筒', '风洞S腔', '石英腔', '亚克力腔', '开放空间'
    ]
    # TG4 选项
    TG4_OPTIONS = [
        '设定无干扰', '设定有S腔内0930放电装置干扰',
        '设定有操作人员处于目标1m以内干扰', '设定有常压放电源干扰'
    ]
    # TG5 选项
    TG5_OPTIONS = [
        '单人近经过', '多人近经过', '2倍r之外有人长时间活动',
        '5倍r之外有人长时间活动', '10倍r之外有人长时间活动'
    ]
    # CH1 选项：探测系统通道数
    CH1_OPTIONS = ['12', '16']
    # CH2 选项：探测系统采样频率
    CH2_OPTIONS = ['200K', '300K', '400K']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        # 顶部：类型选择 + 生成按钮
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("实验状态类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("TC12", "TC12")
        self.type_combo.addItem("TC34", "TC34")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        top_row.addWidget(self.type_combo, stretch=1)

        self.gen_btn = QPushButton("生成和记录实验状态")
        self.gen_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.gen_btn.clicked.connect(self.generate_state)
        top_row.addWidget(self.gen_btn)
        main_layout.addLayout(top_row)

        # 主体：左右分栏（TC12 / TC34）
        splitter = QSplitter(Qt.Horizontal)

        # TC12 区域
        tc12_widget = QWidget()
        tc12_layout = QVBoxLayout(tc12_widget)
        tc12_layout.addWidget(self._make_title_label("TC12"))
        # 图示
        tc12_diagram_group = QGroupBox("TC12 示意图")
        tc12_diagram_layout = QVBoxLayout(tc12_diagram_group)
        from visualization import create_canvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavTb
        self.tc12_canvas = create_canvas(self)
        self.tc12_toolbar = NavTb(self.tc12_canvas, self)
        tc12_diagram_layout.addWidget(self.tc12_toolbar)
        tc12_diagram_layout.addWidget(self.tc12_canvas, stretch=1)
        tc12_layout.addWidget(tc12_diagram_group)
        # 参数录入
        tc12_param_group = QGroupBox("TC12 参数录入")
        tc12_param_layout = QVBoxLayout(tc12_param_group)
        self.tc12_param_widgets = self._build_param_panel(tc12_param_layout, include_gamma=False)
        tc12_layout.addWidget(tc12_param_group, stretch=1)
        splitter.addWidget(tc12_widget)

        # TC34 区域
        tc34_widget = QWidget()
        tc34_layout = QVBoxLayout(tc34_widget)
        tc34_layout.addWidget(self._make_title_label("TC34"))
        tc34_diagram_group = QGroupBox("TC34 示意图")
        tc34_diagram_layout = QVBoxLayout(tc34_diagram_group)
        self.tc34_canvas = create_canvas(self)
        self.tc34_toolbar = NavTb(self.tc34_canvas, self)
        tc34_diagram_layout.addWidget(self.tc34_toolbar)
        tc34_diagram_layout.addWidget(self.tc34_canvas, stretch=1)
        tc34_layout.addWidget(tc34_diagram_group)
        tc34_param_group = QGroupBox("TC34 参数录入")
        tc34_param_layout = QVBoxLayout(tc34_param_group)
        self.tc34_param_widgets = self._build_param_panel(tc34_param_layout, include_gamma=True)
        tc34_layout.addWidget(tc34_param_group, stretch=1)
        splitter.addWidget(tc34_widget)

        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter, stretch=1)

        # 底部：已生成状态列表（表格形式）
        list_group = QGroupBox("已生成实验状态记录")
        list_layout = QVBoxLayout(list_group)
        
        # 操作栏
        ops_row = QHBoxLayout()
        
        # 下拉菜单选择状态
        ops_row.addWidget(QLabel("选择状态:"))
        self.state_select_combo = QComboBox()
        self.state_select_combo.addItem("请选择...", "")
        self.state_select_combo.currentIndexChanged.connect(self.on_state_selected)
        ops_row.addWidget(self.state_select_combo, stretch=1)
        
        # 操作按钮
        self.load_btn = QPushButton("加载参数")
        self.load_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px;")
        self.load_btn.clicked.connect(self.load_selected_state)
        self.load_btn.setEnabled(False)
        ops_row.addWidget(self.load_btn)
        
        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px;")
        self.delete_btn.clicked.connect(self.delete_selected_state)
        self.delete_btn.setEnabled(False)
        ops_row.addWidget(self.delete_btn)
        
        self.clear_all_btn = QPushButton("清空全部")
        self.clear_all_btn.setStyleSheet("background-color: #9E9E9E; color: white; padding: 5px;")
        self.clear_all_btn.clicked.connect(self.clear_all_states)
        ops_row.addWidget(self.clear_all_btn)
        
        self.push_state_btn = QPushButton("推送状态到Tab6/7/8")
        self.push_state_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 5px;")
        self.push_state_btn.clicked.connect(self.push_selected_state)
        self.push_state_btn.setEnabled(False)
        ops_row.addWidget(self.push_state_btn)
        
        list_layout.addLayout(ops_row)
        
        # 表格
        self.state_table = QTableWidget()
        self.state_table.setColumnCount(5)
        self.state_table.setHorizontalHeaderLabels(['ID', '名称', '报告BLOCK序号', '类型', '参数预览'])
        self.state_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.state_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.state_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.state_table.cellClicked.connect(self.on_table_clicked)
        list_layout.addWidget(self.state_table)
        
        main_layout.addWidget(list_group)
        
        # 初始绘制图示
        self._draw_diagrams()

    def _make_title_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2196F3; padding: 4px;")
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _build_param_panel(self, layout, include_gamma=False):
        """构建参数录入面板，返回控件字典"""
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setLabelAlignment(Qt.AlignRight)
        widgets = {}

        # α或K
        widgets['alpha'] = QLineEdit()
        widgets['alpha'].setPlaceholderText("度")
        form.addRow("α或K (主布控板夹角, 度):", widgets['alpha'])

        if include_gamma:
            widgets['gamma'] = QLineEdit()
            widgets['gamma'].setPlaceholderText("度")
            form.addRow("γ (高精度曲线坐标布控板夹角, 度):", widgets['gamma'])

        # β或L
        widgets['beta'] = QLineEdit()
        widgets['beta'].setPlaceholderText("度")
        form.addRow("β或L (探测器参考原点与导引线夹角, 度):", widgets['beta'])

        # r
        widgets['r'] = QLineEdit()
        widgets['r'].setPlaceholderText("m")
        form.addRow("r (探测器参考原点与目标等效中心距离, m):", widgets['r'])

        # D
        widgets['D'] = QLineEdit()
        widgets['D'].setPlaceholderText("度")
        form.addRow("D (目标等效轮廓半径, 度):", widgets['D'])

        # 激励策略 1~4 阶
        for order in range(1, 5):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            params_edit = QLineEdit()
            params_edit.setPlaceholderText(f"例如: V1 T1 T0 (一阶) / V1 T1 V2 T2 T0 (二阶) ...")
            unit_combo = QComboBox()
            unit_combo.addItems(['ms', 's'])
            row_layout.addWidget(params_edit, stretch=1)
            row_layout.addWidget(QLabel("电压单位: V, 时间单位:"))
            row_layout.addWidget(unit_combo)
            label = f"{['一阶','二阶','三阶','四阶'][order-1]}波激励策略:"
            form.addRow(label, row_widget)
            widgets[f'wave{order}_params'] = params_edit
            widgets[f'wave{order}_unit'] = unit_combo

        # TG1
        widgets['TG1'] = QLineEdit()
        widgets['TG1'].setPlaceholderText("气压")
        tg1_unit = QComboBox()
        tg1_unit.addItems(['Pa', '大气压'])
        tg1_row = QWidget()
        tg1_row_layout = QHBoxLayout(tg1_row)
        tg1_row_layout.setContentsMargins(0, 0, 0, 0)
        tg1_row_layout.addWidget(widgets['TG1'])
        tg1_row_layout.addWidget(tg1_unit)
        form.addRow("TG1 (目标工作气压):", tg1_row)
        widgets['TG1_unit'] = tg1_unit

        # TG2, TG3
        tg23_widget = QWidget()
        tg23_layout = QHBoxLayout(tg23_widget)
        tg23_layout.setContentsMargins(0, 0, 0, 0)
        widgets['TG2'] = QComboBox()
        widgets['TG2'].addItems(self.TG2_OPTIONS)
        widgets['TG3'] = QComboBox()
        widgets['TG3'].addItems(self.TG3_OPTIONS)
        tg23_layout.addWidget(QLabel("TG2:"))
        tg23_layout.addWidget(widgets['TG2'], stretch=1)
        tg23_layout.addWidget(QLabel("TG3:"))
        tg23_layout.addWidget(widgets['TG3'], stretch=1)
        form.addRow("TG2,TG3 (电荷发生器类型):", tg23_widget)

        # TG4
        widgets['TG4'] = QComboBox()
        widgets['TG4'].addItems(self.TG4_OPTIONS)
        form.addRow("TG4 (设定的测试环境):", widgets['TG4'])

        # TG5
        widgets['TG5'] = QComboBox()
        widgets['TG5'].addItems(self.TG5_OPTIONS)
        form.addRow("TG5 (记录随机干扰源):", widgets['TG5'])

        # CH1: 探测系统通道数
        widgets['CH1'] = QComboBox()
        widgets['CH1'].addItems(self.CH1_OPTIONS)
        form.addRow("CH1 (探测系统通道数):", widgets['CH1'])

        # CH2: 探测系统采样频率
        widgets['CH2'] = QComboBox()
        widgets['CH2'].addItems(self.CH2_OPTIONS)
        form.addRow("CH2 (探测系统采样频率):", widgets['CH2'])

        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return widgets

    def on_type_changed(self):
        self._draw_diagrams()

    def _draw_diagrams(self):
        import matplotlib as mpl
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        mpl.rcParams['axes.unicode_minus'] = False
        mpl.rcParams['mathtext.fontset'] = 'cm'
        from state_diagram import draw_tc12, draw_tc34
        try:
            draw_tc12(self.tc12_canvas.fig)
            self.tc12_canvas.draw()
        except Exception as e:
            pass
        try:
            draw_tc34(self.tc34_canvas.fig)
            self.tc34_canvas.draw()
        except Exception as e:
            pass

    def _collect_params(self, widgets, state_type):
        """从控件收集参数，返回dict"""
        params = {}
        params['α或K'] = widgets['alpha'].text().strip()
        if 'gamma' in widgets:
            params['γ'] = widgets['gamma'].text().strip()
        params['β或L'] = widgets['beta'].text().strip()
        params['r'] = widgets['r'].text().strip()
        params['D'] = widgets['D'].text().strip()
        for order in range(1, 5):
            p = widgets[f'wave{order}_params'].text().strip()
            if p:
                unit = widgets[f'wave{order}_unit'].currentText()
                params[f'{order}阶波激励策略'] = f"{p} (时间单位:{unit}, 电压单位:V)"
        params['TG1'] = f"{widgets['TG1'].text().strip()} {widgets['TG1_unit'].currentText()}"
        params['TG2'] = widgets['TG2'].currentText()
        params['TG3'] = widgets['TG3'].currentText()
        params['TG4'] = widgets['TG4'].currentText()
        params['TG5'] = widgets['TG5'].currentText()
        params['CH1'] = widgets['CH1'].currentText()
        params['CH2'] = widgets['CH2'].currentText()
        params['状态类型'] = state_type
        return params

    def generate_state(self):
        from experiment_state import STATE_REGISTRY
        state_type = self.type_combo.currentData()
        if state_type == 'TC12':
            widgets = self.tc12_param_widgets
        else:
            widgets = self.tc34_param_widgets
        params = self._collect_params(widgets, state_type)
        # 简单校验关键参数
        if not params.get('α或K') or not params.get('r'):
            QMessageBox.warning(self, "提示", "请至少填写 α或K 和 r 参数")
            return
        state = STATE_REGISTRY.add_state({
            'type': state_type,
            'params': params,
        })
        # 更新下拉菜单和表格
        self._update_state_list()
        # 自动刷新其他Tab的实验状态下拉菜单
        mw = self.window()
        if mw and hasattr(mw, 'tab1'):
            mw.tab1.refresh_experiment_states()
            mw.tab2.refresh_experiment_states()
            mw.tab4.refresh_push_states()
        # 自动刷新其他Tab的实验状态下拉菜单
        mw = self.window()
        if mw:
            for attr_name in ['tab1', 'tab2', 'tab3', 'tab4', 'tab_batch', 'tab_bg_sub', 'tab_sensitivity']:
                tab = getattr(mw, attr_name, None)
                if tab and hasattr(tab, 'refresh_experiment_states'):
                    try:
                        tab.refresh_experiment_states()
                    except Exception:
                        pass
        
        QMessageBox.information(self, "成功",
            f"已生成实验状态:\n名称: {state['name']}\n报告BLOCK序号: {state['block_no']}\n\n"
            f"所有业务Tab的实验状态下拉菜单已自动刷新。")
    
    def _update_state_list(self):
        """更新下拉菜单和表格"""
        from experiment_state import STATE_REGISTRY
        
        # 更新下拉菜单
        current_text = self.state_select_combo.currentText()
        self.state_select_combo.clear()
        self.state_select_combo.addItem("请选择...", "")
        states = STATE_REGISTRY.get_all_states()
        for s in states:
            self.state_select_combo.addItem(f"[{s['id']}] {s['name']}", s['id'])
        
        # 更新表格
        self.state_table.setRowCount(len(states))
        for row, s in enumerate(states):
            self.state_table.setItem(row, 0, QTableWidgetItem(str(s['id'])))
            self.state_table.setItem(row, 1, QTableWidgetItem(s['name']))
            self.state_table.setItem(row, 2, QTableWidgetItem(s['block_no']))
            self.state_table.setItem(row, 3, QTableWidgetItem(s['type']))
            
            # 参数预览
            params_preview = ", ".join([f"{k}={v}" for k, v in s.get('params', {}).items()][:5])
            if len(s.get('params', {})) > 5:
                params_preview += "..."
            self.state_table.setItem(row, 4, QTableWidgetItem(params_preview))
        
        # 恢复之前的选择
        idx = self.state_select_combo.findText(current_text)
        if idx >= 0:
            self.state_select_combo.setCurrentIndex(idx)
    
    def on_state_selected(self, index):
        """下拉菜单选择状态"""
        state_id = self.state_select_combo.currentData()
        enabled = bool(state_id)
        self.load_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)
        self.push_state_btn.setEnabled(enabled)
        
        # 同步表格选中
        if state_id:
            for row in range(self.state_table.rowCount()):
                if self.state_table.item(row, 0).text() == str(state_id):
                    self.state_table.selectRow(row)
                    break
    
    def on_table_clicked(self, row, column):
        """表格点击选中"""
        state_id = int(self.state_table.item(row, 0).text())
        idx = self.state_select_combo.findData(state_id)
        if idx >= 0:
            self.state_select_combo.setCurrentIndex(idx)
    
    def load_selected_state(self):
        """加载选中状态的参数到表单"""
        from experiment_state import STATE_REGISTRY
        state_id = self.state_select_combo.currentData()
        if not state_id:
            return
        
        state = STATE_REGISTRY.get_state_by_id(state_id)
        if not state:
            QMessageBox.warning(self, "提示", "未找到选中的实验状态")
            return
        
        # 根据类型选择控件集
        state_type = state.get('type', 'TC12')
        if state_type == 'TC12':
            widgets = self.tc12_param_widgets
            self.type_combo.setCurrentIndex(0)
        else:
            widgets = self.tc34_param_widgets
            self.type_combo.setCurrentIndex(1)
        
        params = state.get('params', {})
        
        # 填充参数
        widgets['alpha'].setText(params.get('α或K', ''))
        if 'gamma' in widgets:
            widgets['gamma'].setText(params.get('γ', ''))
        widgets['beta'].setText(params.get('β或L', ''))
        widgets['r'].setText(params.get('r', ''))
        widgets['D'].setText(params.get('D', ''))
        
        # 激励策略
        for order in range(1, 5):
            key = f'{order}阶波激励策略'
            if key in params:
                val = params[key]
                # 提取参数部分（去掉单位说明）
                import re
                match = re.match(r'(.+?)\s*\(时间单位:', val)
                if match:
                    widgets[f'wave{order}_params'].setText(match.group(1).strip())
                else:
                    widgets[f'wave{order}_params'].setText(val)
                
                # 设置单位
                if '(时间单位:ms' in val:
                    widgets[f'wave{order}_unit'].setCurrentIndex(0)
                else:
                    widgets[f'wave{order}_unit'].setCurrentIndex(1)
        
        # TG1
        tg1_val = params.get('TG1', '')
        if tg1_val:
            parts = tg1_val.split()
            if len(parts) >= 1:
                widgets['TG1'].setText(parts[0])
                if len(parts) >= 2:
                    idx = widgets['TG1_unit'].findText(parts[1])
                    if idx >= 0:
                        widgets['TG1_unit'].setCurrentIndex(idx)
        
        # TG2-TG5
        for key in ['TG2', 'TG3', 'TG4', 'TG5']:
            val = params.get(key, '')
            if val and key in widgets:
                idx = widgets[key].findText(val)
                if idx >= 0:
                    widgets[key].setCurrentIndex(idx)
        
        # CH1, CH2
        for key in ['CH1', 'CH2']:
            val = params.get(key, '')
            if val and key in widgets:
                idx = widgets[key].findText(val)
                if idx >= 0:
                    widgets[key].setCurrentIndex(idx)
        
        QMessageBox.information(self, "成功", f"已加载实验状态: {state['name']}")
    
    def delete_selected_state(self):
        """删除选中的状态"""
        from experiment_state import STATE_REGISTRY
        state_id = self.state_select_combo.currentData()
        if not state_id:
            return
        
        state = STATE_REGISTRY.get_state_by_id(state_id)
        if not state:
            QMessageBox.warning(self, "提示", "未找到选中的实验状态")
            return
        
        ret = QMessageBox.question(self, "确认删除",
            f"确定要删除实验状态 '{state['name']}' 吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        
        STATE_REGISTRY.remove_state(state_id)
        self._update_state_list()
        
        # 刷新其他Tab
        mw = self.window()
        if mw and hasattr(mw, 'tab1'):
            mw.tab1.refresh_experiment_states()
            mw.tab2.refresh_experiment_states()
            mw.tab4.refresh_push_states()
        
        QMessageBox.information(self, "成功", f"已删除实验状态: {state['name']}")
    
    def clear_all_states(self):
        """清空所有实验状态"""
        from experiment_state import STATE_REGISTRY
        states = STATE_REGISTRY.get_all_states()
        if not states:
            QMessageBox.information(self, "提示", "没有可清空的实验状态")
            return
        
        ret = QMessageBox.question(self, "确认清空",
            f"确定要清空全部 {len(states)} 个实验状态吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        
        STATE_REGISTRY.clear()
        self._update_state_list()
        
        # 刷新其他Tab
        mw = self.window()
        if mw and hasattr(mw, 'tab1'):
            mw.tab1.refresh_experiment_states()
            mw.tab2.refresh_experiment_states()
            mw.tab4.refresh_push_states()
        
        QMessageBox.information(self, "成功", "已清空全部实验状态")
    
    def push_selected_state(self):
        """将选中的实验状态推送到Tab6/7/8"""
        from experiment_state import STATE_REGISTRY
        state_id = self.state_select_combo.currentData()
        if not state_id:
            return
        
        state = STATE_REGISTRY.get_state_by_id(state_id)
        if not state:
            QMessageBox.warning(self, "提示", "未找到选中的实验状态")
            return
        
        state_name = state['name']
        
        mw = self.window()
        if not mw:
            QMessageBox.warning(self, "提示", "无法获取主窗口")
            return
        
        pushed_tabs = []
        tab_map = {
            'tab_batch': '多组数据扫参对比',
            'tab_bg_sub': '背景对消批处理',
            'tab_sensitivity': '通道敏感性分析'
        }
        
        for attr_name, tab_label in tab_map.items():
            tab = getattr(mw, attr_name, None)
            if tab and hasattr(tab, 'push_experiment_state'):
                try:
                    tab.push_experiment_state(state_name)
                    pushed_tabs.append(tab_label)
                except Exception as e:
                    log(f"[ExperimentState] 推送失败 {tab_label}: {e}")
        
        if pushed_tabs:
            QMessageBox.information(self, "推送成功",
                f"已将实验状态 '{state_name}' 推送到:\n" + "\n".join(pushed_tabs))
        else:
            QMessageBox.warning(self, "提示", "未找到可推送的目标Tab")


# ============= Tab6: Markdown 报告创建与显示 =============

class ReportTab(QWidget):
    """Markdown报告Tab：整合各Tab的BLOCK，编辑、预览、保存"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
        from experiment_state import REPORT_MANAGER
        REPORT_MANAGER.set_report_dir(self.report_dir)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar_row = QHBoxLayout()
        self.create_btn = QPushButton("创建报告")
        self.create_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 6px;")
        self.create_btn.clicked.connect(self.create_report)
        toolbar_row.addWidget(self.create_btn)

        self.save_dir_btn = QPushButton("保存位置")
        self.save_dir_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px;")
        self.save_dir_btn.clicked.connect(self.choose_save_dir)
        toolbar_row.addWidget(self.save_dir_btn)

        self.preview_toggle_btn = QPushButton("markdown分栏预览: 开")
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.setChecked(True)
        self.preview_toggle_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 6px;")
        self.preview_toggle_btn.clicked.connect(self.toggle_preview)
        toolbar_row.addWidget(self.preview_toggle_btn)

        self.refresh_btn = QPushButton("刷新BLOCK列表")
        self.refresh_btn.clicked.connect(self.refresh_block_list)
        toolbar_row.addWidget(self.refresh_btn)

        self.save_md_btn = QPushButton("保存为.md文件")
        self.save_md_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 6px;")
        self.save_md_btn.clicked.connect(self.save_md_file)
        toolbar_row.addWidget(self.save_md_btn)

        toolbar_row.addStretch()
        self.dir_label = QLabel(f"保存位置: {self.report_dir}")
        self.dir_label.setStyleSheet("color: #666; padding: 4px;")
        toolbar_row.addWidget(self.dir_label)
        main_layout.addLayout(toolbar_row)

        # 主体：左右分栏（编辑器 / 预览）
        splitter = QSplitter(Qt.Horizontal)

        # 左：BLOCK列表 + 编辑器
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("报告BLOCK列表（来自各Tab）："))
        self.block_list = QListWidget()
        self.block_list.setMaximumHeight(120)
        left_layout.addWidget(self.block_list)

        del_row = QHBoxLayout()
        self.del_btn = QPushButton("删除选中BLOCK")
        self.del_btn.clicked.connect(self.delete_block)
        del_row.addWidget(self.del_btn)
        self.clear_btn = QPushButton("清空全部BLOCK")
        self.clear_btn.clicked.connect(self.clear_blocks)
        del_row.addWidget(self.clear_btn)
        left_layout.addLayout(del_row)

        left_layout.addWidget(QLabel("Markdown 编辑区（可编辑）："))
        self.md_edit = QTextEdit()
        self.md_edit.setFont(QFont("Consolas", 10))
        self.md_edit.textChanged.connect(self.update_preview)
        left_layout.addWidget(self.md_edit, stretch=1)
        splitter.addWidget(left_widget)

        # 右：预览
        self.preview_widget = QWidget()
        preview_layout = QVBoxLayout(self.preview_widget)
        preview_layout.addWidget(QLabel("Markdown 预览："))
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        preview_layout.addWidget(self.preview_edit, stretch=1)
        splitter.addWidget(self.preview_widget)

        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter, stretch=1)

        self.refresh_block_list()

    def refresh_block_list(self):
        from experiment_state import REPORT_MANAGER
        self.block_list.clear()
        for i, b in enumerate(REPORT_MANAGER.get_all_blocks()):
            self.block_list.addItem(f"[{i}] {b.title} ({b.source_tab})")

    def create_report(self):
        from experiment_state import REPORT_MANAGER
        md = REPORT_MANAGER.to_full_markdown()
        self.md_edit.setPlainText(md)
        self.update_preview()
        QMessageBox.information(self, "成功", "已创建报告（整合所有BLOCK）")

    def choose_save_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择报告保存位置", self.report_dir)
        if d:
            self.report_dir = d
            self.dir_label.setText(f"保存位置: {self.report_dir}")
            from experiment_state import REPORT_MANAGER
            REPORT_MANAGER.set_report_dir(d)

    def toggle_preview(self):
        checked = self.preview_toggle_btn.isChecked()
        self.preview_widget.setVisible(checked)
        self.preview_toggle_btn.setText("markdown分栏预览: 开" if checked else "markdown分栏预览: 关")

    def update_preview(self):
        """简单的markdown预览（HTML渲染）"""
        text = self.md_edit.toPlainText()
        try:
            html = self._simple_md_to_html(text)
        except Exception:
            html = "<p>预览生成失败</p>"
        try:
            self.preview_edit.setHtml(html)
        except Exception:
            pass

    def _simple_md_to_html(self, text):
        """简易markdown转HTML"""
        import html as html_mod
        lines = text.split('\n')
        out = []
        in_table = False
        for line in lines:
            esc = html_mod.escape(line)
            if line.startswith('# '):
                out.append(f"<h1>{esc[2:]}</h1>")
            elif line.startswith('## '):
                out.append(f"<h2>{esc[3:]}</h2>")
            elif line.startswith('### '):
                out.append(f"<h3>{esc[4:]}</h3>")
            elif line.startswith('> '):
                out.append(f"<blockquote>{esc[2:]}</blockquote>")
            elif line.startswith('|') and '---' not in line:
                cells = [c.strip() for c in line.strip('|').split('|')]
                if not in_table:
                    out.append("<table border='1' cellpadding='4' cellspacing='0'>")
                    in_table = True
                    out.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                else:
                    out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            elif line.strip() == '' and in_table:
                out.append("</table>")
                in_table = False
            elif line.startswith('---'):
                out.append("<hr>")
            else:
                out.append(f"<p>{esc}</p>")
        if in_table:
            out.append("</table>")
        return "\n".join(out)

    def delete_block(self):
        from experiment_state import REPORT_MANAGER
        row = self.block_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的BLOCK")
            return
        REPORT_MANAGER.remove_block(row)
        self.refresh_block_list()
        self.create_report()

    def clear_blocks(self):
        from experiment_state import REPORT_MANAGER
        ret = QMessageBox.question(self, "确认", "确定清空全部BLOCK？")
        if ret == QMessageBox.Yes:
            REPORT_MANAGER.clear()
            self.refresh_block_list()
            self.md_edit.clear()
            self.preview_edit.clear()

    def save_md_file(self):
        text = self.md_edit.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "提示", "报告内容为空")
            return
        os.makedirs(self.report_dir, exist_ok=True)
        from datetime import datetime
        default_name = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存Markdown文件", os.path.join(self.report_dir, default_name),
            "Markdown (*.md)"
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                QMessageBox.information(self, "成功", f"报告已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", str(e))


# ============= 主窗口 =============

class SignalProcessorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("极化带效应探测系统_TC12/TC34_基本数据处理与分析")
        
        screen = QApplication.primaryScreen().availableGeometry()
        width = min(1400, screen.width() - 100)
        height = min(900, screen.height() - 100)
        self.setGeometry(100, 100, width, height)
        
        self.setMinimumSize(800, 600)
        
        # 设置应用字体
        font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(font)
        
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
    
    def setup_ui(self):
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建Tab
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        
        # Tab1: 实验状态定义
        self.tab_exp_state = ExperimentStateTab()
        self.tab_widget.addTab(self.tab_exp_state, "📋 实验状态定义")
        
        # Tab2: 数据预处理
        self.tab_preprocess = PreprocessTab()
        self.tab_widget.addTab(self.tab_preprocess, "🛠️ 数据预处理")
        
        # Tab3: 单组数据矩阵处理
        self.tab_matrix = MatrixTransformTab()
        self.tab_widget.addTab(self.tab_matrix, "🔢 单组数据矩阵处理")
        
        # Tab4: 两组数据时域处理
        self.tab_time = TimeDomainTab()
        self.tab_widget.addTab(self.tab_time, "📊 两组数据时域处理")
        
        # Tab5: 两组数据频域处理
        self.tab_freq = FrequencyDomainTab()
        self.tab_widget.addTab(self.tab_freq, "🎵 两组数据频域处理")
        
        # Tab6: 多组数据扫参对比
        self.tab_batch = BatchCompareTab()
        self.tab_widget.addTab(self.tab_batch, "📦 多组数据扫参对比")
        
        # Tab6.5: 背景对消批处理
        self.tab_bg_sub = BackgroundSubtractionTab()
        self.tab_widget.addTab(self.tab_bg_sub, "🔄 背景对消批处理")
        
        # Tab9: 通道敏感性分析
        self.tab_sensitivity = ChannelSensitivityTab()
        self.tab_widget.addTab(self.tab_sensitivity, "🎯 通道敏感性分析")

        # Tab10: 相似性计算方法理论指南
        self.tab_methods_guide = SimilarityMethodsGuideTab()
        self.tab_widget.addTab(self.tab_methods_guide, "📚 相似性方法理论指南")

        # Tab7: Markdown 报告创建与显示
        self.tab_report = ReportTab()
        self.tab_widget.addTab(self.tab_report, "📝 Markdown报告")
        
        # 注册预处理目标Tab：预处理结果将推送到时域/频域/矩阵Tab
        self.tab_preprocess.register_target_tab(self.tab_time)
        self.tab_preprocess.register_target_tab(self.tab_freq)
        self.tab_preprocess.register_target_tab(self.tab_matrix)
        
        # 兼容旧变量名（避免其他代码引用报错）
        self.tab1 = self.tab_time
        self.tab2 = self.tab_freq
        self.tab3 = self.tab_matrix
        self.tab4 = self.tab_preprocess
        self.tab5 = self.tab_batch
        self.tab5_5 = self.tab_bg_sub
        self.tab6 = self.tab_exp_state
        self.tab7 = self.tab_report
        self.tab9 = self.tab_sensitivity
        
        layout.addWidget(self.tab_widget)
        
        # 刷新各Tab的实验状态下拉菜单（从全局注册表读取）
        self.tab_time.refresh_experiment_states()
        self.tab_freq.refresh_experiment_states()
        self.tab_sensitivity.refresh_experiment_states()
    
    def setup_menu(self):
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        open_action = QAction("打开文件", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        open_btn = QPushButton("📂 打开文件")
        open_btn.clicked.connect(self.open_file)
        toolbar.addWidget(open_btn)
        
        toolbar.addSeparator()
        
        about_btn = QPushButton("❓ 关于")
        about_btn.clicked.connect(self.show_about)
        toolbar.addWidget(about_btn)
    
    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪 | 请选择一个Tab开始使用")
    
    def open_file(self):
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            pass
        elif current_tab == 1:
            self.tab_preprocess.file_selector.browse_file()
        elif current_tab == 2:
            self.tab_matrix.file_selector.browse_file()
        elif current_tab == 3:
            self.tab_time.file_a_selector.browse_file()
        elif current_tab == 4:
            self.tab_freq.file_a_selector.browse_file()
        elif current_tab == 5:
            self.tab_batch.add_data_group()
    
    def show_about(self):
        QMessageBox.about(self, "关于",
            "<h2>极化带效应探测系统_TC12/TC34_基本数据处理与分析 v1.0</h2>"
            "<p>时域信号处理和可视化基础功能</p>"
            "<p><b>功能特点：</b></p>"
            "<ul>"
            "<li>支持多种时域相似性度量</li>"
            "<li>支持多种频域相似性度量</li>"
            "<li>支持多种矩阵转换方法</li>"
            "<li>支持多种可视化方法</li>"
            "<li>支持多种文件格式：CSV, TXT, Excel, NI TDMS/TDM/LVM, HDF5, WAV, BIN</li>"
            "<li>支持多种图像保存格式：PNG, JPG, TIFF, PDF, SVG, EPS</li>"
            "</ul>"
            "<p>© 202606 极化带效应探测系统代码族TC系列</p>"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置应用样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            padding: 5px 15px;
            border: 1px solid #999;
            border-radius: 3px;
            background-color: #e0e0e0;
        }
        QPushButton:hover {
            background-color: #d0d0d0;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #999;
        }
        QTableWidget {
            gridline-color: #cccccc;
            border: 1px solid #cccccc;
        }
        QTableWidget::item:selected {
            background-color: #0078d7;
            color: white;
        }
        QListWidget {
            border: 1px solid #cccccc;
            padding: 5px;
        }
        QListWidget::item:selected {
            background-color: #0078d7;
            color: white;
        }
        QTabWidget::pane {
            border: 1px solid #cccccc;
            background-color: #ffffff;
        }
        QTabBar::tab {
            padding: 8px 16px;
            margin-right: 2px;
            border: 1px solid #cccccc;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            background-color: #e0e0e0;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 2px solid #0078d7;
        }
        QTabBar::tab:hover {
            background-color: #d0d0d0;
        }
    """)
    
    window = SignalProcessorMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
