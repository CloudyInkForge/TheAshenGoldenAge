import numpy as np
from PIL import Image

class ColorMaskGenerator:
    """
    用于在 PNG 图像中生成特定颜色掩码的类。
    支持 RGB 24位深度图像，输出为 np.uint8 类型的二值数组（0/1）。
    """

    def __init__(self, tolerance: int = 0):
        """
        初始化颜色匹配器。
        :param tolerance: 允许的 RGB 颜色容差（欧几里得距离阈值），默认为0表示精确匹配。
        """
        self.tolerance = tolerance

    def read_image(self, path: str) -> np.ndarray:
        """
        读取 PNG 图像并返回 RGB 格式的 NumPy 数组。
        :param path: PNG 文件路径
        :return: 形状为 (H, W, 3) 的 uint8 数组
        """
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return np.array(img)

    def generate_mask(self, color, path: str, tolerance: int = None) -> np.ndarray:
        """
        生成颜色掩码。
        :param color: 目标颜色，可以是 (R, G, B) 元组或 0xRRGGBB 整数
        :param path: PNG 文件路径（若不传入则使用类内部路径）
        :param tolerance: 本次调用的容差，覆盖初始化时的值
        :return: 形状为 (H, W) 的 uint8 数组，1表示匹配颜色，0表示不匹配
        """
        if tolerance is None:
            tolerance = self.tolerance

        # 读取图像
        img = self.read_image(path)

        # 统一颜色格式为 (R, G, B) 元组
        if isinstance(color, int):
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            color = (r, g, b)
        elif not (isinstance(color, (tuple, list)) and len(color) == 3):
            raise ValueError("color 必须是 (R,G,B) 元组或 0xRRGGBB 整数")

        # 计算掩码
        if tolerance == 0:
            # 精确匹配
            mask = np.all(img == np.array(color, dtype=img.dtype), axis=-1)
        else:
            # 带容差的欧几里得距离匹配
            diff = img.astype(np.int16) - np.array(color, dtype=np.int16)
            sq_dist = np.sum(diff * diff, axis=-1)
            mask = sq_dist <= (tolerance * tolerance)

        return mask.astype(np.uint8)

    def save_mask(self, mask: np.ndarray, output_path: str):
        """
        将掩码保存为 PNG 图像（方便可视化）。
        :param mask: 二值掩码数组
        :param output_path: 输出文件路径
        """
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)
        img_out = Image.fromarray(mask * 255, mode='L')   # 灰度图，0/255
        img_out.save(output_path)

    # 可选：统计匹配像素数量
    def count_matched_pixels(self, mask: np.ndarray) -> int:
        """返回掩码中1的个数（即匹配颜色像素总数）。"""
        return int(np.sum(mask))

    # 可选：检查是否存在面积大于阈值的连通区域（需要连通域分析，此处仅作示例）
    # 若需要连通域过滤，可引入 scipy.ndimage.label，但为保持“尽量只使用numpy”的原则暂不实现
'''
finder = ColorMaskGenerator(tolerance=0)
mask = finder.generate_mask((146, 5, 199), "TheAshenGoldenAge/map_data/provinces.png")
count = np.sum(mask)
print(f"匹配的像素点数量：{count}")
'''