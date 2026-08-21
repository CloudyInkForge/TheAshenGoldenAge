import os
import sys
tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 即 tools/
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None 
from utils.get_color import ColorMaskGenerator  # 假设已有该类
from utils.match_color import CSVLookup

class HeightmapSampler:
    """
    根据 provinces 图像中的颜色匹配坐标，
    从二倍分辨率的 heightmap.png 中采样 16 位灰度值。
    支持直接输入省份 ID，通过 CSVLookup 获取对应颜色后采样。
    """

    def __init__(self, provinces_path: str, heightmap_path: str,
                 tolerance: int = 0,
                 csv_path: str = 'TheAshenGoldenAge/map_data/definition.csv'):
        """
        :param provinces_path: 用于颜色匹配的 provinces.png 路径
        :param heightmap_path: 二倍分辨率的 16 位灰度 heightmap.png 路径
        :param tolerance: 颜色匹配容差，传递给 ColorMaskGenerator
        :param csv_path: 省份定义 CSV 文件路径，用于 ID 到颜色的映射
        """
        self.provinces_path = provinces_path
        self.heightmap_path = heightmap_path
        self.tolerance = tolerance
        self.mask_generator = ColorMaskGenerator(tolerance=tolerance)
        self.heightmap = self._load_heightmap()
        self.lookup = CSVLookup(csv_path)

    def _load_heightmap(self) -> np.ndarray:
        """加载 16 位灰度 heightmap.png，返回 uint16 数组"""
        img = Image.open(self.heightmap_path)
        # 常见 16 位灰度模式：'I', 'I;16', 'I;16L', 'I;16B'
        if img.mode not in ('I', 'I;16', 'I;16L', 'I;16B'):
            # 如果不是 16 位，尝试转换为 16 位（可能丢失精度）
            img = img.convert('I')
        return np.array(img, dtype=np.uint16)

    def get_absolute_coordinates(self, color) -> list:
        """
        获取 provinces 图像中匹配颜色像素的绝对坐标列表，
        格式为 [(x, y), (x, y), ...]，原点在图像左上角。
        """
        mask = self.mask_generator.generate_mask(color, self.provinces_path, self.tolerance)
        coords_rc = np.argwhere(mask == 1)          # (row, col) => (y, x)
        coords_xy = coords_rc[:, [1, 0]]            # 转为 (x, y)
        return [tuple(coord) for coord in coords_xy]

    def sample_from_heightmap(self, color, scale_factor: int = 2, return_type: str = 'full'):
        """
        根据颜色匹配坐标，从 heightmap 中采样对应位置的灰度值。

        :param color: 目标颜色
        :param scale_factor: 坐标放大倍数（heightmap 相对 provinces 的倍数）
        :param return_type:
            'full'   -> 返回 [(orig_x, orig_y, scaled_x, scaled_y, gray_value), ...]
            'scaled' -> 返回 [(scaled_x, scaled_y, gray_value), ...]
            'gray'   -> 只返回灰度值列表 [gray_value, ...]
        :return: 根据 return_type 返回对应格式的列表
        """
        # 获取原始坐标 (x, y)
        orig_coords = np.array(self.get_absolute_coordinates(color), dtype=np.int64)
        if orig_coords.size == 0:
            return [] if return_type != 'gray' else []

        # 坐标放大
        scaled_coords = orig_coords * scale_factor

        # 检查 heightmap 边界，过滤越界点
        hm_h, hm_w = self.heightmap.shape
        valid = (scaled_coords[:, 0] < hm_w) & (scaled_coords[:, 1] < hm_h)
        orig_valid = orig_coords[valid]
        scaled_valid = scaled_coords[valid]

        # 采样灰度值：注意 numpy 索引顺序为 [row, col] => [y, x]
        gray_values = self.heightmap[scaled_valid[:, 1], scaled_valid[:, 0]]

        if return_type == 'gray':
            return [int(g) for g in gray_values]
        elif return_type == 'scaled':
            return [(int(x), int(y), int(g)) for (x, y), g in zip(scaled_valid, gray_values)]
        else:  # 'full' 或任何其他值
            return [(int(ox), int(oy), int(sx), int(sy), int(g))
                    for (ox, oy), (sx, sy), g in zip(orig_valid, scaled_valid, gray_values)]

    def sample_from_id(self, province_id, scale_factor: int = 2, return_type: str = 'gray'):
        """
        根据省份 ID 采样灰度值。内部通过 CSVLookup 将 ID 转换为颜色，
        然后调用 sample_from_heightmap 完成采样。

        :param province_id: 省份 ID（整数或字符串）
        :param scale_factor: 坐标放大倍数
        :param return_type: 返回格式，与 sample_from_heightmap 相同
        :return: 根据 return_type 返回对应格式的列表；若 ID 不存在则返回空列表
        """
        color = self.lookup.get(str(province_id))
        if color is None:
            # ID 未找到时返回空列表（或可根据需要抛出异常）
            return []
        return self.sample_from_heightmap(color, scale_factor, return_type)


if __name__ == '__main__':
    sampler = HeightmapSampler(
        provinces_path=r"D:\CloudyInkForge\CK3\TheAshenGoldenAge\TheAshenGoldenAge\map_data\provinces.png",
        heightmap_path=r"D:\CloudyInkForge\CK3\heightmap.png",
        tolerance=0
    )

    # 使用省份 ID 采样灰度值（示例 ID: 10073）
    gray_values = sampler.sample_from_id(10073, scale_factor=2, return_type='gray')
    print("ID 9768 的灰度值列表：", gray_values)
