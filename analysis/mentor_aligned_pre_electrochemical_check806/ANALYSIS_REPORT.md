# 电化学实验前动态网络分析 V1

## 数据与口径

- 精确归档工况数：32。
- 每文件独立动态判断坏道；通道、时间窗和 Welch 段不作为独立实验重复。
- 慢动态使用完整 10 Hz 对齐时序；高频时间行为使用完整 Welch 峰轨迹和频带功率。
- 本报告为导师建议下的第一版数据驱动结果，不对数据模态直接赋予器件物理名称。

## 运行摘要

- 自动坏道记录数（文件×通道）：{"20260806": 48}。
- 20260806 网络摘要行数：32。
- 达到 |r|>=0.3 且错位对照 p<=0.05 的共同低高频耦合项：0。
- 20260806 RUN 相对本地背景频带比较行数：100。
- 20260806 的 80--200 kHz RUN 对照中，全记录平均功率为正 20/20，逐通道典型功率差为正 20/20。
- 20260806 跨至少半数健康通道且持续率中位数>=20%的候选线簇：0。

## 结果解释边界

- ACF、AR(1) 和 Allan 指标描述有效时间尺度，不直接等同于某个已知 RC 元件参数。
- 低高频耦合的错位时间对照用于抑制自相关造成的虚假相关，但仍是同一文件内证据。
- 高频峰轨迹来自每段保留的前 64 个峰，适合比较持续性和探测器依赖，不等价于完整高频波形。
- 物理源归因仍需结合本地背景、换位、媒体和后续受控实验。

## 输出表

- `channel_health_dynamic.csv`：逐文件动态健康通道。
- `slow_relaxation_metrics.csv`、`allan_deviation.csv`：慢动态时间尺度。
- `network_summary.csv`、`channel_pair_lag_network.csv`：多通道网络结构。
- `low_high_coupling.csv`：准静态状态与高频包络耦合。
- `band_temporal_dynamics.csv`、`matched_band_contrasts.csv`：高频带时间行为和本地对照。
- `matched_narrow_line_contrasts.csv`：窄线相对本地对照、邻域漂移检查和逐段出现率。
- `matched_slow_dynamics_contrasts.csv`、`matched_allan_contrasts.csv`：慢动态相对本地对照。
- `matched_network_contrasts.csv`：网络结构相对本地对照。
- `low_rate_pair_coherence.csv`、`low_rate_coherence_summary.csv`：1 Hz--1.5 kHz跨通道相干结构。
- `matched_low_rate_coherence_contrasts.csv`：跨通道相干结构相对本地对照。
- `slow_periodicity_candidates.csv`：固定3.1秒候选及盲搜低频周期的跨通道/前后半段支持。
- `line_tracks.csv`、`line_cross_channel_support.csv`：窄谱线持续性和通道支持。
- `cross_detector_synchrony.csv`：duo 同场双探测器共同动态。
