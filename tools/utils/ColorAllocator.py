import re
import math
import colorsys
from typing import List, Tuple, Dict, Optional


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
        self._node_demands = {}

        self._parse_and_validate()
        self._build_hue_perception_tables()
        self._assign_colors_by_space(self.root_key, (self.root_key,),
                                     h_range=(0.0, 360.0),
                                     s_range=(0.3, 0.7),
                                     l_range=(0.3, 0.7))

    def assign(self) -> Dict[str, Tuple[int, int, int]]:
        return self.b_colors

    # ========== 解析与需求计算 ==========
    def _parse_and_validate(self):
        def calc_demand(node, path):
            if not isinstance(node, dict):
                raise TypeError(f"节点 {path} 必须是字典")
            children = {k: v for k, v in node.items()
                        if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
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
            if demand < 0:
                raise RuntimeError(f"节点 {path} 的需求计算异常")
            self._node_demands[path] = demand
            return demand

        root_node = self.tree[self.root_key]
        total_demand = calc_demand(root_node, (self.root_key,))
        if total_demand <= 0:
            raise ValueError("总员工数必须大于0")

    # ========== 色相感知灵敏度建模 ==========
    def _build_hue_perception_tables(self):
        """
        构建色相感知权重表与累积感知长度表。
        使用双峰模型：在黄色 (60°) 和蓝色 (240°) 附近灵敏度高，
        在绿色 (150°) 和红色 (330°) 附近灵敏度低。
        w(h) = 1.0 + 0.35 * cos(2 * (h - 60°) )，取值范围 [0.65, 1.35]。
        对 0~360 度每整度采样，计算累积积分（梯形法则）。
        """
        self._hue_samples = 361  # 0 到 360 共 361 个点
        self._hue_weights = [0.0] * self._hue_samples
        step = 1.0  # 1 度
        total_sum = 0.0
        for i in range(self._hue_samples):
            h = i  # 0..360
            rad = math.radians(2 * (h - 60))
            w = 1.0 + 0.35 * math.cos(rad)
            self._hue_weights[i] = w
            total_sum += w * step
        # 构建累积分布（未归一化）
        self._cumulative = [0.0] * self._hue_samples
        cum = 0.0
        for i in range(self._hue_samples):
            cum += self._hue_weights[i] * step
            self._cumulative[i] = cum
        # 归一化系数，使总感知长度为 1（用于比例映射）
        self._total_perception = cum

    def _hue_perception_length(self, h1: float, h2: float) -> float:
        """计算色相区间 [h1, h2) 的感知长度。h1, h2 在 [0,360] 内。"""
        if h1 >= h2:
            return 0.0
        # 确保在 [0,360] 内
        h1 = max(0.0, min(360.0, h1))
        h2 = max(0.0, min(360.0, h2))
        # 线性插值累积值
        def cum_at(h):
            i = int(h)
            if i >= 360:
                return self._cumulative[360]
            frac = h - i
            return self._cumulative[i] + frac * (self._cumulative[i+1] - self._cumulative[i])
        return cum_at(h2) - cum_at(h1)

    def _perceptual_mid_hue(self, h_range: Tuple[float, float]) -> float:
        """返回色相区间的感知中点，即左右感知长度相等的点。"""
        h1, h2 = h_range
        total_len = self._hue_perception_length(h1, h2)
        if total_len <= 0:
            return (h1 + h2) / 2.0
        target = self._hue_perception_length(h1, h2) / 2.0
        # 二分查找
        lo, hi = h1, h2
        for _ in range(50):  # 足够精度
            mid = (lo + hi) / 2.0
            left_len = self._hue_perception_length(h1, mid)
            if left_len < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    def _hue_interval_by_perception(self, h_start: float, h_end: float,
                                    perception_fraction: float) -> Tuple[float, float]:
        """
        从 h_start 开始，截取一段感知长度等于 perception_fraction * 区间总感知长度的子区间，
        返回 (new_start, new_end)。若 perception_fraction == 1 则直接返回 (h_start, h_end)。
        """
        if perception_fraction <= 0:
            return h_start, h_start
        if perception_fraction >= 1.0:
            return h_start, h_end
        total_len = self._hue_perception_length(h_start, h_end)
        target_len = total_len * perception_fraction
        # 二分找 new_end
        lo, hi = h_start, h_end
        for _ in range(50):
            mid = (lo + hi) / 2.0
            if self._hue_perception_length(h_start, mid) < target_len:
                lo = mid
            else:
                hi = mid
        new_end = (lo + hi) / 2.0
        return h_start, new_end

    # ========== 跳跃排列 ==========
    @staticmethod
    def _leapfrog_order(n: int) -> List[int]:
        """
        生成 [0, n) 的一个排列，使得排列后相邻原始索引在位置上尽可能远。
        使用逐层二分策略。
        """
        if n <= 0:
            return []
        if n == 1:
            return [0]
        order = []
        intervals = [(0, n - 1)]
        while intervals:
            next_intervals = []
            for lo, hi in intervals:
                if lo > hi:
                    continue
                mid = (lo + hi) // 2
                order.append(mid)
                if lo <= mid - 1:
                    next_intervals.append((lo, mid - 1))
                if mid + 1 <= hi:
                    next_intervals.append((mid + 1, hi))
            intervals = next_intervals
        return order

    # ========== 基于空间划分的颜色分配 ==========
    def _assign_colors_by_space(self, node_name: str, path: tuple,
                                h_range: Tuple[float, float],
                                s_range: Tuple[float, float],
                                l_range: Tuple[float, float],
                                d_index: int = None, d_count: int = None,
                                k_index: int = None, k_count: int = None):
        """
        递归为树中每个节点分配颜色。

        核心改进：当切分轴为 H 时，子区间按“感知均匀”方式分配，使每个子节点
        获得的色相感知长度与其需求成正比，而非线性长度。
        """
        # 取出当前节点的原始数据
        node = self.tree
        for part in path:
            node = node[part]

        # 筛选合法子节点
        children = {k: v for k, v in node.items()
                    if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}

        # 确定子节点的切分轴
        child_axis = None
        if children:
            first_cname = next(iter(children))
            if first_cname.startswith('b_'):
                child_axis = 'L'
            elif first_cname.startswith('c_'):
                child_axis = 'S'
            else:
                child_axis = 'H'

        # 计算当前节点的默认颜色坐标
        # H 取感知中点，S、L 取线性中点
        h_mid = self._perceptual_mid_hue(h_range)
        s_mid = (s_range[0] + s_range[1]) / 2.0
        l_mid = (l_range[0] + l_range[1]) / 2.0

        # === d节点专属环绕取色 ===
        is_d_node = node_name.startswith('d_')
        d_staggered = False

        if is_d_node and d_index is not None and d_count is not None:
            s_center = (s_range[0] + s_range[1]) / 2.0
            l_center = (l_range[0] + l_range[1]) / 2.0

            if d_count > 1:
                d_staggered = True
                order = self._leapfrog_order(d_count)
                rank = order.index(d_index)
                base_angle = 2.0 * math.pi * rank / d_count

                # 跨k角度微调
                if k_index is not None and k_count is not None and k_count > 1:
                    angle_offset = 2.0 * math.pi * 0.03 * (k_index % 7)
                    base_angle += angle_offset

                s_half = (s_range[1] - s_range[0]) / 2.0
                l_half = (l_range[1] - l_range[0]) / 2.0
                radius = min(s_half, l_half) * 0.5

                s_mid = s_center + radius * math.cos(base_angle)
                l_mid = l_center + radius * math.sin(base_angle)

                s_mid = max(s_range[0], min(s_range[1], s_mid))
                l_mid = max(l_range[0], min(l_range[1], l_mid))
            else:
                # 单个d节点仍可应用跨k微调（保持原有意图）
                if k_index is not None and k_count is not None and k_count > 1:
                    offset_pattern = [-0.04, 0.0, 0.04]
                    k_s_offset = offset_pattern[k_index % 3] * (s_range[1] - s_range[0])
                    s_mid = max(s_range[0], min(s_range[1], s_center + k_s_offset))
                    l_mid = l_center
                # 不设置 d_staggered，以便可叠加父节点偏移

        # === 父节点微小偏移 ===
        if child_axis is not None and not d_staggered:
            depth = len(path)
            sign = 1 if depth % 2 == 0 else -1
            offset_ratio = 0.02
            if child_axis == 'H':
                # 在H轴上偏移时，仍使用线性偏移（微小量不影响感知均匀性）
                h_mid += sign * (h_range[1] - h_range[0]) * offset_ratio
            elif child_axis == 'S':
                s_mid += sign * (s_range[1] - s_range[0]) * offset_ratio
            l_mid += sign * (l_range[1] - l_range[0]) * offset_ratio

        rgb = self._hsl_to_rgb(h_mid, s_mid, l_mid)

        # 保存颜色
        path_str = '|'.join(path)
        self.node_colors[path_str] = rgb
        if node_name.startswith('b_'):
            self.b_colors[path_str] = rgb

        if not children:
            return

        # 准备子节点
        child_items = []
        total_demand = 0
        for cname, cnode in children.items():
            cpath = path + (cname,)
            demand = self._node_demands.get(cpath, 0)
            child_items.append((cname, cnode, demand, cpath))
            total_demand += demand

        if total_demand == 0:
            return

        axis = child_axis

        # === 跳跃排列重排子节点顺序 ===
        n_children = len(child_items)
        lf_order = self._leapfrog_order(n_children)
        # 先计算每个子节点应获得的“长度”（如果是H轴则为感知长度，否则为线性长度）
        child_lengths = []
        for cname, cnode, demand, cpath in child_items:
            if axis == 'H':
                total_len = self._hue_perception_length(h_range[0], h_range[1])
                child_lengths.append(total_len * (demand / total_demand))
            elif axis == 'S':
                total_len = s_range[1] - s_range[0]
                child_lengths.append(total_len * (demand / total_demand))
            else:  # L
                total_len = l_range[1] - l_range[0]
                child_lengths.append(total_len * (demand / total_demand))

        # 按跳跃顺序排列长度及子项
        reordered_lengths = [child_lengths[lf_order[j]] for j in range(n_children)]
        reordered_items = [child_items[lf_order[j]] for j in range(n_children)]

        # 分配区间
        if axis == 'H':
            current_h = h_range[0]
            for j, (cname, cnode, demand, cpath) in enumerate(reordered_items):
                target_len = reordered_lengths[j]
                child_h_end = self._hue_interval_by_perception(
                    current_h, h_range[1],
                    target_len / self._hue_perception_length(current_h, h_range[1])
                )[1] if self._hue_perception_length(current_h, h_range[1]) > 0 else current_h
                child_h_range = (current_h, child_h_end)
                current_h = child_h_end
                child_s_range = s_range
                child_l_range = l_range

                # 传递上下文索引
                orig_idx = lf_order[j]
                new_d_index = d_index
                new_d_count = d_count
                new_k_index = k_index
                new_k_count = k_count
                if cname.startswith('d_'):
                    new_d_index = orig_idx
                    new_d_count = n_children
                elif cname.startswith('k_'):
                    new_k_index = orig_idx
                    new_k_count = n_children
                    new_d_index = None
                    new_d_count = None
                elif cname.startswith('e_'):
                    new_k_index = None
                    new_k_count = None
                    new_d_index = None
                    new_d_count = None
                elif cname.startswith('c_'):
                    new_d_index = None
                    new_d_count = None

                self._assign_colors_by_space(cname, cpath,
                                             child_h_range, child_s_range, child_l_range,
                                             d_index=new_d_index, d_count=new_d_count,
                                             k_index=new_k_index, k_count=new_k_count)
        else:
            # S 或 L 轴，线性分配
            if axis == 'S':
                start = s_range[0]
                length = s_range[1] - s_range[0]
            else:  # L
                start = l_range[0]
                length = l_range[1] - l_range[0]

            current_start = start
            for j, (cname, cnode, demand, cpath) in enumerate(reordered_items):
                interval_length = reordered_lengths[j]
                child_h_range = h_range
                if axis == 'S':
                    child_s_range = (current_start, current_start + interval_length)
                    child_l_range = l_range
                else:
                    child_s_range = s_range
                    child_l_range = (current_start, current_start + interval_length)
                current_start += interval_length

                orig_idx = lf_order[j]
                new_d_index = d_index
                new_d_count = d_count
                new_k_index = k_index
                new_k_count = k_count
                if cname.startswith('d_'):
                    new_d_index = orig_idx
                    new_d_count = n_children
                elif cname.startswith('k_'):
                    new_k_index = orig_idx
                    new_k_count = n_children
                    new_d_index = None
                    new_d_count = None
                elif cname.startswith('e_'):
                    new_k_index = None
                    new_k_count = None
                    new_d_index = None
                    new_d_count = None
                elif cname.startswith('c_'):
                    new_d_index = None
                    new_d_count = None

                self._assign_colors_by_space(cname, cpath,
                                             child_h_range, child_s_range, child_l_range,
                                             d_index=new_d_index, d_count=new_d_count,
                                             k_index=new_k_index, k_count=new_k_count)

    @staticmethod
    def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
        r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
        return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

    # ========== 文件处理（保持不变） ==========
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
                        raise ValueError(f"解析块时缺少闭合 '}}'，位置 {i}")
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
                        raise ValueError(f"解析数组时缺少闭合 '}}'，位置 {i}")
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
                raise KeyError(f"指定的根键 '{root_key}' 在解析后的树中不存在")
        return cls(tree, root_key=root_key)

    def apply_colors_to_file(self, input_filepath: str, output_filepath: Optional[str] = None):
        if output_filepath is None:
            output_filepath = input_filepath
        try:
            with open(input_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            raise IOError(f"读取输入文件失败: {input_filepath}, 错误: {e}")

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
            raise IOError(f"写入输出文件失败: {output_filepath}, 错误: {e}")

    @classmethod
    def process_file(cls, input_path: str, output_path: Optional[str] = None, root_key: Optional[str] = None):
        allocator = cls.from_file(input_path, root_key=root_key)
        allocator.apply_colors_to_file(input_path, output_path)
        if not allocator.b_colors:
            raise RuntimeError("处理完成但未生成任何员工颜色分配")
        return allocator.b_colors


if __name__ == "__main__":
    allocator = ColorAllocator.from_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt", root_key="h_taga_hanjin")
    print("员工颜色数量:", len(allocator.b_colors))
    allocator.apply_colors_to_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt")