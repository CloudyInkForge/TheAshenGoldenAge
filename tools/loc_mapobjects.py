from utils.get_title import TAGA_Parser
from utils.match_color import CSVLookup
from utils.get_color import ColorMaskGenerator


class LocMapProcessor:
    """
    处理地图对象（省份）的工具类。
    根据领地文件获取省份ID，结合CSV颜色映射和省份PNG地图生成掩码，并输出统计信息。
    """

    def __init__(self, landed_titles_path: str, definition_csv_path: str, provinces_png_path: str, tolerance: int = 0):
        """
        初始化处理器，创建所需的辅助类实例。

        :param landed_titles_path: 领地文件路径（如 TAGA_china.txt）
        :param definition_csv_path: CSV颜色映射文件路径（definition.csv）
        :param provinces_png_path: 省份PNG地图路径（provinces.png）
        :param tolerance: 颜色容差（欧几里得距离阈值），默认0精确匹配
        """
        self.landed_titles_path = landed_titles_path
        self.definition_csv_path = definition_csv_path
        self.provinces_png_path = provinces_png_path
        self.tolerance = tolerance

        # 初始化三个工具类
        self.parser = TAGA_Parser(landed_titles_path)
        self.csv_lookup = CSVLookup(definition_csv_path)
        self.mask_generator = ColorMaskGenerator(tolerance)

        # 存储省份ID列表和对应的掩码列表
        self.province_ids = []
        self.masks = []

    def get_province_ids(self, limit: int = 5) -> list:
        """
        从领地文件中获取省份ID列表。
        默认只取前5个（便于测试），传入 limit=None 可获取全部。

        :param limit: 要获取的省份数量，默认5
        :return: 省份ID列表（整数）
        """
        all_ids = self.parser.get_all_provinces()
        if limit is not None:
            self.province_ids = all_ids[:limit]
        else:
            self.province_ids = all_ids
        return self.province_ids

    def generate_masks(self) -> list:
        """
        对当前存储的 province_ids 中的每个省份生成二值掩码数组，
        并将这些掩码存入 self.masks 列表。

        :return: 掩码列表（每个元素为 np.ndarray, dtype=uint8）
        """
        # 如果尚未获取省份ID，则默认获取前5个
        if not self.province_ids:
            self.get_province_ids()  # 默认 limit=5

        self.masks = []
        for pid in self.province_ids:
            # 从CSV中查询该省份对应的RGB颜色（以字符串形式查询）
            color = self.csv_lookup.get(str(pid))
            if color is None:
                print(f"警告：省份 {pid} 在CSV中未找到对应颜色，跳过")
                continue
            # 生成掩码
            mask = self.mask_generator.generate_mask(color, self.provinces_png_path)
            self.masks.append(mask)
        return self.masks

    def print_counts(self) -> None:
        """
        遍历所有生成的掩码，打印每个掩码中匹配像素（值为1）的数量。
        """
        if not self.masks:
            print("没有掩码可统计，请先调用 generate_masks() 生成掩码。")
            return

        for idx, mask in enumerate(self.masks):
            count = self.mask_generator.count_matched_pixels(mask)
            pid = self.province_ids[idx] if idx < len(self.province_ids) else "?"
            print(f"掩码 {idx} (省份 {pid}) 的匹配像素数量：{count}")


# ===== 使用示例（供测试） =====
if __name__ == '__main__':
    # 请根据实际文件路径调整
    LANDED_TITLES = "TheAshenGoldenAge/common/landed_titles/TAGA_china.txt"
    DEFINITION_CSV = "TheAshenGoldenAge/map_data/definition.csv"
    PROVINCES_PNG = "TheAshenGoldenAge/map_data/provinces.png"

    # 创建处理器实例
    processor = LocMapProcessor(LANDED_TITLES, DEFINITION_CSV, PROVINCES_PNG)

    # 第二步：获取省份ID（默认取前5个）
    ids = processor.get_province_ids()
    print(f"获取到的省份ID（前{len(ids)}个）: {ids}")

    # 第三步：生成掩码
    masks = processor.generate_masks()
    print(f"共生成 {len(masks)} 个掩码")

    # 第四步：打印每个掩码的像素计数
    processor.print_counts()