#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_title_history.py
======================
配合 get_title.py 使用：解析法理领地文件（landed_titles）的层级关系，
自动生成 / 合并 CK3 头衔历史文件，并同步在人物文件中为 holder 生成角色。

头衔历史中每个（脚本生成的）日期块包含 liege / government / holder：

    k_henan = {
        327.12.8 = {
            liege = e_china                     <- 法理直接上级，自动推导
            government = celestial_government   <- 来自下方 HISTORY_ENTRIES
            holder = k_henan_01                 <- 头衔名 + 序号，自动编号
        }
        1066.1.1 = {
            liege = e_china
            government = celestial_government
            holder = k_henan_02
        }
    }

holder 命名规则：{头衔名}_{两位序号}。序号 = 该日期块在头衔块中的次序
（按日期先后从 01 计起，块内已有的日期块同样参与计数）；若该序号对应
的名称已被占用，则顺延取下一个空号。

同时在 CHARACTERS_PATH 指定的人物文件中，为这些 holder 生成角色块：

    k_henan_01 = {
        religion = "jingxue"                    <- CHARACTER_RELIGION
        culture = "TAGA_jin"                 <- CHARACTER_CULTURE
        251.1.1 = { birth = yes }               <- 日期 - HOLDER_BIRTH_OFFSET 年
        311.1.1 = { death = yes }               <- 日期 + HOLDER_DEATH_OFFSET 年
    }

religion / culture / 生卒年份偏移均为配置区可调参数。

每个头衔（无论等级）都是独立的块；development_level、effect 等由使用者
手动维护，本脚本一律不生成、不修改。

可重复运行（合并规则，保证旧内容不受影响）：
  * 头衔历史文件中某头衔在某日期下，只要已存在包含 liege / government
    （默认还包括 holder，见 SKIP_IF_HOLDER）的日期块，就视为“已处理”，
    脚本绝不再为该日期插入新块 —— 手动编辑过的旧年份原样保留；
  * 只含 change_development_level 等其他内容的同日期块不会阻止生成
    （CK3 允许同一日期出现多个块，按顺序生效，可与生成的块共存）；
  * 已有日期块含 liege / government 却缺 holder（例如旧版脚本生成的
    文件），且该日期在 HISTORY_ENTRIES 中、该日期没有任何 holder 时，
    脚本会向块内补写一行 holder（纯插入，不改写任何已有行）；日期不在
    HISTORY_ENTRIES 中的块视为手动维护，一律不动，SKIP_DATES 指定的
    日期同样不补写；
  * 人物文件只追加“尚不存在”的角色，已有角色原样保留；
  * 脚本从不删除、改写、重排任何已有行，只做整行 / 整块插入。

用法：
    python build_title_history.py             # 生成 / 合并两个输出文件
    python build_title_history.py --dry-run   # 仅预览将插入的内容，不写文件
"""

import argparse
import os
import re
import shutil
import sys
from collections import OrderedDict

try:
    from utils.get_title import TAGA_Parser
except ImportError:
    sys.exit('错误：找不到 get_title.py（TAGA_Parser）。请将本脚本与 get_title.py 放在同一目录运行。')

# =========================================================================
#                                 配置区
# =========================================================================

# 法理领地文件，可填单个路径字符串，也可填多个路径的列表。
LANDED_TITLES_PATH = r'TheAshenGoldenAge\common\landed_titles\TAGA_china.txt'

# 输出的头衔历史文件；已存在时自动执行“只增不改”的合并。
OUTPUT_PATH = r'TheAshenGoldenAge\history\titles\e_taga_hanjin.txt'

# 输出的人物历史文件；已存在时只追加其中尚不存在的角色。
# 置为 '' 可禁用人物文件（头衔历史仍会照常写入 holder）。
CHARACTERS_PATH = r'TheAshenGoldenAge\history\characters\jin.txt'

# 日期 -> 政府类型（按时间先后书写），键格式 "年.月.日"。值的写法：
#   字符串 —— 所有等级统一使用，如 'celestial_government'
#   字典   —— 按等级分别指定，如 {'k': 'steppe_admin_government', 'default': None}
#             * 键为头衔等级前缀，可用 'default' 兜底；
#             * 值为 None，或等级未列出且无 default，表示该等级在该日期不生成条目。
HISTORY_ENTRIES = OrderedDict([
    ('327.12.8',  'taga_hanjin_government'),
    # 按等级区分的写法示例（1178 年仅王国改用 steppe，公国/伯爵领不生成条目）：
    # ('1178.1.1', {'k': 'steppe_admin_government'}),
])

# 个别头衔的政府覆盖：{头衔: {日期: 政府或None}}，优先级高于 HISTORY_ENTRIES。
GOVERNMENT_OVERRIDES = {
    # 'k_henan': {'1178.1.1': 'steppe_admin_government'},
}

# liege 覆盖，用于“非法理上级”的宗主（例如 1178 年被大金征服）：
#   字符串 —— 该头衔所有日期都用它作 liege
#   None   —— 该头衔一律不写 liege 行
#   字典   —— {日期: liege或None}，可用 'default' 键兜底；未命中的日期回落法理上级
LIEGE_OVERRIDES = {
    # 'k_henan': {'1178.1.1': 'e_jin'},
    'e_taga_si': {'327.12.8': 'h_taga_hanjin'},      # 司州（司隶）
    'e_taga_yu': {'327.12.8': 'h_taga_hanjin'},      # 豫州
    'e_taga_ji': {'327.12.8': 'h_taga_hanjin'},      # 冀州
    'e_taga_yan': {'327.12.8': 'h_taga_hanjin'},     # 兖州
    'e_taga_xv': {'327.12.8': 'h_taga_hanjin'},      # 徐州
    'e_taga_qing': {'327.12.8': 'h_taga_hanjin'},    # 青州
    'e_taga_jing': {'327.12.8': 'h_taga_hanjin'},    # 荆州
    'e_taga_yang': {'327.12.8': 'h_taga_hanjin'},    # 扬州
    'e_taga_yi': {'327.12.8': 'h_taga_hanjin'},      # 益州
    'e_taga_liang': {'327.12.8': 'h_taga_hanjin'},   # 凉州
    'e_taga_bing': {'327.12.8': 'h_taga_hanjin'},    # 并州
    'e_taga_you': {'327.12.8': 'h_taga_hanjin'},     # 幽州
    'e_taga_jiao': {'327.12.8': 'h_taga_hanjin'},    # 交州
}

# 完全不生成历史的头衔。
EXCLUDE_TITLES = set()

# 只为这些等级生成条目（'e'/'k'/'d'/'c'/'b'）。默认不含男爵领。
INCLUDE_TIERS = ('e', 'k', 'd', 'c')

# 指定头衔在指定日期不生成条目（也不补写 holder）：{头衔: {日期, ...}}。
SKIP_DATES = {
    # 'd_dongji': {'1178.1.1'},
}

# 同日期已有块中含有 holder（但无 liege/government）时，是否也视为已处理。
# True = 用户手动写过该日期（哪怕只写了 holder），脚本不再插入该日期。
SKIP_IF_HOLDER = True

# -------------------------- holder 与人物生成 --------------------------

# 是否在日期块中生成 holder，并同步维护人物文件。False 时与旧版行为一致。
GENERATE_HOLDERS = True

# 新角色的宗教与文化（输出时自动加引号；None 表示不写该行）。
CHARACTER_RELIGION = 'jingxue'
CHARACTER_CULTURE = 'TAGA_jin'

# 角色出生年 = 日期块日期的年份 - HOLDER_BIRTH_OFFSET；
# 角色死亡年 = 日期块日期的年份 + HOLDER_DEATH_OFFSET（月、日保持不变）。
HOLDER_BIRTH_OFFSET = 30
HOLDER_DEATH_OFFSET = 30

# 合并写入前是否把原文件备份为 <路径> + '.bak'（对两个输出文件均生效）。
MAKE_BACKUP = True

# 新建输出文件时是否写入说明性文件头注释（对两个输出文件均生效）。
WRITE_HEADER = True

# =========================================================================
#                               实现部分
# =========================================================================

DATE_KEY_RE = re.compile(r'^\s*(\d{1,4})\.(\d{1,2})\.(\d{1,2})\s*$')
DATE_LINE_RE = re.compile(r'^\s*(\d{1,4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{')
TITLE_LINE_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{')
KEY_LINE_RE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_]*)\s*=')
HOLDER_VAL_RE = re.compile(r'^\s*holder\s*=\s*"?([A-Za-z0-9_\-]+)')
CHAR_NAME_LINE_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*\{')

TIER_NAMES = {'e': '帝国', 'k': '王国', 'd': '公国', 'c': '伯爵领', 'b': '男爵领'}


def normalize_date(text):
    """'867.1.1' -> ((867, 1, 1), '867.1.1')"""
    m = DATE_KEY_RE.match(str(text))
    if not m:
        raise ValueError('日期 %r 不合法（应为 年.月.日，如 1066.1.1）' % text)
    y, mo, d = (int(g) for g in m.groups())
    return (y, mo, d), '%d.%d.%d' % (y, mo, d)


def format_date(dt):
    """(867, 1, 1) -> '867.1.1'"""
    return '%d.%d.%d' % dt


def shift_year(dt, years):
    """日期元组整体平移若干年，月、日不变。"""
    return (dt[0] + years, dt[1], dt[2])


def tier_of(title):
    return title.split('_', 1)[0]


def _normalize_date_map(mapping):
    """把 {'1066.1.1': v, 'default': v} 规范化为 {日期元组: v, 'default': v}。"""
    out = {}
    for k, v in mapping.items():
        out['default' if k == 'default' else normalize_date(k)[0]] = v
    return out


# ------------------------------ 文件读写 ------------------------------

def read_text_lines(path):
    """读取 UTF-8 文本文件，返回 (行列表, 是否带BOM, 换行符)。"""
    with open(path, 'rb') as f:
        raw = f.read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    return text.splitlines(), bom, ('\r\n' if '\r\n' in text else '\n')


def write_text_lines(path, lines, bom, newline):
    data = newline.join(lines)
    if data:
        data += newline
    with open(path, 'wb') as f:
        if bom:
            f.write(b'\xef\xbb\xbf')
        f.write(data.encode('utf-8'))


def ensure_dir(path):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)


# ------------------------------ 法理层级 ------------------------------

def build_de_jure(landed_paths):
    """
    基于 get_title.TAGA_Parser 解析法理层级。
    返回：
      titles —— 头衔列表，按法理文件出现顺序（父在前、子在后）
      parent —— {头衔: 法理直接上级}，顶级头衔不在字典中（即无 liege）
    """
    titles, parent = [], {}
    seen = set()
    for p in landed_paths:
        # get_title.py 未公开层级接口，这里直接使用其内部方法
        hierarchy = TAGA_Parser(p)._parse_hierarchy()
        children = {t: list(info['children']) for t, info in hierarchy.items()}
        is_child = set()
        for ch in children.values():
            is_child.update(ch)

        def dfs(title):
            if title in seen:
                return
            seen.add(title)
            titles.append(title)
            for child in children.get(title, ()):
                parent[child] = title
                dfs(child)

        for root in (t for t in hierarchy if t not in is_child):
            dfs(root)
    return titles, parent


# --------------------------- 已有历史文件解析 ---------------------------

def parse_history_file(lines):
    """
    解析已有的头衔历史文件（标准排版：日期块/闭合括号各自成行或常规排布）。
    返回：
      blocks —— [{'name','start','end','entries':[{'date','start','end',
                 'has_liege','has_gov','has_holder','holder_val'}]}]，
                 entries 按文件顺序；holder_val 为块内 holder 的取值（可能为 None）
      balanced —— 花括号是否配平（False 时调用方应拒绝合并，以免破坏手编内容）
    """
    blocks, stack = [], []
    depth, balanced = 0, True

    for i, raw in enumerate(lines):
        code = raw.split('#', 1)[0]           # 去掉行内注释
        if not code.strip():
            continue

        if depth == 0:
            m = TITLE_LINE_RE.match(code)
            if m:
                stack.append(dict(kind='title', name=m.group(1), start=i, entries=[]))
        elif depth == 1 and stack and stack[-1]['kind'] == 'title':
            m = DATE_LINE_RE.match(code)
            if m:
                y, mo, d = (int(g) for g in m.groups())
                stack.append(dict(kind='date', date=(y, mo, d), start=i,
                                  has_liege=False, has_gov=False,
                                  has_holder=False, holder_val=None))
        elif depth == 2 and stack and stack[-1]['kind'] == 'date':
            m = KEY_LINE_RE.match(code)       # 只认日期块“直接”子键
            if m:
                key = m.group(1)
                if key == 'liege':
                    stack[-1]['has_liege'] = True
                elif key == 'government':
                    stack[-1]['has_gov'] = True
                elif key == 'holder':
                    stack[-1]['has_holder'] = True
                    mv = HOLDER_VAL_RE.match(code)
                    if mv:
                        stack[-1]['holder_val'] = mv.group(1)

        depth += code.count('{') - code.count('}')
        if depth < 0:
            balanced = False
            depth = 0

        while stack and depth <= (0 if stack[-1]['kind'] == 'title' else 1):
            closed = stack.pop()
            closed['end'] = i
            if closed['kind'] == 'date':
                if stack and stack[-1]['kind'] == 'title':
                    stack[-1]['entries'].append(closed)
                else:
                    balanced = False
            else:
                blocks.append(closed)

    if stack or depth != 0:
        balanced = False
    return blocks, balanced


def entry_handled(entry):
    """该日期块是否已包含脚本职责范围内的信息（liege/government，可选 holder）。"""
    return bool(entry['has_liege'] or entry['has_gov'] or
                (SKIP_IF_HOLDER and entry['has_holder']))


def parse_character_names(lines):
    """解析人物文件，返回 (已有角色名集合, 花括号是否配平)。"""
    names, depth, balanced = set(), 0, True
    for raw in lines:
        code = raw.split('#', 1)[0]
        if not code.strip():
            continue
        if depth == 0:
            m = CHAR_NAME_LINE_RE.match(code)
            if m:
                names.add(m.group(1))
        depth += code.count('{') - code.count('}')
        if depth < 0:
            balanced = False
            depth = 0
    if depth != 0:
        balanced = False
    return names, balanced


# ------------------------------ 生成文本 ------------------------------

def _quote(value):
    text = str(value)
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return text
    return '"%s"' % text


def make_date_block(date_str, liege, government, holder, indent='\t'):
    """生成一个日期块；liege / government / holder 为 None（或空）时对应行不生成。"""
    inner = indent + '\t'
    lines = ['%s%s = {' % (indent, date_str)]
    if liege:
        lines.append('%sliege = %s' % (inner, liege))
    if government:
        lines.append('%sgovernment = %s' % (inner, government))
    if holder:
        lines.append('%sholder = %s' % (inner, holder))
    lines.append('%s}' % indent)
    return lines


def make_title_block(title, items, indent='\t'):
    """items: [日期元组, 日期串, liege, government, holder], ..."""
    lines = ['%s = {' % title]
    for it in items:
        lines.extend(make_date_block(it[1], it[2], it[3], it[4], indent))
    lines.append('}')
    return lines


def make_character_block(name, birth_str, death_str, indent='\t'):
    """生成人物块（与头衔历史中的 holder 同名对应）。"""
    lines = ['%s = {' % name]
    if CHARACTER_RELIGION:
        lines.append('%sreligion = %s' % (indent, _quote(CHARACTER_RELIGION)))
    if CHARACTER_CULTURE:
        lines.append('%sculture = %s' % (indent, _quote(CHARACTER_CULTURE)))
    if birth_str:
        lines.append('%s%s = { birth = yes }' % (indent, birth_str))
    if death_str:
        lines.append('%s%s = { death = yes }' % (indent, death_str))
    lines.append('}')
    return lines


def make_header(landed_paths):
    return [
        '# ' + '=' * 68,
        '# 本文件由 build_title_history.py 生成并维护：',
        '#   liege      —— 按法理（landed_titles）层级自动推导；',
        '#   government —— 来自脚本配置；',
        '#   holder     —— 头衔名_序号，对应人物文件中的同名角色。',
        '# 脚本只追加新条目 / 补写缺失的 holder，不会修改或删除已有内容。',
        '# 法理来源：' + '、'.join(landed_paths),
        '# ' + '=' * 68,
        '',
    ]


def make_characters_header():
    return [
        '# ' + '=' * 68,
        '# 本文件由 build_title_history.py 生成并维护：',
        '#   为头衔历史中脚本命名的 holder（头衔名_序号）生成角色，',
        '#   birth/death 按头衔日期 ± 偏移年推算，religion/culture 来自脚本配置。',
        '# 只追加尚不存在的角色，不会修改或删除已有内容。',
        '# ' + '=' * 68,
        '',
    ]


# ------------------------------ 插入定位 ------------------------------

def _line_safe_after(line):
    """该行作为某日期块的结束行时，其后插入新块是否安全（行尾不能是未闭合的 '{'）。"""
    code = line.split('#', 1)[0]
    braces = [c for c in code if c in '{}']
    return not braces or braces[-1] == '}'


def find_insert_pos(block, dt, lines):
    """返回新日期块应插入到的行号（在该行之前插入）；无法安全插入返回 None。"""
    entries = block['entries']
    same = [e for e in entries if e['date'] == dt]
    if same:                                   # 已有同日期块：紧跟其后
        e = same[-1]
        pos = e['end'] + 1
        if pos > block['end'] or not _line_safe_after(lines[e['end']]):
            return None
        return pos
    earlier = [e for e in entries if e['date'] < dt]
    if earlier:                                # 跟在最后一个更早的日期块之后
        e = earlier[-1]
        pos = e['end'] + 1
        if pos > block['end'] or not _line_safe_after(lines[e['end']]):
            return None
        return pos
    if entries:                                # 比所有已有日期都早：排在最前
        return entries[0]['start']
    # 块内没有任何日期块：插到头衔块闭合行之前（要求该行只是单个 '}'）
    closing = lines[block['end']].split('#', 1)[0].strip()
    if closing == '}':
        return block['end']
    return None


def detect_indent(block, lines):
    """猜测该头衔块中日期条目使用的缩进。"""
    for e in block['entries']:
        ws = re.match(r'^([ \t]*)', lines[e['start']]).group(1)
        if ws:
            return ws
    for i in range(block['start'] + 1, block['end']):
        if lines[i].strip():
            ws = re.match(r'^([ \t]*)', lines[i]).group(1)
            if ws:
                return ws
    return '\t'


def detect_inner_indent(entry, lines, fallback):
    """日期块内部键行的缩进（取块内第一个非空行的前导空白）。"""
    for i in range(entry['start'] + 1, entry['end'] + 1):
        if lines[i].strip():
            ws = re.match(r'^([ \t]*)', lines[i]).group(1)
            return ws or fallback
    return fallback


# ------------------------------ 取值逻辑 ------------------------------

def resolve_government(title, dt, dates_cfg, gov_ov):
    """该头衔该日期的政府类型；None 表示不生成该日期条目。"""
    if title in gov_ov:
        ov = gov_ov[title]
        if isinstance(ov, dict):
            if dt in ov:
                return ov[dt]
            if 'default' in ov:
                return ov['default']
        else:
            return ov                         # 字符串，或显式 None（不生成）
    val = dates_cfg[dt]
    if isinstance(val, dict):
        tier = tier_of(title)
        if tier in val:
            return val[tier]
        if 'default' in val:
            return val['default']
        return None
    return val


def resolve_liege(title, dt, parent, liege_ov):
    """该头衔该日期的 liege；None 表示不写 liege 行。"""
    if title in liege_ov:
        ov = liege_ov[title]
        if isinstance(ov, dict):
            if dt in ov:
                return ov[dt]
            if 'default' in ov:
                return ov['default']
            # 未命中日期 -> 回落到法理上级
        else:
            return ov                         # 字符串，或显式 None
    return parent.get(title)                  # 顶级头衔 -> None


def _assign_holder(title, number, used):
    """生成 holder 名（头衔名_两位序号）；该序号名已被占用时顺延取空号。"""
    n = number
    while '%s_%02d' % (title, n) in used:
        n += 1
    name = '%s_%02d' % (title, n)
    used.add(name)
    if n != number:
        print('[提示] %s 第 %d 个日期块的默认 holder 名已被占用，顺延使用 %s。'
              % (title, number, name))
    return name


# -------------------------------- 主流程 --------------------------------

def main():
    ap = argparse.ArgumentParser(
        description='根据法理层级生成/合并 CK3 头衔历史与人物历史'
                    '（liege / government / holder）')
    ap.add_argument('--dry-run', action='store_true', help='只预览将插入的内容，不写文件')
    args = ap.parse_args()

    # ---- 1. 规范化配置 ----
    try:
        dates_cfg, date_str = OrderedDict(), {}
        for k, v in HISTORY_ENTRIES.items():
            dt, ds = normalize_date(k)
            dates_cfg[dt] = v
            date_str[dt] = ds
        gov_ov = {t: (_normalize_date_map(v) if isinstance(v, dict) else v)
                  for t, v in GOVERNMENT_OVERRIDES.items()}
        liege_ov = {t: (_normalize_date_map(v) if isinstance(v, dict) else v)
                    for t, v in LIEGE_OVERRIDES.items()}
        skip_dates = {t: {normalize_date(k)[0] for k in s}
                      for t, s in SKIP_DATES.items()}
    except ValueError as exc:
        sys.exit('配置错误：%s' % exc)
    if not dates_cfg:
        sys.exit('配置错误：HISTORY_ENTRIES 不能为空。')

    # ---- 2. 法理层级 ----
    landed_paths = ([LANDED_TITLES_PATH] if isinstance(LANDED_TITLES_PATH, str)
                    else list(LANDED_TITLES_PATH))
    try:
        de_jure_order, parent = build_de_jure(landed_paths)
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit('读取法理文件失败：%s' % exc)
    if not de_jure_order:
        sys.exit('法理文件中未解析到任何头衔（get_title.py 只识别 e/k/d/c/b 前缀）。')

    titles = [t for t in de_jure_order
              if tier_of(t) in INCLUDE_TIERS and t not in EXCLUDE_TITLES]
    tier_stat = OrderedDict()
    for t in titles:
        tier_stat[tier_of(t)] = tier_stat.get(tier_of(t), 0) + 1
    summary = '、'.join('%s%d个' % (TIER_NAMES.get(k, k + '_'), v)
                        for k, v in tier_stat.items())
    print('法理解析：%d 个头衔，本次处理 %d 个（%s）'
          % (len(de_jure_order), len(titles), summary or '无'))
    print('日期配置：%s' % '、'.join(date_str[dt] for dt in dates_cfg))
    use_chars = GENERATE_HOLDERS and bool(CHARACTERS_PATH)
    if GENERATE_HOLDERS:
        print('holder：自动编号为 头衔名_序号（按日期块次序）；'
              '角色生卒 = 日期 -%d / +%d 年'
              % (HOLDER_BIRTH_OFFSET, HOLDER_DEATH_OFFSET))

    # ---- 3. 读取已有头衔历史文件 ----
    lines, bom, newline = [], False, '\n'
    file_exists = os.path.exists(OUTPUT_PATH)
    balanced, by_name, handled = True, {}, {}

    if file_exists:
        try:
            lines, bom, newline = read_text_lines(OUTPUT_PATH)
        except UnicodeDecodeError:
            sys.exit('%s 不是 UTF-8 编码，请先转换为 UTF-8。' % OUTPUT_PATH)
        blocks, balanced = parse_history_file(lines)
        for b in blocks:
            if b['name'] in by_name:
                print('[警告] 输出文件中 %s 出现多个块，只在第一个块内追加。' % b['name'])
            handled.setdefault(b['name'], set()).update(
                e['date'] for e in b['entries'] if entry_handled(e))
            by_name.setdefault(b['name'], b)
        print('输出文件：%s（已存在，执行只增不改合并）' % OUTPUT_PATH)
    else:
        print('输出文件：%s（不存在，将新建）' % OUTPUT_PATH)

    # ---- 3b. 读取已有人物文件 ----
    char_lines, char_bom, char_newline = [], False, '\n'
    char_exists = use_chars and os.path.exists(CHARACTERS_PATH)
    char_names, char_balanced = set(), True
    if char_exists:
        try:
            char_lines, char_bom, char_newline = read_text_lines(CHARACTERS_PATH)
        except UnicodeDecodeError:
            sys.exit('%s 不是 UTF-8 编码，请先转换为 UTF-8。' % CHARACTERS_PATH)
        char_names, char_balanced = parse_character_names(char_lines)
        print('人物文件：%s（已存在，只追加不存在的角色）' % CHARACTERS_PATH)
    elif use_chars:
        print('人物文件：%s（不存在，将新建）' % CHARACTERS_PATH)

    # ---- 4. 生成插入计划 ----
    insertions = OrderedDict()   # 行号 -> [要插入的行]（在该行之前插入）
    new_blocks = []              # 尚不在文件中的头衔 -> 整块追加到文件末尾
    report, example = [], None
    added_total = backfill_total = touched_titles = 0
    skip_stat = OrderedDict([('已有条目', 0), ('SKIP_DATES', 0), ('等级未配置政府', 0)])
    ensure_map = OrderedDict()   # 角色名 -> 推算生卒所用日期

    def add_insert(pos, chunk):
        insertions.setdefault(pos, []).extend(chunk)

    for title in titles:
        # 4.1 该头衔需要新增的日期条目（与原逻辑一致）
        items = []
        for dt in dates_cfg:
            if dt in handled.get(title, ()):
                skip_stat['已有条目'] += 1
                continue
            if dt in skip_dates.get(title, ()):
                skip_stat['SKIP_DATES'] += 1
                continue
            gov = resolve_government(title, dt, dates_cfg, gov_ov)
            if gov is None:
                skip_stat['等级未配置政府'] += 1
                continue
            items.append([dt, date_str[dt],
                          resolve_liege(title, dt, parent, liege_ov), gov, None])
        items.sort(key=lambda it: it[0])

        block = by_name.get(title)
        existing = block['entries'] if block else []
        backfills = []                  # [(既有日期块, holder名)]
        title_ensure = OrderedDict()    # 角色名 -> 日期

        # 4.2 holder 编号与补写判定
        if GENERATE_HOLDERS:
            pat = re.compile(r'^%s_\d+$' % re.escape(title))
            used = {e['holder_val'] for e in existing if e['holder_val']}
            for e in existing:          # 文件中已是“脚本命名”的 holder -> 确保人物存在
                hv = e['holder_val']
                if hv and pat.match(hv) and hv not in title_ensure:
                    title_ensure[hv] = e['date']

            # 槽位 = 既有日期块 + 新日期块，按日期先后（同日期时既有在前）
            slots = ([(e['date'], 0, e) for e in existing] +
                     [(it[0], 1, it) for it in items])
            slots.sort(key=lambda s: (s[0], s[1]))
            backfilled_dates = set()
            for number, (dt, kind, payload) in enumerate(slots, 1):
                date_has_holder = any(x['has_holder'] for x in existing
                                      if x['date'] == dt)
                if kind:                # 新日期块：按次序编号
                    payload[4] = (None if date_has_holder
                                  else _assign_holder(title, number, used))
                else:                   # 既有日期块：判定是否补写 holder
                    e = payload
                    if ((e['has_liege'] or e['has_gov']) and not e['has_holder']
                            and not date_has_holder and dt not in backfilled_dates
                            and dt in dates_cfg
                            and dt not in skip_dates.get(title, ())):
                        h = _assign_holder(title, number, used)
                        backfills.append((e, h))
                        title_ensure[h] = dt
                        backfilled_dates.add(dt)

        # 4.3 写入计划
        written = []
        if block is None:
            if items:
                new_blocks.append((title, items))
                written = items
                added_total += len(items)
                touched_titles += 1
                report.append('[新建块] %-26s %s'
                              % (title, ', '.join(it[1] for it in items)))
                if example is None:
                    example = (title, True, items[0])
        else:
            indent = detect_indent(block, lines)
            for e, h in backfills:      # 向既有日期块内补写一行 holder
                key_indent = detect_inner_indent(e, lines, indent + '\t')
                add_insert(e['start'] + 1, ['%sholder = %s' % (key_indent, h)])
                backfill_total += 1
                report.append('[补holder] %-25s %s -> %s'
                              % (title, format_date(e['date']), h))
            groups = OrderedDict()
            for it in items:
                pos = find_insert_pos(block, it[0], lines)
                if pos is None:
                    print('[警告] %s 结构特殊（闭合括号与内容同行？），无法安全插入 %s，请手动处理。'
                          % (title, it[1]))
                    continue
                groups.setdefault(pos, []).append(it)
            for pos, its in groups.items():
                chunk = []
                for it in its:
                    chunk.extend(make_date_block(it[1], it[2], it[3], it[4], indent))
                add_insert(pos, chunk)
                written.extend(its)
            if written:
                added_total += len(written)
                touched_titles += 1
                report.append('[追加]   %-26s %s'
                              % (title, ', '.join(it[1] for it in written)))
                if example is None:
                    example = (title, False, written[0])
            elif backfills:
                touched_titles += 1

        # 4.4 登记需要确保存在的角色
        for it in written:
            if it[4] and it[4] not in title_ensure:
                title_ensure[it[4]] = it[0]
        for name in sorted(title_ensure, key=lambda n: title_ensure[n]):
            ensure_map.setdefault(name, title_ensure[name])

    # ---- 4b. 人物插入计划 ----
    char_add, char_kept = [], 0
    if use_chars:
        for name, dt in ensure_map.items():
            if name in char_names:
                char_kept += 1
                continue
            birth = shift_year(dt, -HOLDER_BIRTH_OFFSET)
            death = shift_year(dt, HOLDER_DEATH_OFFSET)
            char_add.append((name, format_date(birth), format_date(death)))

    # 文件末尾追加的新头衔块
    if new_blocks:
        tail = []
        for title, items in new_blocks:
            if tail:
                tail.append('')             # 块之间空一行
            tail.extend(make_title_block(title, items))
        if not lines:
            if WRITE_HEADER:
                tail = make_header(landed_paths) + tail
        elif lines[-1].strip():
            tail.insert(0, '')              # 与已有内容之间空一行
        add_insert(len(lines), tail)

    # ---- 5. 摘要与写出 ----
    title_changes = bool(insertions)
    char_changes = bool(char_add)

    if not title_changes and not char_changes:
        print('\n没有需要新增的条目，头衔历史与人物文件均保持不变。')
        if not balanced:
            print('[警告] 现有头衔历史文件花括号不配平，建议检查。')
        if use_chars and not char_balanced:
            print('[警告] 现有人物文件花括号不配平，建议检查。')
        return
    if title_changes and not balanced:
        sys.exit('错误：%s 花括号不配平或结构异常。为避免破坏手动编辑的内容，已中止，请先修正。'
                 % OUTPUT_PATH)
    if char_changes and not char_balanced:
        sys.exit('错误：%s 花括号不配平或结构异常。为避免破坏手动编辑的内容，已中止，请先修正。'
                 % CHARACTERS_PATH)

    if title_changes:
        print('\n===== 头衔历史：将新增 %d 个日期条目、补写 %d 个 holder（涉及 %d 个头衔）====='
              % (added_total, backfill_total, touched_titles))
        for line in report:
            print(line)
    else:
        print('\n头衔历史：无需改动。')
    for reason, n in skip_stat.items():
        if n:
            print('跳过 %d 处（%s）' % (n, reason))

    if example:
        title, is_new, it = example
        print('\n条目样式示例（%s%s）：' % (title, '，新建块' if is_new else ''))
        for l in make_date_block(it[1], it[2], it[3], it[4], '\t'):
            print('    ' + l)

    if use_chars:
        if char_add:
            extra = ('（另有 %d 个已存在，保留不动）' % char_kept) if char_kept else ''
            print('\n===== 人物文件：将新增 %d 个角色%s =====' % (len(char_add), extra))
            for name, b, d in char_add:
                print('  %-30s %s 生 / %s 卒' % (name, b, d))
            name, b, d = char_add[0]
            print('\n角色样式示例（%s）：' % name)
            for l in make_character_block(name, b, d):
                print('    ' + l)
        elif char_kept:
            print('\n人物文件：%d 个相关角色均已存在，无需新增。' % char_kept)

    if args.dry_run:
        print('\n[dry-run] 以上内容未写入文件。')
        return

    # ---- 6. 写出 ----
    if title_changes:
        for pos in sorted(insertions, reverse=True):   # 自底向上插入，避免行号失效
            lines[pos:pos] = insertions[pos]
        ensure_dir(OUTPUT_PATH)
        if MAKE_BACKUP and file_exists:
            shutil.copy2(OUTPUT_PATH, OUTPUT_PATH + '.bak')
            print('\n已备份原头衔历史文件 -> %s.bak' % OUTPUT_PATH)
        write_text_lines(OUTPUT_PATH, lines, bom, newline)
        print('头衔历史：新增 %d 个日期条目（%d 个新建块）、补写 %d 个 holder，已写入 %s'
              % (added_total, len(new_blocks), backfill_total, OUTPUT_PATH))

    if char_changes:
        tail = []
        for name, b, d in char_add:
            if tail:
                tail.append('')             # 角色之间空一行
            tail.extend(make_character_block(name, b, d))
        if not char_lines:
            if WRITE_HEADER:
                tail = make_characters_header() + tail
        elif char_lines[-1].strip():
            tail.insert(0, '')              # 与已有内容之间空一行
        char_lines.extend(tail)
        ensure_dir(CHARACTERS_PATH)
        if MAKE_BACKUP and char_exists:
            shutil.copy2(CHARACTERS_PATH, CHARACTERS_PATH + '.bak')
            print('已备份原人物文件 -> %s.bak' % CHARACTERS_PATH)
        write_text_lines(CHARACTERS_PATH, char_lines, char_bom, char_newline)
        print('人物文件：新增 %d 个角色，已写入 %s' % (len(char_add), CHARACTERS_PATH))


if __name__ == '__main__':
    main()