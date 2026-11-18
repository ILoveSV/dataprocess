def calc_figsize(n_subplots, n_cols=1, target_ratio=3.0, text_height=10):
    """计算符合比例约束的图表尺寸
    
    参数:
        n_subplots: 子图总数
        n_cols: 列数
        target_ratio: 目标宽高比
        text_height: 文字高度（磅）
    
    约束:
        - 每张子图的宽高比 ≤ 3.3
        - 图的高度与图中文字高度之比 ≤ 7.5
    """
    max_aspect_ratio = 3.3
    max_height_ratio = 7.5
    
    text_height_inch = text_height / 72.0
    max_total_height = max_height_ratio * text_height_inch
    
    n_rows = (n_subplots + n_cols - 1) // n_cols
    
    while n_rows * 0.3 > max_total_height and n_cols < n_subplots:
        n_cols += 1
        n_rows = (n_subplots + n_cols - 1) // n_cols
    
    total_height = max_total_height
    subplot_height = total_height / n_rows
    
    effective_ratio = min(target_ratio, max_aspect_ratio)
    subplot_width = subplot_height * effective_ratio
    
    total_width = subplot_width * n_cols
    total_aspect = total_width / total_height
    
    if total_aspect > max_aspect_ratio:
        total_width = max_aspect_ratio * total_height
        subplot_width = total_width / n_cols
    
    return (total_width, total_height)