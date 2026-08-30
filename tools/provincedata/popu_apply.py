import os
import re
import sys
import math
import pandas as pd

# 添加项目根目录到路径，以便导入 TAGA_Parser
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.utils.get_title import TAGA_Parser


class PopuApplier:
    """
    根据 popu.xlsx 第五列计算 development 值，并更新历史标题文件中对应伯爵领的发展度。
    """

    def __init__(self, landed_titles_path: str, popu_excel_path: str = None, history_file_path: str = None):
        """
        初始化。

        :param landed_titles_path: CK3 领地文件路径
        :param popu_excel_path: popu.xlsx 文件路径，默认与当前脚本同目录下的 popu.xlsx
        :param history_file_path: 历史标题文件路径，默认相对路径 TheAshenGoldenAge/history/titles/e_taga_hanjin.txt
        """
        self.parser = TAGA_Parser(landed_titles_path)
        if popu_excel_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            popu_excel_path = os.path.join(current_dir, 'popu.xlsx')
        self.popu_excel_path = popu_excel_path

        if history_file_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            history_file_path = os.path.join(base_dir, 'TheAshenGoldenAge', 'history', 'titles', 'e_taga_hanjin.txt')
        self.history_file_path = history_file_path

    def _compute_development(self, value) -> int:
        """
        根据第五列数值计算 development 值。
        规则：小于等于 0.1 视为 1；每比 0.1 大 10%（即 0.01），则加 1。
        """
        try:
            x = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(x):
            return None
        if x <= 0.1:
            return 1
        over = x - 0.1
        # 每 0.01 加 1，向下取整
        dev = 1 + int(over / 0.01)
        return dev

    def _get_counties_under_duchy(self, duchy_title: str) -> list:
        """获取指定公爵领下所有伯爵领（c_）头衔。"""
        hierarchy = self.parser._parse_hierarchy()
        if duchy_title not in hierarchy:
            return []
        counties = []

        def dfs(title: str):
            for child in hierarchy[title].get('children', []):
                if child.startswith('c_'):
                    counties.append(child)
                else:
                    # 递归处理可能存在的中间头衔
                    dfs(child)

        dfs(duchy_title)
        return counties

    def _update_county_block(self, content: str, county: str, dev: int) -> str:
        """
        在历史文件内容中更新指定伯爵领的 development 值（305.1.25）。
        如果块不存在则新建。
        """
        # 查找块起始
        pattern = re.compile(r'^(\s*)' + re.escape(county) + r'\s*=\s*\{', re.MULTILINE)
        match = pattern.search(content)
        if not match:
            # 未找到，新建块
            new_block = f"{county} = {{\n\t305.1.25 = {{ change_development_level = {dev} }}\n}}\n"
            return content + "\n" + new_block

        start_idx = match.end() - 1  # 指向 '{'
        # 括号匹配找到块结束
        brace_count = 0
        idx = start_idx
        while idx < len(content):
            if content[idx] == '{':
                brace_count += 1
            elif content[idx] == '}':
                brace_count -= 1
                if brace_count == 0:
                    block_end_idx = idx
                    break
            idx += 1
        else:
            raise ValueError(f"无法匹配 {county} 块的右括号")

        block = content[start_idx:block_end_idx + 1]
        # 在块内查找 305.1.25 的 development 条目
        dev_pattern = re.compile(r'305\.1\.25\s*=\s*\{\s*change_development_level\s*=\s*(\d+)\s*\}', re.IGNORECASE)
        m = dev_pattern.search(block)
        if m:
            # 替换数值
            new_block = block[:m.start(1)] + str(dev) + block[m.end(1):]
        else:
            # 插入到块内第一个 '{' 之后
            insert_pos = block.find('{') + 1
            insert_text = f"\n\t305.1.25 = {{ change_development_level = {dev} }}"
            new_block = block[:insert_pos] + insert_text + block[insert_pos:]

        # 替换原块
        updated_content = content[:start_idx] + new_block + content[block_end_idx + 1:]
        return updated_content

    def apply_development(self) -> None:
        """
        执行 development 计算与历史文件更新。
        """
        # 读取 popu.xlsx
        if not os.path.exists(self.popu_excel_path):
            raise FileNotFoundError(f"找不到文件 {self.popu_excel_path}，请先运行 popu.py 和 popu_handle.py。")
        df = pd.read_excel(self.popu_excel_path)

        required_cols = ['duchy_title', 'households_per_barony']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Excel 缺少列 '{col}'，请确保已运行 popu_handle.py。")

        # 构建 duchy -> development 映射
        duchy_dev_map = {}
        for _, row in df.iterrows():
            duchy = row['duchy_title']
            value = row['households_per_barony']
            dev = self._compute_development(value)
            if dev is not None:
                duchy_dev_map[duchy] = dev
            else:
                print(f"警告：公爵领 {duchy} 的第五列值无效，跳过。")

        # 构建 county -> development 映射
        county_dev_map = {}
        for duchy, dev in duchy_dev_map.items():
            counties = self._get_counties_under_duchy(duchy)
            if not counties:
                print(f"警告：公爵领 {duchy} 下未找到伯爵领。")
            for county in counties:
                county_dev_map[county] = dev

        print(f"共需更新 {len(county_dev_map)} 个伯爵领的 development 值。")

        # 读取历史文件
        if not os.path.exists(self.history_file_path):
            raise FileNotFoundError(f"找不到历史文件 {self.history_file_path}")
        with open(self.history_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 逐个更新
        for county, dev in county_dev_map.items():
            content = self._update_county_block(content, county, dev)

        # 写回
        with open(self.history_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"历史文件已更新：{self.history_file_path}")


if __name__ == '__main__':
    # 领地文件路径，与之前脚本保持一致
    LANDED_TITLES = r'TheAshenGoldenAge\common\landed_titles\TAGA_china.txt'
    applier = PopuApplier(LANDED_TITLES)
    applier.apply_development()