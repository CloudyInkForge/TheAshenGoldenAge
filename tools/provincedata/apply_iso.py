import os
import openpyxl
from config import (
    elevation1000,
    elevation2000,
    elevation3000,
    plain_v,
    hill_v,
    plateau_v,
)

def to_num(value, row, col_name):
    """将单元格值转换为数值，若失败则抛出异常"""
    if value is None:
        raise ValueError(f"第{row}行{col_name}为空，请检查数据")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"第{row}行{col_name}不是有效数字: {value!r}")
    raise ValueError(f"第{row}行{col_name}类型不支持: {type(value)}")

def main():
    file_path = "tools\provincedata\main.xlsx"
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"未找到文件: {file_path}")

    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    # 气候类型映射
    climate_map = {
        1: "高温",
        2: "炎热",
        3: "温润",
        4: "温暖",
        5: "温和",
        6: "湿润草原",
        7: "干旱草原",
        8: "戈壁沙漠",
    }

    for row in range(2, ws.max_row + 1):
        # 获取关键列值，用于判断是否为空行
        key_vals = [
            ws.cell(row=row, column=4).value,
            ws.cell(row=row, column=5).value,
            ws.cell(row=row, column=6).value,
            ws.cell(row=row, column=7).value,   # 新增：第七列
            ws.cell(row=row, column=8).value,
            ws.cell(row=row, column=9).value,
            ws.cell(row=row, column=10).value,
        ]
        # 如果整行关键列为空，视为结束，跳过
        if all(v is None for v in key_vals):
            continue

        # 第六列：海拔灰度值
        gray = to_num(ws.cell(row=row, column=6).value, row, "第六列(海拔灰度)")

        # 第十一列：根据灰度值分档
        if gray < elevation1000:          # < 16000
            col11 = 0
        elif gray < elevation2000:        # 16000 ~ 24000
            col11 = 1
        elif gray < elevation3000:        # 24000 ~ 30000
            col11 = 2
        else:                             # >= 30000
            col11 = 3
        ws.cell(row=row, column=11).value = col11

        # 第五列：原始数值
        val5 = to_num(ws.cell(row=row, column=5).value, row, "第五列")
        # 第十二列：第五列 - 第十一列，最小为1
        col12 = val5 - col11
        if col12 < 1:
            col12 = 1
        # 若结果为整数，存为int，否则保留float
        if col12 == int(col12):
            col12 = int(col12)
        ws.cell(row=row, column=12).value = col12

        # 第四列：用于第十三列计算
        val4 = to_num(ws.cell(row=row, column=4).value, row, "第四列")
        if val4 < 1:
            raise ValueError(f"第{row}行第四列小于1，不符合规则: {val4}")

        # 第十二列与第四列之和
        # 要求两者均为整数（或接近整数），否则无法映射
        if abs(col12 - round(col12)) > 1e-9:
            raise ValueError(f"第{row}行第十二列存在小数，无法映射: {col12}")
        if abs(val4 - round(val4)) > 1e-9:
            raise ValueError(f"第{row}行第四列存在小数，无法映射: {val4}")

        int_col12 = int(round(col12))
        int_val4 = int(round(val4))
        sum_val = int_col12 + int_val4

        # 第十三列映射
        if sum_val == 9:
            col13 = 1
        elif sum_val in (7, 8):
            col13 = 2
        elif sum_val == 6:
            col13 = 3
        elif sum_val == 5:
            col13 = 4
        elif sum_val == 4:
            col13 = 5
        elif sum_val == 3:
            if int_col12 == 1:
                col13 = 6
            elif int_val4 == 1:
                col13 = 7
            else:
                raise ValueError(
                    f"第{row}行：第十二列+第四列之和为3，"
                    f"但第十二列={int_col12}，第四列={int_val4}，不符合特殊映射规则"
                )
        elif sum_val == 2:
            col13 = 8
        else:
            raise ValueError(
                f"第{row}行：第十二列+第四列之和={sum_val}，超出2~9的映射范围，无法确定第十三列"
            )

        ws.cell(row=row, column=13).value = col13

        # 第十四列：气候类型
        if col13 not in climate_map:
            raise ValueError(f"第{row}行：第十三列值{col13}无法映射气候类型")
        ws.cell(row=row, column=14).value = climate_map[col13]

        # 第八、九、十列：平原、丘陵、高原数量
        val8 = to_num(ws.cell(row=row, column=8).value, row, "第八列(平原)")
        val9 = to_num(ws.cell(row=row, column=9).value, row, "第九列(丘陵)")
        val10 = to_num(ws.cell(row=row, column=10).value, row, "第十列(高原)")

        # 第十五列：加权总和
        col15 = val8 * plain_v + val9 * hill_v + val10 * plateau_v
        if col15 == int(col15):
            col15 = int(col15)
        ws.cell(row=row, column=15).value = col15

        # ================== 新增：第十六列 ==================
        # 第七列：方差值（数值很大）
        val7 = to_num(ws.cell(row=row, column=7).value, row, "第七列(方差)")
        # 先取整（向下取整）
        int_val7 = int(val7)
        # 根据取整后的方差值确定系数
        if int_val7 < 1000000:
            coeff = 1.0
        elif int_val7 < 3000000:
            coeff = 0.8
        elif int_val7 < 5000000:
            coeff = 0.5
        elif int_val7 < 10000000:
            coeff = 0.3
        elif int_val7 < 18000000:
            coeff = 0.2
        else:
            coeff = 0.1

        # 第十六列 = 第十五列 * 系数，然后取整
        col16 = int(col15 * coeff)
        ws.cell(row=row, column=16).value = col16
        # ==================================================

    wb.save(file_path)
    print(f"处理完成，已写回 {file_path}")

if __name__ == "__main__":
    main()