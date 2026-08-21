import os
import sys
import time
import numpy as np
import pandas as pd

# 确保可以导入同目录下的 hight 模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from hight import HeightmapSampler


def main():
    # ===== 配置路径（请根据实际环境修改） =====
    provinces_path = r"D:\CloudyInkForge\CK3\TheAshenGoldenAge\TheAshenGoldenAge\map_data\provinces.png"
    heightmap_path = r"D:\CloudyInkForge\CK3\heightmap.png"

    # definition.csv 通常与 provinces.png 在同一目录下
    csv_path = os.path.join(os.path.dirname(provinces_path), "definition.csv")
    if not os.path.exists(csv_path):
        csv_path = 'TheAshenGoldenAge/map_data/definition.csv'

    # ===== 初始化采样器 =====
    sampler = HeightmapSampler(
        provinces_path=provinces_path,
        heightmap_path=heightmap_path,
        tolerance=0,
        csv_path=csv_path
    )

    # ===== 读取 Excel =====
    main_xlsx = os.path.join(CURRENT_DIR, 'main.xlsx')
    df = pd.read_excel(main_xlsx, header=0)  # 第一行为表头

    # 获取第一列的所有 ID（跳过表头）
    ids = df.iloc[:, 0].tolist()
    total_ids = len(ids)

    # 存储结果
    avg_list = []
    var_list = []
    lt6000_list = []
    between_list = []
    gt14000_list = []

    start_time = time.time()

    # ===== 逐 ID 处理 =====
    for idx, pid in enumerate(ids, 1):
        # 进度提示（单行动态刷新）
        progress = idx / total_ids * 100
        sys.stdout.write(f"\r进度: {idx}/{total_ids} ({progress:.1f}%) - 当前ID: {pid}")
        sys.stdout.flush()

        # 处理可能的浮点数 ID（如 1.0 → 1）
        if isinstance(pid, float) and pid.is_integer():
            pid = int(pid)

        # 调用 sample_from_id 获取灰度值列表
        gray_values = sampler.sample_from_id(pid, scale_factor=2, return_type='gray')

        if not gray_values:
            avg_list.append(np.nan)
            var_list.append(np.nan)
            lt6000_list.append(0)
            between_list.append(0)
            gt14000_list.append(0)
            continue

        arr = np.array(gray_values, dtype=np.float64)

        # 平均灰度值
        avg = np.mean(arr)
        # 方差：总体方差（如需样本方差请改为 np.var(arr, ddof=1)）
        var = np.var(arr)

        # 各类别数量
        lt6000 = int(np.sum(arr < 6000))
        between = int(np.sum((arr >= 6000) & (arr <= 14000)))
        gt14000 = int(np.sum(arr > 14000))

        avg_list.append(avg)
        var_list.append(var)
        lt6000_list.append(lt6000)
        between_list.append(between)
        gt14000_list.append(gt14000)

    # 换行，结束进度显示
    sys.stdout.write("\n")

    # ===== 写入结果到第六至第十列 =====
    # 确保 DataFrame 至少有 10 列（索引 0~9）
    while len(df.columns) < 10:
        df[f'col_{len(df.columns)+1}'] = np.nan

    df.iloc[:, 5] = avg_list       # 第六列：平均灰度值
    df.iloc[:, 6] = var_list       # 第七列：方差
    df.iloc[:, 7] = lt6000_list    # 第八列：<6000 的点数量
    df.iloc[:, 8] = between_list   # 第九列：6000-14000 的点数量
    df.iloc[:, 9] = gt14000_list   # 第十列：>14000 的点数量

    # ===== 保存 Excel =====
    df.to_excel(main_xlsx, index=False)
    elapsed = time.time() - start_time
    print(f"处理完成！共处理 {total_ids} 个ID，耗时 {elapsed:.2f} 秒。结果已写入 {main_xlsx}")


if __name__ == '__main__':
    main()