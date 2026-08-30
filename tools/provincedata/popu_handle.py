import os
import sys
import pandas as pd

# 添加项目根目录到路径，以便导入 TAGA_Parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.utils.get_title import TAGA_Parser


class PopuHandler:
    """
    处理 popu.xlsx，为每个公爵领统计男爵领数量并计算户数/男爵领比值。
    """

    def __init__(self, landed_titles_path: str, popu_excel_path: str = None):
        """
        初始化。

        :param landed_titles_path: CK3 领地文件路径
        :param popu_excel_path: popu.xlsx 文件路径，默认与当前脚本同目录下的 popu.xlsx
        """
        self.parser = TAGA_Parser(landed_titles_path)
        if popu_excel_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            popu_excel_path = os.path.join(current_dir, 'popu.xlsx')
        self.popu_excel_path = popu_excel_path

    def _count_baronies_under_duchy(self, duchy_title: str) -> int:
        """
        统计指定公爵领下所有男爵领（b_）的数量。
        通过解析领地文件的层级结构，递归统计 duchy 下所有以 'b_' 开头的头衔数量。
        """
        hierarchy = self.parser._parse_hierarchy()
        if duchy_title not in hierarchy:
            return 0

        count = 0

        def dfs(title: str):
            nonlocal count
            entry = hierarchy[title]
            # 统计当前头衔的子头衔中，类型为 b 的数量
            for child in entry.get('children', []):
                if child.startswith('b_'):
                    count += 1
                else:
                    # 递归统计非 b 子头衔下的 b
                    dfs(child)

        dfs(duchy_title)
        return count

    def process(self) -> None:
        """
        读取 popu.xlsx，添加第四列（男爵领数量）和第五列（户数/男爵领比值），
        并保存回原文件。
        """
        if not os.path.exists(self.popu_excel_path):
            raise FileNotFoundError(f"找不到文件 {self.popu_excel_path}，请先运行 popu.py 生成该文件。")

        df = pd.read_excel(self.popu_excel_path)

        # 检查必要的列是否存在
        required_cols = ['duchy_title', 'households']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Excel 文件缺少列 '{col}'，请确保已运行 popu.py 中的 PopuMatcher。")

        # 计算每个公爵领的男爵领数量
        barony_counts = []
        ratios = []

        for idx, row in df.iterrows():
            duchy = row['duchy_title']
            # 获取男爵领数量
            try:
                count = self._count_baronies_under_duchy(duchy)
            except Exception as e:
                print(f"警告：处理 {duchy} 时出错（{e}），男爵领数量置为 0")
                count = 0
            barony_counts.append(count)

            # 计算比值
            households = row['households']
            if pd.notna(households) and count > 0:
                try:
                    ratio = round(float(households) / count, 3)
                except (ValueError, TypeError):
                    ratio = None
            else:
                ratio = None
            ratios.append(ratio)

        # 添加新列
        df['barony_count'] = barony_counts
        df['households_per_barony'] = ratios

        # 保存
        df.to_excel(self.popu_excel_path, index=False)
        print(f"已更新 {self.popu_excel_path}，新增第四列 'barony_count' 和第五列 'households_per_barony'。")


if __name__ == '__main__':
    # 领地文件路径，与 popu.py 中保持一致
    LANDED_TITLES = r'TheAshenGoldenAge\common\landed_titles\TAGA_china.txt'
    handler = PopuHandler(LANDED_TITLES)
    handler.process()