import numpy as np
from utils.get_title import TAGA_Parser
from utils.match_color import CSVLookup
from utils.get_color import ColorMaskGenerator
from utils.shortest_point import MaxInscribedCircleFinder
from utils.LocatorPositionUpdater import LocatorPositionUpdater


class LocMapProcessor:
    """
    处理地图对象（省份）的工具类。
    根据头衔键获取其下所有省份ID，结合CSV颜色映射和省份PNG地图生成掩码，
    并支持裁剪每个掩码（保留一圈零边界），返回裁剪数组及其左下角坐标，
    以及计算最大内切圆。
    """

    def __init__(self, landed_titles_path: str, definition_csv_path: str,
                 provinces_png_path: str, tolerance: int = 0):
        self.landed_titles_path = landed_titles_path
        self.definition_csv_path = definition_csv_path
        self.provinces_png_path = provinces_png_path
        self.tolerance = tolerance

        self.parser = TAGA_Parser(landed_titles_path)
        self.csv_lookup = CSVLookup(definition_csv_path)
        self.mask_generator = ColorMaskGenerator(tolerance)

        self.province_ids = []
        self.masks = []

    # ---------- 第二个方法：通过头衔键获取省份ID ----------
    def get_province_ids(self, title_key: str) -> list:
        """
        根据给定的头衔键（如 'k_taga_henan'）获取该头衔下所有省份ID。
        头衔必须存在，否则抛出 ValueError。
        """
        self.province_ids = self.parser.get_provinces_for_title(title_key)
        return self.province_ids

    # ---------- 生成掩码 ----------
    def generate_masks(self) -> list:
        """
        对当前存储的 province_ids 中的每个省份生成二值掩码数组，
        并将掩码存入 self.masks，同时更新 self.province_ids 为成功生成掩码的ID。
        如果 province_ids 为空，则打印警告并返回空列表。
        """
        if not self.province_ids:
            print("警告：没有省份ID可生成掩码，返回空列表。")
            return []

        self.masks = []
        successful_ids = []
        for pid in self.province_ids:
            color = self.csv_lookup.get(str(pid))
            if color is None:
                print(f"警告：省份 {pid} 在CSV中未找到对应颜色，跳过")
                continue
            mask = self.mask_generator.generate_mask(color, self.provinces_png_path)
            self.masks.append(mask)
            successful_ids.append(pid)
        self.province_ids = successful_ids
        return self.masks

    # ---------- 裁剪掩码 ----------
    def crop_masks_with_border(self) -> list:
        """
        对每个掩码裁剪，保留一圈零边界，并返回裁剪数组及其左下角坐标。
        """
        if not self.masks:
            print("警告：没有掩码可裁剪，请先调用 generate_masks()")
            return []

        H, W = self.masks[0].shape
        results = []

        for mask in self.masks:
            rows, cols = np.where(mask == 1)
            if len(rows) == 0:
                cropped = mask.copy()
                x_bottom, y_bottom = 0, 0
            else:
                r_min, r_max = rows.min(), rows.max()
                c_min, c_max = cols.min(), cols.max()
                r_min = max(0, r_min - 1)
                r_max = min(H - 1, r_max + 1)
                c_min = max(0, c_min - 1)
                c_max = min(W - 1, c_max + 1)
                cropped = mask[r_min:r_max + 1, c_min:c_max + 1]
                x_bottom = c_min
                y_bottom = H - 1 - r_max

            results.append((cropped, (x_bottom, y_bottom)))

        return results

    # ---------- 计算最大内切圆 ----------
    def get_max_inscribed_circle_centers(self) -> list:
        """
        对每个掩码计算最大内切圆，返回圆心（原始坐标系）和半径。
        """
        if not self.masks:
            self.generate_masks()
            if not self.masks:
                print("错误：无法生成任何掩码。")
                return []

        cropped_results = self.crop_masks_with_border()
        if not cropped_results:
            return []

        H, W = self.masks[0].shape
        finder = MaxInscribedCircleFinder()
        results = []

        for pid, mask, (cropped, (x_bottom, y_bottom)) in zip(
                self.province_ids, self.masks, cropped_results):

            if np.all(cropped == 0):
                results.append({'province_id': pid, 'radius': 0.0, 'centers': []})
                continue

            centers_crop, radius = finder.find_centers(cropped.astype(bool))

            # 转换坐标
            c_min = x_bottom
            r_max = H - 1 - y_bottom
            cropped_h, cropped_w = cropped.shape
            r_min = r_max - cropped_h + 1

            centers_orig = []
            for (row_c, col_c) in centers_crop:
                row_orig = r_min + row_c
                col_orig = c_min + col_c
                x = col_orig
                y = H - 1 - row_orig
                centers_orig.append((x, y))

            results.append({
                'province_id': pid,
                'radius': radius,
                'centers': centers_orig
            })

        return results

    # ---------- 辅助 ----------
    def print_counts(self) -> None:
        if not self.masks:
            print("没有掩码可统计，请先调用 generate_masks()")
            return
        for idx, mask in enumerate(self.masks):
            count = self.mask_generator.count_matched_pixels(mask)
            pid = self.province_ids[idx] if idx < len(self.province_ids) else "?"
            print(f"掩码 {idx} (省份 {pid}) 的匹配像素数量：{count}")


# ===== 使用示例 =====
if __name__ == '__main__':
    LANDED_TITLES = "TheAshenGoldenAge/common/landed_titles/TAGA_china.txt"
    DEFINITION_CSV = "TheAshenGoldenAge/map_data/definition.csv"
    PROVINCES_PNG = "TheAshenGoldenAge/map_data/provinces.png"

    processor = LocMapProcessor(LANDED_TITLES, DEFINITION_CSV, PROVINCES_PNG)

    title = "d_taga_linchuan"   # 请替换为实际存在的头衔
    try:
        ids = processor.get_province_ids(title)
        print(f"头衔 '{title}' 下共有 {len(ids)} 个省份，前6个: {ids[:6]}")
    except ValueError as e:
        print(e)
        exit()

    masks = processor.generate_masks()
    print(f"共生成 {len(masks)} 个掩码")

    cropped_results = processor.crop_masks_with_border()
    print(f"共裁剪出 {len(cropped_results)} 个区域")

    circle_results = processor.get_max_inscribed_circle_centers()
    for res in circle_results:
        print(f"省份 {res['province_id']}: 半径 {res['radius']:.2f}, 圆心数 {len(res['centers'])}")