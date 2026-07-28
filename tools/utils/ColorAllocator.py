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
        self.node_colors: Dict[str, Tuple[int, int, int]] = {}   # 存储所有节点的颜色
        self._node_demands = {}

        self._parse_and_validate()
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

    # ========== 跳跃排列（核心优化） ==========
    @staticmethod
    def _leapfrog_order(n: int) -> List[int]:
        """
        生成 [0, n) 的一个排列，使得排列后相邻原始索引在位置上尽可能远。

        使用逐层二分策略：
        - 第一层：取整个范围 [0, n-1] 的中点
        - 第二层：取左半段和右半段各自的中点
        - 第三层：取四个四分之一段各自的中点
        - ...依次类推，直到所有位置被填充

        例如 n=8 返回 [4, 1, 6, 0, 2, 5, 7, 3]，
        意味着位置 0 放 child[4]，位置 1 放 child[1]，位置 2 放 child[6]...
        这样 child[0] 在位置 3，child[1] 在位置 1，它们之间隔了 2 个位置，
        而非像顺序排列那样紧挨在一起。

        效果：对于 n 个等权子节点，相邻子节点（在树结构中相邻）在颜色空间中
        的间距约为 range/2，而顺序排列仅为 range/n。
        当 n=20 时，顺序排列相邻间距 = range/20 = 0.025（几乎无法区分），
        跳跃排列相邻间距 ≈ range/2 = 0.25（清晰可辨），提升约 10 倍。
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

        当前节点获得其空间范围的中点颜色（含微小偏移），然后根据子节点包含的
        b 数量在对应维度上按比例切分空间，递归处理子节点。

        - 子节点为 c_ ：在 S 轴上切分
        - 子节点为 b_ ：在 L 轴上切分
        - 其他（e_/k_/d_ 或根的直接子节点）：在 H 轴上切分

        优化一（跳跃排列）：
        在为子节点分配切分轴上的位置时，使用 _leapfrog_order 重新排列分配顺序。
        原始顺序中相邻的子节点会被分配到切分轴上相距最远的位置，使得在树结构中
        相邻的兄弟节点在颜色上差异最大，从而大幅提高同级可区分性。
        同时，所有子节点仍然被限制在父节点的颜色空间范围内，保持了"同属一个上级"
        的视觉聚类效果——通过 H 范围（e/k/d级）、S 范围（c级）、L 范围（b级）
        即可判断从属关系。

        优化二（父节点偏移）：
        为父节点（非叶子节点）的颜色添加微小偏移（2%），避免与"恰好落在范围中心"
        的子节点颜色完全重合。偏移方向按深度交替，使相邻层级的父节点产生明暗差异，
        进一步增强层级可辨识度。

        优化三（d节点环绕取色）：
        为 d 节点在所属 k 节点的 S-L 平面上，以中点为中心进行环绕分布。
        使用跳跃排列决定各 d 节点的环绕角度，使同 k 内相邻 d 在角度上相距最大，
        同时通过跨 k 角度微调避免不同 k 中 d 节点的颜色重合。
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

        # 计算当前节点的默认中点颜色
        h_mid = (h_range[0] + h_range[1]) / 2.0
        s_mid = (s_range[0] + s_range[1]) / 2.0
        l_mid = (l_range[0] + l_range[1]) / 2.0

        # === 优化三：d节点专属环绕取色 ===
        # 同k内d节点在S-L平面上以中点为中心环绕分布，最大化二维区分度
        # 同时通过跨k角度微调避免不同k的d节点重合
        is_d_node = node_name.startswith('d_')
        d_staggered = False

        if is_d_node and d_index is not None and d_count is not None:
            # 计算S-L平面的中心点
            s_center = (s_range[0] + s_range[1]) / 2.0
            l_center = (l_range[0] + l_range[1]) / 2.0

            if d_count > 1:
                d_staggered = True
                # 使用跳跃排列决定各d的环绕顺序，使相邻d在角度上相距最大
                order = self._leapfrog_order(d_count)
                rank = order.index(d_index)      # 当前d在跳跃排列中的位置
                base_angle = 2.0 * math.pi * rank / d_count

                # 跨k区分：根据k_index对环绕角度进行微小旋转
                if k_index is not None and k_count is not None and k_count > 1:
                    # 旋转角度偏移量，使用质数7避免与等分角度产生周期性重合
                    angle_offset = 2.0 * math.pi * 0.03 * (k_index % 7)
                    base_angle += angle_offset

                # 计算环绕半径：取S和L范围半宽的较小值乘以系数，确保所有点均在范围内
                s_half = (s_range[1] - s_range[0]) / 2.0
                l_half = (l_range[1] - l_range[0]) / 2.0
                radius = min(s_half, l_half) * 0.5   # 0.5倍半宽使d节点始终簇拥在中心周围

                # 根据角度和半径计算具体位置
                s_mid = s_center + radius * math.cos(base_angle)
                l_mid = l_center + radius * math.sin(base_angle)

                # 裁剪到有效范围，防止浮点误差越界
                s_mid = max(s_range[0], min(s_range[1], s_mid))
                l_mid = max(l_range[0], min(l_range[1], l_mid))
            else:
                # 单个d节点：直接取中点，但可应用跨k微调（仍取中点，添加微小S偏移以保留原设计意图）
                if k_index is not None and k_count is not None and k_count > 1:
                    offset_pattern = [-0.04, 0.0, 0.04]
                    k_s_offset = offset_pattern[k_index % 3] * (s_range[1] - s_range[0])
                    s_mid = max(s_range[0], min(s_range[1], s_center + k_s_offset))
                    l_mid = l_center
                # 单个d节点不设置d_staggered，以便仍然可以应用父节点偏移（如需）
                # 这里保持 d_staggered = False，与原有逻辑一致

        # 优化二：为父节点添加微小偏移，避免与中心子节点颜色完全重合
        # d节点已使用环绕逻辑（d_staggered=True）时跳过，避免干扰精心设计的环绕位置
        if child_axis is not None and not d_staggered:
            depth = len(path)
            sign = 1 if depth % 2 == 0 else -1
            offset_ratio = 0.02  # 2% 偏移，足够避免重合但不影响视觉聚类
            # 在切分轴方向偏移：避免该轴上的中心子节点与父节点完全重合
            if child_axis == 'H':
                h_mid += sign * (h_range[1] - h_range[0]) * offset_ratio
            elif child_axis == 'S':
                s_mid += sign * (s_range[1] - s_range[0]) * offset_ratio
            # 在 L 方向始终偏移：为所有层级的父节点提供与子节点的明度差异
            l_mid += sign * (l_range[1] - l_range[0]) * offset_ratio

        rgb = self._hsl_to_rgb(h_mid, s_mid, l_mid)

        # 保存颜色
        path_str = '|'.join(path)
        self.node_colors[path_str] = rgb
        if node_name.startswith('b_'):
            self.b_colors[path_str] = rgb

        if not children:
            return  # 叶子节点（b_）或无子节点

        # 计算子节点总需求和
        child_items = []
        total_demand = 0
        for cname, cnode in children.items():
            cpath = path + (cname,)
            demand = self._node_demands.get(cpath, 0)
            child_items.append((cname, cnode, demand, cpath))
            total_demand += demand

        if total_demand == 0:
            return

        axis = child_axis  # 已在上方确定

        # 在选定轴上按需求比例分配子区间
        if axis == 'H':
            start = h_range[0]
            length = h_range[1] - h_range[0]
        elif axis == 'S':
            start = s_range[0]
            length = s_range[1] - s_range[0]
        else:  # 'L'
            start = l_range[0]
            length = l_range[1] - l_range[0]

        # === 优化一：使用跳跃排列重新排序子节点的位置分配 ===
        # lf_order[j] 表示第 j 个位置上应该放置哪个原始子节点
        # 这样原始顺序中相邻的子节点会被分配到切分轴上相距最远的位置
        n_children = len(child_items)
        lf_order = self._leapfrog_order(n_children)
        reordered_items = [child_items[lf_order[j]] for j in range(n_children)]

        current_start = start
        for j, (cname, cnode, demand, cpath) in enumerate(reordered_items):
            interval_length = length * (demand / total_demand)
            child_h_range = h_range
            child_s_range = s_range
            child_l_range = l_range
            if axis == 'H':
                child_h_range = (current_start, current_start + interval_length)
            elif axis == 'S':
                child_s_range = (current_start, current_start + interval_length)
            else:  # 'L'
                child_l_range = (current_start, current_start + interval_length)
            current_start += interval_length

            # === 传递上下文索引信息给子节点（用于d节点环绕取色） ===
            # orig_idx: 当前子节点在原始顺序中的索引（跳跃排列前的位置）
            orig_idx = lf_order[j]
            new_d_index = d_index
            new_d_count = d_count
            new_k_index = k_index
            new_k_count = k_count

            if cname.startswith('d_'):
                # 记录此d在兄弟d中的原始序号和总数，供环绕取色使用
                new_d_index = orig_idx
                new_d_count = n_children
                # k信息保持不变，传递下去用于跨k角度微调
            elif cname.startswith('k_'):
                # 记录此k在兄弟k中的原始序号和总数
                new_k_index = orig_idx
                new_k_count = n_children
                # 进入新k，重置d信息
                new_d_index = None
                new_d_count = None
            elif cname.startswith('e_'):
                # 进入新e，重置k和d信息
                new_k_index = None
                new_k_count = None
                new_d_index = None
                new_d_count = None
            elif cname.startswith('c_'):
                # c和b不需要d上下文
                new_d_index = None
                new_d_count = None

            self._assign_colors_by_space(cname, cpath,
                                         child_h_range, child_s_range, child_l_range,
                                         d_index=new_d_index, d_count=new_d_count,
                                         k_index=new_k_index, k_count=new_k_count)

    @staticmethod
    def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
        """HSL -> RGB 转换，h in [0,360), s,l in [0,1]，输出 (0-255)"""
        r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
        return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

    # ========== 文件处理（保留原有格式，使用新颜色） ==========
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
                # 判断数组还是块
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

        stack = []  # (name, start_line)
        i = 0
        while i < len(lines):
            line = lines[i]
            # 检测块开始
            m = re.match(r'^\s*([\w_]+)\s*=\s*\{', line)
            if m:
                key = m.group(1)
                if key.startswith(('h_', 'e_', 'k_', 'd_', 'c_', 'b_')):
                    stack.append((key, i))
                i += 1
                continue

            # 检测块结束
            if re.match(r'^\s*\}', line):
                if not stack:
                    i += 1
                    continue
                key, start_line = stack.pop()
                # 构建完整路径
                path_parts = [k for k, _ in stack] + [key]
                full_path = '|'.join(path_parts)

                new_rgb = None
                if key.startswith('b_'):
                    new_rgb = self.b_colors.get(full_path)
                elif key.startswith(('e_', 'k_', 'd_', 'c_')):
                    new_rgb = self.node_colors.get(full_path)

                if new_rgb is not None:
                    # 在块内查找并替换 color 行
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
                    # 如果原块内没有 color 行，则在 } 前插入新行
                    if not replaced:
                        indent = re.match(r'^(\s*)\}', lines[i])
                        indent_str = indent.group(1) if indent else ''
                        color_line = f"{indent_str}    color = {{ {new_rgb[0]} {new_rgb[1]} {new_rgb[2]} }}\n"
                        lines.insert(i, color_line)
                        i += 1  # 因为插入了一行，需要跳过它
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


# 使用示例
if __name__ == "__main__":
    allocator = ColorAllocator.from_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt", root_key="h_taga_hanjin")
    print("员工颜色数量:", len(allocator.b_colors))
    allocator.apply_colors_to_file("TheAshenGoldenAge/common/landed_titles/TAGA_china.txt")