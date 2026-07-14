import re
from collections import deque
from typing import List, Tuple, Dict, Optional

GRID_SIZE = 18
MAX_POINTS = GRID_SIZE ** 3


class ColorAllocator:
    def __init__(self, company_tree: dict, root_key: str = None):
        if root_key is None:
            root_key = next(iter(company_tree))
        if root_key not in company_tree:
            raise ValueError(f"指定的根节点 '{root_key}' 不存在")
        self.root_key = root_key
        self.tree = {root_key: company_tree[root_key]}
        self.b_colors: Dict[str, Tuple[int, int, int]] = {}
        self._grid = [[[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self._e_infos = []
        self._node_demands = {}
        self._all_b_paths = []

        self._parse_and_validate()
        self._allocate()

    def assign(self) -> Dict[str, Tuple[int, int, int]]:
        return self.b_colors

    def _parse_and_validate(self):
        def calc_demand(node, path):
            children = {k: v for k, v in node.items() if k.startswith(('e_','k_','d_','c_','b_'))}
            if not children:
                if path[-1].startswith('b_'):
                    self._node_demands[path] = 1
                    self._all_b_paths.append(path)
                    return 1
                else:
                    raise ValueError(f"叶子节点 {path} 不是员工(b_)")
            demand = 0
            for child_name, child_node in children.items():
                child_path = path + (child_name,)
                demand += calc_demand(child_node, child_path)
            self._node_demands[path] = demand
            return demand

        root_node = self.tree[self.root_key]
        total_demand = calc_demand(root_node, (self.root_key,))
        if total_demand > MAX_POINTS:
            raise ValueError(f"总员工数 {total_demand} 超出颜色网格容量 {MAX_POINTS}")

        def collect_e(node, path):
            for key, val in node.items():
                if key.startswith('e_'):
                    if 'color' not in val:
                        raise ValueError(f"E 节点 {path+(key,)} 缺少 color")
                    r, g, b = val['color']
                    if any(v % 15 for v in (r, g, b)):
                        raise ValueError(f"E 节点 {path+(key,)} 的颜色 {val['color']} 必须是 15 的倍数")
                    ix, iy, iz = r//15, g//15, b//15
                    if not (0 <= ix < GRID_SIZE and 0 <= iy < GRID_SIZE and 0 <= iz < GRID_SIZE):
                        raise ValueError(f"E 节点 {path+(key,)} 颜色超出范围")
                    self._e_infos.append((path+(key,), val, (ix, iy, iz), self._node_demands[path+(key,)]))

        collect_e(root_node, (self.root_key,))
        if not self._e_infos:
            raise ValueError("未找到任何 E 部门")

    def _allocate(self):
        queues, demands, e_grid_id, e_paths = [], [], [], []
        center_used = {}
        for e_path, e_node, (ix, iy, iz), demand in self._e_infos:
            if (ix, iy, iz) in center_used:
                raise ValueError(f"E 节点 {e_path} 与 {center_used[(ix,iy,iz)]} 中心颜色冲突")
            center_used[(ix, iy, iz)] = e_path
            if demand == 0:
                continue
            e_id = len(queues) + 1
            self._grid[ix][iy][iz] = e_id
            q = deque([(ix, iy, iz)])
            queues.append(q)
            demands.append(demand - 1)
            e_grid_id.append(e_id)
            e_paths.append(e_path)

        dirs = [(dx, dy, dz) for dx in (-1,0,1) for dy in (-1,0,1) for dz in (-1,0,1) if not (dx==0 and dy==0 and dz==0)]
        while not all(d == 0 for d in demands):
            for i, (q, rem, eid) in enumerate(zip(queues, demands, e_grid_id)):
                if rem == 0:
                    continue
                if not q:
                    raise RuntimeError(f"E 节点 {e_paths[i]} 无法分配足够颜色，尚缺 {rem} 个")
                x, y, z = q.popleft()
                for dx, dy, dz in dirs:
                    nx, ny, nz = x+dx, y+dy, z+dz
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and 0 <= nz < GRID_SIZE:
                        if self._grid[nx][ny][nz] == 0:
                            self._grid[nx][ny][nz] = eid
                            demands[i] -= 1
                            q.append((nx, ny, nz))
                            if demands[i] == 0:
                                break
                if demands[i] == 0:
                    q.clear()

        e_point_sets = {}
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                for k in range(GRID_SIZE):
                    eid = self._grid[i][j][k]
                    if eid > 0:
                        e_point_sets.setdefault(eid, []).append((i, j, k))

        for idx, e_info in enumerate(self._e_infos):
            e_path, e_node, _, demand = e_info
            if demand == 0:
                continue
            points = e_point_sets[idx + 1]
            children = {k: v for k, v in e_node.items() if k.startswith('k_')}
            self._recursive_divide(e_path, points, children)

    def _recursive_divide(self, parent_path: Tuple, points: List, children: Dict):
        if not children:
            return
        child_items = []
        for cname, cnode in children.items():
            cpath = parent_path + (cname,)
            child_items.append((cname, cnode, self._node_demands[cpath]))

        demands_list = [d for _, _, d in child_items]
        subsets, centers = self._cluster_partition(points, demands_list)

        for (cname, cnode, _), sub_pts, center in zip(child_items, subsets, centers):
            cpath = parent_path + (cname,)
            cnode['color'] = [center[0]*15, center[1]*15, center[2]*15]

            if cname.startswith('k_'):
                next_prefix = 'd_'
            elif cname.startswith('d_'):
                next_prefix = 'c_'
            elif cname.startswith('c_'):
                next_prefix = 'b_'
            else:
                next_prefix = None

            if next_prefix:
                next_children = {k: v for k, v in cnode.items() if k.startswith(next_prefix)}
                if next_children:
                    if next_prefix == 'b_':
                        b_names = list(next_children.keys())
                        if len(b_names) != len(sub_pts):
                            raise RuntimeError(f"C 节点 {cpath} 下的员工数 ({len(b_names)}) 与分配的点数 ({len(sub_pts)}) 不一致")
                        center_allocated = False
                        pt_idx = 0
                        for b_name in b_names:
                            b_path = cpath + (b_name,)
                            if not center_allocated:
                                self.b_colors['|'.join(b_path)] = (center[0]*15, center[1]*15, center[2]*15)
                                center_allocated = True
                            else:
                                while pt_idx < len(sub_pts) and sub_pts[pt_idx] == center:
                                    pt_idx += 1
                                if pt_idx >= len(sub_pts):
                                    raise RuntimeError(f"员工 {b_path} 分配颜色时点数不足")
                                p = sub_pts[pt_idx]
                                self.b_colors['|'.join(b_path)] = (p[0]*15, p[1]*15, p[2]*15)
                                pt_idx += 1
                    else:
                        self._recursive_divide(cpath, sub_pts, next_children)

    def _cluster_partition(self, points, demands):
        n = len(demands)
        if n == 1:
            center = self._find_center(points)
            return [points], [center]

        total = sum(demands)
        target = total // 2
        indexed = list(enumerate(demands))
        indexed.sort(key=lambda x: x[1], reverse=True)
        sum1, group1 = 0, set()
        for idx, val in indexed:
            if sum1 + val <= target or not group1:
                group1.add(idx)
                sum1 += val

        def dist_sq(a, b):
            return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2

        p1 = points[0]
        p2 = max(points, key=lambda pt: dist_sq(p1, pt))
        sorted_pts = sorted(points, key=lambda pt: dist_sq(pt, p2) - dist_sq(pt, p1))
        P1 = sorted_pts[:sum1]
        P2 = sorted_pts[sum1:]
        center1 = self._find_center(P1)
        center2 = self._find_center(P2)

        dem1 = [demands[i] for i in range(n) if i in group1]
        dem2 = [demands[i] for i in range(n) if i not in group1]
        subs1, cens1 = self._cluster_partition(P1, dem1)
        subs2, cens2 = self._cluster_partition(P2, dem2)

        all_subs, all_cens = [None]*n, [None]*n
        idx1, idx2 = 0, 0
        for i in range(n):
            if i in group1:
                all_subs[i] = subs1[idx1]
                all_cens[i] = cens1[idx1]
                idx1 += 1
            else:
                all_subs[i] = subs2[idx2]
                all_cens[i] = cens2[idx2]
                idx2 += 1
        return all_subs, all_cens

    def _find_center(self, points):
        sx = sum(p[0] for p in points)
        sy = sum(p[1] for p in points)
        sz = sum(p[2] for p in points)
        n = len(points)
        cx, cy, cz = sx/n, sy/n, sz/n
        return min(points, key=lambda p: (p[0]-cx)**2 + (p[1]-cy)**2 + (p[2]-cz)**2)

    # ========== 文件处理部分 ==========
    @staticmethod
    def parse_paradox_script(text: str) -> dict:
        """解析 Paradox 脚本为字典（支持嵌套、数组、注释）"""
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
                # 判断是数组还是块
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
                    return obj, i + 1  # 跳过 '}'
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
                val = text[start:i]
                i += 1
                return val, i
            else:
                raise ValueError(f"未预期的字符: {text[i]}")
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
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = cls.parse_paradox_script(content)
        if root_key is None:
            if not tree:
                raise ValueError("文件中没有解析到任何顶级定义")
            root_key = next(iter(tree))
        return cls(tree, root_key=root_key)

    def _parse_with_lines(self, text: str):
        """返回 (tree, line_map)，line_map: 完整路径 -> (start_line, end_line)"""
        lines = text.splitlines(keepends=True)
        self._lines_ref = lines

        tree = {}
        line_map = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r'^\s*(#|$)', line):
                i += 1
                continue
            m = re.match(r'^(\s*)([\w_]+)\s*=\s*\{', line)
            if m:
                key = m.group(2)
                start_line = i
                block_tree, end_line = self._parse_block_with_lines(lines, i, start_line, key)
                tree[key] = block_tree
                i = end_line + 1
            else:
                i += 1

        def build_map(node, path):
            for k, v in node.items():
                cur = f"{path}|{k}" if path else k
                if isinstance(v, dict) and 'start_line' in v:
                    line_map[cur] = (v['start_line'], v['end_line'])
                if isinstance(v, dict):
                    build_map(v, cur)

        build_map(tree, '')
        return tree, line_map

    def _parse_block_with_lines(self, lines, i, block_start_line, block_key):
        """
        解析从第 i 行（已含开括号）开始的块，返回 (sub_tree, end_line)。
        自动修正深度计数，正确处理嵌套子块。
        """
        sub_tree = {}
        depth = 1   # 当前行开括号已计入
        j = i + 1
        while j < len(lines) and depth > 0:
            line = lines[j]
            # 更新深度
            depth += line.count('{') - line.count('}')
            if depth == 0:
                end_line = j
                break

            # 检测子块
            m = re.match(r'^\s*([\w_]+)\s*=\s*\{', line)
            if m:
                child_key = m.group(1)
                child_start = j
                # 递归解析子块（内部会处理完整个子块直到其闭合行）
                child_tree, child_end = self._parse_block_with_lines(
                    lines, j, child_start, child_key
                )
                sub_tree[child_key] = child_tree
                # 子块闭合行 child_end 包含了 '}'，外层循环尚未处理到该行，
                # 需要手动将外层 depth 减1，并跳过 child_end 行
                depth -= 1          # 抵消子块闭合括号
                j = child_end + 1   # 跳过子块闭合行
                continue
            j += 1
        else:
            raise ValueError(f"未闭合的块: {block_key} 开始于行 {block_start_line}")

        sub_tree['start_line'] = block_start_line
        sub_tree['end_line'] = end_line
        return sub_tree, end_line

    def apply_colors_to_file(self, input_filepath: str, output_filepath: Optional[str] = None):
        if output_filepath is None:
            output_filepath = input_filepath

        with open(input_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        stack = []  # 元素: (块键名, 开始行号)
        i = 0
        while i < len(lines):
            line = lines[i]
            # 匹配 "key = {" 的行，key 以 h_/e_/k_/d_/c_/b_ 开头
            m = re.match(r'^\s*([\w_]+)\s*=\s*\{', line)
            if m:
                key = m.group(1)
                if key.startswith(('h_', 'e_', 'k_', 'd_', 'c_', 'b_')):
                    stack.append((key, i))
                i += 1
                continue

            # 匹配只包含 } 的行（闭合块）
            if re.match(r'^\s*\}', line):
                if stack:
                    key, start_line = stack.pop()
                    if key.startswith('b_'):
                        # 构建完整路径：栈中剩余的所有上级 + 当前 b_
                        path_parts = [k for k, _ in stack] + [key]
                        b_path = '|'.join(path_parts)
                        if b_path in self.b_colors:
                            new_rgb = self.b_colors[b_path]
                            # 在 start_line ~ i 之间查找并替换 color 行
                            for k in range(start_line, i + 1):
                                cm = re.match(r'(\s*color\s*=\s*\{)\s*(\d+)\s+(\d+)\s+(\d+)\s*(\}.*)', lines[k])
                                if cm:
                                    new_line = f"{cm.group(1)} {new_rgb[0]} {new_rgb[1]} {new_rgb[2]} {cm.group(5)}"
                                    if lines[k].endswith('\n'):
                                        new_line += '\n'
                                    lines[k] = new_line
                                    break
                i += 1
                continue

            i += 1

        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    @classmethod
    def process_file(cls, input_path: str, output_path: Optional[str] = None, root_key: Optional[str] = None):
        allocator = cls.from_file(input_path, root_key=root_key)
        allocator.apply_colors_to_file(input_path, output_path)
        return allocator.b_colors

allocator = ColorAllocator.from_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt", root_key="h_taga_hanjin")
print("员工颜色数量:", len(allocator.b_colors))
allocator.apply_colors_to_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt")