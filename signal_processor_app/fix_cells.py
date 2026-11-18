#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复优化版notebook中的错误"""

import json

with open('time_freq_analysis.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        
        # 修复 Cell 11: 短时自相关
        if '自相关' in src:
            new_src = '''# ⚡ 短时自相关优化: 简化实现
print('\\n' + '='*40 + '\\n短时自相关\\n' + '='*40)
ws, hop = 32, 16  # 减小窗口
n_win = max(1, (N-ws)//hop+1)

# 简化实现
ac_list = []
for i in range(min(10, n_win)):
    seg = x[i*hop:i*hop+ws]
    if len(seg) >= ws//2:
        corr = np.correlate(seg, seg, 'same')
        corr = corr / (corr[ws//2] + 1e-12)
        ac_list.append(corr[:ws//2])

if ac_list:
    ac = np.array(ac_list)
    plt.figure(figsize=(12, 4))
    plt.imshow(ac, aspect='auto', origin='lower', cmap='viridis')
    plt.title('短时自相关'); plt.colorbar()
    plt.tight_layout(); plt.show()
else:
    print('数据不足')'''
            cell['source'] = [new_src]
            print(f'Fixed Cell {i}: 短时自相关')
        
        # 修复 Cell 12: 频谱特征
        elif '频谱特征' in src:
            new_src = '''# 📊 频谱特征
print('\\n' + '='*40 + '\\n频谱特征\\n' + '='*40)
freqs = np.fft.rfftfreq(N, 1/FS)  # 重新计算freqs
mag = np.abs(np.fft.rfft(x))/N; mag[1:]*=2
peak_idx = np.argmax(mag[1:])+1
peak_freq = freqs[peak_idx] if peak_idx < len(freqs) else freqs[-1]
centroid = np.sum(freqs[1:]*mag[1:])/(np.sum(mag[1:])+1e-12)

plt.figure(figsize=(12, 4))
plt.plot(freqs, mag, 'b-', lw=0.8)
plt.axvline(peak_freq, color='r', ls='--', label=f'峰值={peak_freq:.1f}Hz')
plt.axvline(centroid, color='g', ls='--', label=f'质心={centroid:.1f}Hz')
plt.xlim([0, FS/2]); plt.legend(); plt.grid(alpha=0.3)
plt.tight_layout(); plt.show()

print(f'\\n✅ 分析完成!')'''
            cell['source'] = [new_src]
            print(f'Fixed Cell {i}: 频谱特征')

with open('time_freq_analysis.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Done!')