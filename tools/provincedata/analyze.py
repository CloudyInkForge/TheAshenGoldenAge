#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本说明：
1. 读取 main.xlsx 第十八列（索引 17），跳过第一行表头。
2. 统计气候类型出现次数。
3. 按参数表计算四个时代（01/02/03/04）户口总数，以及各气候类型户口数占比。
4. 输出文字报告，并用 matplotlib 生成图表。

假设：
- 参数表中 01-04 的数值表示对应气候类型单个样本/聚落的户口数；
- 第十八列的气候类型名称与参数表一致（脚本已做空格清理）。
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ----------------------------- 配置 -----------------------------
FILE = 'tools\provincedata\main.xlsx'
ERAS = ['01', '02', '03', '04']

# 中文字体设置：如果图表中文乱码，可在此处改为系统已有中文字体
plt.rcParams['font.sans-serif'] = [
    'SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB',
    'Arial Unicode MS', 'Noto Sans CJK SC', 'sans-serif'
]
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110

# ----------------------------- 参数表 -----------------------------
climate_data = {
    '气候类型': [
        '湿润草原', '干旱草原', '戈壁沙漠', '温和高原', '温和丘陵',
        '温暖农田', '温暖平原', '温暖丘陵', '温润平原', '温润丘陵',
        '炎热平原', '炎热丘陵', '炎热谷地', '高温盆地', '高温丘陵'
    ],
    '产业': [
        '牧田', '牧场', '薄田', '旱田', '小旱田',
        '良田', '农田', '小农田', '水旱田', '水旱梯田',
        '水田', '水梯田', '小水田', '圩田', '梯田'
    ],
    '01': [0.18, 0.12, 0.12, 0.45, 0.17, 1.00, 0.75, 0.45, 1.50, 0.90, 2.00, 0.90, 0.60, 1.36, 0.82],
    '02': [0.18, 0.12, 0.12, 0.60, 0.29, 1.65, 1.30, 0.60, 2.00, 1.20, 2.50, 1.20, 1.00, 2.73, 0.82],
    '03': [0.22, 0.12, 0.12, 0.60, 0.37, 2.00, 1.50, 0.78, 2.50, 1.50, 3.00, 1.50, 1.20, 3.00, 1.64],
    '04': [0.22, 0.12, 0.12, 1.00, 0.37, 2.00, 1.50, 0.90, 2.50, 1.50, 3.50, 1.80, 1.20, 4.00, 1.80],
}
climate_table = pd.DataFrame(climate_data)


def load_counts(file_path):
    """读取 main.xlsx 第十八列，并统计非空值出现次数。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")

    df = pd.read_excel(file_path, header=0)

    if df.shape[1] < 18:
        raise ValueError(f"文件列数不足 18 列，实际列数: {df.shape[1]}")

    # 第十八列索引为 17；header=0 已自动跳过第一行作为表头
    raw = df.iloc[:, 17].dropna().astype(str).str.strip()
    raw = raw[raw != '']

    if raw.empty:
        raise ValueError("第十八列没有有效数据。")

    return raw.value_counts()


def compute_counts(counts):
    """合并统计次数与参数表，计算四时代户口总数及占比。"""
    valid_types = climate_table['气候类型'].tolist()
    counts_dict = counts.to_dict()

    # 检查是否存在参数表之外的类型
    unknown = set(counts.index) - set(valid_types)
    if unknown:
        print(f"警告：第十八列中存在参数表之外的值，已忽略：{unknown}")

    counts_df = pd.DataFrame({
        '气候类型': valid_types,
        '次数': [counts_dict.get(t, 0) for t in valid_types]
    })

    merged = counts_df.merge(climate_table, on='气候类型', how='left')

    for era in ERAS:
        merged[f'{era}_户口数'] = merged['次数'] * merged[era].astype(float)
        total = merged[f'{era}_户口数'].sum()
        merged[f'{era}_占比%'] = merged[f'{era}_户口数'] / total * 100 if total else 0.0

    totals = {era: merged[f'{era}_户口数'].sum() for era in ERAS}

    return counts_df, merged, totals


def print_report(counts_df, merged, totals):
    """输出文字结果。"""
    print('=' * 80)
    print('第十八列气候类型出现次数统计')
    print('=' * 80)
    print(counts_df.sort_values('次数', ascending=False).to_string(index=False))
    print()

    print('=' * 80)
    print('四个时代户口总数')
    print('=' * 80)
    for era, total in totals.items():
        print(f'  {era} 时代: {total:,.4f}')
    print()

    for era in ERAS:
        print('=' * 80)
        print(f'{era} 时代：十五种气候类型户口数及占比')
        print('=' * 80)
        tmp = merged[['气候类型', '产业', f'{era}_户口数', f'{era}_占比%']].copy()
        tmp = tmp.sort_values(f'{era}_户口数', ascending=False)

        formatters = {
            f'{era}_户口数': lambda x, e=era: f'{x:,.4f}',
            f'{era}_占比%': lambda x, e=era: f'{x:.2f}%'
        }
        print(tmp.to_string(index=False, formatters=formatters))
        print()


def make_charts(counts_df, merged, totals):
    """生成多种图表。"""
    valid_types = merged['气候类型'].tolist()

    # 颜色方案
    era_colors = ['#4C72B0', '#DD8452', '#55A868', '#C44E52']
    type_colors = [plt.cm.tab20(i) for i in range(len(valid_types))]

    fig, axes = plt.subplots(2, 2, figsize=(22, 14))
    fig.suptitle('气候类型与四时代户口分析', fontsize=22, fontweight='bold')

    # 图1：四时代户口总数柱状图
    ax = axes[0, 0]
    total_values = [totals[e] for e in ERAS]
    bars = ax.bar(ERAS, total_values, color=era_colors, edgecolor='white', width=0.6)
    for bar, val in zip(bars, total_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + max(total_values) * 0.01,
            f'{val:,.2f}',
            ha='center',
            va='bottom',
            fontsize=11,
            fontweight='bold'
        )
    ax.set_xlabel('时代', fontsize=12)
    ax.set_ylabel('户口总数', fontsize=12)
    ax.set_title('四个时代户口总数', fontsize=14)
    ax.set_ylim(0, max(total_values) * 1.15 if max(total_values) else 1)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # 图2：气候类型出现次数条形图
    ax = axes[0, 1]
    cnt_sorted = counts_df.sort_values('次数')
    norm = plt.Normalize(vmin=cnt_sorted['次数'].min(), vmax=max(cnt_sorted['次数'].max(), 1))
    bar_colors = plt.cm.Blues(norm(cnt_sorted['次数'].values))
    bars = ax.barh(cnt_sorted['气候类型'], cnt_sorted['次数'], color=bar_colors, edgecolor='grey', alpha=0.9)
    for bar, val in zip(bars, cnt_sorted['次数']):
        ax.text(
            val + max(cnt_sorted['次数']) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(int(val)),
            va='center',
            fontsize=10
        )
    ax.set_xlabel('出现次数', fontsize=12)
    ax.set_ylabel('气候类型', fontsize=12)
    ax.set_title('第十八列气候类型出现次数', fontsize=14)
    ax.grid(axis='x', linestyle='--', alpha=0.5)

    # 图3：十五种气候类型四时代户口数分组柱状图
    ax = axes[1, 0]
    x = np.arange(len(valid_types))
    width = 0.2
    for i, era in enumerate(ERAS):
        vals = merged[f'{era}_户口数'].values
        offset = (i - (len(ERAS) - 1) / 2) * width
        bars = ax.bar(
            x + offset,
            vals,
            width,
            label=era,
            color=era_colors[i],
            edgecolor='white'
        )
    ax.set_xticks(x)
    ax.set_xticklabels(valid_types, rotation=45, ha='right', fontsize=10)
    ax.set_xlabel('气候类型', fontsize=12)
    ax.set_ylabel('户口数', fontsize=12)
    ax.set_title('十五种气候类型四时代户口数', fontsize=14)
    ax.legend(title='时代', fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    all_era_values = [merged[f'{era}_户口数'].max() for era in ERAS]
    if max(all_era_values):
        ax.set_ylim(0, max(all_era_values) * 1.15)

    # 图4：各气候类型户口数占比堆叠百分比图
    ax = axes[1, 1]
    share_cols = [f'{era}_占比%' for era in ERAS]
    share_df = merged[['气候类型'] + share_cols].set_index('气候类型')
    share_df.T.plot(
        kind='bar',
        stacked=True,
        ax=ax,
        color=type_colors,
        edgecolor='white',
        legend=False,
        width=0.6
    )
    ax.set_xticklabels(ERAS, rotation=0)
    ax.set_xlabel('时代', fontsize=12)
    ax.set_ylabel('占比 (%)', fontsize=12)
    ax.set_title('各气候类型户口数占比构成', fontsize=14)
    ax.set_ylim(0, 100)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # 堆叠图图例放在整个图下方
    handles = [
        mpatches.Patch(color=type_colors[i], label=share_df.index[i])
        for i in range(len(share_df.index))
    ]
    fig.legend(
        handles=handles,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.03),
        ncol=5,
        fontsize=9,
        title='气候类型'
    )

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig('era_population_charts.png', dpi=300, bbox_inches='tight')
    print('图表已保存为：era_population_charts.png')
    plt.show()


def main():
    try:
        counts = load_counts(FILE)
    except Exception as e:
        print(f'读取数据失败：{e}')
        return

    counts_df, merged, totals = compute_counts(counts)
    print_report(counts_df, merged, totals)
    make_charts(counts_df, merged, totals)


if __name__ == '__main__':
    main()