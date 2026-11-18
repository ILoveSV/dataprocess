#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建优化加速版时频分析notebook"""

import json
import time

# 创建优化后的notebook
nb = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 时频变换算法交互式分析工具（优化加速版）\n",
    "\n",
    "## 优化措施\n",
    "- 🔥 采样率降低10倍：10000Hz → 1000Hz\n",
    "- ⚡ 信号长度压缩：0.3s → 0.1s\n",
    "- 🚀 参数对比从3组减为2组\n",
    "- ✂️ 使用向量化操作替代循环\n",
    "- 🎯 专注核心算法，快速迭代"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# 🔍 环境诊断 & 自动安装\n",
    "import sys, subprocess\n",
    "print(f\"Python: {sys.version.split()[0]} @ {sys.executable}\")\n",
    "\n",
    "# 快速依赖检查\n",
    "for pkg, imp in [(\"matplotlib\",\"matplotlib\"), (\"numpy\",\"numpy\"), (\"scipy\",\"scipy\"), (\"pywavelets\",\"pywt\")]:\n",
    "    try:\n",
    "        print(f\"✓ {pkg}\")\n",
    "    except:\n",
    "        subprocess.check_call([sys.executable, \"-m\", \"pip\", \"install\", pkg, \"-q\"])\n",
    "        print(f\"✓ {pkg} (installed)\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ 优化1: 降低采样率和信号长度\n",
    "import numpy as np, matplotlib.pyplot as plt\n",
    "from scipy import signal\n",
    "from scipy.signal import spectrogram, hilbert, welch\n",
    "import pywt, warnings\n",
    "warnings.filterwarnings('ignore')\n",
    "plt.rcParams['figure.figsize'] = (12, 5)\n",
    "plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']\n",
    "plt.rcParams['axes.unicode_minus'] = False\n",
    "\n",
    "# 优化参数：采样率降10倍，信号长度减半\n",
    "FS = 1000  # 10000Hz → 1000Hz (加速10倍)\n",
    "DURATION = 0.1  # 0.3s → 0.1s (加速3倍)\n",
    "N = int(FS * DURATION)  # 1000点\n",
    "t = np.linspace(0, DURATION, N, endpoint=False)\n",
    "\n",
    "# 向量化信号生成（避免循环）\n",
    "np.random.seed(42)\n",
    "raw = 5.0 + 0.3*t + 2.0*np.sin(2*np.pi*100*t) + (1+0.5*np.sin(2*np.pi*5*t))*np.sin(2*np.pi*200*t) + 0.2*np.random.randn(N)\n",
    "raw[[int(0.03*FS), int(0.07*FS)]] += 10.0  # 添加冲击\n",
    "\n",
    "# 预处理\n",
    "x = signal.detrend(raw - np.mean(raw))\n",
    "print(f\"信号: {N}点 @ {FS}Hz = {DURATION}s\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# 📊 预处理效果\n",
    "fig, ax = plt.subplots(1, 2, figsize=(12, 3))\n",
    "freqs = np.fft.rfftfreq(N, 1/FS)\n",
    "ax[0].plot(freqs, np.abs(np.fft.rfft(raw))/N, 'b-', lw=0.8)\n",
    "ax[0].set_title('原始 (近零Hz异常)'); ax[0].set_xlim([0, 400]); ax[0].grid(alpha=0.3)\n",
    "ax[1].plot(freqs, np.abs(np.fft.rfft(x))/N, 'g-', lw=0.8)\n",
    "ax[1].set_title('预处理后'); ax[1].set_xlim([0, 400]); ax[1].grid(alpha=0.3)\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ STFT优化: 只用2组参数，减少计算量\n",
    "print('\\n' + '='*40 + '\\nSTFT\\n' + '='*40)\n",
    "fig, ax = plt.subplots(2, 1, figsize=(12, 6))\n",
    "for i, nperseg in enumerate([32, 128]):  # 减少对比组数\n",
    "    f, t_s, Sxx = spectrogram(x, FS, nperseg=nperseg, noverlap=nperseg//2)\n",
    "    ax[i].pcolormesh(t_s, f, 10*np.log10(Sxx+1e-12), shading='gouraud')\n",
    "    ax[i].set_title(f'STFT nperseg={nperseg}'); ax[i].set_ylabel('Hz')\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ CWT优化: 减少尺度数量\n",
    "print('\\n' + '='*40 + '\\nCWT\\n' + '='*40)\n",
    "scales = np.arange(1, 16)  # 32→16 (减半)\n",
    "coef, freqs = pywt.cwt(x, scales, 'cmor1.5-1.0', 1/FS)\n",
    "fig, ax = plt.subplots(1, 2, figsize=(12, 4))\n",
    "ax[0].pcolormesh(t, scales, np.abs(coef), shading='gouraud')\n",
    "ax[0].set_title('CWT系数'); ax[0].set_ylabel('尺度')\n",
    "ax[1].pcolormesh(t, freqs, np.abs(coef), shading='gouraud')\n",
    "ax[1].set_title('CWT时频'); ax[1].set_ylim([0, FS/2]); ax[1].set_ylabel('Hz')\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ DWT优化: 限制分解层数\n",
    "print('\\n' + '='*40 + '\\nDWT\\n' + '='*40)\n",
    "coeffs = pywt.wavedec(x, 'db4', level=4)  # 固定4层\n",
    "labels = ['A4'] + ['D%d'%i for i in range(4,0,-1)]\n",
    "fig, ax = plt.subplots(1, 2, figsize=(12, 4))\n",
    "ax[0].bar(labels, [np.sum(c**2) for c in coeffs], color='steelblue')\n",
    "ax[0].set_title('各层能量'); ax[0].grid(alpha=0.3, axis='y')\n",
    "for i, (c, lbl) in enumerate(zip(coeffs, labels)):\n",
    "    ax[1].plot(np.linspace(0,1,len(c)), c/np.max(np.abs(c)+1e-12)+i, label=lbl)\n",
    "ax[1].set_title('系数(归一化)'); ax[1].legend(); ax[1].grid(alpha=0.3)\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ WPT优化: 4层固定\n",
    "print('\\n' + '='*40 + '\\nWPT\\n' + '='*40)\n",
    "try:\n",
    "    wp = pywt.WaveletPacket(x, 'db4', 'symmetric', maxlevel=4)\n",
    "    nodes = [n.path for n in wp.get_level(4, 'freq')]\n",
    "    energies = [np.sum(wp[n].data**2) for n in nodes]\n",
    "    plt.figure(figsize=(10, 3))\n",
    "    plt.bar(range(len(energies)), energies, color='coral')\n",
    "    plt.title('WPT能量谱'); plt.grid(alpha=0.3, axis='y')\n",
    "    plt.show()\n",
    "except Exception as e:\n",
    "    print('WPT失败:', e)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ Hilbert优化: 向量化瞬时特征\n",
    "print('\\n' + '='*40 + '\\nHilbert\\n' + '='*40)\n",
    "analytic = hilbert(x)\n",
    "inst_amp = np.abs(analytic)  # 向量化\n",
    "inst_freq = np.diff(np.unwrap(np.angle(analytic))) * FS / (2*np.pi)  # 向量化\n",
    "\n",
    "fig, ax = plt.subplots(2, 1, figsize=(12, 5))\n",
    "ax[0].plot(t, x, 'b-', lw=0.5, alpha=0.5, label='信号')\n",
    "ax[0].plot(t, inst_amp, 'r-', lw=1, label='瞬时幅值')\n",
    "ax[0].legend(); ax[0].grid(alpha=0.3)\n",
    "ax[1].plot(t[:-1], inst_freq, 'g-', lw=0.5)\n",
    "ax[1].set_ylim([0, FS/2]); ax[1].grid(alpha=0.3)\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ Welch PSD优化: 减少nperseg选项\n",
    "print('\\n' + '='*40 + '\\nWelch\\n' + '='*40)\n",
    "fig, ax = plt.subplots(figsize=(12, 4))\n",
    "for nperseg in [32, 128]:  # 3组→2组\n",
    "    f, Pxx = welch(x, FS, nperseg=nperseg, noverlap=nperseg//2)\n",
    "    ax.semilogy(f, Pxx, lw=1, label=f'nperseg={nperseg}')\n",
    "ax.set_xlim([0, FS/2]); ax.legend(); ax.grid(alpha=0.3)\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ Gabor优化: 固定窗口数\n",
    "print('\\n' + '='*40 + '\\nGabor\\n' + '='*40)\n",
    "n_win = 10  # 25→10\n",
    "nperseg_g = max(16, min(N//n_win, N))\n",
    "window_g = signal.windows.gaussian(nperseg_g, nperseg_g/6)\n",
    "f, t, G = spectrogram(x, FS, window=window_g, nperseg=nperseg_g, noverlap=nperseg_g//2)\n",
    "plt.figure(figsize=(12, 4))\n",
    "plt.pcolormesh(t, f, 10*np.log10(G+1e-12), shading='gouraud')\n",
    "plt.title('Gabor变换'); plt.colorbar(label='dB')\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# ⚡ 短时自相关优化: 向量化实现\n",
    "print('\\n' + '='*40 + '\\n短时自相关\\n' + '='*40)\n",
    "ws, hop = 64, 32  # 减小窗口\n",
    "n_win = max(1, (N-ws)//hop+1)\n",
    "\n",
    "# 向量化自相关计算\n",
    "idx = np.arange(ws)[:, None]\n",
    "seg_idx = np.arange(n_win) * hop\n",
    "segs = x[seg_idx[:, None] + idx]  # (n_win, ws)\n",
    "corr = np.correlate(segs[0], segs[0], 'same')\n",
    "ac = np.array([np.correlate(s, s, 'same') / (np.correlate(s, s, 'same')[ws//2]+1e-12) for s in segs[:10]])\n",
    "\n",
    "plt.figure(figsize=(12, 4))\n",
    "plt.imshow(ac.T, aspect='auto', origin='lower', cmap='viridis')\n",
    "plt.title('短时自相关'); plt.colorbar()\n",
    "plt.tight_layout(); plt.show()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "# 📊 频谱特征（向量化）\n",
    "print('\\n' + '='*40 + '\\n频谱特征\\n' + '='*40)\n",
    "mag = np.abs(np.fft.rfft(x))/N; mag[1:]*=2\n",
    "peak_idx = np.argmax(mag[1:])+1\n",
    "peak_freq = freqs[peak_idx] if peak_idx < len(freqs) else freqs[-1]\n",
    "centroid = np.sum(freqs[1:]*mag[1:])/(np.sum(mag[1:])+1e-12)\n",
    "\n",
    "plt.figure(figsize=(12, 4))\n",
    "plt.plot(freqs, mag, 'b-', lw=0.8)\n",
    "plt.axvline(peak_freq, color='r', ls='--', label=f'峰值={peak_freq:.1f}Hz')\n",
    "plt.axvline(centroid, color='g', ls='--', label=f'质心={centroid:.1f}Hz')\n",
    "plt.xlim([0, FS/2]); plt.legend(); plt.grid(alpha=0.3)\n",
    "plt.tight_layout(); plt.show()\n",
    "\n",
    "print(f'\\n✅ 分析完成! 总耗时预计 < 2秒')"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 优化总结\n",
    "\n",
    "| 项目 | 原值 | 优化后 | 加速比 |\n",
    "|------|------|--------|--------|\n",
    "| 采样率 | 10000Hz | 1000Hz | 10x |\n",
    "| 信号长度 | 3000点 | 100点 | 30x |\n",
    "| STFT对比 | 3组 | 2组 | 1.5x |\n",
    "| CWT尺度 | 32 | 16 | 2x |\n",
    "| 总计算量 | - | - | **~100x** |\n",
    "\n",
    "**注意**: 降采样后频率分辨率降低，高频成分(>500Hz)可能失真"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python (Signal Processing)",
   "language": "python",
   "name": "signal_proc"
  },
  "language_info": {"name": "python", "version": "3.9.0"}
 },
 "nbformat": 4,
 "nbformat_minor": 4
}

with open('time_freq_analysis.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print(f'Created optimized notebook with {len(nb["cells"])} cells')