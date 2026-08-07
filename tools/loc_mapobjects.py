import numpy as np
from pathlib import Path
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

    # ---------- 新增：整合业务，将最大内切圆圆心应用到定位文件 ----------
    def apply_circles_to_locators(self, title_key: str, base_path: str = None) -> None:
        """
        完整业务流程：
        1. 根据头衔键获取所有省份 ID；
        2. 生成掩码并计算每个省份的最大内切圆圆心（取第一个）；
        3. 使用 LocatorPositionUpdater 将圆心坐标更新到定位文件中。

        :param title_key: 头衔键，如 'd_taga_linchuan'
        :param base_path: 项目根目录（包含 TheAshenGoldenAge 文件夹），
                          若不提供，则自动从 self.landed_titles_path 向上查找。
        """
        # 1. 获取省份 ID
        try:
            self.get_province_ids(title_key)
        except ValueError as e:
            print(f"错误：{e}")
            return

        if not self.province_ids:
            print("警告：该头衔下没有省份 ID，无法继续。")
            return

        # 2. 计算最大内切圆（内部会自动生成掩码）
        circle_results = self.get_max_inscribed_circle_centers()
        if not circle_results:
            print("错误：无法获取任何省份的圆心结果。")
            return

        # 3. 确定项目根目录（用于 LocatorPositionUpdater）
        if base_path is None:
            # 从 self.landed_titles_path 向上查找包含 TheAshenGoldenAge 的父目录
            landed_path = Path(self.landed_titles_path).resolve()
            root_path = None
            for parent in landed_path.parents:
                if (parent / "TheAshenGoldenAge").is_dir():
                    root_path = parent
                    break
            if root_path is None:
                # 若未找到，则使用默认的自动推断（基于本脚本位置）
                updater = LocatorPositionUpdater()
                print("信息：未找到项目根目录，使用默认推断（基于脚本位置）。")
            else:
                updater = LocatorPositionUpdater(base_path=str(root_path))
        else:
            updater = LocatorPositionUpdater(base_path=base_path)

        # 4. 遍历每个省份，取第一个圆心更新定位
        for res in circle_results:
            pid = res['province_id']
            centers = res['centers']
            if not centers:
                print(f"省份 {pid} 没有有效圆心，跳过。")
                continue

            x, y = centers[0]  # 取第一个圆心
            # 转为整数（像素坐标本身为整数，但以防浮点误差）
            x_int = int(round(x))
            y_int = int(round(y))

            try:
                updater.update_position(id=pid, x=x_int, y=y_int)
                print(f"省份 {pid} 更新成功：position = ({x_int}, 0.0, {y_int})")
            except Exception as e:
                print(f"省份 {pid} 更新失败：{e}")


if __name__ == '__main__':
    # 配置文件路径（请根据实际项目结构调整）
    LANDED_TITLES = "TheAshenGoldenAge/common/landed_titles/TAGA_china.txt"
    DEFINITION_CSV = "TheAshenGoldenAge/map_data/definition.csv"
    PROVINCES_PNG = "TheAshenGoldenAge/map_data/provinces.png"

    # 初始化处理器
    processor = LocMapProcessor(LANDED_TITLES, DEFINITION_CSV, PROVINCES_PNG)

    # 指定要处理的头衔（请替换为实际存在的头衔键）
    TITLE_KEY = "e_taga_xv"

    try:
        # 一键执行完整流程：获取省份ID → 生成掩码 → 计算最大内切圆 → 更新定位文件
        processor.apply_circles_to_locators(TITLE_KEY)
        print(f"\n成功完成头衔 '{TITLE_KEY}' 的定位更新。")
    except Exception as e:
        print(f"\n处理过程中发生错误：{e}")

