import re
import os

# 提供的基础建筑列表
BUILDINGS = [
    "taga_ag_jgl_01",
    "taga_ag_gob_01",
    "taga_ag_dsr_01",
    "taga_ag_ct_plt_01",
    "taga_ag_ct_hil_01",
    "taga_ag_wt_fld_01",
    "taga_ag_wt_pln_01",
    "taga_ag_wt_hil_01",
    "taga_ag_nst_pln_01",
    "taga_ag_nst_hil_01",
    "taga_ag_mst_pln_01",
    "taga_ag_mst_hil_01",
    "taga_ag_mst_vly_01",
    "taga_ag_sst_bsn_01",
    "taga_ag_sst_hil_01",
]

# 地形中特殊字段对应的额外建筑
EXTRA_BUILDINGS = {
    "CT": "taga_fc_hemp_01",
    "WT": "taga_fc_silk_01",
    "NST": "taga_fc_ramie_01",
}

# 插入日期块使用的游戏日期
DEFAULT_DATE = "280.1.1"


class FixProvinceHistory:
    def __init__(self, history_path, terrain_path):
        """
        :param history_path: 省份历史文件路径
        :param terrain_path: 省份地形文件路径
        """
        self.history_path = history_path
        self.terrain_path = terrain_path
        self.terrain_map = {}       # province_id -> terrain (str)
        self.building_map = {}      # terrain -> base building name
        self._build_building_map()

    def _build_building_map(self):
        """根据 BUIILDINGS 列表构建 地形 -> 基础建筑 的映射"""
        for b in BUILDINGS:
            # 例如 "taga_ag_ct_hil_01" -> 去掉前缀 "taga_ag_" 和后缀 "_01" 得到 "ct_hil"
            middle = b[len("taga_ag_"):-len("_01")]
            terrain = "TAGA_" + middle.upper()
            self.building_map[terrain] = b

    def load_terrain_map(self):
        """读取地形文件，解析 province_id = TERRAIN 行"""
        with open(self.terrain_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    parts = line.split('=')
                    if len(parts) == 2:
                        pid = parts[0].strip()
                        terrain = parts[1].strip()
                        if pid.isdigit():
                            self.terrain_map[int(pid)] = terrain

    def generate_buildings(self, terrain):
        """
        根据地形字符串生成需要添加的建筑列表。
        规则：
          - 基础建筑来自 building_map；若地形含 "WT"，则编号 _01 改为 _02。
          - 若地形含 "CT" / "WT" / "NST"，额外添加对应的纤维作物建筑。
        """
        if terrain not in self.building_map:
            print(f"警告：未找到地形 {terrain} 对应的基础建筑，跳过")
            return []

        base = self.building_map[terrain]
        # WT 字段特殊处理：将 01 改为 02
        if "WT" in terrain:
            base = base.replace("_01", "_02")

        buildings = [base]

        # 添加额外建筑
        for key, extra in EXTRA_BUILDINGS.items():
            if key in terrain:
                buildings.append(extra)

        return buildings

    def process(self):
        """主处理流程：读取文件 -> 修改 -> 写回"""
        self.load_terrain_map()

        with open(self.history_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配所有省份块起始 "数字 = {"
        pattern = re.compile(r'(\d+)\s*=\s*\{')
        matches = list(pattern.finditer(content))

        # 从后往前处理，避免索引偏移
        for match in reversed(matches):
            province_id = int(match.group(1))
            if province_id not in self.terrain_map:
                continue

            start = match.start()
            # 找到匹配的右括号（处理嵌套）
            depth = 1
            i = match.end()  # 从第一个 { 之后开始
            while i < len(content) and depth > 0:
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                i += 1
            end = i  # 右括号之后的位置

            block = content[start:end]
            terrain = self.terrain_map[province_id]
            buildings = self.generate_buildings(terrain)
            if not buildings:
                continue

            # 如果块中已经包含所有建筑，则跳过（简单去重）
            if all(b in block for b in buildings):
                continue

            # 检测块内的缩进（取第一个非空行的前导空白）
            indent = ""
            for line in block.splitlines():
                if line.strip():
                    indent = line[:len(line) - len(line.lstrip())]
                    break
            if not indent:
                indent = "\t"  # 默认使用制表符

            # 构造插入文本
            lines = []
            lines.append(f"{indent}{DEFAULT_DATE} = {{")
            lines.append(f"{indent}\tbuildings = {{")
            for b in buildings:
                lines.append(f"{indent}\t\t{b}")
            lines.append(f"{indent}\t}}")
            lines.append(f"{indent}}}")
            insert_text = "\n" + "\n".join(lines) + "\n"

            # 在右括号前插入
            insert_pos = end - 1  # 右括号字符的位置
            # 若前面不是换行，补一个换行，保持格式
            prefix = ""
            if insert_pos > 0 and content[insert_pos - 1] != '\n':
                prefix = "\n"
            content = content[:insert_pos] + prefix + insert_text + content[insert_pos:]

        # 写回文件
        with open(self.history_path, 'w', encoding='utf-8') as f:
            f.write(content)


if __name__ == "__main__":
    # 请根据实际路径修改以下两个文件路径
    history_file = r"TheAshenGoldenAge\history\provinces\taga_k_jiangzuo.txt"
    terrain_file = r"TheAshenGoldenAge\common\province_terrain\00_province_terrain.txt"

    if not os.path.exists(history_file) or not os.path.exists(terrain_file):
        print("文件路径不存在，请检查后重试。")
    else:
        fixer = FixProvinceHistory(history_file, terrain_file)
        fixer.process()
        print("处理完成！")