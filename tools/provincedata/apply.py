import os
import pandas as pd
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.utils.get_title import TAGA_Parser

class Applyer:
    """
    将领地文件中的省份与对应的男爵领（b_）头衔映射，并写入 Excel 文件。
    """

    def __init__(self, landed_titles_path: str, excel_path: str = None):
        """
        初始化解析器并设定 Excel 输出路径。

        :param landed_titles_path: CK3 领地文件（如 TAGA_china.txt）的路径
        :param excel_path: 输出 Excel 文件路径，默认为当前文件同目录下的 main.xlsx
        """
        self.parser = TAGA_Parser(landed_titles_path)
        if excel_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            excel_path = os.path.join(current_dir, 'main.xlsx')
        self.excel_path = excel_path

    def applybp(self) -> None:
        """
        执行映射并写入 Excel。
        第一列：province ID（整数）
        第二列：对应的 b_ 头衔键（字符串），若无则留空
        """
        # 1. 获取所有省份
        provinces = self.parser.get_all_provinces()

        # 2. 获取所有男爵领头衔
        baronies = self.parser.get_all_baronies()

        # 3. 构建 province -> b_title 映射
        province_to_barony = {}
        for b in baronies:
            try:
                provs = self.parser.get_provinces_for_title(b)
                for p in provs:
                    # 如果同一省份出现在多个 b 中（理论上不会），则最后一个覆盖
                    province_to_barony[p] = b
            except ValueError:
                # 头衔不存在则跳过
                continue

        # 4. 组装数据
        data = [(p, province_to_barony.get(p, '')) for p in provinces]

        # 5. 写入 Excel
        df = pd.DataFrame(data, columns=['province_id', 'barony_title'])
        df.to_excel(self.excel_path, index=False)
        print(f"已写入 {len(data)} 条记录到 {self.excel_path}")

    # ========== 新增 applyc3 方法 ==========
    def applyc3(self, yml_path: str = None) -> None:
        """
        从本地化 YML 文件中提取男爵领头衔的翻译，并写入 Excel 的第三列。

        :param yml_path: YML 文件路径，默认使用相对路径
                         TheAshenGoldenAge/localization/simp_chinese/TAGAtitle_l_simp_chinese.yml
        """
        if yml_path is None:
            # 根据当前文件位置构造相对路径（与 landed_titles 保持同级目录结构）
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            yml_path = os.path.join(base_dir, 'TheAshenGoldenAge', 'localization', 'simp_chinese',
                                    'TAGAtitle_l_simp_chinese.yml')

        # 1. 解析 YML 文件，提取 b_ 开头的键值对
        translation_map = {}
        try:
            with open(yml_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or ':' not in line:
                        continue
                    # 分割键值（第一个冒号）
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    # 去除可能的引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if key.startswith('b_'):
                        translation_map[key] = value
        except FileNotFoundError:
            print(f"错误：找不到 YML 文件 {yml_path}")
            raise

        # 2. 读取现有 Excel
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Excel 文件 {self.excel_path} 不存在，请先运行 applybp()")

        df = pd.read_excel(self.excel_path)
        if 'barony_title' not in df.columns:
            raise ValueError("Excel 缺少 'barony_title' 列，请先运行 applybp()")

        # 3. 添加翻译列（第三列）
        df['barony_translation'] = df['barony_title'].map(translation_map).fillna('')

        # 4. 写回 Excel（保留前两列）
        df.to_excel(self.excel_path, index=False)
        print(f"已更新翻译列（共 {len(df)} 行）到 {self.excel_path}")
    # ========== 新增结束 ==========

if __name__ == '__main__':
    # 领地文件路径（可替换为实际路径）
    LANDED_TITLES = r'TheAshenGoldenAge\\common\\landed_titles\\TAGA_china.txt'
    app = Applyer(LANDED_TITLES)
    app.applybp()          # 生成前两列
    app.applyc3()        # 如需生成第三列，取消注释此行