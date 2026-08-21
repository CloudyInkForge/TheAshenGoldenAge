# iso.py
import config


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

coords = [(6832, 2618), (7178, 2498), (6338, 2298)]
print(iso.classify(coords))