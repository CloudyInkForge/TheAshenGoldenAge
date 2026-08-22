import os
import sys
from openpyxl import load_workbook

# 将脚本所在目录加入 sys.path，以便导入同目录下的 config.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 从 config.py 导入字典数据
from config import DSR, GOB, JGL, CT, WT, NST, MST, SST

# 配置字典映射：数字 8 到 1 依次对应
MAPPING = {
    8: DSR,
    7: GOB,
    6: JGL,
    5: CT,
    4: WT,
    3: NST,
    2: MST,
    1: SST,
}

# 校验每个字典的值之和必须为 1
for num, mapping in MAPPING.items():
    total = sum(mapping.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"数字 {num} 对应的字典比例之和不为 1，实际为 {total}")

# Excel 文件路径（相对脚本目录）
EXCEL_PATH = os.path.join(BASE_DIR, 'main.xlsx')
if not os.path.exists(EXCEL_PATH):
    raise FileNotFoundError(f"文件不存在: {EXCEL_PATH}")

# 加载工作簿
wb = load_workbook(EXCEL_PATH)
ws = wb.active  # 使用活动工作表

# 分组存储：{分类值: [(行号, 第十六列数值), ...]}
groups = {i: [] for i in range(1, 9)}

# 读取数据，从第 2 行开始（跳过表头）
for row_idx in range(2, ws.max_row + 1):
    # 第十三列：分类值
    category_cell = ws.cell(row=row_idx, column=13)
    if category_cell.value is None:
        continue  # 跳过空行

    try:
        category = int(category_cell.value)
    except (ValueError, TypeError):
        raise ValueError(f"第 {row_idx} 行第十三列不是有效整数: {category_cell.value!r}")

    if category not in MAPPING:
        raise ValueError(f"第 {row_idx} 行第十三列值 {category} 不在 1~8 范围内")

    # 第十六列：用于排序的整数
    value_cell = ws.cell(row=row_idx, column=16)
    if value_cell.value is None:
        raise ValueError(f"第 {row_idx} 行第十六列为空")

    try:
        value = int(value_cell.value)
    except (ValueError, TypeError):
        # 尝试按浮点数处理，要求必须是整数值（如 3.0）
        try:
            float_val = float(value_cell.value)
            if not float_val.is_integer():
                raise ValueError
            value = int(float_val)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"第 {row_idx} 行第十六列不是整数: {value_cell.value!r}")

    groups[category].append((row_idx, value))

# 处理每个分组
for category, rows in groups.items():
    if not rows:
        continue

    mapping = MAPPING[category]
    keys = list(mapping.keys())          # 保持字典插入顺序
    proportions = list(mapping.values())
    N = len(rows)

    # 组内按第十六列数值从大到小排序
    rows.sort(key=lambda x: x[1], reverse=True)

    # 根据方案 A 计算每个字母应分配的行数
    if len(keys) == 1:
        counts = [N]
    elif len(keys) == 2:
        n_a = int(N * proportions[0])
        n_b = N - n_a
        counts = [n_a, n_b]
    elif len(keys) == 3:
        n_a = int(N * proportions[0])
        n_b = int(N * proportions[1])
        n_c = N - n_a - n_b
        counts = [n_a, n_b, n_c]
    else:
        raise ValueError(f"数字 {category} 对应的字典键数量不支持: {len(keys)}")

    # 依次分配字母并写入
    idx = 0
    for i, count in enumerate(counts):
        letter = chr(ord('a') + i)       # 'a', 'b', 'c'
        key_text = keys[i] if i < len(keys) else ""

        for _ in range(count):
            if idx >= N:
                break
            row_idx, _ = rows[idx]

            # 写入第十七列字母
            ws.cell(row=row_idx, column=17, value=letter)

            # 拼接第十八列名字
            col14_value = ws.cell(row=row_idx, column=14).value
            col14_str = "" if col14_value is None else str(col14_value)
            new_name = col14_str + key_text if key_text else col14_str
            ws.cell(row=row_idx, column=18, value=new_name)

            idx += 1

    if idx != N:
        raise RuntimeError(f"分组 {category} 分配数量错误：已分配 {idx} 行，总行数 {N}")

# 保存修改
wb.save(EXCEL_PATH)
print("处理完成，文件已保存。")