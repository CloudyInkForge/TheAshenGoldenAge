import numpy as np
from utils.get_title import TAGA_Parser
from utils.match_color import CSVLookup
from utils.get_color import ColorMaskGenerator
from utils.shortest_point import MaxInscribedCircleFinder   # 新增导入


class LocMapProcessor:
    """
    处理地图对象（省份）的工具类。
    根据领地文件获取省份ID，结合CSV颜色映射和省份PNG地图生成掩码，
    并支持裁剪每个掩码（保留一圈零边界），返回裁剪数组及其左下角坐标。
    """

    def __init__(self, landed_titles_path: str, definition_csv_path: str,
                 provinces_png_path: str, tolerance: int = 0):
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

    # ---------- 第二个方法 ----------
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

    # ---------- 第三个方法（已修改，更新 self.province_ids） ----------
    def generate_masks(self) -> list:
        """
        对当前存储的 province_ids 中的每个省份生成二值掩码数组，
        并将这些掩码存入 self.masks 列表。
        同时更新 self.province_ids 为成功生成掩码的省份ID（跳过未找到颜色的）。

        :return: 掩码列表（每个元素为 np.ndarray, dtype=uint8）
        """
        # 如果尚未获取省份ID，则默认获取前5个
        if not self.province_ids:
            self.get_province_ids()  # 默认 limit=5

        self.masks = []
        successful_ids = []   # 记录成功生成掩码的省份ID
        for pid in self.province_ids:
            color = self.csv_lookup.get(str(pid))
            if color is None:
                print(f"警告：省份 {pid} 在CSV中未找到对应颜色，跳过")
                continue
            mask = self.mask_generator.generate_mask(color, self.provinces_png_path)
            self.masks.append(mask)
            successful_ids.append(pid)
        # 更新 province_ids 为实际成功的ID，保证与 masks 长度一致
        self.province_ids = successful_ids
        return self.masks

    # ---------- 第四个方法 ----------
    def crop_masks_with_border(self) -> list:
        """
        对每个掩码进行裁剪，保留一圈零边界（即包含所有1的最小矩形向外扩展一个像素），
        并计算裁剪后数组左下角在原数组坐标系下的坐标（原点为原数组左下角 (0,0)，x向右，y向上）。

        :return: 列表，每个元素为 (cropped_array, (x, y))
                 cropped_array 为裁剪后的二维 uint8 数组；
                 (x, y) 为裁剪后数组左下角对应的新坐标系坐标。
                 如果掩码中无1，则返回原数组和 (0, 0)（即原数组左下角）。
        """
        if not self.masks:
            print("警告：没有掩码可裁剪，请先调用 generate_masks() 生成掩码。")
            return []

        # 获取原数组尺寸（假设所有掩码尺寸相同）
        H, W = self.masks[0].shape
        results = []

        for mask in self.masks:
            # 找到所有值为1的像素位置
            rows, cols = np.where(mask == 1)
            if len(rows) == 0:
                # 没有匹配像素，返回整个数组和左下角 (0,0)
                cropped = mask.copy()
                x_bottom = 0
                y_bottom = 0
            else:
                # 最小外接矩形
                r_min, r_max = rows.min(), rows.max()
                c_min, c_max = cols.min(), cols.max()

                # 向外扩展一个像素，并确保不越界
                r_min = max(0, r_min - 1)
                r_max = min(H - 1, r_max + 1)
                c_min = max(0, c_min - 1)
                c_max = min(W - 1, c_max + 1)

                # 裁剪
                cropped = mask[r_min:r_max + 1, c_min:c_max + 1]

                # 计算左下角坐标（新坐标系）
                # 原数组左下角为 (0,0)，x = 列索引，y = H-1 - 行索引
                x_bottom = c_min
                y_bottom = H - 1 - r_max

            results.append((cropped, (x_bottom, y_bottom)))

        return results

    # ---------- 新方法：计算最大内切圆并转换坐标 ----------
    def get_max_inscribed_circle_centers(self) -> list:
        """
        对每个掩码计算最大内切圆，返回每个掩码的圆心（原始坐标系）和半径。
        内部会先调用 generate_masks() 和 crop_masks_with_border() 确保数据存在。

        :return: 列表，每个元素为 dict，包含：
                 - 'province_id': 省份ID
                 - 'radius': 最大内切圆半径（浮点数）
                 - 'centers': 圆心坐标列表，每个坐标为 (x, y)，
                               原数组坐标系（原点左下角，x向右，y向上）。
                 若掩码全为0，则 radius=0，centers=[]。
        """
        # 确保掩码已生成
        if not self.masks:
            self.generate_masks()
            if not self.masks:
                print("错误：无法生成任何掩码。")
                return []

        # 获取裁剪结果（包含数组和左下角坐标）
        cropped_results = self.crop_masks_with_border()
        if not cropped_results:
            return []

        # 原数组尺寸
        H, W = self.masks[0].shape

        # 创建最大内切圆计算器
        finder = MaxInscribedCircleFinder()

        results = []
        # 遍历每个省份（province_ids 与 masks 长度一致）
        for pid, mask, (cropped, (x_bottom, y_bottom)) in zip(
                self.province_ids, self.masks, cropped_results):

            # 检查裁剪数组是否全零
            if np.all(cropped == 0):
                results.append({
                    'province_id': pid,
                    'radius': 0.0,
                    'centers': []
                })
                continue

            # 计算最大内切圆（在裁剪数组坐标系中）
            centers_crop, radius = finder.find_centers(cropped.astype(bool))

            # 从裁剪左下角坐标推导出裁剪区域在原数组中的行列范围
            c_min = x_bottom
            r_max = H - 1 - y_bottom
            cropped_h, cropped_w = cropped.shape
            r_min = r_max - cropped_h + 1

            # 将每个圆心转换到原始数组坐标系
            centers_orig = []
            for (row_c, col_c) in centers_crop:
                # 原数组中的行列索引
                row_orig = r_min + row_c
                col_orig = c_min + col_c
                # 转换为原数组坐标系 (x, y)
                x = col_orig
                y = H - 1 - row_orig
                centers_orig.append((x, y))

            results.append({
                'province_id': pid,
                'radius': radius,
                'centers': centers_orig
            })

        return results

    # ---------- 辅助方法（打印统计） ----------
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


# ===== 使用示例（测试） =====
if __name__ == '__main__':
    # 请根据实际文件路径调整
    LANDED_TITLES = "TheAshenGoldenAge/common/landed_titles/TAGA_china.txt"
    DEFINITION_CSV = "TheAshenGoldenAge/map_data/definition.csv"
    PROVINCES_PNG = "TheAshenGoldenAge/map_data/provinces.png"

    # 创建处理器实例
    processor = LocMapProcessor(LANDED_TITLES, DEFINITION_CSV, PROVINCES_PNG)

    # 第二步：获取省份ID（默认取前5个）
    ids = processor.get_province_ids(6)
    print(f"获取到的省份ID（前{len(ids)}个）: {ids}")

    # 第三步：生成掩码
    masks = processor.generate_masks()
    print(f"共生成 {len(masks)} 个掩码，对应省份: {processor.province_ids}")

    # 第四步：裁剪并获取左下角坐标
    cropped_results = processor.crop_masks_with_border()
    print(f"共裁剪出 {len(cropped_results)} 个区域")

    # 第五步：计算最大内切圆并转换坐标
    circle_results = processor.get_max_inscribed_circle_centers()
    for res in circle_results:
        print(f"省份 {res['province_id']}: 半径 {res['radius']:.2f}, 圆心数 {len(res['centers'])}")
        for (x, y) in res['centers']:
            print(f"  圆心坐标 (x={x}, y={y})")