import os
import pandas as pd
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.utils.get_title import TAGA_Parser

class PopuGenerator:
    """
    生成公爵领（d_）及其本地化名称的Excel文件。
    """

    def __init__(self, landed_titles_path: str, yml_path: str = None, excel_path: str = None):
        """
        初始化。

        :param landed_titles_path: CK3 领地文件路径
        :param yml_path: 本地化 YML 文件路径，默认使用 TheAshenGoldenAge/localization/simp_chinese/TAGAtitle_l_simp_chinese.yml
        :param excel_path: 输出 Excel 路径，默认当前目录 popu.xlsx
        """
        self.parser = TAGA_Parser(landed_titles_path)

        if yml_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            yml_path = os.path.join(base_dir, 'TheAshenGoldenAge', 'localization', 'simp_chinese',
                                    'TAGAtitle_l_simp_chinese.yml')
        self.yml_path = yml_path

        if excel_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            excel_path = os.path.join(current_dir, 'popu.xlsx')
        self.excel_path = excel_path

    def generate(self) -> None:
        """
        获取所有公爵领及其翻译，写入 Excel。
        """
        # 1. 获取所有公爵领头衔
        duchies = self.parser.get_all_duchies()

        # 2. 解析 YML 文件，提取 d_ 开头的键值对
        translation_map = {}
        try:
            with open(self.yml_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or ':' not in line:
                        continue
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    # 去除可能的引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if key.startswith('d_'):
                        translation_map[key] = value
        except FileNotFoundError:
            print(f"错误：找不到 YML 文件 {self.yml_path}")
            raise

        # 3. 组装数据
        data = [(d, translation_map.get(d, '')) for d in duchies]

        # 4. 写入 Excel
        df = pd.DataFrame(data, columns=['duchy_title', 'duchy_translation'])
        df.to_excel(self.excel_path, index=False)
        print(f"已写入 {len(data)} 条公爵领记录到 {self.excel_path}")


class PopuMatcher:
    """
    从《东晋人口》Excel中匹配公爵领的户数，并填入popu.xlsx的第三列。
    """

    def __init__(self, popu_excel_path: str, source_excel_path: str):
        """
        初始化。

        :param popu_excel_path: popu.xlsx 文件路径（由 PopuGenerator 生成）
        :param source_excel_path: 东晋人口.xlsx 文件路径
        """
        self.popu_excel_path = popu_excel_path
        self.source_excel_path = source_excel_path

    def match_and_fill(self) -> None:
        """
        执行匹配并填充户数，输出未匹配的公爵领。
        """
        # 读取 popu.xlsx
        df_popu = pd.read_excel(self.popu_excel_path)
        if 'duchy_translation' not in df_popu.columns:
            raise ValueError("popu.xlsx 缺少 'duchy_translation' 列，请先运行 PopuGenerator.generate()")

        # 读取东晋人口.xlsx，提取B列（名称）和C列（户数）
        df_source = pd.read_excel(self.source_excel_path)
        # 使用位置索引获取第二列和第三列
        names_source = df_source.iloc[:, 1].astype(str).str.strip()
        households_source = df_source.iloc[:, 2]  # 户数可能为数字或文本，保持原样

        # 构建去除“郡”、“国”后的名称 -> 户数 映射（取第一个匹配）
        source_map = {}
        for name, hh in zip(names_source, households_source):
            cleaned = name.replace('郡', '').replace('国', '').strip()
            if cleaned and cleaned not in source_map:
                source_map[cleaned] = hh

        # 遍历 popu 中的翻译名进行匹配
        translations = df_popu['duchy_translation'].astype(str).str.strip()
        households_filled = []
        unmatched_duchies = []

        for idx, trans in enumerate(translations):
            cleaned_trans = trans.replace('郡', '').replace('国', '').strip()
            if cleaned_trans in source_map:
                households_filled.append(source_map[cleaned_trans])
            else:
                households_filled.append(None)  # 未匹配则留空
                unmatched_duchies.append(df_popu.iloc[idx]['duchy_title'])

        # 添加第三列
        df_popu['households'] = households_filled
        df_popu.to_excel(self.popu_excel_path, index=False)

        # 输出未匹配信息
        print(f"\n匹配完成，共 {len(df_popu)} 个公爵领，其中 {len(unmatched_duchies)} 个未匹配到户数。")
        if unmatched_duchies:
            print("未匹配到户数的公爵领：")
            for d in unmatched_duchies:
                print(f"  {d}")


if __name__ == '__main__':
    # 领地文件路径（根据实际情况调整）
    LANDED_TITLES = r'TheAshenGoldenAge\common\landed_titles\TAGA_china.txt'
    # 生成 popu.xlsx
    generator = PopuGenerator(LANDED_TITLES)
    generator.generate()

    # 匹配户数
    POPU_EXCEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'popu.xlsx')
    SOURCE_EXCEL = r'D:\CloudyInkForge\book\野望毅任B\资料库\东晋人口.xlsx'
    matcher = PopuMatcher(POPU_EXCEL, SOURCE_EXCEL)
    matcher.match_and_fill()