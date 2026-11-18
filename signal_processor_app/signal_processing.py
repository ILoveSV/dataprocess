# -*- coding: utf-8 -*-
"""
信号处理核心模块
包含：相似性度量、频域变换、矩阵转换、可视化
"""
import numpy as np
from scipy import signal, fft, stats
from scipy.spatial.distance import (euclidean, cityblock, chebyshev, minkowski,
                                    cosine, correlation, jensenshannon, hamming)
from scipy.stats import pearsonr, spearmanr, kendalltau, entropy
from scipy.spatial import distance
from sklearn.metrics import mutual_info_score, mean_squared_error, mean_absolute_error
from sklearn.preprocessing import normalize, StandardScaler
from sklearn.metrics.pairwise import cosine_similarity, rbf_kernel, polynomial_kernel
import warnings
warnings.filterwarnings('ignore')

# ========================
# 背景对消算法（10种）
# ========================

BACKGROUND_SUBTRACTION_METHODS = [
    '直接相减',
    '归一化相减',
    '均值消除',
    '线性拟合消除',
    '多项式拟合消除',
    '小波变换消除',
    '自适应滤波消除',
    '互相关对齐相减',
    '频域相减',
    'PCA主成分消除'
]

BG_STATISTICAL_METHODS = [
    '均值平均',
    '中位数平均',
    '均方根平均',
    '加权平均(按SNR)',
    '剔除极值后均值'
]


def compute_statistical_background(bg_data_list, method='均值平均'):
    """
    对多组背景数据进行统计平均处理
    
    参数:
        bg_data_list: 背景数据列表，每个元素为1D数组
        method: 统计方法
    
    返回:
        统计处理后的背景数据（1D数组）
    """
    if not bg_data_list:
        return np.array([])
    
    bg_arrays = [np.asarray(bg).flatten() for bg in bg_data_list if bg is not None and len(bg) > 0]
    
    if len(bg_arrays) == 0:
        return np.array([])
    
    min_len = min(len(bg) for bg in bg_arrays)
    aligned_data = [bg[:min_len] for bg in bg_arrays]
    
    if method == '均值平均':
        return np.mean(aligned_data, axis=0)
    
    elif method == '中位数平均':
        return np.median(aligned_data, axis=0)
    
    elif method == '均方根平均':
        return np.sqrt(np.mean(np.square(aligned_data), axis=0))
    
    elif method == '加权平均(按SNR)':
        snrs = []
        for bg in aligned_data:
            signal_power = np.mean(bg ** 2)
            noise_power = np.var(bg) if np.var(bg) > 0 else 1e-10
            snrs.append(signal_power / noise_power)
        
        total_snr = sum(snrs)
        if total_snr == 0:
            weights = np.ones(len(snrs)) / len(snrs)
        else:
            weights = [snr / total_snr for snr in snrs]
        
        result = np.zeros(min_len)
        for weight, bg in zip(weights, aligned_data):
            result += weight * bg
        return result
    
    elif method == '剔除极值后均值':
        data_matrix = np.vstack(aligned_data)
        
        std_factor = 3.0
        mean_vals = np.mean(data_matrix, axis=0)
        std_vals = np.std(data_matrix, axis=0)
        
        lower_bound = mean_vals - std_factor * std_vals
        upper_bound = mean_vals + std_factor * std_vals
        
        result = np.zeros(min_len)
        for i in range(min_len):
            column = data_matrix[:, i]
            mask = (column >= lower_bound[i]) & (column <= upper_bound[i])
            if np.any(mask):
                result[i] = np.mean(column[mask])
            else:
                result[i] = mean_vals[i]
        return result
    
    else:
        return np.mean(aligned_data, axis=0)


def subtract_background(data, bg_data, method='直接相减', **kwargs):
    """
    背景对消处理
    
    参数:
        data: 实验数据（1D数组）
        bg_data: 背景数据（1D数组）
        method: 对消方法
        **kwargs: 额外参数
    
    返回:
        对消后的数据（1D数组）
    """
    data = np.asarray(data).flatten()
    bg_data = np.asarray(bg_data).flatten()
    
    min_len = min(len(data), len(bg_data))
    data = data[:min_len]
    bg_data = bg_data[:min_len]
    
    if method == '直接相减':
        return data - bg_data
    
    elif method == '归一化相减':
        data_norm = (data - np.mean(data)) / np.std(data) if np.std(data) > 0 else data
        bg_norm = (bg_data - np.mean(bg_data)) / np.std(bg_data) if np.std(bg_data) > 0 else bg_data
        return data_norm - bg_norm
    
    elif method == '均值消除':
        bg_mean = np.mean(bg_data)
        return data - bg_mean
    
    elif method == '线性拟合消除':
        x = np.arange(len(bg_data))
        slope, intercept = np.polyfit(x, bg_data, 1)
        bg_fit = slope * x + intercept
        return data - bg_fit
    
    elif method == '多项式拟合消除':
        degree = kwargs.get('degree', 3)
        x = np.arange(len(bg_data))
        coeffs = np.polyfit(x, bg_data, degree)
        bg_fit = np.polyval(coeffs, x)
        return data - bg_fit
    
    elif method == '小波变换消除':
        try:
            import pywt
            wavelet = kwargs.get('wavelet', 'db4')
            level = kwargs.get('level', 5)
            coeffs_data = pywt.wavedec(data, wavelet, level=level)
            coeffs_bg = pywt.wavedec(bg_data, wavelet, level=level)
            coeffs_sub = [c_d - c_b for c_d, c_b in zip(coeffs_data, coeffs_bg)]
            return pywt.waverec(coeffs_sub, wavelet)[:len(data)]
        except ImportError:
            return data - bg_data
    
    elif method == '自适应滤波消除':
        from scipy.signal import lfilter
        order = kwargs.get('order', 10)
        b, a = signal.butter(order, 0.1, btype='low')
        bg_smooth = lfilter(b, a, bg_data)
        return data - bg_smooth
    
    elif method == '互相关对齐相减':
        corr = signal.correlate(data, bg_data, mode='full')
        shift = np.argmax(corr) - (len(bg_data) - 1)
        bg_shifted = np.roll(bg_data, shift)
        return data - bg_shifted
    
    elif method == '频域相减':
        data_fft = fft.fft(data)
        bg_fft = fft.fft(bg_data)
        result_fft = data_fft - bg_fft
        return np.real(fft.ifft(result_fft))
    
    elif method == 'PCA主成分消除':
        try:
            from sklearn.decomposition import PCA
            combined = np.vstack([data, bg_data]).T
            pca = PCA(n_components=1)
            pca.fit(combined)
            bg_pca = pca.transform(combined) @ pca.components_
            return data - bg_pca[:, 0]
        except ImportError:
            return data - bg_data
    
    else:
        return data - bg_data


# ========================
# 相似性度量方法（15+种）
# ========================

SIMILARITY_METHODS = {
    '时域': [
        '欧几里得距离',
        '曼哈顿距离',
        '切比雪夫距离',
        '闵可夫斯基距离',
        '余弦相似度',
        '皮尔逊相关系数',
        '斯皮尔曼等级相关',
        '肯德尔秩相关',
        '互相关峰值',
        '动态时间规整(DTW)',
        '结构相似性(SSIM)',
        '均方误差(MSE)',
        '均方根误差(RMSE)',
        '平均绝对误差(MAE)',
        '标准化互信息(NMI)',
        '巴氏距离',
        '最大信息系数(MIC)',
        '能量差',
        '波形重叠指数',
        '谱相干性'
    ],
    '频域': [
        '频谱欧几里得距离',
        '频谱曼哈顿距离',
        '频谱余弦相似度',
        '频谱皮尔逊相关',
        '频谱MSE',
        '频谱RMSE',
        '频谱MAE',
        '频谱互相关',
        '频谱DTW',
        '频谱SSIM',
        '频谱巴氏距离',
        '频谱能量差',
        '频谱熵差',
        '频谱KL散度',
        '频谱JS散度',
        '频谱相干性',
        '频谱重心差',
        '频谱带宽差',
        '频谱平坦度差',
        '频谱 rolloff 差'
    ]
}


def ensure_same_length(x, y):
    """确保两个序列长度相同，以较短的为准"""
    min_len = min(len(x), len(y))
    return x[:min_len], y[:min_len]


def euclidean_dist(x, y):
    """欧几里得距离"""
    x, y = ensure_same_length(x, y)
    return euclidean(x, y)


def manhattan_dist(x, y):
    """曼哈顿距离"""
    x, y = ensure_same_length(x, y)
    return cityblock(x, y)


def chebyshev_dist(x, y):
    """切比雪夫距离"""
    x, y = ensure_same_length(x, y)
    return chebyshev(x, y)


def minkowski_dist(x, y, p=3):
    """闵可夫斯基距离"""
    x, y = ensure_same_length(x, y)
    return minkowski(x, y, p=p)


def cosine_sim(x, y):
    """余弦相似度"""
    x, y = ensure_same_length(x, y)
    x = x.reshape(1, -1)
    y = y.reshape(1, -1)
    return float(cosine_similarity(x, y)[0, 0])


def pearson_corr(x, y):
    """皮尔逊相关系数"""
    x, y = ensure_same_length(x, y)
    r, p = pearsonr(x, y)
    return r


def spearman_corr(x, y):
    """斯皮尔曼等级相关系数"""
    x, y = ensure_same_length(x, y)
    r, p = spearmanr(x, y)
    return r


def kendall_corr(x, y):
    """肯德尔秩相关系数"""
    x, y = ensure_same_length(x, y)
    tau, p = kendalltau(x, y)
    return tau


def cross_correlation_peak(x, y):
    """互相关峰值（FFT加速版）"""
    x, y = ensure_same_length(x, y)
    x = x - np.mean(x)
    y = y - np.mean(y)
    
    # FFT加速互相关计算 O(n log n) 替代 O(n²)
    n = len(x)
    fft_size = 1
    while fft_size < 2 * n - 1:
        fft_size *= 2
    X = np.fft.fft(x, fft_size)
    Y = np.fft.fft(y, fft_size)
    corr = np.fft.ifft(X * np.conj(Y)).real
    
    return np.max(np.abs(corr)) / (np.std(x) * np.std(y) * len(x) + 1e-10)


def cross_correlation_coeff(x, y):
    """互相关系数"""
    x, y = ensure_same_length(x, y)
    x_mean, y_mean = np.mean(x), np.mean(y)
    x_std, y_std = np.std(x), np.std(y)
    
    if x_std == 0 or y_std == 0:
        return 0.0
    
    x_norm = (x - x_mean) / x_std
    y_norm = (y - y_mean) / y_std
    
    n = len(x)
    fft_size = 1
    while fft_size < 2 * n - 1:
        fft_size *= 2
    X = np.fft.fft(x_norm, fft_size)
    Y = np.fft.fft(y_norm, fft_size)
    corr = np.fft.ifft(X * np.conj(Y)).real
    
    return np.max(corr) / n


def dtw_distance(x, y, use_downsamp=False, max_points=1000000):
    """动态时间规整距离（优化版）
    
    参数:
        use_downsamp: 是否启用降采样（默认False，由用户在预处理阶段控制）
        max_points: 降采样最大点数（默认1000000，基本无限制）
    """
    x = np.asarray(x).flatten()
    y = np.asarray(y).flatten()
    
    # 降采样减少计算量（可选）
    if use_downsamp:
        if len(x) > max_points:
            x = signal.resample(x, max_points)
        if len(y) > max_points:
            y = signal.resample(y, max_points)
    
    try:
        from dtaidistance import dtw
        return dtw.distance(x, y)
    except ImportError:
        # 简化版DTW实现（使用降采样后的小数据）
        n, m = len(x), len(y)
        dtw_matrix = np.inf * np.ones((n+1, m+1))
        dtw_matrix[0, 0] = 0
        
        for i in range(1, n+1):
            for j in range(1, m+1):
                cost = abs(x[i-1] - y[j-1])
                dtw_matrix[i, j] = cost + min(dtw_matrix[i-1, j], 
                                               dtw_matrix[i, j-1], 
                                               dtw_matrix[i-1, j-1])
        return dtw_matrix[n, m]


def ssim_index(x, y):
    """结构相似性指数"""
    x, y = ensure_same_length(x, y)
    mu_x, mu_y = np.mean(x), np.mean(y)
    sigma_x, sigma_y = np.std(x), np.std(y)
    sigma_xy = np.mean((x - mu_x) * (y - mu_y))
    
    c1, c2 = 1e-10, 1e-10
    ssim = ((2*mu_x*mu_y + c1) * (2*sigma_xy + c2)) / \
           ((mu_x**2 + mu_y**2 + c1) * (sigma_x**2 + sigma_y**2 + c2))
    return ssim


def mse_error(x, y):
    """均方误差"""
    x, y = ensure_same_length(x, y)
    return mean_squared_error(x, y)


def rmse_error(x, y):
    """均方根误差"""
    return np.sqrt(mse_error(x, y))


def mae_error(x, y):
    """平均绝对误差"""
    x, y = ensure_same_length(x, y)
    return mean_absolute_error(x, y)


def normalized_mutual_info(x, y):
    """标准化互信息"""
    x, y = ensure_same_length(x, y)
    # 将连续数据离散化
    bins = min(20, len(x) // 10)
    if bins < 2:
        bins = 2
    x_discrete = np.digitize(x, np.linspace(x.min(), x.max(), bins))
    y_discrete = np.digitize(y, np.linspace(y.min(), y.max(), bins))
    mi = mutual_info_score(x_discrete, y_discrete)
    h_x = entropy(np.bincount(x_discrete, minlength=bins+1))
    h_y = entropy(np.bincount(y_discrete, minlength=bins+1))
    if h_x > 0 and h_y > 0:
        return 2 * mi / (h_x + h_y)
    return 0


def bhattacharyya_dist(x, y):
    """巴氏距离"""
    x, y = ensure_same_length(x, y)
    bins = min(50, len(x) // 5)
    if bins < 2:
        bins = 2
    hist_x, _ = np.histogram(x, bins=bins, density=True)
    hist_y, _ = np.histogram(y, bins=bins, density=True)
    hist_x = hist_x / np.sum(hist_x)
    hist_y = hist_y / np.sum(hist_y)
    bc = np.sum(np.sqrt(hist_x * hist_y))
    return -np.log(bc + 1e-10)


def max_info_coefficient(x, y):
    """最大信息系数（优化版）"""
    x, y = ensure_same_length(x, y)
    n = len(x)
    
    # 优化：限制最大bin数和组合数
    max_bins = min(10, int(np.sqrt(n/10)))  # 减少从20到10
    if max_bins < 2:
        max_bins = 2
    
    # 只检查有限的网格组合（主要组合）
    mic_score = 0
    # 使用主要的对角线组合（更少的计算）
    for bins_xy in range(2, max_bins+1):
        x_discrete = np.digitize(x, np.linspace(x.min(), x.max(), bins_xy))
        y_discrete = np.digitize(y, np.linspace(y.min(), y.max(), bins_xy))
        mi = mutual_info_score(x_discrete, y_discrete)
        mic_score = max(mic_score, mi / np.log2(bins_xy + 1e-10))
    
    return mic_score


def energy_difference(x, y):
    """能量差"""
    x, y = ensure_same_length(x, y)
    ex, ey = np.sum(x**2), np.sum(y**2)
    return abs(ex - ey) / (max(ex, ey) + 1e-10)


def waveform_overlap(x, y):
    """波形重叠指数"""
    x, y = ensure_same_length(x, y)
    # 归一化
    x_n = (x - np.min(x)) / (np.max(x) - np.min(x) + 1e-10)
    y_n = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-10)
    overlap = np.sum(np.minimum(x_n, y_n)) / len(x)
    return overlap


def spectral_coherence(x, y, fs=1.0):
    """谱相干性"""
    x, y = ensure_same_length(x, y)
    f, csd = signal.csd(x, y, fs=fs, nperseg=min(256, len(x)//4))
    pxx = signal.welch(x, fs=fs, nperseg=min(256, len(x)//4))[1]
    pyy = signal.welch(y, fs=fs, nperseg=min(256, len(x)//4))[1]
    coh = np.abs(csd)**2 / (pxx * pyy + 1e-10)
    return np.mean(coh)


# 时域方法映射
TIME_DOMAIN_METHODS = {
    '欧几里得距离': euclidean_dist,
    '曼哈顿距离': manhattan_dist,
    '切比雪夫距离': chebyshev_dist,
    '闵可夫斯基距离': minkowski_dist,
    '余弦相似度': cosine_sim,
    '皮尔逊相关系数': pearson_corr,
    '斯皮尔曼等级相关': spearman_corr,
    '肯德尔秩相关': kendall_corr,
    '互相关系数': cross_correlation_coeff,
    '互相关峰值': cross_correlation_peak,
    '动态时间规整(DTW)': dtw_distance,
    '结构相似性(SSIM)': ssim_index,
    '均方误差(MSE)': mse_error,
    '均方根误差(RMSE)': rmse_error,
    '平均绝对误差(MAE)': mae_error,
    '标准化互信息(NMI)': normalized_mutual_info,
    '巴氏距离': bhattacharyya_dist,
    '最大信息系数(MIC)': max_info_coefficient,
    '能量差': energy_difference,
    '波形重叠指数': waveform_overlap,
    '谱相干性': spectral_coherence,
    '协方差': lambda x, y: np.cov(x, y)[0, 1],
    '归一化互相关': cross_correlation_coeff
}


# ========================
# 频域相似性度量
# ========================

def get_spectrum(x, fs=1.0):
    """获取单边幅度谱"""
    x = np.asarray(x, dtype=float).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    n = len(x)
    fft_vals = np.fft.rfft(x)
    mag = np.abs(fft_vals) / n
    mag[1:] *= 2  # 除直流分量外乘以2
    return mag


def freq_euclidean(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return euclidean(sx, sy)


def freq_manhattan(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return cityblock(sx, sy)


def freq_cosine(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx.reshape(1, -1)
    sy = sy.reshape(1, -1)
    return float(cosine_similarity(sx, sy)[0, 0])


def freq_pearson(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return pearsonr(sx, sy)[0]


def freq_mse(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return mean_squared_error(sx, sy)


def freq_rmse(x, y, fs=1.0):
    return np.sqrt(freq_mse(x, y, fs))


def freq_mae(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return mean_absolute_error(sx, sy)


def freq_crosscorr(x, y, fs=1.0):
    """频域互相关系数（FFT加速版）"""
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx - np.mean(sx)
    sy = sy - np.mean(sy)
    
    # FFT加速互相关计算
    n = max(len(sx), len(sy))
    fft_size = 1
    while fft_size < 2 * n - 1:
        fft_size *= 2
    Sx = np.fft.fft(sx, fft_size)
    Sy = np.fft.fft(sy, fft_size)
    corr = np.fft.ifft(Sx * np.conj(Sy)).real
    
    return np.max(np.abs(corr)) / (np.std(sx) * np.std(sy) * len(sx) + 1e-10)


def freq_dtw(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return dtw_distance(sx, sy)


def freq_ssim(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return ssim_index(sx, sy)


def freq_bhattacharyya(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx / (np.sum(sx) + 1e-10)
    sy = sy / (np.sum(sy) + 1e-10)
    bc = np.sum(np.sqrt(sx * sy))
    return -np.log(bc + 1e-10)


def freq_energy_diff(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    return abs(np.sum(sx**2) - np.sum(sy**2)) / (max(np.sum(sx**2), np.sum(sy**2)) + 1e-10)


def freq_entropy_diff(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx / (np.sum(sx) + 1e-10)
    sy = sy / (np.sum(sy) + 1e-10)
    return abs(entropy(sx) - entropy(sy))


def freq_kl_divergence(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx / (np.sum(sx) + 1e-10)
    sy = sy / (np.sum(sy) + 1e-10)
    return np.sum(sx * np.log((sx + 1e-10) / (sy + 1e-10)))


def freq_js_divergence(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    sx = sx / (np.sum(sx) + 1e-10)
    sy = sy / (np.sum(sy) + 1e-10)
    m = 0.5 * (sx + sy)
    kl1 = np.sum(sx * np.log((sx + 1e-10) / (m + 1e-10)))
    kl2 = np.sum(sy * np.log((sy + 1e-10) / (m + 1e-10)))
    return 0.5 * (kl1 + kl2)


def freq_coherence(x, y, fs=1.0):
    return spectral_coherence(x, y, fs)


def freq_centroid_diff(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    freqs = np.fft.rfftfreq(len(x), d=1/fs)
    cx = np.sum(freqs * sx) / (np.sum(sx) + 1e-10)
    cy = np.sum(freqs * sy) / (np.sum(sy) + 1e-10)
    return abs(cx - cy)


def freq_bandwidth_diff(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    freqs = np.fft.rfftfreq(len(x), d=1/fs)
    cx = np.sum(freqs * sx) / (np.sum(sx) + 1e-10)
    cy = np.sum(freqs * sy) / (np.sum(sy) + 1e-10)
    bx = np.sqrt(np.sum((freqs - cx)**2 * sx) / (np.sum(sx) + 1e-10))
    by = np.sqrt(np.sum((freqs - cy)**2 * sy) / (np.sum(sy) + 1e-10))
    return abs(bx - by)


def freq_flatness_diff(x, y, fs=1.0):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    gx = np.exp(np.mean(np.log(sx + 1e-10))) / (np.mean(sx) + 1e-10)
    gy = np.exp(np.mean(np.log(sy + 1e-10))) / (np.mean(sy) + 1e-10)
    return abs(gx - gy)


def freq_rolloff_diff(x, y, fs=1.0, roll_percent=0.85):
    sx, sy = get_spectrum(x, fs), get_spectrum(y, fs)
    freqs = np.fft.rfftfreq(len(x), d=1/fs)
    
    cumsum_x = np.cumsum(sx)
    rx = freqs[np.searchsorted(cumsum_x, roll_percent * cumsum_x[-1])] if cumsum_x[-1] > 0 else 0
    cumsum_y = np.cumsum(sy)
    ry = freqs[np.searchsorted(cumsum_y, roll_percent * cumsum_y[-1])] if cumsum_y[-1] > 0 else 0
    return abs(rx - ry)


# 频域方法映射
FREQ_DOMAIN_METHODS = {
    '频谱欧几里得距离': freq_euclidean,
    '频谱曼哈顿距离': freq_manhattan,
    '频谱余弦相似度': freq_cosine,
    '频谱皮尔逊相关': freq_pearson,
    '频谱MSE': freq_mse,
    '频谱RMSE': freq_rmse,
    '频谱MAE': freq_mae,
    '频谱互相关': freq_crosscorr,
    '频谱DTW': freq_dtw,
    '频谱SSIM': freq_ssim,
    '频谱巴氏距离': freq_bhattacharyya,
    '频谱能量差': freq_energy_diff,
    '频谱熵差': freq_entropy_diff,
    '频谱KL散度': freq_kl_divergence,
    '频谱JS散度': freq_js_divergence,
    '频谱相干性': freq_coherence,
    '频谱重心差': freq_centroid_diff,
    '频谱带宽差': freq_bandwidth_diff,
    '频谱平坦度差': freq_flatness_diff,
    '频谱 rolloff 差': freq_rolloff_diff
}


# ========================
# 矩阵转换方法（15+种）
# ========================

MATRIX_METHODS = [
    '自相关矩阵',
    '协方差矩阵',
    '相关系数矩阵',
    'Hankel矩阵',
    'Toeplitz矩阵',
    'STFT时频矩阵',
    '连续小波变换(CWT)',
    '短时自相关矩阵',
    '分段均值矩阵',
    '分段标准差矩阵',
    '相空间重构矩阵',
    '差分矩阵',
    '累积和矩阵',
    '对数谱矩阵',
    '功率谱密度矩阵',
    'Mel频谱矩阵',
    '离散余弦变换矩阵',
    '希尔伯特谱矩阵',
    'EMD本征模态矩阵',
    'VMD模态矩阵'
]


def autocorrelation_matrix(x, lag=50):
    """自相关矩阵（FFT加速版）"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    lag = min(lag, len(x)//2)
    
    # FFT加速自相关计算（O(n log n)替代O(n²)）
    n = len(x)
    fft_size = 1
    while fft_size < 2 * n - 1:
        fft_size *= 2
    X = np.fft.fft(x, fft_size)
    acf = np.fft.ifft(X * np.conj(X)).real[:n]
    acf = acf / acf[0]  # 归一化
    
    n = min(lag, len(acf))
    mat = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            mat[i, j] = acf[abs(i-j)]
    return mat


def covariance_matrix(x, segments=10):
    """协方差矩阵 - 将信号分段后计算协方差"""
    x = np.asarray(x).flatten()
    seg_len = len(x) // segments
    data_matrix = np.array([x[i*seg_len:(i+1)*seg_len] for i in range(segments)])
    return np.cov(data_matrix.T)


def correlation_matrix(x, segments=10):
    """相关系数矩阵"""
    x = np.asarray(x).flatten()
    seg_len = len(x) // segments
    data_matrix = np.array([x[i*seg_len:(i+1)*seg_len] for i in range(segments)])
    return np.corrcoef(data_matrix.T)


def hankel_matrix(x, rows=50):
    """Hankel矩阵"""
    x = np.asarray(x).flatten()
    rows = min(rows, len(x)//2)
    cols = len(x) - rows + 1
    mat = np.zeros((rows, cols))
    for i in range(rows):
        mat[i, :] = x[i:i+cols]
    return mat


def toeplitz_matrix(x, size=50):
    """Toeplitz矩阵"""
    x = np.asarray(x).flatten()
    size = min(size, len(x)//2)
    c = x[:size]
    r = x[:size]
    from scipy.linalg import toeplitz
    return toeplitz(c, r)


def stft_matrix(x, fs=1.0, nperseg=256):
    """STFT时频矩阵（优化版）"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    # 优化：限制窗长，加速计算
    nperseg = min(nperseg, len(x)//4, 512)  # 最大512点
    if nperseg < 8:
        nperseg = 8
    f, t, Zxx = signal.stft(x, fs=fs, nperseg=nperseg)
    return np.abs(Zxx)


def cwt_matrix(x, fs=1.0, wavelet='cmor1.5-1.0'):
    """连续小波变换矩阵（优化版）"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    try:
        import pywt
        # 优化：限制尺度数，最大32（原128）
        scales = np.arange(1, min(32, len(x)//8))
        coef, _ = pywt.cwt(x, scales, wavelet)
        return np.abs(coef)
    except ImportError:
        # 使用Morlet小波的简化实现
        return _simplified_cwt(x, fs)


def _simplified_cwt(x, fs=1.0):
    """简化版CWT（使用Morlet小波，优化版）"""
    n = len(x)
    # 优化：限制尺度数
    scales = np.arange(1, min(32, n//8))
    coef = np.zeros((len(scales), n))
    for i, scale in enumerate(scales):
        # Morlet小波
        sigma = scale / fs
        t = np.arange(-3*sigma, 3*sigma, 1/fs)
        if len(t) < 3:
            t = np.linspace(-3*sigma, 3*sigma, 7)
        wavelet = np.exp(-t**2 / (2*sigma**2)) * np.cos(2*np.pi*t/sigma)
        wavelet = wavelet / np.linalg.norm(wavelet)
        conv = np.convolve(x, wavelet, mode='same')
        coef[i, :] = np.abs(conv)
    return coef


def short_time_autocorr_matrix(x, window_size=256, hop=128):
    """短时自相关矩阵（优化版）"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    # 优化：限制窗口大小
    window_size = min(window_size, len(x)//4, 256)
    hop = min(hop, window_size//2)
    n = len(x)
    num_windows = (n - window_size) // hop + 1
    max_lag = window_size // 2
    mat = np.zeros((num_windows, max_lag))
    for i in range(num_windows):
        start = i * hop
        window = x[start:start+window_size]
        acf = np.correlate(window, window, mode='full')
        acf = acf[len(acf)//2:len(acf)//2+max_lag]
        if acf[0] > 0:
            acf = acf / acf[0]
        mat[i, :] = acf
    return mat


def segmented_mean_matrix(x, segments=20, subsegments=10):
    """分段均值矩阵"""
    x = np.asarray(x).flatten()
    seg_len = len(x) // segments
    mat = np.zeros((segments, subsegments))
    for i in range(segments):
        seg = x[i*seg_len:(i+1)*seg_len]
        sub_len = len(seg) // subsegments
        for j in range(subsegments):
            mat[i, j] = np.mean(seg[j*sub_len:(j+1)*sub_len])
    return mat


def segmented_std_matrix(x, segments=20, subsegments=10):
    """分段标准差矩阵"""
    x = np.asarray(x).flatten()
    seg_len = len(x) // segments
    mat = np.zeros((segments, subsegments))
    for i in range(segments):
        seg = x[i*seg_len:(i+1)*seg_len]
        sub_len = len(seg) // subsegments
        for j in range(subsegments):
            mat[i, j] = np.std(seg[j*sub_len:(j+1)*sub_len])
    return mat


def phase_space_matrix(x, dim=3, tau=1):
    """相空间重构矩阵（Takens嵌入）"""
    x = np.asarray(x).flatten()
    n = len(x) - (dim - 1) * tau
    if n <= 0:
        n = max(1, len(x) - dim + 1)
        tau = 1
    mat = np.zeros((n, dim))
    for i in range(dim):
        mat[:, i] = x[i*tau:i*tau+n]
    return mat


def difference_matrix(x, order=1, segments=20):
    """差分矩阵"""
    x = np.asarray(x).flatten()
    for _ in range(order):
        x = np.diff(x)
    seg_len = len(x) // segments
    mat = np.zeros((segments, seg_len))
    for i in range(segments):
        mat[i, :] = x[i*seg_len:(i+1)*seg_len]
    return mat


def cumulative_sum_matrix(x, segments=20):
    """累积和矩阵"""
    x = np.asarray(x).flatten()
    cs = np.cumsum(x)
    seg_len = len(cs) // segments
    mat = np.zeros((segments, seg_len))
    for i in range(segments):
        mat[i, :] = cs[i*seg_len:(i+1)*seg_len]
    return mat


def log_spectrogram_matrix(x, fs=1.0, nperseg=256):
    """对数谱矩阵"""
    Z = stft_matrix(x, fs, nperseg)
    return np.log(Z + 1e-10)


def psd_matrix(x, fs=1.0, nperseg=256, overlap_ratio=0.5):
    """功率谱密度矩阵（优化版）"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    # 优化：限制窗长，最大512点
    nperseg = min(nperseg, len(x)//4, 512)
    if nperseg < 8:
        nperseg = 8
    noverlap = int(nperseg * overlap_ratio)
    f, Pxx = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
    # 构建多分辨率PSD矩阵
    windows = [nperseg, nperseg//2, nperseg//4]
    mat = []
    for win in windows:
        if win < 8:
            continue
        f_win, Pxx_win = signal.welch(x, fs=fs, nperseg=win)
        mat.append(Pxx_win)
    if mat:
        max_len = max(len(m) for m in mat)
        mat_padded = [np.pad(m, (0, max_len-len(m)), 'constant') for m in mat]
        return np.array(mat_padded)
    return Pxx.reshape(1, -1)


def mel_spectrogram_matrix(x, fs=1.0, n_mels=128):
    """Mel频谱矩阵"""
    try:
        import librosa
        S = librosa.feature.melspectrogram(y=x.astype(float), sr=fs, n_mels=n_mels)
        return librosa.power_to_db(S, ref=np.max)
    except ImportError:
        # 简化Mel频谱实现
        return _simplified_mel_spectrogram(x, fs, n_mels)


def _simplified_mel_spectrogram(x, fs=1.0, n_mels=128):
    """简化Mel频谱"""
    x = np.asarray(x).flatten()
    Z = stft_matrix(x, fs)
    n_fft = Z.shape[0] * 2 - 2
    freqs = np.linspace(0, fs/2, Z.shape[0])
    mel_freqs = 2595 * np.log10(1 + freqs / 700)
    mel_points = np.linspace(mel_freqs[0], mel_freqs[-1], n_mels+2)
    
    mel_spec = np.zeros((n_mels, Z.shape[1]))
    for i in range(n_mels):
        f_left = 700 * (10**(mel_points[i]/2595) - 1)
        f_center = 700 * (10**(mel_points[i+1]/2595) - 1)
        f_right = 700 * (10**(mel_points[i+2]/2595) - 1)
        
        for j, f in enumerate(freqs):
            if f_left <= f <= f_right:
                if f < f_center:
                    weight = (f - f_left) / (f_center - f_left + 1e-10)
                else:
                    weight = (f_right - f) / (f_right - f_center + 1e-10)
                mel_spec[i, :] += weight * Z[j, :]
    return np.log10(mel_spec + 1e-10)


def dct_matrix(x, segments=20):
    """离散余弦变换矩阵"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    seg_len = len(x) // segments
    mat = np.zeros((segments, seg_len))
    for i in range(segments):
        seg = x[i*seg_len:(i+1)*seg_len]
        from scipy.fftpack import dct
        mat[i, :] = dct(seg, type=2, norm='ortho')
    return mat


def hilbert_spectrum_matrix(x, fs=1.0):
    """希尔伯特谱矩阵"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    analytic = signal.hilbert(x)
    amplitude = np.abs(analytic)
    instantaneous_phase = np.unwrap(np.angle(analytic))
    instantaneous_freq = np.diff(instantaneous_phase) / (2.0 * np.pi) * fs
    
    # 构建时频表示
    segments = 50
    seg_len = len(instantaneous_freq) // segments
    mat = np.zeros((segments, seg_len))
    for i in range(segments):
        mat[i, :] = instantaneous_freq[i*seg_len:(i+1)*seg_len] * amplitude[i*seg_len:(i+1)*seg_len]
    return mat


def emd_matrix(x, max_imf=8):
    """EMD本征模态函数矩阵"""
    x = np.asarray(x).flatten()
    # 去趋势和去直流分量（防止近零Hz出现异常大值）
    x = x - np.mean(x)
    if len(x) > 10:
        x = signal.detrend(x)
    try:
        import PyEMD
        emd = PyEMD.EMD()
        imfs = emd(x, max_imf=max_imf)
        return imfs.T
    except ImportError:
        # 简化EMD实现
        return _simplified_emd(x, max_imf)


def _simplified_emd(x, max_imf=8):
    """简化EMD实现"""
    x = np.asarray(x).flatten()
    imfs = []
    residual = x.copy()
    
    for _ in range(max_imf):
        if len(residual) < 10:
            break
        h = residual.copy()
        for _ in range(10):  # 筛分迭代
            maxima = signal.find_peaks(h)[0]
            minima = signal.find_peaks(-h)[0]
            if len(maxima) < 2 or len(minima) < 2:
                break
            from scipy.interpolate import CubicSpline
            upper = CubicSpline(maxima, h[maxima])(np.arange(len(h)))
            lower = CubicSpline(minima, h[minima])(np.arange(len(h)))
            mean_env = (upper + lower) / 2
            h = h - mean_env
        imfs.append(h)
        residual = residual - h
    
    imfs.append(residual)
    return np.array(imfs).T


def vmd_matrix(x, K=5, alpha=2000, tau=0):
    """VMD模态分解矩阵"""
    try:
        import vmdpy
        u, _, _ = vmdpy.VMD(x, alpha, tau, K, 0, 1, 1e-7)
        return u.T
    except ImportError:
        # 回退到EMD
        return _simplified_emd(x, K)


MATRIX_METHOD_MAP = {
    '自相关矩阵': autocorrelation_matrix,
    '协方差矩阵': covariance_matrix,
    '相关系数矩阵': correlation_matrix,
    'Hankel矩阵': hankel_matrix,
    'Toeplitz矩阵': toeplitz_matrix,
    'STFT时频矩阵': stft_matrix,
    '连续小波变换(CWT)': cwt_matrix,
    '短时自相关矩阵': short_time_autocorr_matrix,
    '分段均值矩阵': segmented_mean_matrix,
    '分段标准差矩阵': segmented_std_matrix,
    '相空间重构矩阵': phase_space_matrix,
    '差分矩阵': difference_matrix,
    '累积和矩阵': cumulative_sum_matrix,
    '对数谱矩阵': log_spectrogram_matrix,
    '功率谱密度矩阵': psd_matrix,
    'Mel频谱矩阵': mel_spectrogram_matrix,
    '离散余弦变换矩阵': dct_matrix,
    '希尔伯特谱矩阵': hilbert_spectrum_matrix,
    'EMD本征模态矩阵': emd_matrix,
    'VMD模态矩阵': vmd_matrix
}


# ========================
# 计算相似性并返回结果
# ========================

def compute_time_similarity(data_a, data_b, method_name, fs=1.0):
    """计算时域相似性，返回多参数指标
    
    返回字典:
        value: 主相似性值
        indicators: {参数名: 值} 的字典，包含多个衍生指标
    """
    if method_name not in TIME_DOMAIN_METHODS:
        raise ValueError(f"未知的时域相似性方法: {method_name}")
    
    func = TIME_DOMAIN_METHODS[method_name]
    x = np.asarray(data_a).flatten()
    y = np.asarray(data_b).flatten()
    
    try:
        result = func(x, y)
        value = float(result)
        
        # 计算多参数指标
        indicators = {'主值': value}
        
        # 计算数据统计特征（用于后续评估）
        x_mean, x_std = np.mean(x), np.std(x)
        y_mean, y_std = np.mean(y), np.std(y)
        x_len, y_len = len(x), len(y)
        
        # 根据方法类型计算不同的衍生指标
        if method_name in ['相关系数', '皮尔逊相关系数']:
            indicators['绝对值'] = abs(value)
            indicators['显著性'] = float(np.abs(value) > 0.7)
            indicators['方向'] = '正相关' if value > 0 else ('负相关' if value < 0 else '无相关')
        
        elif method_name in ['互相关系数', '归一化互相关']:
            indicators['峰值位置'] = float(np.argmax(np.correlate(x, y, mode='full')) - (len(x)-1))
            indicators['归一化值'] = float(value / (x_std * y_std + 1e-10)) if x_std > 0 and y_std > 0 else 0
        
        elif method_name in ['欧氏距离', '曼哈顿距离', '切比雪夫距离']:
            indicators['归一化距离'] = float(value / max(np.std(x), np.std(y), 1e-10))
            indicators['相对距离'] = float(value / max(np.abs(x_mean), np.abs(y_mean), 1e-10))
        
        elif method_name in ['Cos相似度', '余弦相似度']:
            indicators['角度(度)'] = float(np.arccos(min(1, max(-1, value))) * 180 / np.pi)
            indicators['相似度等级'] = float(min(1, max(0, (value + 1) / 2)))
        
        elif method_name in ['互信息', '归一化互信息']:
            indicators['信息增益'] = float(value)
            indicators['归一化值'] = float(value / max(np.log2(x_len), np.log2(y_len), 1e-10))
        
        elif method_name in ['DTW', '动态时间规整']:
            indicators['归一化距离'] = float(value / max(len(x), len(y)))
            indicators['时间扭曲程度'] = float(value / np.sqrt(len(x) * len(y)))
        
        elif method_name in ['编辑距离', 'Levenshtein距离']:
            indicators['归一化距离'] = float(value / max(len(x), len(y)))
            indicators['相似度'] = float(1 - value / max(len(x), len(y)))
        
        elif method_name in ['Jaccard相似度', 'Dice系数']:
            indicators['相似度等级'] = value
            indicators['差异度'] = float(1 - value)
        
        # 通用指标
        indicators['数据A均值'] = float(x_mean)
        indicators['数据B均值'] = float(y_mean)
        indicators['数据A标准差'] = float(x_std)
        indicators['数据B标准差'] = float(y_std)
        indicators['数据A长度'] = int(x_len)
        indicators['数据B长度'] = int(y_len)
        
        return {'value': value, 'indicators': indicators}
    except Exception as e:
        raise RuntimeError(f"计算{method_name}失败: {e}")


def compute_freq_similarity(data_a, data_b, method_name, fs=1.0):
    """计算频域相似性，返回多参数指标
    
    返回字典:
        value: 主相似性值
        indicators: {参数名: 值} 的字典，包含多个衍生指标
    """
    if method_name not in FREQ_DOMAIN_METHODS:
        raise ValueError(f"未知的频域相似性方法: {method_name}")
    
    func = FREQ_DOMAIN_METHODS[method_name]
    x = np.asarray(data_a).flatten()
    y = np.asarray(data_b).flatten()
    
    try:
        result = func(x, y, fs)
        value = float(result)
        
        # 计算多参数指标
        indicators = {'主值': value}
        
        # 计算数据统计特征
        x_mean, x_std = np.mean(x), np.std(x)
        y_mean, y_std = np.mean(y), np.std(y)
        x_len, y_len = len(x), len(y)
        
        # 根据方法类型计算不同的衍生指标
        if method_name in ['频谱相关系数', '幅度谱相关']:
            indicators['绝对值'] = abs(value)
            indicators['显著性'] = float(np.abs(value) > 0.7)
        
        elif method_name in ['功率谱相似度', '能量谱相似度']:
            indicators['归一化值'] = float(value / max(x_std**2, y_std**2, 1e-10))
            indicators['能量比'] = float(np.sum(x**2) / np.sum(y**2)) if np.sum(y**2) > 0 else 0
        
        elif method_name in ['相位谱相似度', '相位一致性']:
            indicators['一致性等级'] = float(min(1, max(0, (value + 1) / 2)))
        
        elif method_name in ['频率响应相似度']:
            indicators['响应匹配度'] = float(min(1, max(0, value)))
        
        # 通用指标
        indicators['数据A均值'] = float(x_mean)
        indicators['数据B均值'] = float(y_mean)
        indicators['数据A标准差'] = float(x_std)
        indicators['数据B标准差'] = float(y_std)
        indicators['数据A长度'] = int(x_len)
        indicators['数据B长度'] = int(y_len)
        
        return {'value': value, 'indicators': indicators}
    except Exception as e:
        raise RuntimeError(f"计算{method_name}失败: {e}")


def convert_to_matrix(data, method_name, fs=1.0, **kwargs):
    """将时域数据转换为矩阵"""
    if method_name not in MATRIX_METHOD_MAP:
        raise ValueError(f"未知的矩阵转换方法: {method_name}")
    
    func = MATRIX_METHOD_MAP[method_name]
    x = np.asarray(data).flatten()
    
    # 获取函数签名，只传递接受的参数
    import inspect
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    call_args = {'x': x}
    if 'fs' in params:
        call_args['fs'] = fs
    # 添加其他合法参数
    for key in kwargs:
        if key in params and key not in ['x', 'fs']:
            call_args[key] = kwargs[key]
    
    try:
        return func(**call_args)
    except Exception as e:
        raise RuntimeError(f"矩阵转换{method_name}失败: {e}")


# ========================
# 数据预处理模块：粗粒化与窗口截断
# ========================

# 粗粒化方法注册表：方法名 -> (函数, 参数定义, 效果说明)
# 参数定义: [(参数键, 显示名, 最小值, 最大值, 步长, 默认值, 说明), ...]
COARSENING_METHODS = {}


def _register_coarsening(name, func, params, tooltip):
    COARSENING_METHODS[name] = {'func': func, 'params': params, 'tooltip': tooltip}


# ---- 1. 均值抽样 ----
def _coarse_mean(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.mean(x[:n*factor].reshape(n, factor), axis=1)

_register_coarsening('均值抽样', _coarse_mean,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取均值合并为1点。值越大输出越短、越平滑，细节丢失越多。')],
    '将每factor个相邻样本取算术平均合并为一个点。适用于抑制高频随机噪声、突出低频趋势，因子越大降采样率越高。')

# ---- 2. 最大值抽样 ----
def _coarse_max(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.max(x[:n*factor].reshape(n, factor), axis=1)

_register_coarsening('最大值抽样', _coarse_max,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取最大值。保留峰值特征，适合冲击/瞬态信号。')],
    '每factor个样本取最大值，保留峰值与瞬态事件，对正冲击敏感。')

# ---- 3. 最小值抽样 ----
def _coarse_min(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.min(x[:n*factor].reshape(n, factor), axis=1)

_register_coarsening('最小值抽样', _coarse_min,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取最小值。保留谷值特征。')],
    '每factor个样本取最小值，保留负向谷值与下冲事件。')

# ---- 4. 中值抽样 ----
def _coarse_median(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.median(x[:n*factor].reshape(n, factor), axis=1)

_register_coarsening('中值抽样', _coarse_median,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取中位数。对离群点鲁棒，抗脉冲干扰。')],
    '每factor个样本取中位数，对离群点与脉冲干扰鲁棒，保留信号主体形态。')

# ---- 5. 求和抽样 ----
def _coarse_sum(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.sum(x[:n*factor].reshape(n, factor), axis=1)

_register_coarsening('求和抽样', _coarse_sum,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点求和。等效能量累积，适合能量/功率分析。')],
    '每factor个样本求和，等效能量累积，适合能量或功率类信号聚合。')

# ---- 6. RMS抽样 ----
def _coarse_rms(x, factor=10, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.sqrt(np.mean(x[:n*factor].reshape(n, factor)**2, axis=1))

_register_coarsening('RMS抽样', _coarse_rms,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取均方根。反映能量水平，常用于振动评价。')],
    '每factor个样本取均方根值(RMS)，反映局部能量水平，是振动评价的常用粗粒化。')

# ---- 7. 分位数抽样 ----
def _coarse_quantile(x, factor=10, q=0.5, **_):
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    return np.quantile(x[:n*factor].reshape(n, factor), q, axis=1)

_register_coarsening('分位数抽样', _coarse_quantile,
    [('factor', '抽样因子', 2, 1000, 1, 10, '每factor个点取分位数。'),
     ('q', '分位数q', 0.0, 1.0, 0.05, 0.5, '0=最小值, 0.5=中位数, 1=最大值。控制保留分布位置。')],
    '每factor个样本取指定分位数，q=0.5等同中值抽样，可灵活选择分布位置。')

# ---- 8. 移动平均 ----
def _coarse_moving_avg(x, window=20, **_):
    window = max(1, int(window))
    if window >= len(x):
        return np.array([np.mean(x)])
    cumsum = np.cumsum(np.insert(x, 0, 0))
    return (cumsum[window:] - cumsum[:-window]) / window

_register_coarsening('移动平均', _coarse_moving_avg,
    [('window', '窗口长度', 2, 10000, 1, 20, '滑动窗口点数。越大越平滑，但滞后增加。')],
    '滑动窗口算术平均，平滑曲线、抑制噪声，窗口越大平滑越强但相位滞后增大。')

# ---- 9. 移动中值 ----
def _coarse_moving_median(x, window=20, **_):
    window = max(1, int(window))
    if window >= len(x):
        return np.array([np.median(x)])
    from scipy.ndimage import median_filter
    return median_filter(x, size=window, mode='nearest')[window-1::1][:max(1, len(x)-window+1)]

_register_coarsening('移动中值', _coarse_moving_median,
    [('window', '窗口长度', 2, 10000, 1, 20, '滑动窗口点数。去除脉冲噪声效果好。')],
    '滑动中值滤波，有效去除脉冲/椒盐噪声，保留边缘跳变。')

# ---- 10. 指数加权移动平均(EWMA) ----
def _coarse_ewma(x, alpha=0.3, **_):
    alpha = float(np.clip(alpha, 1e-3, 1.0))
    out = np.empty_like(x, dtype=float)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i-1]
    return out

_register_coarsening('指数加权移动平均', _coarse_ewma,
    [('alpha', '平滑系数α', 0.001, 1.0, 0.01, 0.3, '越大越跟踪当前值(1=无平滑)，越小越平滑但滞后大。')],
    '指数加权移动平均(EWMA)，对新数据加权更高，α越小平滑越强、滞后越大。')

# ---- 11. 低通滤波降采样 ----
def _coarse_lp_decimate(x, factor=10, cutoff=0.4, fs=1.0, **_):
    factor = max(1, int(factor))
    if factor == 1:
        return x.copy()
    from scipy.signal import butter, filtfilt
    nyq = 0.5 * fs
    wn = float(np.clip(cutoff, 1e-4, 0.99))
    b, a = butter(4, wn, btype='low')
    y = filtfilt(b, a, x)
    return y[::factor]

_register_coarsening('低通滤波降采样', _coarse_lp_decimate,
    [('factor', '降采样因子', 2, 1000, 1, 10, '每factor个点取1点。'),
     ('cutoff', '归一化截止频率', 0.001, 0.99, 0.01, 0.4, '相对Nyquist的归一化频率。越小滤除高频越多。')],
    '先低通滤波再降采样，防止混叠，是标准降采样流程，cutoff控制抗混叠强度。')

# ---- 12. 小波近似系数 ----
def _coarse_wavelet(x, level=3, wavelet_idx=0, **_):
    import pywt
    wavelets = ['db4', 'db2', 'sym4', 'coif3']
    wavelet = wavelets[int(wavelet_idx) % len(wavelets)]
    level = max(1, int(level))
    max_lvl = pywt.dwt_max_level(len(x), pywt.Wavelet(wavelet))
    level = min(level, max(1, max_lvl))
    coeffs = pywt.wavedec(x, wavelet, level=level)
    approx = coeffs[0]
    return approx

_register_coarsening('小波近似系数', _coarse_wavelet,
    [('level', '分解层数', 1, 15, 1, 3, '越大输出越短，保留越低频成分。'),
     ('wavelet_idx', '小波基(0=db4,1=db2,2=sym4,3=coif3)', 0, 3, 1, 0, '不同小波基的平滑与正交特性不同。')],
    '离散小波分解取近似系数，保留低频趋势、丢弃高频细节，level越大压缩比越高。')

# ---- 13. PCA降维 ----
def _coarse_pca(x, n_components=10, segment_len=50, **_):
    n_components = max(1, int(n_components))
    segment_len = max(2, int(segment_len))
    n_seg = len(x) // segment_len
    if n_seg < n_components:
        n_components = max(1, n_seg)
    if n_seg == 0:
        return x.copy()
    mat = x[:n_seg*segment_len].reshape(n_seg, segment_len)
    from sklearn.decomposition import PCA
    pca = PCA(n_components=n_components)
    pca.fit(mat)
    proj = pca.transform(mat)
    return proj.flatten()

_register_coarsening('PCA降维', _coarse_pca,
    [('n_components', '主成分数', 1, 100, 1, 10, '保留的主成分个数。越多信息越全但压缩比降低。'),
     ('segment_len', '分段长度', 2, 500, 1, 50, '每段样本数，构成PCA样本矩阵的列数。')],
    '将信号分段后做PCA主成分分析，提取主要变化模式，适合周期/准周期信号降维。')

# ---- 14. 分段聚类中心 ----
def _coarse_segment_cluster(x, n_segments=20, n_clusters=5, **_):
    n_segments = max(1, int(n_segments))
    n_clusters = max(1, int(n_clusters))
    seg_len = max(1, len(x) // n_segments)
    n_seg = len(x) // seg_len
    if n_seg == 0:
        return x.copy()
    mat = x[:n_seg*seg_len].reshape(n_seg, seg_len)
    from sklearn.cluster import KMeans
    n_clusters = min(n_clusters, n_seg)
    km = KMeans(n_clusters=n_clusters, n_init=3, random_state=0)
    labels = km.fit_predict(mat)
    centers = km.cluster_centers_
    return centers.flatten()

_register_coarsening('分段聚类中心', _coarse_segment_cluster,
    [('n_segments', '分段数', 1, 1000, 1, 20, '信号被切分的段数。'),
     ('n_clusters', '聚类数', 1, 50, 1, 5, '典型模式个数。越多保留细节越多。')],
    '将信号分段后K-Means聚类，输出典型模式中心，提取代表性波形片段。')

# ---- 15. 直方图特征 ----
def _coarse_histogram(x, n_bins=50, **_):
    n_bins = max(2, int(n_bins))
    hist, edges = np.histogram(x, bins=n_bins)
    centers = (edges[:-1] + edges[1:]) / 2
    return hist.astype(float)

_register_coarsening('直方图特征', _coarse_histogram,
    [('n_bins', '直方图箱数', 2, 1000, 1, 50, '分箱数量。越多分辨率越高但越稀疏。')],
    '统计信号幅值分布直方图，反映幅值分布特性，丢失时序信息。')

# ---- 16. 符号化(SAX近似) ----
def _coarse_symbolize(x, n_symbols=8, factor=10, **_):
    n_symbols = max(2, int(n_symbols))
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return x.copy()
    piece = np.mean(x[:n*factor].reshape(n, factor), axis=1)
    # 按分位数划分符号
    quantiles = np.linspace(0, 1, n_symbols+1)[1:-1]
    breaks = np.quantile(piece, quantiles)
    symbols = np.digitize(piece, breaks)
    return symbols.astype(float)

_register_coarsening('符号化(SAX)', _coarse_symbolize,
    [('n_symbols', '符号数', 2, 32, 1, 8, '离散符号个数。越多分辨率越高。'),
     ('factor', '分段因子', 1, 1000, 1, 10, '每factor个点聚合成1个符号。')],
    '分段均值后按分位数离散化为符号序列(SAX近似)，大幅压缩数据并保留形态趋势。')

# ---- 17. 阈值二值化 ----
def _coarse_threshold(x, threshold=0.0, factor=1, **_):
    threshold = float(threshold)
    factor = max(1, int(factor))
    n = len(x) // factor
    if n == 0:
        return (x > threshold).astype(float)
    piece = np.mean(x[:n*factor].reshape(n, factor), axis=1)
    return (piece > threshold).astype(float)

_register_coarsening('阈值二值化', _coarse_threshold,
    [('threshold', '阈值', -1e9, 1e9, 0.1, 0.0, '大于阈值记1，否则记0。'),
     ('factor', '分段因子', 1, 1000, 1, 1, '先分段均值再二值化，>1可降噪。')],
    '按阈值将信号二值化，提取事件触发/状态切换信息，factor>1可先降噪。')

# ---- 18. 标准化分段统计 ----
def _coarse_segment_stats(x, n_segments=20, **_):
    n_segments = max(1, int(n_segments))
    seg_len = max(1, len(x) // n_segments)
    n_seg = len(x) // seg_len
    if n_seg == 0:
        return x.copy()
    mat = x[:n_seg*seg_len].reshape(n_seg, seg_len)
    means = np.mean(mat, axis=1)
    stds = np.std(mat, axis=1)
    # 标准化后拼接
    out = np.concatenate([means, stds])
    return out

_register_coarsening('标准化分段统计', _coarse_segment_stats,
    [('n_segments', '分段数', 1, 1000, 1, 20, '信号切分段数。输出为2倍段数的均值+标准差序列。')],
    '分段提取均值与标准差并拼接，压缩为统计特征序列，保留局部趋势与波动。')

# ---- 19. Top-Hat形态学 ----
def _coarse_tophat(x, window=20, **_):
    window = max(1, int(window))
    from scipy.ndimage import white_tophat, grey_opening
    if window >= len(x):
        return x - np.min(x)
    return white_tophat(x, size=window, mode='nearest')

_register_coarsening('Top-Hat形态学', _coarse_tophat,
    [('window', '结构元素尺寸', 2, 10000, 1, 20, '大于该尺寸的趋势被去除。越大保留越宽频段。')],
    '白Top-Hat形态学运算，去除缓慢变化的背景趋势，突出局部峰/谷特征。')

# ---- 20. 重采样插值 ----
def _coarse_resample(x, target_length=1000, **_):
    target_length = max(2, int(target_length))
    if target_length == len(x):
        return x.copy()
    if target_length > len(x):
        # 上采样：线性插值
        old_idx = np.linspace(0, 1, len(x))
        new_idx = np.linspace(0, 1, target_length)
        return np.interp(new_idx, old_idx, x)
    else:
        # 下采样：取均匀间隔点
        idx = np.linspace(0, len(x)-1, target_length).astype(int)
        return x[idx]

_register_coarsening('重采样插值', _coarse_resample,
    [('target_length', '目标长度', 2, 100000, 1, 1000, '输出样本数。小于原始=降采样，大于=上采样。')],
    '将信号重采样到指定长度，统一不同长度信号便于对齐比较，支持上下采样。')


def apply_coarsening(data, method_name, fs=1.0, **params):
    """应用粗粒化方法"""
    if method_name not in COARSENING_METHODS:
        raise ValueError(f"未知的粗粒化方法: {method_name}")
    entry = COARSENING_METHODS[method_name]
    func = entry['func']
    x = np.asarray(data).flatten()
    # 构造调用参数
    import inspect
    sig = inspect.signature(func)
    call_args = {'x': x}
    if 'fs' in sig.parameters:
        call_args['fs'] = fs
    for k, v in params.items():
        if k in sig.parameters:
            call_args[k] = v
    try:
        return np.asarray(func(**call_args)).flatten()
    except Exception as e:
        raise RuntimeError(f"粗粒化{method_name}失败: {e}")


# ========================
# 窗口截断方法
# ========================

def _time_to_index(t, fs):
    """时间(秒)转样本索引"""
    return max(0, int(round(t * fs)))


def truncate_single_window(data, fs, t_start, t_end):
    """单窗口截断：保留[t_start, t_end]时间段数据"""
    x = np.asarray(data).flatten()
    i0 = _time_to_index(t_start, fs)
    i1 = _time_to_index(t_end, fs)
    i0 = max(0, min(i0, len(x)))
    i1 = max(i0, min(i1, len(x)))
    if i1 <= i0:
        raise ValueError(f"截断区间为空: [{t_start}, {t_end}]秒，对应样本[{i0}, {i1}]")
    return x[i0:i1]


def truncate_multi_window(data, fs, windows):
    """多窗口截断：windows为[(t_start, t_end), ...]，结果按顺序拼接"""
    x = np.asarray(data).flatten()
    if not windows:
        raise ValueError("多窗口截断未提供任何时段")
    segments = []
    for (t0, t1) in windows:
        i0 = _time_to_index(t0, fs)
        i1 = _time_to_index(t1, fs)
        i0 = max(0, min(i0, len(x)))
        i1 = max(i0, min(i1, len(x)))
        if i1 > i0:
            segments.append(x[i0:i1])
    if not segments:
        raise ValueError("所有时段均为空，请检查起止时间")
    return np.concatenate(segments)


def truncate_periodic_window(data, fs, T0, T1, T2):
    """周期性窗口截断：从T0开始，每隔T1取T2时长数据，拼接所有窗口"""
    x = np.asarray(data).flatten()
    T0 = float(T0); T1 = float(T1); T2 = float(T2)
    if T1 <= 0:
        raise ValueError("周期T1必须大于0")
    if T2 <= 0:
        raise ValueError("窗口时长T2必须大于0")
    if T2 > T1:
        raise ValueError("窗口时长T2不能大于周期T1")
    total_time = len(x) / fs
    segments = []
    t = T0
    while t + T2 <= total_time + 1e-9:
        i0 = _time_to_index(t, fs)
        i1 = _time_to_index(t + T2, fs)
        i0 = max(0, min(i0, len(x)))
        i1 = max(i0, min(i1, len(x)))
        if i1 > i0:
            segments.append(x[i0:i1])
        t += T1
    if not segments:
        raise ValueError(f"周期窗口未截取到数据，请检查T0={T0}, T1={T1}, T2={T2}与信号总时长{total_time:.3f}秒")
    return np.concatenate(segments)


# ========================
# 并行计算模块
# ========================

import os as _os
from concurrent.futures import ThreadPoolExecutor, as_completed

# 默认并行工作线程数：取 CPU 核数，但限制在 [2, 8] 之间，避免过度竞争
def _default_workers():
    try:
        n = _os.cpu_count() or 2
    except Exception:
        n = 2
    return max(2, min(8, n))


def _should_parallelize(total_methods, data_len, min_data_len=8000, min_methods=4):
    """智能判断是否值得并行

    并行的收益主要来自：
    1. 方法数较多（>= min_methods），有足够任务填充线程
    2. 单次计算耗时较长（数据量 >= min_data_len），足以抵消线程调度开销

    对于小数据量或少量方法，串行更快。
    阈值基于实测：N<8000 时线程开销大于收益，N>=8000 时并行开始有正向加速。
    """
    if total_methods < min_methods:
        return False
    if data_len < min_data_len:
        return False
    return True


def compute_time_similarity_batch(data_a, data_b, method_names, fs=1.0, max_workers=None, progress_cb=None):
    """并行批量计算时域相似性

    参数:
        data_a, data_b: 一维数组
        method_names: 方法名列表
        fs: 采样率
        max_workers: 最大线程数，None则自动
        progress_cb: 可选回调 fn(done, total, method, result_or_error)
    返回:
        list[dict]: 每项 {'method', 'value', 'indicators', 'ok'}
            - ok=True时value为float，indicators为dict
            - ok=False时value为错误字符串
    """
    if max_workers is None:
        max_workers = _default_workers()
    x = np.asarray(data_a).flatten()
    y = np.asarray(data_b).flatten()
    total = len(method_names)
    results = [None] * total

    def _worker(idx, m):
        try:
            result = compute_time_similarity(x, y, m, fs)
            return idx, m, result['value'], result['indicators'], None
        except Exception as e:
            return idx, m, None, None, str(e)[:60]

    if total == 0:
        return []
    use_parallel = _should_parallelize(total, min(len(x), len(y))) and max_workers > 1
    if not use_parallel:
        for i, m in enumerate(method_names):
            _, _, val, indicators, err = _worker(i, m)
            results[i] = {'method': m, 'value': (val if err is None else f"Error: {err}"), 
                         'indicators': indicators, 'ok': err is None}
            if progress_cb:
                progress_cb(i + 1, total, m, results[i]['value'])
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_worker, i, m): i for i, m in enumerate(method_names)}
        done_cnt = 0
        for fut in as_completed(futures):
            idx, m, val, indicators, err = fut.result()
            results[idx] = {'method': m, 'value': (val if err is None else f"Error: {err}"), 
                         'indicators': indicators, 'ok': err is None}
            done_cnt += 1
            if progress_cb:
                progress_cb(done_cnt, total, m, results[idx]['value'])
    return results


def compute_freq_similarity_batch(data_a, data_b, method_names, fs=1.0, max_workers=None, progress_cb=None):
    """并行批量计算频域相似性，接口同 compute_time_similarity_batch"""
    if max_workers is None:
        max_workers = _default_workers()
    x = np.asarray(data_a).flatten()
    y = np.asarray(data_b).flatten()
    total = len(method_names)
    results = [None] * total

    def _worker(idx, m):
        try:
            result = compute_freq_similarity(x, y, m, fs)
            return idx, m, result['value'], result['indicators'], None
        except Exception as e:
            return idx, m, None, None, str(e)[:60]

    if total == 0:
        return []
    use_parallel = _should_parallelize(total, min(len(x), len(y))) and max_workers > 1
    if not use_parallel:
        for i, m in enumerate(method_names):
            _, _, val, indicators, err = _worker(i, m)
            results[i] = {'method': m, 'value': (val if err is None else f"Error: {err}"), 
                         'indicators': indicators, 'ok': err is None}
            if progress_cb:
                progress_cb(i + 1, total, m, results[i]['value'])
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_worker, i, m): i for i, m in enumerate(method_names)}
        done_cnt = 0
        for fut in as_completed(futures):
            idx, m, val, indicators, err = fut.result()
            results[idx] = {'method': m, 'value': (val if err is None else f"Error: {err}"), 
                         'indicators': indicators, 'ok': err is None}
            done_cnt += 1
            if progress_cb:
                progress_cb(done_cnt, total, m, results[idx]['value'])
    return results


def convert_to_matrix_batch(data, method_names, fs=1.0, max_workers=None, progress_cb=None, **kwargs):
    """并行批量矩阵转换

    返回:
        list[dict]: 每项 {'method', 'matrix', 'shape', 'ok', 'error'}
    """
    if max_workers is None:
        max_workers = _default_workers()
    x = np.asarray(data).flatten()
    total = len(method_names)
    results = [None] * total

    def _worker(idx, m):
        try:
            mat = convert_to_matrix(x, m, fs=fs, **kwargs)
            return idx, m, mat, mat.shape, None
        except Exception as e:
            return idx, m, None, None, str(e)[:80]

    if total == 0:
        return []
    use_parallel = _should_parallelize(total, len(x)) and max_workers > 1
    if not use_parallel:
        for i, m in enumerate(method_names):
            _, _, mat, shape, err = _worker(i, m)
            results[i] = {'method': m, 'matrix': mat, 'shape': shape, 'ok': err is None, 'error': err}
            if progress_cb:
                progress_cb(i + 1, total, m, results[i])
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_worker, i, m): i for i, m in enumerate(method_names)}
        done_cnt = 0
        for fut in as_completed(futures):
            idx, m, mat, shape, err = fut.result()
            results[idx] = {'method': m, 'matrix': mat, 'shape': shape, 'ok': err is None, 'error': err}
            done_cnt += 1
            if progress_cb:
                progress_cb(done_cnt, total, m, results[idx])
    return results
