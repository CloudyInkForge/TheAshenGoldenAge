import re
from typing import List, Union

class TAGA_Parser:
    """
    解析 CK3 领地文件（TAGA_china.txt），提取指定层级的标识符或省份编号。

    Attributes:
        file_path (str): 领地文件的路径。
        _cache (dict): 缓存已解析的数据，避免重复读取。
    """

    def __init__(self, file_path: str):
        """
        初始化解析器。

        Args:
            file_path (str): 领地文件的绝对或相对路径。
        """
        self.file_path = file_path
        self._cache = {}

    def _read_file(self) -> str:
        """读取文件内容，处理 BOM 头。"""
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            return f.read()

    def get_items(self, item_type: str) -> List[Union[str, int]]:
        """
        根据需求类型提取对应的元素列表。

        Args:
            item_type (str): 支持的类型：
                - 'province' : 返回所有省份编号（整数列表）
                - 'e'        : 返回所有帝国头衔键（如 'e_taga_si'）
                - 'k'        : 返回所有王国头衔键
                - 'd'        : 返回所有公国头衔键
                - 'c'        : 返回所有伯爵领头衔键
                - 'b'        : 返回所有男爵领头衔键

        Returns:
            List[Union[str, int]]: 匹配的元素列表。对于 province 返回整数列表，其余返回字符串列表。

        Raises:
            ValueError: 当传入不支持的 item_type 时抛出。
        """
        if item_type not in ('province', 'e', 'k', 'd', 'c', 'b'):
            raise ValueError(f"不支持的类型 '{item_type}'，请使用 'province', 'e', 'k', 'd', 'c', 'b' 之一。")

        # 检查缓存
        if item_type in self._cache:
            return self._cache[item_type]

        content = self._read_file()

        if item_type == 'province':
            # 提取所有 province = 数字
            pattern = re.compile(r'province\s*=\s*(\d+)')
            matches = [int(num) for num in pattern.findall(content)]
        else:
            # 提取以 item_type_ 开头的头衔键（例如 k_taga_henan）
            prefix = item_type + '_'
            # 匹配行首缩进后的键，后跟 ' =' 或 ' = {'
            pattern = re.compile(r'^\s*(' + re.escape(prefix) + r'[a-zA-Z0-9_]+)\s*=', re.MULTILINE)
            matches = pattern.findall(content)

        # 缓存结果
        self._cache[item_type] = matches
        return matches

    def get_all_provinces(self) -> List[int]:
        """便捷方法：获取所有省份编号。"""
        return self.get_items('province')

    def get_all_kingdoms(self) -> List[str]:
        """便捷方法：获取所有王国头衔键。"""
        return self.get_items('k')

    def get_all_duchies(self) -> List[str]:
        """便捷方法：获取所有公国头衔键。"""
        return self.get_items('d')

    def get_all_counties(self) -> List[str]:
        """便捷方法：获取所有伯爵领头衔键。"""
        return self.get_items('c')

    def get_all_baronies(self) -> List[str]:
        """便捷方法：获取所有男爵领头衔键。"""
        return self.get_items('b')

    def get_all_empires(self) -> List[str]:
        """便捷方法：获取所有帝国头衔键。"""
        return self.get_items('e')

'''
# ===== 使用示例 =====
if __name__ == '__main__':
    # 配置文件路径（请根据实际情况修改）
    FILE_PATH = r'TheAshenGoldenAge\\common\\landed_titles\\TAGA_china.txt'

    parser = TAGA_Parser(FILE_PATH)

    # 获取所有省份编号
    provinces = parser.get_items('province')
    print(f"省份总数: {len(provinces)}")
    print(f"前10个省份: {provinces[:10]}")

    # 获取所有王国头衔
    kingdoms = parser.get_all_kingdoms()
    print(f"\n王国总数: {len(kingdoms)}")
    print(f"王国列表: {kingdoms}")

    # 获取所有伯爵领
    counties = parser.get_all_counties()
    print(f"\n伯爵领总数: {len(counties)}")
    print(f"前5个伯爵领: {counties[:5]}")
'''