import re
from utils.LocatorPositionUpdater import LocatorPositionUpdater


class LocatorPositionReader(LocatorPositionUpdater):
    """
    只读工具：从定位文件中读取已有的 position，不修改任何文件。

    用法：
        reader = LocatorPositionReader()
        coords = reader.get_positions([16780, 7789, 6780])
        print(coords)  # [(x, y), (x, y), (x, y)]
    """

    def __init__(self, base_path: str = None):
        super().__init__(base_path)

    def get_positions(self, province_ids: list[int]) -> list[tuple[int, int]]:
        """
        批量读取坐标。

        :param province_ids: 要查询的 ID 列表，例如 [16780, 7789, 6780]
        :return: 按输入顺序返回 [(x, y), ...]，坐标为整数，无小数点
        :raises ValueError: 如果某个 ID 在所有定位文件中都找不到
        """
        # 先构建 id -> (x, y) 映射
        # 按 FILE_BEHAVIOR 顺序读取，若同一 ID 在多个文件中出现，只取最先出现的文件
        coord_map: dict[int, tuple[int, int]] = {}

        for filename in self.FILE_BEHAVIOR:
            file_path = self.data_dir / filename
            if not file_path.exists():
                continue

            current_id = None
            with open(file_path, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue

                    # 匹配 id = 数字
                    id_match = re.match(r'^id\s*=\s*(\d+)\s*$', line)
                    if id_match:
                        current_id = int(id_match.group(1))
                        continue

                    if current_id is None:
                        continue

                    # 匹配 position = { x z y }，例如 position = { 100.000000 0.000000 200.000000 }
                    pos_match = re.match(
                        r'^position\s*=\s*\{\s*(-?\d+(?:\.\d+)?)\s+'
                        r'-?\d+(?:\.\d+)?\s+(-?\d+(?:\.\d+)?)\s*\}\s*$',
                        line
                    )
                    if pos_match:
                        # 只保留第一次遇到的 ID 对应坐标
                        if current_id not in coord_map:
                            coord_map[current_id] = (
                                int(float(pos_match.group(1))),
                                int(float(pos_match.group(2))),
                            )
                        current_id = None  # 取到坐标后，等待下一个 id
                        continue

                    # 遇到块结束符，重置当前 id
                    if line == '}':
                        current_id = None

        # 按传入顺序返回结果
        result = []
        for pid in province_ids:
            if pid not in coord_map:
                raise ValueError(f"ID {pid} 在任何定位文件中未找到。")
            result.append(coord_map[pid])

        return result

    def get_position(self, province_id: int) -> tuple[int, int]:
        """读取单个 ID 的坐标。"""
        return self.get_positions([province_id])[0]


if __name__ == "__main__":
    reader = LocatorPositionReader()
    ids = [10780, 7789, 6780]
    coordinates = reader.get_positions(ids)
    print(coordinates)  # 例如 [(100, 200), (300, 400), (500, 600)]