import re
import colorsys
from collections import deque
from typing import List, Tuple, Dict, Optional

GRID_SIZE = 18  # 保留，但不再使用
MAX_POINTS = GRID_SIZE ** 3  # 保留，但不再使用


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
        self.node_colors: Dict[str, Tuple[int, int, int]] = {}  # 存储所有节点的颜色（含上级）
        self._node_demands = {}

        self._parse_and_validate()
        self._assign_colors_recursive(self.root_key, (self.root_key,), None, 0)

    def assign(self) -> Dict[str, Tuple[int, int, int]]:
        return self.b_colors

    # ========== 解析与需求计算（移除 E 节点校验） ==========
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
            if demand < 0:
                raise RuntimeError(f"节点 {path} 的需求计算异常")
            self._node_demands[path] = demand
            return demand

        root_node = self.tree[self.root_key]
        total_demand = calc_demand(root_node, (self.root_key,))
        if total_demand <= 0:
            raise ValueError("总员工数必须大于0")
        # 不再检查 MAX_POINTS，因为不再使用网格

    # ========== 新的分层颜色分配 ==========
    def _assign_colors_recursive(self, node_name: str, path: tuple, parent_color: Optional[tuple],
                                 sibling_index: int, sibling_count: int = 1,
                                 level: int = 0, hue_shift: float = 0.0):
        """自顶向下为节点及其子树分配颜色，parent_color 为 (h, s, l) 或 None"""
        node = self.tree
        # 根据 path 定位到当前节点
        current = node
        for part in path:
            current = current[part]

        # 确定当前节点的 HSL
        if parent_color is None:  # 顶层 h
            # 假设未来可能有多个 h，这里用黄金角度保证分散
            # 当前只有一个 h，我们就用固定基础色相 0
            h_val = 0.0
            s_val = 0.65
            l_val = 0.55
        else:
            h_base, s_base, l_base = parent_color
            if node_name.startswith('e_'):
                # e 层：基于父 h 色相，兄弟间色相均匀拉开 120° 范围
                if sibling_count <= 1:
                    offset = 0.0
                else:
                    # 均匀分布在 [-60°, 60°] 之间
                    offset = (sibling_index - (sibling_count - 1) / 2) * (120.0 / (sibling_count - 1))
                h_val = (h_base + offset) % 360.0
                s_val = max(0.2, min(0.95, s_base + (sibling_index % 3 - 1) * 0.05))
                l_val = max(0.2, min(0.8, l_base + (sibling_index % 2) * 0.08 - 0.04))
            elif node_name.startswith('k_'):
                # k 层：主变饱和度/亮度，色相微调
                h_val = (h_base + (sibling_index % 5 - 2) * 6.0) % 360.0
                s_val = max(0.3, min(0.9, s_base + (sibling_index - (sibling_count - 1) / 2) * 0.15))
                l_val = max(0.25, min(0.75, l_base + (sibling_index % 3 - 1) * 0.1))
            elif node_name.startswith('d_'):
                h_val = (h_base + (sibling_index % 3 - 1) * 5.0) % 360.0
                s_val = max(0.35, min(0.85, s_base + (sibling_index - (sibling_count - 1) / 2) * 0.1))
                l_val = max(0.3, min(0.7, l_base + (sibling_index % 2) * 0.06 - 0.03))
            elif node_name.startswith('c_'):
                h_val = (h_base + (sibling_index % 4 - 2) * 4.0) % 360.0
                s_val = max(0.4, min(0.8, s_base + (sibling_index - (sibling_count - 1) / 2) * 0.05))
                l_val = max(0.35, min(0.65, l_base + (sibling_index % 2) * 0.05 - 0.025))
            else:  # b_ 员工
                # 基于父 c 颜色，加微小的确定性偏移（基于路径哈希）
                import hashlib
                hash_bytes = hashlib.md5(('|'.join(path)).encode()).digest()
                h_offset = (hash_bytes[0] - 127) / 127 * 5.0   # ±5°
                s_offset = (hash_bytes[1] - 127) / 127 * 0.05
                l_offset = (hash_bytes[2] - 127) / 127 * 0.05
                h_val = (h_base + h_offset) % 360.0
                s_val = max(0.1, min(1.0, s_base + s_offset))
                l_val = max(0.1, min(0.9, l_base + l_offset))
                # b 颜色直接写入
                rgb = self._hsl_to_rgb(h_val, s_val, l_val)
                self.b_colors['|'.join(path)] = rgb
                # b 节点不存储到 node_colors（避免覆盖上级路径）
                return

        # 保存当前节点的颜色 (h,s,l) 供子节点使用，同时转为 RGB 存入 node_colors
        rgb = self._hsl_to_rgb(h_val, s_val, l_val)
        self.node_colors['|'.join(path)] = rgb

        # 处理子节点
        children = {k: v for k, v in current.items() if k.startswith(('e_', 'k_', 'd_', 'c_', 'b_'))}
        child_items = list(children.items())
        n_children = len(child_items)
        for idx, (cname, cnode) in enumerate(child_items):
            cpath = path + (cname,)
            if cname.startswith('b_'):
                # 直接为员工着色，传入父节点颜色
                self._assign_colors_recursive(cname, cpath, (h_val, s_val, l_val), idx, n_children, level + 1)
            else:
                self._assign_colors_recursive(cname, cpath, (h_val, s_val, l_val), idx, n_children, level + 1)

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