import os
import sys
from typing import List

# 确保可以导入 tools.utils.get_title
# 假设脚本运行在项目根目录，将根目录添加到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) if os.path.basename(current_dir) == 'tools' else current_dir
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.utils.get_title import TAGA_Parser


class ProvinceAppender:
    """
    从领地文件中提取省份列表，并将每个省份以固定格式追加到指定历史省份文件中。
    """

    # 默认路径（相对于项目根目录）
    DEFAULT_LANDED_TITLES = os.path.join(
        "TheAshenGoldenAge", "common", "landed_titles", "TAGA_china.txt"
    )
    DEFAULT_TARGET_FILE = os.path.join(
        "TheAshenGoldenAge", "history", "provinces", "taga_k_jiangzuo.txt"
    )

    # 每个省份的固定条目模板
    ENTRY_TEMPLATE = """{province_id} = {{
	culture = TAGA_jin
	religion = jingxue
	holding = taga_xian_holding
}}
"""

    def __init__(
        self,
        landed_titles_path: str = None,
        target_file_path: str = None,
    ):
        """
        初始化追加器。

        Args:
            landed_titles_path: 领地文件路径，默认使用 DEFAULT_LANDED_TITLES。
            target_file_path: 目标历史省份文件路径，默认使用 DEFAULT_TARGET_FILE。
        """
        self.landed_titles_path = (
            landed_titles_path or self.DEFAULT_LANDED_TITLES
        )
        self.target_file_path = (
            target_file_path or self.DEFAULT_TARGET_FILE
        )
        # 确保路径基于项目根目录
        if not os.path.isabs(self.landed_titles_path):
            self.landed_titles_path = os.path.join(project_root, self.landed_titles_path)
        if not os.path.isabs(self.target_file_path):
            self.target_file_path = os.path.join(project_root, self.target_file_path)

        self._parser = None
        self._province_list = None

    def _get_parser(self) -> TAGA_Parser:
        """获取（或创建）解析器实例。"""
        if self._parser is None:
            self._parser = TAGA_Parser(self.landed_titles_path)
        return self._parser

    def fetch_provinces(self) -> List[int]:
        """
        从领地文件中提取所有省份编号。

        Returns:
            List[int]: 省份编号列表。
        """
        if self._province_list is None:
            parser = self._get_parser()
            self._province_list = parser.get_all_provinces()
        return self._province_list

    def format_province_entry(self, province_id: int) -> str:
        """
        根据省份编号生成格式化的条目字符串。

        Args:
            province_id: 省份编号。

        Returns:
            str: 格式化后的条目（包含换行）。
        """
        return self.ENTRY_TEMPLATE.format(province_id=province_id)

    def append_to_file(self, province_list: List[int] = None) -> None:
        """
        将省份条目追加到目标文件末尾。

        Args:
            province_list: 省份编号列表，若为 None 则自动调用 fetch_provinces()。
        """
        if province_list is None:
            province_list = self.fetch_provinces()

        if not province_list:
            print("警告：未获取到任何省份，操作中止。")
            return

        # 确保目标目录存在
        os.makedirs(os.path.dirname(self.target_file_path), exist_ok=True)

        # 读取原文件内容（若文件不存在则创建）
        content = ""
        if os.path.exists(self.target_file_path):
            with open(self.target_file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        else:
            print(f"目标文件不存在，将创建：{self.target_file_path}")

        # 如果原内容不为空且结尾没有换行，先补一个换行，避免粘连
        if content and not content.endswith('\n'):
            content += '\n'

        # 生成所有省份条目
        entries = []
        for pid in province_list:
            entries.append(self.format_province_entry(pid))

        # 合并并写入
        new_content = content + ''.join(entries)

        with open(self.target_file_path, 'w', encoding='utf-8-sig') as f:
            f.write(new_content)

        print(f"成功追加 {len(province_list)} 个省份到 {self.target_file_path}")

    def run(self) -> None:
        """执行完整流程：获取省份并追加。"""
        provinces = self.fetch_provinces()
        print(f"从领地文件中提取到 {len(provinces)} 个省份。")
        self.append_to_file(provinces)


def main():
    """命令行入口。"""
    appender = ProvinceAppender()
    appender.run()


if __name__ == "__main__":
    main()