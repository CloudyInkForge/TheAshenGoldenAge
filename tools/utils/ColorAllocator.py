import re
from typing import List, Tuple, Dict, Optional

# -------------------- 三维旋转定义 --------------------
ROTATIONS = [
    # 0: x, y, z → (x, y, z)
    (lambda w, h, d: (w, h, d), lambda x, y, z: (x, y, z)),
    # 1: 交换 x,y
    (lambda w, h, d: (h, w, d), lambda x, y, z: (y, x, z)),
    # 2: 交换 x,z
    (lambda w, h, d: (d, h, w), lambda x, y, z: (z, y, x)),
    # 3: 交换 y,z
    (lambda w, h, d: (w, d, h), lambda x, y, z: (x, z, y)),
    # 4: 循环 x→y, y→z, z→x
    (lambda w, h, d: (h, d, w), lambda x, y, z: (y, z, x)),
    # 5: 循环 x→z, z→y, y→x
    (lambda w, h, d: (d, w, h), lambda x, y, z: (z, x, y)),
]


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
        """返回所有员工 (b_) 的 sRGB 颜色"""
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

    def _allocate(self):
        MARGINS = {
            'e_': 0,
            'k_': 0,
            'd_': 0,
            'c_': 0,
        }
        DEFAULT_MARGIN = 0

        def get_margin(node_name: str) -> int:
            for prefix, n in MARGINS.items():
                if node_name.startswith(prefix):
                    return n
            return DEFAULT_MARGIN

        def build_shape(path: Tuple[str, ...]):
            node = self.tree
            for part in path:
                node = node[part]

            if path[-1].startswith('b_'):
                key = '|'.join(path)
                return (1, 1, 1), [(key, 0, 0, 0)]

            children = {k: v for k, v in node.items()
                        if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            child_items = []
            for cname in children:
                cpath = path + (cname,)
                size, b_list = build_shape(cpath)
                child_items.append((cname, size, b_list))

            child_items.sort(key=lambda x: x[1][0] * x[1][1] * x[1][2], reverse=True)

            occupied = set()
            max_x = max_y = max_z = 0
            global_b_list = []

            for cname, (w, h, d), b_list in child_items:
                margin = get_margin(cname)
                w_margin = w + 2 * margin
                h_margin = h + 2 * margin
                d_margin = d + 2 * margin
                b_list_margin = [(bk, x + margin, y + margin, z + margin)
                                 for (bk, x, y, z) in b_list]

                best_placement = None
                best_longest_side = float('inf')
                best_volume = float('inf')

                candidates = set()
                if not occupied:
                    candidates.add((0, 0, 0))
                else:
                    for rot_idx, (size_fn, _) in enumerate(ROTATIONS):
                        rw, rh, rd = size_fn(w_margin, h_margin, d_margin)
                        for (ox_, oy_, oz_) in occupied:
                            candidates.add((ox_ + 1, oy_, oz_))
                            if ox_ - rw >= 0:
                                candidates.add((ox_ - rw, oy_, oz_))
                            candidates.add((ox_, oy_ + 1, oz_))
                            if oy_ - rh >= 0:
                                candidates.add((ox_, oy_ - rh, oz_))
                            candidates.add((ox_, oy_, oz_ + 1))
                            if oz_ - rd >= 0:
                                candidates.add((ox_, oy_, oz_ - rd))

                for ox, oy, oz in candidates:
                    for rot_idx, (size_fn, rot_fn) in enumerate(ROTATIONS):
                        rw, rh, rd = size_fn(w_margin, h_margin, d_margin)
                        if ox < 0 or oy < 0 or oz < 0:
                            continue
                        conflict = False
                        for x in range(rw):
                            if conflict: break
                            for y in range(rh):
                                if conflict: break
                                for z in range(rd):
                                    if (ox + x, oy + y, oz + z) in occupied:
                                        conflict = True
                                        break
                        if conflict:
                            continue

                        new_max_x = max(max_x, ox + rw)
                        new_max_y = max(max_y, oy + rh)
                        new_max_z = max(max_z, oz + rd)
                        new_longest = max(new_max_x, new_max_y, new_max_z)
                        new_vol = new_max_x * new_max_y * new_max_z
                        if new_longest < best_longest_side or \
                           (new_longest == best_longest_side and new_vol < best_volume):
                            best_longest_side = new_longest
                            best_volume = new_vol
                            best_placement = (ox, oy, oz, rot_idx, new_max_x, new_max_y, new_max_z)

                if best_placement is None:
                    raise RuntimeError(f"无法放置子块 {cname}，可能空间不足")

                ox, oy, oz, rot_idx, new_max_x, new_max_y, new_max_z = best_placement
                size_fn, rot_fn = ROTATIONS[rot_idx]
                rw, rh, rd = size_fn(w_margin, h_margin, d_margin)

                for x in range(rw):
                    for y in range(rh):
                        for z in range(rd):
                            occupied.add((ox + x, oy + y, oz + z))

                max_x, max_y, max_z = new_max_x, new_max_y, new_max_z

                for bk, lx, ly, lz in b_list_margin:
                    rx, ry, rz = rot_fn(lx, ly, lz)
                    gx, gy, gz = ox + rx, oy + ry, oz + rz
                    global_b_list.append((bk, gx, gy, gz))

            # ---- 新增调试输出：强制正方体前的原始包围盒 ----
            print(f"[构建节点] {'|'.join(path)}: 原始包围盒: {max_x}×{max_y}×{max_z}")

            max_dim = max(max_x, max_y, max_z)
            size_cube = (max_dim, max_dim, max_dim)

            total_cells = max_dim * max_dim * max_dim
            real_points = len(global_b_list)
            dead_points = total_cells - real_points
            print(f"[构建节点] {'|'.join(path)}: 员工数={real_points}, "
                  f"正方体边长={max_dim}, 格点总数={total_cells}, 无效点={dead_points}")

            return size_cube, global_b_list

        root_path = (self.root_key,)
        (size_x, size_y, size_z), global_b_assignments = build_shape(root_path)

        total_cells = size_x * size_y * size_z
        real_points = len(global_b_assignments)
        dead_points = total_cells - real_points
        print(f"\n===== 最终点阵 =====")
        print(f"尺寸: {size_x} × {size_y} × {size_z} = {total_cells} 格点")
        print(f"真实员工点: {real_points}, 无效点(占位): {dead_points}")

        RGB_BOX = {
            'R_min': 30, 'R_max': 225,
            'G_min': 30, 'G_max': 225,
            'B_min': 30, 'B_max': 225
        }

        def grid_to_rgb(x, y, z):
            R = RGB_BOX['R_min'] + (RGB_BOX['R_max'] - RGB_BOX['R_min']) * (x / max(size_x - 1, 1))
            G = RGB_BOX['G_min'] + (RGB_BOX['G_max'] - RGB_BOX['G_min']) * (y / max(size_y - 1, 1))
            B = RGB_BOX['B_min'] + (RGB_BOX['B_max'] - RGB_BOX['B_min']) * (z / max(size_z - 1, 1))
            return int(round(R)), int(round(G)), int(round(B))

        self.b_colors.clear()
        for bk, x, y, z in global_b_assignments:
            r, g, b = grid_to_rgb(x, y, z)
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            self.b_colors[bk] = (r, g, b)

        rgb_map = {}
        for bk, rgb in self.b_colors.items():
            rgb_map.setdefault(rgb, []).append(bk)
        rgb_collisions = 0
        for rgb, bks in rgb_map.items():
            if len(bks) > 1:
                rgb_collisions += 1
                print(f"🔴 [RGB重复] RGB{rgb} 出现在员工: {', '.join(bks)}")
        if rgb_collisions == 0:
            print("✅ 无最终 RGB 颜色重复")
        else:
            print(f"⚠️ 警告：共有 {rgb_collisions} 组 RGB 颜色重复！")

        def median_int(values):
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            if n == 0:
                return 0
            if n % 2 == 1:
                return sorted_vals[n // 2]
            else:
                return int(round((sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0))

        node_b_cache = {}

        def collect_b_paths(node_path):
            node = self.tree
            for part in node_path:
                node = node[part]
            if node_path[-1].startswith('b_'):
                return ['|'.join(node_path)]
            children = {k: v for k, v in node.items()
                        if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            res = []
            for cname in children:
                res.extend(collect_b_paths(node_path + (cname,)))
            return res

        def populate_cache(node_path):
            key = '|'.join(node_path)
            if key not in node_b_cache:
                node_b_cache[key] = collect_b_paths(node_path)
            node = self.tree
            for part in node_path:
                node = node[part]
            children = {k: v for k, v in node.items()
                        if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
            for cname in children:
                populate_cache(node_path + (cname,))

        populate_cache((self.root_key,))

        self.node_colors.clear()
        for node_path_str, b_list in node_b_cache.items():
            if not b_list or node_path_str.split('|')[-1].startswith('b_'):
                continue
            R_vals = [self.b_colors[bk][0] for bk in b_list]
            G_vals = [self.b_colors[bk][1] for bk in b_list]
            B_vals = [self.b_colors[bk][2] for bk in b_list]
            med_R = median_int(R_vals)
            med_G = median_int(G_vals)
            med_B = median_int(B_vals)
            self.node_colors[node_path_str] = (med_R, med_G, med_B)

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