# iso.py
import sys
import os
from openpyxl import load_workbook

# 将 tools/ 目录加入 Python 路径，以便导入 config 和 locabetter
tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 即 tools/
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

import config
from locabetter import LocatorPositionReader


class _Polyline:
    """折线表达式：内部按 x 排序，左右两端沿相邻线段方向外延为射线。"""

    def __init__(self, points):
        self.points = sorted(points, key=lambda p: p[0])
        if len(self.points) < 2:
            raise ValueError("至少需要两个点才能构成折线")

    @staticmethod
    def _eval(p1, p2, x):
        """在 p1-p2 所在直线上求 x 对应的 y，自动支持线段外延。"""
        x1, y1 = p1
        x2, y2 = p2
        if x2 == x1:
            return y1
        return y1 + (y2 - y1) * (x - x1) / (x2 - x1)

    def y_at(self, x):
        pts = self.points

        # 左端射线
        if x <= pts[0][0]:
            return self._eval(pts[0], pts[1], x)

        # 右端射线
        if x >= pts[-1][0]:
            return self._eval(pts[-2], pts[-1], x)

        # 折线内部线段
        for i in range(len(pts) - 1):
            x1 = pts[i][0]
            x2 = pts[i + 1][0]
            if x1 <= x <= x2:
                return self._eval(pts[i], pts[i + 1], x)

        return None


class ISO:
    def __init__(self):
        # 三条降水线
        self.precip_lines = [
            self._build_line(config.isohyets400),
            self._build_line(config.isohyets800),
            self._build_line(config.isohyets1600),
        ]

        # 四条积温线
        self.gdd_lines = [
            self._build_line(config.isotherm_accumlated3000),
            self._build_line(config.isotherm_accumlated4500),
            self._build_line(config.isotherm_accumlated5300),
            self._build_line(config.isotherm_accumlated6000),
        ]

    @staticmethod
    def _build_line(points):
        """根据坐标列表生成折线表达式。"""
        return _Polyline(points)

    def classify(self, coords):
        """
        传入一个或多个新坐标，返回对应的 [PREC, GDD] 列表。

        - 单个点：iso.classify((x, y))
        - 多个点：iso.classify([(x1, y1), (x2, y2), ...])

        对每个点：
            PREC 初始为 1，每有 1 条降水线的 y 值小于该点 y 值，PREC + 1
            GDD  初始为 1，每有 1 条积温线的 y 值小于该点 y 值，GDD + 1
        """
        # 兼容单个坐标 (x, y) 或 [x, y]
        if len(coords) == 2 and all(isinstance(v, (int, float)) for v in coords):
            coords = [coords]

        result = []

        for coord in coords:
            x, y = coord

            prec = 1
            gdd = 1

            for line in self.precip_lines:
                if y <= line.y_at(x):
                    prec += 1

            for line in self.gdd_lines:
                if y <= line.y_at(x):
                    gdd += 1

            result.append([prec, gdd])

        return result

    __call__ = classify


iso = ISO()


def process_main_xlsx():
    xlsx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.xlsx")

    wb = load_workbook(xlsx_path)
    ws = wb.active

    id_list = []
    row_list = []

    # 从第 2 行开始读，跳过第 1 行表头，第一列为 ID
    for row in range(2, ws.max_row + 1):
        cell_val = ws.cell(row=row, column=1).value
        if cell_val is None:
            continue

        # 尝试转为整数
        try:
            pid = int(cell_val)
        except (ValueError, TypeError):
            continue

        id_list.append(pid)
        row_list.append(row)

    if not id_list:
        print("main.xlsx 第一列没有可用的 ID")
        wb.close()
        return

    # 使用 LocatorPositionReader 通过 ID 获取坐标
    reader = LocatorPositionReader()
    try:
        coords = reader.get_positions(id_list)
    except ValueError as e:
        print(f"获取坐标失败: {e}")
        wb.close()
        return

    results = iso.classify(coords)

    if len(results) != len(row_list):
        print(f"警告：结果数量 {len(results)} 与有效行数 {len(row_list)} 不一致")

    for row, res in zip(row_list, results):
        prec, gdd = res
        ws.cell(row=row, column=4, value=prec)
        ws.cell(row=row, column=5, value=gdd)

    wb.save(xlsx_path)
    wb.close()
    print(f"处理完成，已写入 {len(row_list)} 行到 D/E 列")


if __name__ == "__main__":
    process_main_xlsx()