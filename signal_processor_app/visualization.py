# -*- coding: utf-8 -*-
"""
可视化模块
包含多种图表类型和保存功能
"""
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.cm as cm
from mpl_toolkits.mplot3d import Axes3D
from scipy import signal


VISUALIZATION_METHODS = [
    '折线图 (Line)',
    '散点图 (Scatter)',
    '柱状图 (Bar)',
    '直方图 (Histogram)',
    '热力图 (Heatmap)',
    '等高线图 (Contour)',
    '3D曲面图 (3D Surface)',
    '雷达图 (Radar)',
    '箱线图 (Box Plot)',
    '小提琴图 (Violin)',
    '时频图 (Spectrogram)',
    '瀑布图 (Waterfall)',
    '自相关图 (ACF)',
    'Q-Q图 (Q-Q Plot)',
    '残差图 (Residual)',
    '双轴对比图 (Dual Axis)',
    '饼图 (Pie)',
    '阶梯图 (Stairs)',
    '填充图 (Fill Between)',
    '极坐标图 (Polar)'
]


class MatplotlibCanvas(FigureCanvas):
    """Matplotlib画布类，支持交互式操作"""
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.axes = None
        self.colorbar = None
        
    def clear(self):
        self.fig.clear()
        self.axes = None
        if self.colorbar:
            self.colorbar.remove()
            self.colorbar = None
    
    def get_figure(self):
        return self.fig


def create_canvas(parent=None):
    """创建一个新的matplotlib画布"""
    return MatplotlibCanvas(parent=parent, width=10, height=7, dpi=100)


def plot_line(canvas, x_data, y_data_dict, title='Line Plot', xlabel='Time', ylabel='Amplitude', fs=1.0):
    """折线图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    if isinstance(x_data, (list, tuple)) and len(x_data) > 0 and isinstance(x_data[0], (list, tuple, np.ndarray)):
        # x_data是列表的列表，需要分别处理
        for i, (x, y) in enumerate(zip(x_data, y_data_dict.values())):
            t = np.arange(len(x)) / fs
            ax.plot(t, x, label=list(y_data_dict.keys())[i], alpha=0.8)
    else:
        # 处理字典格式
        for name, y in y_data_dict.items():
            t = np.arange(len(y)) / fs
            ax.plot(t, y, label=name, alpha=0.8, linewidth=1.2)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    canvas.axes = ax
    canvas.draw()


def plot_scatter(canvas, x, y_dict, title='Scatter Plot', xlabel='X', ylabel='Y'):
    """散点图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(y_dict)))
    for i, (name, y) in enumerate(y_dict.items()):
        min_len = min(len(x), len(y))
        ax.scatter(x[:min_len], y[:min_len], c=[colors[i]], label=name, alpha=0.6, s=20)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_bar(canvas, labels, values_dict, title='Bar Chart', xlabel='Category', ylabel='Value'):
    """柱状图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    x = np.arange(len(labels))
    width = 0.8 / len(values_dict)
    colors = plt.cm.tab10(np.linspace(0, 1, len(values_dict)))
    
    for i, (name, values) in enumerate(values_dict.items()):
        ax.bar(x + i * width - 0.4 + width/2, values[:len(labels)], width, label=name, color=colors[i])
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, axis='y')
    canvas.axes = ax
    canvas.draw()


def plot_histogram(canvas, data_dict, title='Histogram', xlabel='Value', ylabel='Frequency'):
    """直方图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(data_dict)))
    for i, (name, data) in enumerate(data_dict.items()):
        ax.hist(np.asarray(data).flatten(), bins=50, alpha=0.5, label=name, color=colors[i], edgecolor='black')
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, axis='y')
    canvas.axes = ax
    canvas.draw()


def plot_heatmap(canvas, matrix, title='Heatmap', xlabel='X', ylabel='Y'):
    """热力图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    im = ax.imshow(matrix, aspect='auto', cmap='viridis', origin='lower')
    canvas.colorbar = canvas.fig.colorbar(im, ax=ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    canvas.axes = ax
    canvas.draw()


def plot_contour(canvas, matrix, title='Contour Plot', xlabel='X', ylabel='Y'):
    """等高线图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    x = np.arange(matrix.shape[1])
    y = np.arange(matrix.shape[0])
    X, Y = np.meshgrid(x, y)
    
    levels = min(20, matrix.shape[0] // 2, matrix.shape[1] // 2)
    if levels < 5:
        levels = 5
    cs = ax.contour(X, Y, matrix, levels=levels, cmap='viridis')
    ax.clabel(cs, inline=True, fontsize=8)
    canvas.colorbar = canvas.fig.colorbar(cs, ax=ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    canvas.axes = ax
    canvas.draw()


def plot_3d_surface(canvas, matrix, title='3D Surface', xlabel='X', ylabel='Y', zlabel='Z'):
    """3D曲面图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111, projection='3d')
    
    x = np.arange(matrix.shape[1])
    y = np.arange(matrix.shape[0])
    X, Y = np.meshgrid(x, y)
    
    surf = ax.plot_surface(X, Y, matrix, cmap='viridis', alpha=0.8, edgecolor='none')
    canvas.colorbar = canvas.fig.colorbar(surf, ax=ax, shrink=0.5)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_zlabel(zlabel)
    canvas.axes = ax
    canvas.draw()


def plot_radar(canvas, labels, values_dict, title='Radar Chart'):
    """雷达图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111, projection='polar')
    
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(values_dict)))
    for i, (name, values) in enumerate(values_dict.items()):
        values = list(values[:len(labels)])
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=1.5, label=name, color=colors[i])
        ax.fill(angles, values, alpha=0.15, color=colors[i])
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    ax.grid(True)
    canvas.axes = ax
    canvas.draw()


def plot_box(canvas, data_dict, title='Box Plot', xlabel='Group', ylabel='Value'):
    """箱线图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    data_list = [np.asarray(d).flatten() for d in data_dict.values()]
    labels = list(data_dict.keys())
    
    bp = ax.boxplot(data_list, labels=labels, patch_artist=True)
    colors = plt.cm.Set3(np.linspace(0, 1, len(data_list)))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3, axis='y')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    canvas.axes = ax
    canvas.draw()


def plot_violin(canvas, data_dict, title='Violin Plot', xlabel='Group', ylabel='Value'):
    """小提琴图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    data_list = [np.asarray(d).flatten() for d in data_dict.values()]
    positions = np.arange(1, len(data_list) + 1)
    labels = list(data_dict.keys())
    
    parts = ax.violinplot(data_list, positions=positions, showmeans=True, showmedians=True)
    colors = plt.cm.Set3(np.linspace(0, 1, len(data_list)))
    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.7)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.grid(True, alpha=0.3, axis='y')
    canvas.axes = ax
    canvas.draw()


def plot_spectrogram(canvas, data, fs=1.0, title='Spectrogram', xlabel='Time', ylabel='Frequency'):
    """时频图（Spectrogram）"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    data = np.asarray(data).flatten()
    nperseg = min(256, len(data) // 8)
    if nperseg < 8:
        nperseg = 8
    
    f, t, Sxx = signal.spectrogram(data, fs, nperseg=nperseg)
    im = ax.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud', cmap='viridis')
    canvas.colorbar = canvas.fig.colorbar(im, ax=ax)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    canvas.axes = ax
    canvas.draw()


def plot_waterfall(canvas, data_list, title='Waterfall Plot', xlabel='Time', ylabel='Amplitude'):
    """瀑布图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111, projection='3d')
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(data_list)))
    for i, (name, data) in enumerate(data_list.items()):
        data = np.asarray(data).flatten()
        t = np.arange(len(data))
        offset = i * np.std(data) * 2
        ax.plot(t, [offset]*len(t), data + offset, color=colors[i], label=name, linewidth=1)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Offset')
    ax.set_zlabel(ylabel)
    ax.legend()
    canvas.axes = ax
    canvas.draw()


def plot_acf(canvas, data_dict, title='Autocorrelation', xlabel='Lag', ylabel='ACF'):
    """自相关图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    max_lags = 100
    for name, data in data_dict.items():
        data = np.asarray(data).flatten()
        lags = min(max_lags, len(data) // 2)
        acf = np.correlate(data, data, mode='full')
        acf = acf[len(acf)//2:len(acf)//2+lags]
        acf = acf / acf[0]
        ax.plot(range(lags), acf, label=name, alpha=0.8, linewidth=1.2)
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_qq(canvas, data_dict, title='Q-Q Plot', xlabel='Theoretical Quantiles', ylabel='Sample Quantiles'):
    """Q-Q图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    from scipy import stats
    for name, data in data_dict.items():
        data = np.asarray(data).flatten()
        stats.probplot(data, dist="norm", plot=ax)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_residual(canvas, data_a, data_b, title='Residual Plot', xlabel='Time', ylabel='Residual'):
    """残差图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    a = np.asarray(data_a).flatten()
    b = np.asarray(data_b).flatten()
    min_len = min(len(a), len(b))
    a, b = a[:min_len], b[:min_len]
    residual = a - b
    t = np.arange(min_len)
    
    ax.plot(t, residual, color='blue', alpha=0.7, linewidth=1)
    ax.axhline(y=0, color='r', linestyle='--', linewidth=1)
    ax.fill_between(t, residual, alpha=0.3, color='blue')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_dual_axis(canvas, data_a, data_b, fs=1.0, title='Dual Axis Comparison', xlabel='Time'):
    """双轴对比图"""
    canvas.clear()
    ax1 = canvas.fig.add_subplot(111)
    ax2 = ax1.twinx()
    
    a = np.asarray(data_a).flatten()
    b = np.asarray(data_b).flatten()
    min_len = min(len(a), len(b))
    t = np.arange(min_len) / fs
    
    line1 = ax1.plot(t, a[:min_len], 'b-', label='A State', linewidth=1.2)
    line2 = ax2.plot(t, b[:min_len], 'r-', label='B State', linewidth=1.2)
    
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel('A State Amplitude', color='b')
    ax2.set_ylabel('B State Amplitude', color='r')
    ax1.tick_params(axis='y', labelcolor='b')
    ax2.tick_params(axis='y', labelcolor='r')
    
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='best')
    ax1.set_title(title, fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    canvas.axes = ax1
    canvas.draw()


def plot_pie(canvas, labels, values, title='Pie Chart'):
    """饼图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    colors = plt.cm.Set3(np.linspace(0, 1, len(values)))
    wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', 
                                       colors=colors, startangle=90)
    ax.set_title(title, fontsize=12, fontweight='bold')
    canvas.axes = ax
    canvas.draw()


def plot_stairs(canvas, data_dict, title='Stairs Plot', xlabel='Time', ylabel='Value'):
    """阶梯图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    for name, data in data_dict.items():
        data = np.asarray(data).flatten()
        t = np.arange(len(data))
        ax.step(t, data, where='mid', label=name, alpha=0.8, linewidth=1.2)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_fill_between(canvas, data_dict, title='Fill Between', xlabel='Time', ylabel='Value'):
    """填充图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111)
    
    names = list(data_dict.keys())
    if len(names) >= 2:
        a = np.asarray(data_dict[names[0]]).flatten()
        b = np.asarray(data_dict[names[1]]).flatten()
        min_len = min(len(a), len(b))
        t = np.arange(min_len)
        ax.fill_between(t, a[:min_len], b[:min_len], alpha=0.5, color='green', label=f'{names[0]} vs {names[1]}')
        ax.plot(t, a[:min_len], color='blue', linewidth=1, label=names[0])
        ax.plot(t, b[:min_len], color='red', linewidth=1, label=names[1])
    else:
        for name, data in data_dict.items():
            data = np.asarray(data).flatten()
            t = np.arange(len(data))
            ax.fill_between(t, data, alpha=0.3, label=name)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    canvas.axes = ax
    canvas.draw()


def plot_polar(canvas, data_dict, title='Polar Plot'):
    """极坐标图"""
    canvas.clear()
    ax = canvas.fig.add_subplot(111, projection='polar')
    
    for name, data in data_dict.items():
        data = np.asarray(data).flatten()
        theta = np.linspace(0, 2*np.pi, len(data))
        ax.plot(theta, np.abs(data), label=name, linewidth=1.2)
    
    ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
    ax.legend(loc='best')
    ax.grid(True)
    canvas.axes = ax
    canvas.draw()


# 方法映射
PLOT_METHODS = {
    '折线图 (Line)': plot_line,
    '散点图 (Scatter)': plot_scatter,
    '柱状图 (Bar)': plot_bar,
    '直方图 (Histogram)': plot_histogram,
    '热力图 (Heatmap)': plot_heatmap,
    '等高线图 (Contour)': plot_contour,
    '3D曲面图 (3D Surface)': plot_3d_surface,
    '雷达图 (Radar)': plot_radar,
    '箱线图 (Box Plot)': plot_box,
    '小提琴图 (Violin)': plot_violin,
    '时频图 (Spectrogram)': plot_spectrogram,
    '瀑布图 (Waterfall)': plot_waterfall,
    '自相关图 (ACF)': plot_acf,
    'Q-Q图 (Q-Q Plot)': plot_qq,
    '残差图 (Residual)': plot_residual,
    '双轴对比图 (Dual Axis)': plot_dual_axis,
    '饼图 (Pie)': plot_pie,
    '阶梯图 (Stairs)': plot_stairs,
    '填充图 (Fill Between)': plot_fill_between,
    '极坐标图 (Polar)': plot_polar
}


def save_figure(canvas, filepath, dpi=300):
    """保存图像到文件"""
    ext = filepath.split('.')[-1].lower()
    supported = ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'pdf', 'svg', 'eps']
    
    if ext not in supported:
        filepath += '.png'
        ext = 'png'
    
    try:
        canvas.fig.savefig(filepath, dpi=dpi, bbox_inches='tight', format=ext)
        return True, filepath
    except Exception as e:
        return False, str(e)


def auto_visualize(canvas, data, method_name, title='Auto Plot', fs=1.0, **kwargs):
    """根据数据类型自动选择可视化方法"""
    data = np.asarray(data)
    
    if method_name == 'auto':
        # 自动选择
        if data.ndim == 2 and data.shape[0] > 10 and data.shape[1] > 10:
            method_name = '热力图 (Heatmap)'
        elif data.ndim == 1:
            method_name = '折线图 (Line)'
        else:
            method_name = '折线图 (Line)'
    
    if method_name == '折线图 (Line)':
        if isinstance(data, dict):
            plot_line(canvas, None, data, title=title, fs=fs)
        else:
            plot_line(canvas, None, {'Data': data}, title=title, fs=fs)
    elif method_name == '热力图 (Heatmap)':
        plot_heatmap(canvas, data, title=title)
    elif method_name == '等高线图 (Contour)':
        plot_contour(canvas, data, title=title)
    elif method_name == '3D曲面图 (3D Surface)':
        plot_3d_surface(canvas, data, title=title)
    elif method_name == '时频图 (Spectrogram)':
        plot_spectrogram(canvas, data, fs=fs, title=title)
    elif method_name == '直方图 (Histogram)':
        if isinstance(data, dict):
            plot_histogram(canvas, data, title=title)
        else:
            plot_histogram(canvas, {'Data': data}, title=title)
    elif method_name == '箱线图 (Box Plot)':
        if isinstance(data, dict):
            plot_box(canvas, data, title=title)
        else:
            plot_box(canvas, {'Data': data}, title=title)
    elif method_name == '小提琴图 (Violin)':
        if isinstance(data, dict):
            plot_violin(canvas, data, title=title)
        else:
            plot_violin(canvas, {'Data': data}, title=title)
    elif method_name == '自相关图 (ACF)':
        if isinstance(data, dict):
            plot_acf(canvas, data, title=title)
        else:
            plot_acf(canvas, {'Data': data}, title=title)
    elif method_name in PLOT_METHODS:
        if isinstance(data, dict):
            PLOT_METHODS[method_name](canvas, data, **kwargs)
        else:
            PLOT_METHODS[method_name](canvas, {'Data': data}, **kwargs)
    else:
        # 默认
        plot_line(canvas, None, {'Data': data}, title=title, fs=fs)
