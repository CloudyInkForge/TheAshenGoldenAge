#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 main.xlsx 更新：
1. TheAshenGoldenAge/common/province_terrain/01_probince_properties.txt
   - 第十二列整数 1-5 映射为 winter_severity_bias
2. TheAshenGoldenAge/common/province_terrain/00_province_terrain.txt
   - 第十三列整数 + 第十七列字母 映射为地形代码

依赖：openpyxl
"""

import re
from pathlib import Path

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit("缺少 openpyxl 依赖，请先安装：pip install openpyxl") from exc


# 路径
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[2]
MOD_DIR = ROOT_DIR / "TheAshenGoldenAge"
TERRAIN_DIR = MOD_DIR / "TheAshenGoldenAge" / "common" / "province_terrain"

EXCEL_FILE = SCRIPT_DIR / "main.xlsx"
TERRAIN_FILE = TERRAIN_DIR / "00_province_terrain.txt"

# 注意：你提供的信息里 properties 文件名有 probince / province 两种拼写，这里做兼容。
PROPERTIES_FILE = TERRAIN_DIR / "01_probince_properties.txt"
if not PROPERTIES_FILE.exists():
    PROPERTIES_FILE = TERRAIN_DIR / "01_province_properties.txt"


# 第十二列整数 -> winter_severity_bias
BIAS_MAP = {
    1: 0.70,
    2: 0.55,
    3: 0.45,
    4: 0.30,
    5: 0.20,
}

# 第十三列整数 + 第十七列字母 -> 地形代码
TERRAIN_CODE_MAP = {
    "8a": "TAGA_DSR",
    "7a": "TAGA_GOB",
    "6a": "TAGA_JGL",
    "5a": "TAGA_CT_PLT",
    "5b": "TAGA_CT_HIL",
    "4a": "TAGA_WT_FLD",
    "4b": "TAGA_WT_PLN",
    "4c": "TAGA_WT_HIL",
    "3a": "TAGA_NST_PLN",
    "3b": "TAGA_NST_HIL",
    "2a": "TAGA_MST_PLN",
    "2b": "TAGA_MST_HIL",
    "2c": "TAGA_MST_VLY",
    "1a": "TAGA_SST_BSN",
    "1b": "TAGA_SST_HIL",
}


def format_bias(value: float) -> str:
    """将 bias 值格式化为与文件一致的字符串。"""
    if value == 0.0:
        return "0.0"
    return f"{value:.2f}"


def read_excel():
    """读取 main.xlsx，返回 bias 更新字典和地形更新字典。"""
    wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
    ws = wb.active

    bias_updates = {}
    terrain_updates = {}
    warnings = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 17:
            continue

        # 第一列：省份 ID
        try:
            province_id = int(row[0])
        except (TypeError, ValueError):
            continue

        # 第十二列：winter_severity_bias 代码
        if row[11] is not None:
            try:
                bias_code = int(row[11])
                if bias_code in BIAS_MAP:
                    bias_updates[province_id] = BIAS_MAP[bias_code]
                else:
                    warnings.append(
                        f"ID {province_id}: 未知的 winter_severity_bias 代码 {bias_code!r}"
                    )
            except (TypeError, ValueError):
                pass

        # 第十三列 + 第十七列：地形代码
        if row[12] is not None and row[16] is not None:
            try:
                terrain_num = int(row[12])
                terrain_letter = str(row[16]).strip().lower()
                terrain_key = f"{terrain_num}{terrain_letter}"

                if terrain_key in TERRAIN_CODE_MAP:
                    terrain_updates[province_id] = TERRAIN_CODE_MAP[terrain_key]
                else:
                    warnings.append(
                        f"ID {province_id}: 未知的地形代码 {terrain_key!r}"
                    )
            except (TypeError, ValueError):
                pass

    return bias_updates, terrain_updates, warnings


def update_terrain_file(path: Path, terrain_updates: dict):
    """更新 00_province_terrain.txt 中的地形值。"""
    if not terrain_updates:
        return

    text = path.read_text(encoding="utf-8")

    # 匹配行格式：ID=terrain
    line_pattern = re.compile(r"(?m)^(\s*)(\d+)(\s*=\s*)(.*?)(\r?\n|$)")

    # 先记录文件中已有的 ID
    existing_ids = {int(m.group(2)) for m in line_pattern.finditer(text)}

    def replace_line(match):
        pid = int(match.group(2))
        if pid not in terrain_updates:
            return match.group(0)

        new_terrain = terrain_updates[pid]
        return f"{match.group(1)}{pid}{match.group(3)}{new_terrain}{match.group(5)}"

    text = line_pattern.sub(replace_line, text)

    # 文件中不存在但 Excel 里有的 ID，统一追加到文件末尾
    missing = {
        pid: terrain
        for pid, terrain in terrain_updates.items()
        if pid not in existing_ids
    }
    if missing:
        if text and not text.endswith("\n"):
            text += "\n"
        for pid in sorted(missing):
            text += f"{pid}={missing[pid]}\n"

    path.write_text(text, encoding="utf-8")
    print(f"已更新 {path.name}：{len(terrain_updates)} 条地形记录")


def update_properties_file(path: Path, bias_updates: dict):
    """更新 01_province_properties.txt / 01_probince_properties.txt 中的 bias。"""
    if not bias_updates:
        return

    text = path.read_text(encoding="utf-8")

    # 匹配 ID = { ... } 块
    block_pattern = re.compile(r"(?m)^(\s*(\d+)\s*=\s*\{)(.*?)(\})", re.S)

    # 替换前先记录文件中已有的 ID
    existing_ids = {int(m.group(2)) for m in block_pattern.finditer(text)}

    def replace_block(match):
        pid = int(match.group(2))
        if pid not in bias_updates:
            return match.group(0)

        new_bias_str = format_bias(bias_updates[pid])
        inner = match.group(3)

        # 替换块中的 winter_severity_bias 数值
        new_inner = re.sub(
            r"(winter_severity_bias\s*=\s*)[-+]?\d*\.?\d+",
            lambda mm: f"{mm.group(1)}{new_bias_str}",
            inner,
        )

        # 如果原块里没有这个属性，则补一个
        if "winter_severity_bias" not in new_inner:
            if new_inner.strip():
                new_inner = new_inner.rstrip() + f"\n\twinter_severity_bias = {new_bias_str}\n"
            else:
                new_inner = f"winter_severity_bias = {new_bias_str}"

        return f"{match.group(1)}{new_inner}{match.group(4)}"

    text = block_pattern.sub(replace_block, text)

    # 文件中不存在但 Excel 里有的 ID，统一追加
    missing = {
        pid: bias
        for pid, bias in bias_updates.items()
        if pid not in existing_ids
    }
    if missing:
        if text and not text.endswith("\n"):
            text += "\n"
        for pid in sorted(missing):
            text += f"{pid} = {{\n\twinter_severity_bias = {format_bias(missing[pid])}\n}}\n"

    path.write_text(text, encoding="utf-8")
    print(f"已更新 {path.name}：{len(bias_updates)} 条 bias 记录")


def main():
    if not EXCEL_FILE.exists():
        raise SystemExit(f"找不到 Excel 文件：{EXCEL_FILE}")

    if not TERRAIN_DIR.exists():
        raise SystemExit(f"找不到 province_terrain 目录：{TERRAIN_DIR}")

    if not TERRAIN_FILE.exists():
        raise SystemExit(f"找不到地形文件：{TERRAIN_FILE}")

    if not PROPERTIES_FILE.exists():
        raise SystemExit(f"找不到 properties 文件：{PROPERTIES_FILE}")

    bias_updates, terrain_updates, warnings = read_excel()

    for msg in warnings:
        print(f"警告：{msg}")

    if not bias_updates and not terrain_updates:
        print("Excel 中没有读取到任何需要更新的数据。")
        return

    update_terrain_file(TERRAIN_FILE, terrain_updates)
    update_properties_file(PROPERTIES_FILE, bias_updates)

    print("完成。")


if __name__ == "__main__":
    main()