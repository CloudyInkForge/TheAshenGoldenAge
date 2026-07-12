import re
from pathlib import Path


class LocatorPositionUpdater:
    """
    用于修改 TheAshenGoldenAge 中地图物件定位文件 position 字段的类。
    用法：
        updater = LocatorPositionUpdater(base_path="项目根目录")
        updater.update_position(id=123, x=500, y=600)
    base_path 默认为自动向上查找包含 'TheAshenGoldenAge' 文件夹的目录。
    注意：假设本脚本位于 tools/utils/ 下，自动推算的根目录为向上三级。
    """

    # 文件名 -> 若找不到ID是否报错
    FILE_BEHAVIOR = {
        "building_locators.txt": True,   # 必须找到，否则报错
        "combat_locators.txt": True,
        "siege_locators.txt": True,
        "stack_locators.txt": True,
        "player_stack_locators.txt": False,  # 已被弃用，ID 可能缺失，忽略即可
    }

    def __init__(self, base_path: str = None):
        """
        :param base_path: 项目根目录，应包含 'TheAshenGoldenAge' 文件夹。
                          若不传，则从本脚本所在位置（tools/utils/）向上三级查找。
        """
        if base_path is None:
            # 脚本位于 tools/utils/ 下，向上三级到达项目根目录
            self.base_path = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_path = Path(base_path).resolve()

        self.data_dir = self.base_path / "TheAshenGoldenAge" / "gfx" / "map" / "map_object_data"
        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")

    def update_position(self, id: int, x: int, y: int):
        """
        将指定 id 的 position 修改为 (x, 0.0, y) 格式，保留6位小数。
        :param id: 要修改的物件ID
        :param x: 新的 X 坐标（整数）
        :param y: 新的 Y 坐标（整数）
        """
        new_x = f"{x:.6f}"
        new_y = f"{y:.6f}"
        new_position_str = f"position={{ {new_x} 0.000000 {new_y} }}"

        for filename, raise_if_missing in self.FILE_BEHAVIOR.items():
            file_path = self.data_dir / filename
            if not file_path.exists():
                print(f"警告: 文件不存在，跳过 -> {file_path}")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            modified = False
            new_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]
                # 检查是否匹配到目标 id
                match = re.match(r'^(\s*)id\s*=\s*(\d+)\s*$', line)
                if match and int(match.group(2)) == id:
                    # 关键修正：保留 id 行本身
                    new_lines.append(line)

                    j = i + 1
                    while j < len(lines):
                        pos_match = re.match(r'^(\s*)position\s*=\s*\{.*\}\s*$', lines[j])
                        if pos_match:
                            orig_indent = pos_match.group(1)
                            new_lines.append(f"{orig_indent}{new_position_str}\n")
                            modified = True
                            i = j + 1
                            break
                        # 如果遇到块结束 '}' 或新的 id 行，则说明格式异常
                        if re.match(r'^\s*\}\s*$', lines[j]) or re.match(r'^\s*id\s*=', lines[j]):
                            raise ValueError(f"在 id={id} 的块中未找到 position 行: {file_path}")
                        new_lines.append(lines[j])
                        j += 1
                    else:
                        raise ValueError(f"在 id={id} 的块中未找到 position 行: {file_path}")
                else:
                    new_lines.append(line)
                    i += 1

            if not modified:
                if raise_if_missing:
                    raise ValueError(f"ID {id} 在文件 {filename} 中未找到，且该文件要求必须存在。")
                else:
                    print(f"信息: ID {id} 在 {filename} 中未找到，已忽略（该文件已弃用）。")
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(f"已更新 {filename} 中 ID {id} 的 position 为 ({x}, 0.0, {y})")


if __name__ == "__main__":
    # 简单测试，实际使用时请根据项目结构调整
    updater = LocatorPositionUpdater()
    updater.update_position(id=1, x=100, y=200)