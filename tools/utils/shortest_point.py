import numpy as np

class MaxInscribedCircleFinder:
    """
    求二值图像中最大内切圆的圆心（可能多个）和半径。

    输入:
        binary_image : np.ndarray, 形状内部为 1 (或 True), 背景为 0 (或 False)。
    输出:
        centers : 圆心坐标列表 [(row, col), ...]
        radius : 最大内切圆半径
    """

    @staticmethod
    def _dt_1d(f: np.ndarray) -> np.ndarray:
        """
        一维欧氏距离变换 (距离平方)
        输入 f: 初始距离值数组 (0 表示边界点, 大数表示无穷)
        输出 g: g[x] = min_i ( (x-i)^2 + f[i] )
        """
        n = len(f)
        g = np.empty(n, dtype=np.float64)
        v = np.empty(n, dtype=np.int32)   # 候选抛物线顶点索引
        z = np.empty(n + 1, dtype=np.float64)  # 各抛物线有效区间的左边界
        k = 0
        v[0] = 0
        z[0] = -np.inf
        z[1] = np.inf

        for q in range(1, n):
            # 计算新抛物线 q 与当前最后一条抛物线 v[k] 的交点
            f_q = f[q]
            v_k = v[k]
            s = ((f_q + q*q) - (f[v_k] + v_k*v_k)) / (2*q - 2*v_k)
            while s <= z[k]:
                k -= 1
                v_k = v[k]
                s = ((f_q + q*q) - (f[v_k] + v_k*v_k)) / (2*q - 2*v_k)
            k += 1
            v[k] = q
            z[k] = s
            z[k + 1] = np.inf

        k = 0
        for q in range(n):
            while z[k + 1] < q:
                k += 1
            g[q] = (q - v[k])**2 + f[v[k]]

        return g

    def find_centers(self, binary_image: np.ndarray):
        """
        计算最大内切圆的圆心集合和半径。

        Parameters
        ----------
        binary_image : np.ndarray (2D, bool 或 0/1)
            前景(形状)为 1/True，背景为 0/False。

        Returns
        -------
        centers : list of tuple
            所有具有最大距离值的像素坐标 (row, col)。
        radius : float
            最大内切圆半径 (欧氏距离)。
        """
        # 确保为浮点或布尔类型，背景0，前景1
        mask = binary_image.astype(bool)
        # 初始 f: 背景(0) 距离0，前景(1) 无穷大
        inf_val = 1e10
        f_init = np.where(mask, inf_val, 0.0).astype(np.float64)

        # 第一步：按行进行一维距离变换（沿列轴，即 axis=1）
        rows, cols = f_init.shape
        G = np.empty_like(f_init)
        for r in range(rows):
            G[r, :] = self._dt_1d(f_init[r, :])

        # 第二步：按列进行一维距离变换（沿行轴，即 axis=0）
        dist_sq = np.empty_like(f_init)
        for c in range(cols):
            dist_sq[:, c] = self._dt_1d(G[:, c])

        # 距离开平方得到实际欧氏距离
        dist = np.sqrt(dist_sq)

        # 只考虑前景区域内的距离
        dist[~mask] = 0.0  # 背景距离置0，不影响最大值查找（如果形状全是背景则返回0）

        # 寻找全局最大距离
        max_val = np.max(dist)
        # 所有达到最大值的像素坐标
        max_positions = np.argwhere(dist == max_val)

        centers = [tuple(pos) for pos in max_positions]  # (row, col)
        radius = max_val

        return centers, radius

'''
# ============ 测试 ============
if __name__ == "__main__":
    # 用户提供的不规则形状
    npa01 = np.array([
        [0]*40,
        [0]*6 + [1]*28 + [0]*6,
        [0]*4 + [1]*32 + [0]*4,
        [0]*3 + [1]*33 + [0]*4,
        [0]*2 + [1]*35 + [0]*3,
        [0]*1 + [1]*37 + [0]*2,
        [0]*1 + [1]*38 + [0]*1,
        [0]*2 + [1]*37 + [0]*1,
        [0]*1 + [1]*38 + [0]*1,
        [0]*1 + [1]*37 + [0]*2,
        [0]*2 + [1]*37 + [0]*1,
        [0]*1 + [1]*38 + [0]*1,
        [0]*1 + [1]*37 + [0]*2,
        [0]*2 + [1]*37 + [0]*1,
        [0]*1 + [1]*38 + [0]*1,
        [0]*1 + [1]*37 + [0]*2,
        [0]*2 + [1]*37 + [0]*1,
        [0]*1 + [1]*38 + [0]*1,
        [0]*2 + [1]*36 + [0]*2,
        [0]*1 + [1]*38 + [0]*1,
        [0]*2 + [1]*36 + [0]*2,
        [0]*1 + [1]*37 + [0]*2,
        [0]*2 + [1]*37 + [0]*1,
        [0]*2 + [1]*36 + [0]*2,
        [0]*2 + [1]*35 + [0]*3,
        [0]*3 + [1]*34 + [0]*3,
        [0]*4 + [1]*32 + [0]*4,
        [0]*5 + [1]*30 + [0]*5,
        [0]*6 + [1]*28 + [0]*6,
        [0]*40
    ])

    finder = MaxInscribedCircleFinder()
    centers, radius = finder.find_centers(npa01)

    print("圆心坐标 (row, col):")
    for c in centers:
        print(f"  {c}")
'''