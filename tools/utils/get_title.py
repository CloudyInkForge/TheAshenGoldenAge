import re
from typing import List, Union, Dict

class TAGA_Parser:
    """
    解析 CK3 领地文件（TAGA_china.txt），提取指定层级的标识符或省份编号，
    并支持根据头衔键递归获取其下所有省份。
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._cache = {}

    def _read_file(self) -> str:
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            return f.read()

    def get_items(self, item_type: str) -> List[Union[str, int]]:
        """原有方法：根据类型提取头衔列表或省份列表"""
        if item_type not in ('province', 'e', 'k', 'd', 'c', 'b'):
            raise ValueError(f"不支持的类型 '{item_type}'")
        if item_type in self._cache:
            return self._cache[item_type]

        content = self._read_file()
        if item_type == 'province':
            pattern = re.compile(r'province\s*=\s*(\d+)')
            matches = [int(num) for num in pattern.findall(content)]
        else:
            prefix = item_type + '_'
            pattern = re.compile(r'^\s*(' + re.escape(prefix) + r'[a-zA-Z0-9_]+)\s*=', re.MULTILINE)
            matches = pattern.findall(content)

        self._cache[item_type] = matches
        return matches

    # ---------- 增强的层级解析 ----------
    def _parse_hierarchy(self) -> Dict[str, Dict[str, Union[List[int], List[str]]]]:
        """
        解析文件构建头衔层级树，使用缩进相对变化来确定父子关系。
        返回字典：{头衔键: {'provinces': [省份ID], 'children': [子头衔键]}}
        """
        content = self._read_file()
        lines = content.splitlines()
        hierarchy = {}
        stack = []  # 元素为 (缩进空格数, 头衔键)

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # 计算前导空白字符，将制表符替换为4个空格
            indent_str = line[:len(line) - len(line.lstrip())]
            indent = len(indent_str.replace('\t', '    '))

            # 匹配省份行
            m = re.match(r'province\s*=\s*(\d+)', stripped)
            if m:
                province_id = int(m.group(1))
                if stack:
                    current_title = stack[-1][1]
                    hierarchy.setdefault(current_title, {'provinces': [], 'children': []})['provinces'].append(province_id)
                continue

            # 匹配头衔定义行
            m = re.match(r'^([ekdcb]_[a-zA-Z0-9_]+)\s*=', stripped)
            if m:
                title = m.group(1)
                # 根据缩进弹出栈：当栈顶缩进 >= 当前缩进时，弹出（表示离开父级）
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                # 如果栈非空，当前头衔是栈顶的子级
                if stack:
                    parent = stack[-1][1]
                    hierarchy.setdefault(parent, {'provinces': [], 'children': []})['children'].append(title)
                # 初始化当前头衔
                hierarchy.setdefault(title, {'provinces': [], 'children': []})
                # 入栈
                stack.append((indent, title))

        return hierarchy

    def get_provinces_for_title(self, title_key: str) -> List[int]:
        """
        递归获取指定头衔及其所有子头衔所包含的省份编号。
        若头衔不存在，抛出 ValueError。
        """
        hierarchy = self._parse_hierarchy()
        if title_key not in hierarchy:
            raise ValueError(f"头衔 '{title_key}' 不存在于领地文件中")

        provinces = []

        def collect(t: str):
            entry = hierarchy[t]
            provinces.extend(entry['provinces'])
            for child in entry['children']:
                collect(child)

        collect(title_key)
        return provinces

    # ---------- 原有便捷方法 ----------
    def get_all_provinces(self) -> List[int]:
        return self.get_items('province')

    def get_all_kingdoms(self) -> List[str]:
        return self.get_items('k')

    def get_all_duchies(self) -> List[str]:
        return self.get_items('d')

    def get_all_counties(self) -> List[str]:
        return self.get_items('c')

    def get_all_baronies(self) -> List[str]:
        return self.get_items('b')

    def get_all_empires(self) -> List[str]:
        return self.get_items('e')

'''
# ===== 使用示例 =====
if __name__ == '__main__':
    FILE_PATH = r'TheAshenGoldenAge\\common\\landed_titles\\TAGA_china.txt'
    parser = TAGA_Parser(FILE_PATH)

    try:
        provinces = parser.get_provinces_for_title('k_taga_henan')
        print(f"王国 k_taga_henan 下共有 {len(provinces)} 个省份")
        print(f"前10个: {provinces[:10]}")
    except ValueError as e:
        print(e)
'''