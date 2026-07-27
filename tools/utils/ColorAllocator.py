import re
import colorsys
from typing import List, Tuple, Dict, Optional
import math

GRID_SIZE = 18
MAX_POINTS = GRID_SIZE ** 3


class ColorAllocator:
    def __init__(self, company_tree: dict, root_key: str = None):
        if not isinstance(company_tree, dict):
            raise TypeError("company_tree 必须为字典类型")
        if not company_tree:
            raise ValueError("company_tree 不能为空")

        if root_key is None:
            root_key = next(iter(company_tree))
        if root_key not in company_tree:
            raise ValueError(f"指定的根节点 '{root_key}' 不存在")

        self.root_key = root_key
        self.tree = {root_key: company_tree[root_key]}
        self.b_colors: Dict[str, Tuple[int, int, int]] = {}
        self.node_colors: Dict[str, Tuple[int, int, int]] = {}

        self._parse_and_validate()
        self._allocate()

    def assign(self) -> Dict[str, Tuple[int, int, int]]:
        return self.b_colors

    def _parse_and_validate(self):
        def calc_demand(node, path):
            if not isinstance(node, dict):
                raise TypeError(f"节点 {path} 必须是字典")
            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            if not children:
                if path[-1].startswith('b_'):
                    self._node_demands[path] = 1
                    return 1
                else:
                    raise ValueError(f"叶子节点 {path} 不是员工(b_)")
            demand = 0
            for child_name, child_node in children.items():
                child_path = path + (child_name,)
                demand += calc_demand(child_node, child_path)
            self._node_demands[path] = demand
            return demand

        self._node_demands = {}
        root_node = self.tree[self.root_key]
        total_demand = calc_demand(root_node, (self.root_key,))
        if total_demand <= 0:
            raise ValueError("总员工数必须大于0")

    # ========== 全新点阵拼接 + 引力分配 ==========
    def _allocate(self):
        # 第一步：构建形状，返回每个b路径在局部坐标的最终位置（全局坐标由递归累加）
        # 我们使用自底向上返回点集和包围盒，并在返回时平移点集。
        def build_shape(node_name, path):
            node = self.tree
            for part in path:
                node = node[part]
            if node_name.startswith('b_'):
                # 单个点，局部坐标 (0,0,0)
                return [(0, 0, 0)], (1, 1, 1)

            # 收集子节点
            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            child_items = []
            for cname in children:
                cpath = path + (cname,)
                pts, bbox = build_shape(cname, cpath)
                child_items.append((cname, pts, bbox))

            # 按体积降序
            child_items.sort(key=lambda x: x[2][0] * x[2][1] * x[2][2], reverse=True)

            # 目标：将子块排列成接近正方体的形状
            total_vol = sum(w * h * d for _, _, (w, h, d) in child_items)
            # 目标边长（向上取整）
            target_side = max(1, math.ceil(total_vol ** (1 / 3)))

            # 放置参数
            x_cursor = 0
            y_cursor = 0
            z_cursor = 0
            row_max_h = 0
            layer_max_y = 0
            # 当前行的宽度限制：目标边长
            row_limit = target_side
            # 当前层的高度限制
            layer_limit = target_side

            placed = []  # (cname, ox, oy, oz, w, h, d, original_pts)

            for cname, pts, (w, h, d) in child_items:
                # 如果放不下，换行
                if x_cursor + w > row_limit and x_cursor > 0:
                    y_cursor += row_max_h
                    row_max_h = 0
                    x_cursor = 0
                # 如果新行超出层高限制，换层
                if y_cursor + h > layer_limit and y_cursor > 0:
                    z_cursor += layer_max_y
                    layer_max_y = 0
                    y_cursor = 0
                    x_cursor = 0
                    row_max_h = 0

                # 放置
                placed.append((cname, x_cursor, y_cursor, z_cursor, w, h, d, pts))
                x_cursor += w
                row_max_h = max(row_max_h, h)
                layer_max_y = max(layer_max_y, y_cursor + h)

            # 计算包围盒
            if not placed:
                return [], (0, 0, 0)
            max_x = max(ox + w for _, ox, _, _, w, _, _, _ in placed)
            max_y = max(oy + h for _, _, oy, _, _, h, _, _ in placed)
            max_z = max(oz + d for _, _, _, oz, _, _, d, _ in placed)
            # 确保至少为1
            max_x = max(max_x, 1)
            max_y = max(max_y, 1)
            max_z = max(max_z, 1)

            # 组合平移后的点集
            all_pts = []
            for cname, ox, oy, oz, _, _, _, pts in placed:
                for (px, py, pz) in pts:
                    all_pts.append((px + ox, py + oy, pz + oz))

            return all_pts, (max_x, max_y, max_z)

        # 从根开始构建
        root_all_pts, root_bbox = build_shape(self.root_key, (self.root_key,))
        # 现在 root_all_pts 是所有 b 点的最终全局坐标（尚未缩放）
        # 同时我们需要知道每个b对应的路径，这里我们没有办法直接区分不同b的点，因为 build_shape 只返回了点集，没有路径映射。
        # 因此我们需要另一种方式：自底向上构建并同时记录每个b的坐标。
        # 重新实现：使用类变量存储b路径到坐标的映射，递归过程中直接更新。

        # 清空之前的临时数据
        self._temp_coords = {}  # b路径 -> [x, y, z] 初始坐标

        def build_and_assign(node_name, path, offset_x=0, offset_y=0, offset_z=0):
            node = self.tree
            for part in path:
                node = node[part]
            if node_name.startswith('b_'):
                b_key = '|'.join(path)
                self._temp_coords[b_key] = [offset_x, offset_y, offset_z]
                return [(0, 0, 0)], (1, 1, 1)

            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            child_items = []
            for cname in children:
                cpath = path + (cname,)
                # 先返回局部坐标的子形状（不应用本层偏移）
                pts, bbox = build_and_assign(cname, cpath, 0, 0, 0)
                child_items.append((cname, pts, bbox))

            # 排序
            child_items.sort(key=lambda x: x[2][0] * x[2][1] * x[2][2], reverse=True)

            total_vol = sum(w * h * d for _, _, (w, h, d) in child_items)
            target_side = max(1, math.ceil(total_vol ** (1 / 3)))

            x_cursor = 0
            y_cursor = 0
            z_cursor = 0
            row_max_h = 0
            layer_max_y = 0
            row_limit = target_side
            layer_limit = target_side

            placed = []
            for cname, pts, (w, h, d) in child_items:
                if x_cursor + w > row_limit and x_cursor > 0:
                    y_cursor += row_max_h
                    row_max_h = 0
                    x_cursor = 0
                if y_cursor + h > layer_limit and y_cursor > 0:
                    z_cursor += layer_max_y
                    layer_max_y = 0
                    y_cursor = 0
                    x_cursor = 0
                    row_max_h = 0

                # 记录本子块在本层中的偏移
                placed.append((cname, x_cursor, y_cursor, z_cursor, w, h, d))
                x_cursor += w
                row_max_h = max(row_max_h, h)
                layer_max_y = max(layer_max_y, y_cursor + h)

            if not placed:
                return [], (0, 0, 0)

            max_x = max(ox + w for _, ox, _, _, w, _, _ in placed)
            max_y = max(oy + h for _, _, oy, _, _, h, _ in placed)
            max_z = max(oz + d for _, _, _, oz, _, _, d in placed)
            max_x = max(max_x, 1)
            max_y = max(max_y, 1)
            max_z = max(max_z, 1)

            # 对每个子块，将其内部b点的坐标加上本层的偏移，然后递归应用偏移
            for cname, ox, oy, oz, _, _, _ in placed:
                cpath = path + (cname,)
                apply_offset(cpath, offset_x + ox, offset_y + oy, offset_z + oz)

            # 合并点集（供上层使用，但坐标仍是本层局部，因为b坐标已通过 apply_offset 直接修改为全局）
            all_pts = []
            for cname, ox, oy, oz, _, _, _ in placed:
                # 为上层提供本子块的点集（局部坐标），但上层还会再加它的偏移，会造成重复。
                # 因此放弃合并点集，改用直接记录b坐标的方式，上层只需知道包围盒用于排列。
                # 上面已经调用了 apply_offset，所以不需要返回点集了。
                pass
            # 返回空点集和包围盒，因为我们不需要再传递点集
            return [], (max_x, max_y, max_z)

        def apply_offset(subtree_path, dx, dy, dz):
            node = self.tree
            for part in subtree_path:
                node = node[part]
            if subtree_path[-1].startswith('b_'):
                key = '|'.join(subtree_path)
                # 如果已存在，则累加；否则初始化为 (0,0,0) 再加偏移
                if key not in self._temp_coords:
                    self._temp_coords[key] = [0, 0, 0]
                self._temp_coords[key][0] += dx
                self._temp_coords[key][1] += dy
                self._temp_coords[key][2] += dz
                return
            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            for cname in children:
                apply_offset(subtree_path + (cname,), dx, dy, dz)

        # 执行构建
        self._temp_coords = {}
        _, root_bbox = build_and_assign(self.root_key, (self.root_key,))
        max_x, max_y, max_z = root_bbox

        # 各轴独立缩放，填满 0-255
        scale_x = 255.0 / max_x if max_x > 0 else 1
        scale_y = 255.0 / max_y if max_y > 0 else 1
        scale_z = 255.0 / max_z if max_z > 0 else 1

        scaled = {}
        for bk, (x, y, z) in self._temp_coords.items():
            sx = int(round(x * scale_x))
            sy = int(round(y * scale_y))
            sz = int(round(z * scale_z))
            scaled[bk] = [max(0, min(255, sx)), max(0, min(255, sy)), max(0, min(255, sz))]

        # 第二步：分层引力收缩
        def collect_b_paths(node_path):
            node = self.tree
            for part in node_path:
                node = node[part]
            if node_path[-1].startswith('b_'):
                return ['|'.join(node_path)]
            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            res = []
            for cname in children:
                res.extend(collect_b_paths(node_path + (cname,)))
            return res

        node_b_cache = {}
        def get_b_list(node_path):
            key = '|'.join(node_path)
            if key not in node_b_cache:
                node_b_cache[key] = collect_b_paths(node_path)
            return node_b_cache[key]

        # 引力层配置（无h，h只有一个，跳过）
        levels = [
            ('e_', 0.1),
            ('k_', 0.1),
            ('d_', 0.1),
            ('c_', 0.1)
        ]

        def get_level_paths(start_path, prefix):
            res = []
            node = self.tree
            for part in start_path:
                node = node[part]
            if start_path[-1].startswith(prefix):
                res.append(start_path)
            children = {k: v for k, v in node.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            for cname in children:
                res.extend(get_level_paths(start_path + (cname,), prefix))
            return res

        for prefix, alpha in levels:
            level_paths = get_level_paths((self.root_key,), prefix)
            for node_path in level_paths:
                b_list = get_b_list(node_path)
                if not b_list:
                    continue
                n = len(b_list)
                cx = sum(scaled[bk][0] for bk in b_list) / n
                cy = sum(scaled[bk][1] for bk in b_list) / n
                cz = sum(scaled[bk][2] for bk in b_list) / n
                for bk in b_list:
                    pt = scaled[bk]
                    pt[0] = pt[0] + alpha * (cx - pt[0])
                    pt[1] = pt[1] + alpha * (cy - pt[1])
                    pt[2] = pt[2] + alpha * (cz - pt[2])

        # 最终取整
        for bk, pt in scaled.items():
            r = max(0, min(255, int(round(pt[0]))))
            g = max(0, min(255, int(round(pt[1]))))
            b = max(0, min(255, int(round(pt[2]))))
            self.b_colors[bk] = (r, g, b)

        # 上级代表色：取下属b最终颜色的平均值
        for key, b_list in node_b_cache.items():
            if not b_list or key.split('|')[-1].startswith('b_'):
                continue
            n = len(b_list)
            avg_r = int(round(sum(self.b_colors[bk][0] for bk in b_list) / n))
            avg_g = int(round(sum(self.b_colors[bk][1] for bk in b_list) / n))
            avg_b = int(round(sum(self.b_colors[bk][2] for bk in b_list) / n))
            self.node_colors[key] = (avg_r, avg_g, avg_b)

    # ========== 文件解析与输出（与之前相同） ==========
    @staticmethod
    def parse_paradox_script(text: str) -> dict:
        if not isinstance(text, str):
            raise TypeError("parse_paradox_script 需要字符串输入")
        if not text.strip():
            raise ValueError("输入文本为空")

        def skip_ws(i):
            while i < len(text) and text[i] in ' \t\r\n':
                i += 1
            return i

        def skip_comment(i):
            if i < len(text) and text[i] == '#':
                i += 1
                while i < len(text) and text[i] != '\n':
                    i += 1
            return i

        def parse_value(i):
            i = skip_ws(i)
            if i >= len(text):
                raise ValueError("意外结束")
            if text[i] == '{':
                i += 1
                i = skip_ws(i)
                if i < len(text) and text[i] == '}':
                    return {}, i + 1
                temp_i = i
                while temp_i < len(text) and text[temp_i] not in '}\n#=' and text[temp_i] != '=':
                    temp_i += 1
                j = skip_ws(temp_i)
                if j < len(text) and text[j] == '=':
                    obj = {}
                    while True:
                        i = skip_ws(i)
                        if i >= len(text) or text[i] == '}':
                            break
                        key_start = i
                        while i < len(text) and text[i] not in ' \t\r\n=}':
                            i += 1
                        key = text[key_start:i]
                        i = skip_ws(i)
                        if i >= len(text) or text[i] != '=':
                            raise ValueError(f"期望 '=' 在键 '{key}' 后")
                        i += 1
                        val, i = parse_value(i)
                        obj[key] = val
                        i = skip_ws(i)
                    if i >= len(text) or text[i] != '}':
                        raise ValueError(f"缺少闭合 '}}'，位置 {i}")
                    return obj, i + 1
                else:
                    arr = []
                    while True:
                        i = skip_ws(i)
                        if i >= len(text) or text[i] == '}':
                            break
                        if text[i] == '#':
                            i = skip_comment(i)
                            continue
                        tok_start = i
                        while i < len(text) and text[i] not in ' \t\r\n,}':
                            i += 1
                        token = text[tok_start:i]
                        try:
                            arr.append(int(token))
                        except ValueError:
                            arr.append(token)
                    if i >= len(text) or text[i] != '}':
                        raise ValueError(f"缺少闭合 '}}'，位置 {i}")
                    return arr, i + 1
            elif text[i].isdigit() or (text[i] == '-' and i + 1 < len(text) and text[i + 1].isdigit()):
                start = i
                if text[i] == '-':
                    i += 1
                while i < len(text) and text[i].isdigit():
                    i += 1
                return int(text[start:i]), i
            elif text[i].isalpha() or text[i] == '_':
                start = i
                while i < len(text) and (text[i].isalnum() or text[i] in '_.'):
                    i += 1
                return text[start:i], i
            elif text[i] == '"':
                i += 1
                start = i
                while i < len(text) and text[i] != '"':
                    i += 1
                if i >= len(text):
                    raise ValueError("字符串缺少结束引号")
                val = text[start:i]
                i += 1
                return val, i
            else:
                raise ValueError(f"未预期的字符: {text[i]} 位置 {i}")
            return None, i

        i = 0
        result = {}
        while i < len(text):
            i = skip_ws(i)
            if i >= len(text):
                break
            if text[i] == '#':
                i = skip_comment(i)
                continue
            key_start = i
            while i < len(text) and text[i] not in ' \t\r\n=}':
                i += 1
            key = text[key_start:i]
            i = skip_ws(i)
            if i < len(text) and text[i] == '=':
                i += 1
                val, i = parse_value(i)
                result[key] = val
            else:
                pass
        return result

    @classmethod
    def from_file(cls, filepath: str, root_key: str = None) -> 'ColorAllocator':
        if not isinstance(filepath, str):
            raise TypeError("filepath 必须为字符串")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在: {filepath}")
        except Exception as e:
            raise IOError(f"读取文件失败: {filepath}, 错误: {e}")
        if not content.strip():
            raise ValueError(f"文件内容为空: {filepath}")
        tree = cls.parse_paradox_script(content)
        if root_key is None:
            if not tree:
                raise ValueError("文件中没有解析到任何顶级定义")
            root_key = next(iter(tree))
        else:
            if root_key not in tree:
                raise KeyError(f"指定的根键 '{root_key}' 不存在于解析后的树中")
        return cls(tree, root_key=root_key)

    def apply_colors_to_file(self, input_filepath: str, output_filepath: Optional[str] = None):
        if output_filepath is None:
            output_filepath = input_filepath
        try:
            with open(input_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            raise IOError(f"读取文件失败: {input_filepath}, 错误: {e}")
        if not lines:
            raise ValueError("输入文件为空")
        stack = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^\s*([\w_]+)\s*=\s*\{', line)
            if m:
                key = m.group(1)
                if key.startswith(('h_', 'e_', 'k_', 'd_', 'c_', 'b_')):
                    stack.append((key, i))
                i += 1
                continue
            if re.match(r'^\s*\}', line):
                if not stack:
                    i += 1
                    continue
                key, start_line = stack.pop()
                path_parts = [k for k, _ in stack] + [key]
                full_path = '|'.join(path_parts)
                new_rgb = None
                if key.startswith('b_'):
                    new_rgb = self.b_colors.get(full_path)
                elif key.startswith(('e_', 'k_', 'd_', 'c_')):
                    new_rgb = self.node_colors.get(full_path)
                if new_rgb is not None:
                    replaced = False
                    for k in range(start_line, i + 1):
                        cm = re.match(r'(\s*color\s*=\s*\{)\s*(\d+)\s+(\d+)\s+(\d+)\s*(\}.*)', lines[k])
                        if cm:
                            new_line = f"{cm.group(1)} {new_rgb[0]} {new_rgb[1]} {new_rgb[2]} {cm.group(5)}"
                            if lines[k].endswith('\n'):
                                new_line += '\n'
                            lines[k] = new_line
                            replaced = True
                            break
                    if not replaced:
                        indent = re.match(r'^(\s*)\}', lines[i])
                        indent_str = indent.group(1) if indent else ''
                        color_line = f"{indent_str}    color = {{ {new_rgb[0]} {new_rgb[1]} {new_rgb[2]} }}\n"
                        lines.insert(i, color_line)
                        i += 1
                i += 1
                continue
            i += 1
        try:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            raise IOError(f"写入文件失败: {output_filepath}, 错误: {e}")

    @classmethod
    def process_file(cls, input_path: str, output_path: Optional[str] = None, root_key: Optional[str] = None):
        allocator = cls.from_file(input_path, root_key=root_key)
        allocator.apply_colors_to_file(input_path, output_path)
        return allocator.b_colors


if __name__ == "__main__":
    allocator = ColorAllocator.from_file(
        "TheAshenGoldenAge/common/landed_titles/TAGA_china.txt",
        root_key="h_taga_hanjin"
    )
    print("员工颜色数量:", len(allocator.b_colors))
    allocator.apply_colors_to_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt")
