# -*- coding: utf-8 -*-
"""
TC12 / TC34 实验状态示意图绘制模块
"""
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def _setup_cn_font(ax):
    """设置中文字体兼容"""
    ax.set_xlabel('')
    ax.set_ylabel('')


def draw_tc12(fig, alpha_deg=120.0, beta_deg=30.0, r_len=5.0, D_deg=1.8):
    """绘制 TC12 示意图

    几何关系：
    - 两条绿色粗线段张开 alpha 角，延长线（红色虚线）交于 A 点
    - 从 A 作 alpha 角平分线（红色虚线，1.3倍长度）
    - 从 A 到 B（红色虚线，5倍长度），B 为圆心绘制黑色粗圆（半径1.8倍）
    - 平分线与 AB 线夹角 beta=30°
    """
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    ax.axis('off')

    alpha = np.deg2rad(alpha_deg)
    beta = np.deg2rad(beta_deg)

    L = 1.0  # 基准长度

    # A 点位于原点
    A = np.array([0.0, 0.0])

    # 两条绿色粗线段（5倍粗线，1倍长度），不相交
    # 线段方向：以 A 为角顶，两线段沿 alpha 角两侧的延长线方向放置，但线段本身不包含 A
    # 取线段在距离 A 为 d0 处开始，长度 L
    d0 = 1.5  # 线段起点距 A 的距离
    dir1 = np.array([np.cos(alpha / 2), np.sin(alpha / 2)])
    dir2 = np.array([np.cos(-alpha / 2), np.sin(-alpha / 2)])

    seg1_start = A + dir1 * d0
    seg1_end = A + dir1 * (d0 + L)
    seg2_start = A + dir2 * d0
    seg2_end = A + dir2 * (d0 + L)

    # 绿色粗线段（5倍粗线）
    ax.plot([seg1_start[0], seg1_end[0]], [seg1_start[1], seg1_end[1]],
            color='green', linewidth=5, solid_capstyle='round')
    ax.plot([seg2_start[0], seg2_end[0]], [seg2_start[1], seg2_end[1]],
            color='green', linewidth=5, solid_capstyle='round')

    # 红色虚线延长线（1倍细线），交于 A
    ext_len = d0 + L + 0.8
    ax.plot([seg1_end[0], A[0]], [seg1_end[1], A[1]],
            color='red', linewidth=1, linestyle='--')
    ax.plot([seg2_end[0], A[0]], [seg2_end[1], A[1]],
            color='red', linewidth=1, linestyle='--')
    # 另一侧延长
    ax.plot([seg1_start[0], A[0] - dir1[0] * 0.3], [seg1_start[1], A[1] - dir1[1] * 0.3],
            color='red', linewidth=1, linestyle='--')
    ax.plot([seg2_start[0], A[0] - dir2[0] * 0.3], [seg2_start[1], A[1] - dir2[1] * 0.3],
            color='red', linewidth=1, linestyle='--')

    # A 点
    ax.plot(*A, 'ko', markersize=5)
    ax.annotate('A', A, textcoords="offset points", xytext=(-12, -10), fontsize=12, fontweight='bold')

    # alpha 角平分线（红色虚线，1.3倍长度）
    bisect_dir = np.array([1.0, 0.0])  # 平分线沿 x 轴正方向
    bisect_len = 1.3 * L
    B_bisect = A + bisect_dir * bisect_len
    ax.plot([A[0], B_bisect[0]], [A[1], B_bisect[1]],
            color='red', linewidth=1, linestyle='--')

    # AB 线（红色虚线，5倍长度），与平分线夹角 beta
    ab_dir = np.array([np.cos(beta), np.sin(beta)])
    ab_len = 5.0 * L
    B = A + ab_dir * ab_len
    ax.plot([A[0], B[0]], [A[1], B[1]],
            color='red', linewidth=1, linestyle='--')

    # B 点圆（黑色，3倍粗线，半径1.8倍）
    circle = plt.Circle(B, 1.8 * L, fill=False, color='black', linewidth=3)
    ax.add_patch(circle)
    ax.annotate('B', B, textcoords="offset points", xytext=(8, 8), fontsize=12, fontweight='bold')
    ax.annotate('D', B, textcoords="offset points", xytext=(8, -14), fontsize=12, fontweight='bold')

    # 标注 alpha 角
    arc_r = 0.6
    theta = np.linspace(-alpha / 2, alpha / 2, 50)
    ax.plot(A[0] + arc_r * np.cos(theta), A[1] + arc_r * np.sin(theta),
            color='blue', linewidth=1)
    ax.annotate(r'$\alpha$ (K)', A + np.array([arc_r + 0.1, 0]),
                fontsize=12, color='blue')

    # 标注 beta 角（平分线与 AB 线之间）
    arc_r2 = 0.9
    theta2 = np.linspace(0, beta, 30)
    ax.plot(A[0] + arc_r2 * np.cos(theta2), A[1] + arc_r2 * np.sin(theta2),
            color='purple', linewidth=1)
    ax.annotate(r'$\beta$ (L)', A + np.array([arc_r2 * np.cos(beta / 2) + 0.1, arc_r2 * np.sin(beta / 2)]),
                fontsize=12, color='purple')

    # 标注 r（AB 线）
    mid = (A + B) / 2
    ax.annotate('r', mid, textcoords="offset points", xytext=(8, -4),
                fontsize=12, fontweight='bold', color='red')

    ax.set_xlim(-2, 8)
    ax.set_ylim(-3, 5)
    ax.set_title('TC12 示意图', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.canvas.draw_idle() if hasattr(fig, 'canvas') and fig.canvas else None


def draw_tc34(fig, alpha_deg=120.0, gamma_deg=70.0, beta_deg=30.0, r_len=5.0, D_deg=1.8):
    """绘制 TC34 示意图

    与 TC12 相同，但有两对线段：
    - 第一对（绿色）与 TC12 相同，延长线交于 A1
    - 第二对（蓝色，5倍粗线，1倍长度），延长线交于 A2，夹角 gamma=70°
    - A1 与 A2 间距 0.3 倍长度
    """
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_aspect('equal')
    ax.axis('off')

    alpha = np.deg2rad(alpha_deg)
    gamma = np.deg2rad(gamma_deg)
    beta = np.deg2rad(beta_deg)
    L = 1.0

    # A1 点
    A1 = np.array([0.0, 0.0])
    # A2 点：距 A1 为 0.3L，沿 x 轴负方向偏移
    A2 = A1 + np.array([-0.3 * L, 0.0])

    d0 = 1.5

    # 第一对绿色线段（与TC12相同），交于 A1
    dir1 = np.array([np.cos(alpha / 2), np.sin(alpha / 2)])
    dir2 = np.array([np.cos(-alpha / 2), np.sin(-alpha / 2)])
    s1 = A1 + dir1 * d0
    e1 = A1 + dir1 * (d0 + L)
    s2 = A1 + dir2 * d0
    e2 = A1 + dir2 * (d0 + L)
    ax.plot([s1[0], e1[0]], [s1[1], e1[1]], color='green', linewidth=5, solid_capstyle='round')
    ax.plot([s2[0], e2[0]], [s2[1], e2[1]], color='green', linewidth=5, solid_capstyle='round')
    ax.plot([e1[0], A1[0]], [e1[1], A1[1]], color='red', linewidth=1, linestyle='--')
    ax.plot([e2[0], A1[0]], [e2[1], A1[1]], color='red', linewidth=1, linestyle='--')
    ax.plot(*A1, 'ko', markersize=5)
    ax.annotate('A1', A1, textcoords="offset points", xytext=(-18, -10), fontsize=12, fontweight='bold')

    # 第二对蓝色线段，交于 A2，夹角 gamma
    # 让蓝色线段朝向不同方向，避免与绿色重叠
    gdir1 = np.array([np.cos(np.pi + gamma / 2), np.sin(np.pi + gamma / 2)])
    gdir2 = np.array([np.cos(np.pi - gamma / 2), np.sin(np.pi - gamma / 2)])
    gs1 = A2 + gdir1 * d0
    ge1 = A2 + gdir1 * (d0 + L)
    gs2 = A2 + gdir2 * d0
    ge2 = A2 + gdir2 * (d0 + L)
    ax.plot([gs1[0], ge1[0]], [gs1[1], ge1[1]], color='blue', linewidth=5, solid_capstyle='round')
    ax.plot([gs2[0], ge2[0]], [gs2[1], ge2[1]], color='blue', linewidth=5, solid_capstyle='round')
    ax.plot([ge1[0], A2[0]], [ge1[1], A2[1]], color='red', linewidth=1, linestyle='--')
    ax.plot([ge2[0], A2[0]], [ge2[1], A2[1]], color='red', linewidth=1, linestyle='--')
    ax.plot(*A2, 'ko', markersize=5)
    ax.annotate('A2', A2, textcoords="offset points", xytext=(-18, 8), fontsize=12, fontweight='bold')

    # A1 的平分线（沿 x 正方向）和 AB 线
    bisect_dir = np.array([1.0, 0.0])
    bisect_len = 1.3 * L
    ax.plot([A1[0], A1[0] + bisect_dir[0] * bisect_len],
            [A1[1], A1[1] + bisect_dir[1] * bisect_len],
            color='red', linewidth=1, linestyle='--')

    ab_dir = np.array([np.cos(beta), np.sin(beta)])
    ab_len = 5.0 * L
    B = A1 + ab_dir * ab_len
    ax.plot([A1[0], B[0]], [A1[1], B[1]], color='red', linewidth=1, linestyle='--')

    circle = plt.Circle(B, 1.8 * L, fill=False, color='black', linewidth=3)
    ax.add_patch(circle)
    ax.annotate('B', B, textcoords="offset points", xytext=(8, 8), fontsize=12, fontweight='bold')
    ax.annotate('D', B, textcoords="offset points", xytext=(8, -14), fontsize=12, fontweight='bold')

    # 标注 alpha
    arc_r = 0.6
    theta = np.linspace(-alpha / 2, alpha / 2, 50)
    ax.plot(A1[0] + arc_r * np.cos(theta), A1[1] + arc_r * np.sin(theta),
            color='blue', linewidth=1)
    ax.annotate(r'$\alpha$ (K)', A1 + np.array([arc_r + 0.1, 0]), fontsize=12, color='blue')

    # 标注 gamma（在 A2 处）
    arc_r3 = 0.6
    theta3 = np.linspace(np.pi - gamma / 2, np.pi + gamma / 2, 50)
    ax.plot(A2[0] + arc_r3 * np.cos(theta3), A2[1] + arc_r3 * np.sin(theta3),
            color='darkblue', linewidth=1)
    ax.annotate(r'$\gamma$ (M)', A2 + np.array([-arc_r3 - 0.5, 0]), fontsize=12, color='darkblue')

    # 标注 beta
    arc_r2 = 0.9
    theta2 = np.linspace(0, beta, 30)
    ax.plot(A1[0] + arc_r2 * np.cos(theta2), A1[1] + arc_r2 * np.sin(theta2),
            color='purple', linewidth=1)
    ax.annotate(r'$\beta$ (L)', A1 + np.array([arc_r2 * np.cos(beta / 2) + 0.1, arc_r2 * np.sin(beta / 2)]),
                fontsize=12, color='purple')

    # 标注 r
    mid = (A1 + B) / 2
    ax.annotate('r', mid, textcoords="offset points", xytext=(8, -4),
                fontsize=12, fontweight='bold', color='red')

    ax.set_xlim(-4, 8)
    ax.set_ylim(-3, 5)
    ax.set_title('TC34 示意图', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.canvas.draw_idle() if hasattr(fig, 'canvas') and fig.canvas else None
