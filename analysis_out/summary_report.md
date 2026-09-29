# 数据汇总报告

## 1. 输入数据概况
- 2m0hz: channels=12, files=40
- 2m30hz: channels=12, files=40
- 2m50hz: channels=12, files=40
- 3m0hz: channels=12, files=40
- 3m30hz: channels=12, files=40
- 3m50hz: channels=12, files=40
- 5m0hz: channels=12, files=40
- 5m30hz: channels=12, files=40
- 5m50hz: channels=12, files=40
- 缺失组: none

## 2. 数据质量诊断
NIST 4-plot 指标仅用于数据质量诊断，不用于周期推断；周期相关判断以 PSD/ACF peak 和匹配表为准。
- NIST 漂移标记通道数: 0；异常分布/尾部标记通道数: 99。

## 3. 背景 vs 泵开启
- 2m30hz vs 2m0hz: total_power 中位比值=1；高对比通道=channel4,channel7,channel1；跨通道共同峰=none Hz。
- 2m50hz vs 2m0hz: total_power 中位比值=0.998；高对比通道=channel5,channel6,channel7；跨通道共同峰=none Hz。
- 3m30hz vs 3m0hz: total_power 中位比值=1；高对比通道=channel10,channel11,channel2；跨通道共同峰=none Hz。
- 3m50hz vs 3m0hz: total_power 中位比值=0.999；高对比通道=channel10,channel2,channel3；跨通道共同峰=none Hz。
- 5m30hz vs 5m0hz: total_power 中位比值=1；高对比通道=channel12,channel8,channel6；跨通道共同峰=none Hz。
- 5m50hz vs 5m0hz: total_power 中位比值=1；高对比通道=channel3,channel12,channel2；跨通道共同峰=none Hz。

## 4. 30Hz vs 50Hz
- 当前低频 PSD 最小 df=0.763 Hz；df<=1Hz 的通道可直接检查 30/50Hz 邻域。若某行标记 unreliable，则 low-frequency resolution insufficient for direct 30/50Hz discrimination。
- 当前严格标记可区分的 channel-distance 对数量: 18；其余建议以边带、高频峰、ACF 衰减作为间接特征，不强行下结论。

## 5. 距离效应
- acf_decay_time_s: 单调衰减比例=91.67%。
- total_power_0_200k: 单调衰减比例=58.33%。
- bandpower_1k_10k: 单调衰减比例=47.22%。
- bandpower_50k_100k: 单调衰减比例=38.89%。
- acf_first_strong_acf: 单调衰减比例=8.33%。
- dominant_peak_psd: 单调衰减比例=0.00%。

## 6. 初步结论
A. 强证据：9 个目标组均有多通道文件，背景对比已按同距离 0Hz 配对，跨通道共同峰可在 cross_channel_peak_summary 中直接追踪。
B. 中等证据：部分泵开启组相对背景存在频段功率和峰簇变化，但需要结合 channel 一致性与 quality_note 二次筛选。
C. 不能支持：不能仅凭 0Hz/30Hz/50Hz 标签声明可区分；低频 df 不足或边带不可靠的行已标记 unreliable。

## 7. 后续建议
- 后续人工/ChatGPT 分析优先使用 background_contrast、cross_channel_peak_summary、psd_acf_matches 三张表交叉验证。
- 对 contrast_score 高但仅单通道出现的峰，先按通道异常处理，不作为组级结论。
- 若目标是直接识别 30Hz/50Hz，保留更长连续时间窗以保证低频 df<=1Hz，并继续记录 actual_df。