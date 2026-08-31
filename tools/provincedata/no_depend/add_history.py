#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_history.py —— 为 CK3 mod(TheAshenGoldenAge) 历史文件批量添加新日期快照

流程:
  1) titles 文件: 每个头衔块 -> 复制"日期<=目标日期且含holder的最近条目",
     日期改为目标日期, holder 的 _数字 后缀改为 _<新后缀>(默认年份), 按时间顺序插回。
  2) characters 文件: 为每个被改写的 holder 生成新角色(复制原角色, 仅改 ID 与
     生卒日期 = 目标日期∓30年), 追加到文件末尾; 共用 holder 自动去重。

用法:
  python add_history.py -d 361.1.1
  python3.13 tools\provincedata\no_depend\add_history.py -d 361.1.1 -e h_taga_hanjin
  python add_history.py -d 310.6.1 --suffix-mode date --dry-run
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ====================== 默认配置(可被命令行覆盖) ======================
MOD_ROOT = "TheAshenGoldenAge"
DEFAULT_TITLES_FILE = "history/titles/e_taga_hanjin.txt"    # 相对 MOD_ROOT
DEFAULT_CHARACTERS_FILE = "history/characters/jin.txt"      # 相对 MOD_ROOT
DEFAULT_DATE: Optional[str] = None                          # 目标日期 "Y.M.D", 如 "310.6.1"
DEFAULT_EXCLUDED_TITLES: Sequence[str] = ()                 # 排除的头衔名, 如 ("h_taga_hanjin",)
DEFAULT_SUFFIX_MODE = "year"        # holder 新后缀: "year" -> _310 ; "date" -> _310_6_1
DEFAULT_BIRTH_OFFSET = -30          # 新角色出生 = 目标日期 + 偏移(年)
DEFAULT_DEATH_OFFSET = 30           # 新角色死亡 = 目标日期 + 偏移(年)

# ============================ 正则 ============================
RE_DATE_KEY    = re.compile(r"^\d{1,4}\.\d{1,2}\.\d{1,2}$")
RE_TOP_HEAD    = re.compile(r"^([A-Za-z0-9_.\-]+)\s*=\s*\{")
RE_ENTRY_HEAD  = re.compile(r"^(\d{1,4}\.\d{1,2}\.\d{1,2})\s*=\s*\{")
RE_HOLDER_ANY  = re.compile(r"\bholder\s*=\s*([A-Za-z0-9_.\-]+)")
RE_HOLDER_LINE = re.compile(r"^(\s*holder\s*=\s*)([A-Za-z0-9_.\-]+)(.*)$")
RE_DATE_PREFIX = re.compile(r"^(\s*)(\d{1,4}\.\d{1,2}\.\d{1,2})")
RE_ID_SUFFIX   = re.compile(r"^(?P<base>.+)_(?P<num>\d+)$")
RE_CHANGE_EFF  = re.compile(r"\bchange_[A-Za-z0-9_]+\s*=")

Date = Tuple[int, int, int]


@dataclass
class Entry:
    date_str: str
    date: Date
    start: int            # 条目头行下标(含)
    end: int              # 条目闭括号行下标(含)
    holders: List[str]


@dataclass
class Doc:
    lines: List[str]
    newline: str
    bom: bool
    trailing_newline: bool


# ============================ 小工具 ============================
def strip_comment(line: str) -> str:
    i = line.find("#")
    return line if i < 0 else line[:i]


def parse_date(s: str) -> Date:
    s = s.strip()
    if not RE_DATE_KEY.match(s):
        raise ValueError(f"非法日期 {s!r}, 应为 Y.M.D 形式(如 310.6.1)")
    y, m, d = (int(x) for x in s.split("."))
    if not (1 <= m <= 12 and 1 <= d <= 31):
        raise ValueError(f"非法日期 {s!r}: 月/日超界")
    return (y, m, d)


def fmt_date(d: Date) -> str:
    return f"{d[0]}.{d[1]}.{d[2]}"


def shift_years(d: Date, years: int) -> Date:
    return (max(1, d[0] + years), d[1], d[2])


def suffix_for(d: Date, mode: str) -> str:
    return str(d[0]) if mode == "year" else f"{d[0]}_{d[1]}_{d[2]}"


def remap_id(holder_id: str, suffix: str) -> Optional[str]:
    """c_taga_luoyang_01 + "310" -> c_taga_luoyang_310 ; 无数字后缀返回 None。"""
    m = RE_ID_SUFFIX.match(holder_id)
    return f"{m['base']}_{suffix}" if m else None


def load_doc(path: Path) -> Doc:
    data = path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    return Doc(text.splitlines(),
               "\r\n" if "\r\n" in text else "\n",
               bom, text.endswith(("\n", "\r")))


def save_doc(path: Path, doc: Doc) -> None:
    text = doc.newline.join(doc.lines)
    if doc.lines and doc.trailing_newline:
        text += doc.newline
    with open(path, "w", encoding="utf-8-sig" if doc.bom else "utf-8", newline="") as f:
        f.write(text)


# ============================ 结构解析 ============================
def find_blocks(lines: List[str]) -> List[Tuple[str, int, int]]:
    """扫描顶层块, 返回 [(块名, 头行下标, 闭括号行下标)]。遇到无法识别的顶层内容抛错。"""
    blocks: List[Tuple[str, int, int]] = []
    i, n = 0, len(lines)
    while i < n:
        code = strip_comment(lines[i]).strip()
        if not code:
            i += 1
            continue
        if code.startswith("}"):
            raise SyntaxError(f"第 {i + 1} 行: 多余的 '}}': {lines[i]!r}")
        m = RE_TOP_HEAD.match(code)
        if not m:
            raise SyntaxError(f"第 {i + 1} 行: 无法识别的顶层行: {lines[i]!r}")
        name = m.group(1)
        if RE_DATE_KEY.match(name):
            raise SyntaxError(f"第 {i + 1} 行: 顶层出现日期条目(缺块头?): {lines[i]!r}")
        depth = code.count("{") - code.count("}")
        start, j = i, i
        while depth > 0:
            j += 1
            if j >= n:
                raise SyntaxError(f"第 {i + 1} 行: 块 {name} 括号不闭合")
            c = strip_comment(lines[j]).strip()
            depth += c.count("{") - c.count("}")
        blocks.append((name, start, j))
        i = j + 1
    return blocks


def find_entries(lines: List[str], b_start: int, b_end: int) -> List[Entry]:
    """解析头衔块体内一层日期条目(按文件顺序)。"""
    entries: List[Entry] = []
    i = b_start + 1
    while i < b_end:
        code = strip_comment(lines[i]).strip()
        m = RE_ENTRY_HEAD.match(code)
        if not m:
            if not code:                      # 空行/纯注释
                i += 1
                continue
            raise SyntaxError(f"第 {i + 1} 行: 头衔块内无法识别的行(应为 '日期 = {{'): {lines[i]!r}")
        date_str = m.group(1)
        try:
            date = parse_date(date_str)
        except ValueError as ex:
            raise SyntaxError(f"第 {i + 1} 行: {ex}")
        start, j, depth = i, i, code.count("{") - code.count("}")
        holders: List[str] = []
        while True:
            c = strip_comment(lines[j]).strip()
            holders.extend(h.group(1) for h in RE_HOLDER_ANY.finditer(c))
            if depth <= 0:
                break
            j += 1
            if j > b_end:
                raise SyntaxError(f"第 {i + 1} 行: 条目 {date_str} 括号不闭合")
            c2 = strip_comment(lines[j]).strip()
            depth += c2.count("{") - c2.count("}")
        entries.append(Entry(date_str, date, start, j, holders))
        i = j + 1
    return entries


def build_char_block(clines: List[str], s: int, e: int, new_id: str,
                     birth: Date, death: Date) -> List[str]:
    """复制角色块: 换 ID, 生卒日期改期, 其余逐行原样保留。"""
    head = re.match(r"^(\s*)[A-Za-z0-9_.\-]+(\s*=\s*\{)", clines[s])
    out = [head.group(1) + new_id + head.group(2) if head else f"{new_id} = {{"]
    body = clines[s + 1:e]

    # 定位生/卒日期条目(兼容单行与多行)
    span: Dict[str, Tuple[int, int]] = {}
    i = 0
    while i < len(body):
        code = strip_comment(body[i]).strip()
        if RE_ENTRY_HEAD.match(code):
            depth, j = code.count("{") - code.count("}"), i
            while depth > 0:
                j += 1
                if j >= len(body):
                    raise SyntaxError(f"角色块(第 {s + 1} 行起)内生卒条目括号不闭合")
                c2 = strip_comment(body[j]).strip()
                depth += c2.count("{") - c2.count("}")
            inner = " ".join(strip_comment(body[k]).strip() for k in range(i, j + 1))
            if "birth" not in span and re.search(r"\bbirth\b\s*=", inner):
                span["birth"] = (i, j)
            elif "death" not in span and re.search(r"\bdeath\b\s*=", inner):
                span["death"] = (i, j)
            i = j + 1
            continue
        i += 1

    def redated(kind: str) -> List[str]:
        a, b = span[kind]
        newd = fmt_date(birth if kind == "birth" else death)
        first = RE_DATE_PREFIX.sub(lambda m: m.group(1) + newd, body[a], count=1)
        return [first] + body[a + 1:b + 1]      # 保留 birth/death 行的其余内容

    covered = set()
    for v in span.values():
        covered.update(range(v[0], v[1] + 1))
    for idx, line in enumerate(body):
        if idx in covered:
            if idx == span["birth"][0]:
                out.extend(redated("birth"))
            elif idx == span["death"][0]:
                out.extend(redated("death"))
            continue
        out.append(line)
    if "birth" not in span:
        out.append(f"\t{fmt_date(birth)} = {{ birth = yes }}")
    if "death" not in span:
        out.append(f"\t{fmt_date(death)} = {{ death = yes }}")
    out.append(clines[e])                        # 原闭括号行
    return out


# ============================ 主流程 ============================
def run(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    date_str = args.date or DEFAULT_DATE
    if not date_str:
        print("错误: 未指定目标日期(用 -d/--date Y.M.D, 或修改脚本内 DEFAULT_DATE)", file=sys.stderr)
        return 2
    try:
        new_date = parse_date(date_str)
    except ValueError as ex:
        print(f"错误: {ex}", file=sys.stderr)
        return 2
    new_date_str = fmt_date(new_date)
    suffix = suffix_for(new_date, args.suffix_mode)
    birth = shift_years(new_date, args.birth_offset)
    death = shift_years(new_date, args.death_offset)
    excluded = set(DEFAULT_EXCLUDED_TITLES) | set(args.exclude)

    titles_path = (Path(args.titles_file) if args.titles_file
                   else Path(args.mod_root) / DEFAULT_TITLES_FILE)
    chars_path = (Path(args.characters_file) if args.characters_file
                  else Path(args.mod_root) / DEFAULT_CHARACTERS_FILE)
    for p in (titles_path, chars_path):
        if not p.is_file():
            print(f"错误: 找不到文件: {p}", file=sys.stderr)
            return 2

    print(f"目标日期: {new_date_str} | holder 新后缀: _{suffix} | "
          f"新角色生卒: {fmt_date(birth)} / {fmt_date(death)}")

    tdoc, cdoc = load_doc(titles_path), load_doc(chars_path)
    tl, cl = tdoc.lines, cdoc.lines

    try:
        title_blocks = find_blocks(tl)
    except SyntaxError as ex:
        print(f"错误: 解析 titles 失败, 未做任何修改: {ex}", file=sys.stderr)
        return 1

    inserts: List[Tuple[int, int, List[str], str]] = []   # (插入行下标, 序号, 新行, 头衔名)
    need: Dict[str, list] = {}                            # 原角色ID -> [新角色ID, [引用头衔...]]

    print(f"\n--- titles: 共 {len(title_blocks)} 个头衔块 ---")
    for name, bs, be in title_blocks:
        if name in excluded:
            print(f"[排除] {name}")
            continue
        try:
            entries = find_entries(tl, bs, be)
        except SyntaxError as ex:
            print(f"错误: {ex}", file=sys.stderr)
            return 1

        # 幂等: 该日期已存在带新后缀的 holder -> 跳过
        if any(en.date == new_date and any(h.endswith("_" + suffix) for h in en.holders)
               for en in entries):
            print(f"[跳过] {name}: {new_date_str} 已存在后缀 _{suffix} 的条目")
            continue

        cand = [en for en in entries if en.holders and en.date <= new_date]
        if not cand:
            print(f"[警告] {name}: 无日期 <= {new_date_str} 且含 holder 的条目, 跳过")
            continue
        src = max(cand, key=lambda en: (en.date, en.end))

        mapping: Dict[str, str] = {}
        kept: List[str] = []
        for h in dict.fromkeys(src.holders):          # 去重且保序
            nh = remap_id(h, suffix)
            if nh is None:
                kept.append(h)
            else:
                mapping[h] = nh
                need.setdefault(h, [nh, []])[1].append(name)

        # 复制模板条目 -> 新条目(仅改日期行与 holder 行)
        new_entry: List[str] = []
        for k in range(src.start, src.end + 1):
            line = tl[k]
            if k == src.start:
                line = RE_DATE_PREFIX.sub(lambda m: m.group(1) + new_date_str, line, count=1)
            else:
                hm = RE_HOLDER_LINE.match(line)
                if hm and hm.group(2) in mapping:
                    line = hm.group(1) + mapping[hm.group(2)] + hm.group(3)
            new_entry.append(line)

        if any(RE_CHANGE_EFF.search(strip_comment(l)) for l in new_entry):
            print(f"[警告] {name}: 模板条目含 change_* 数值效果, 会在 {new_date_str} 再次生效, 请检查!")

        before = [en for en in entries if en.date <= new_date]
        last = max(before, key=lambda en: (en.date, en.end)) if before else None
        at = last.end + 1 if last else bs + 1

        inserts.append((at, len(inserts), new_entry, name))
        parts = [f"{a} -> {b}" for a, b in mapping.items()]
        if kept:
            parts.append(f"原样保留(无数字后缀): {', '.join(kept)}")
        print(f"[插入] {name}: 复制 {src.date_str} 条目 -> {new_date_str} "
              f"(插在第 {at + 1} 行前) | {'; '.join(parts)}")

    # ---------- 生成新角色 ----------
    print("\n--- characters ---")
    try:
        char_blocks = find_blocks(cl)
    except SyntaxError as ex:
        print(f"错误: 解析 characters 失败, 未做任何修改: {ex}", file=sys.stderr)
        return 1
    by_id: Dict[str, Tuple[int, int]] = {}
    for nm, s, e in char_blocks:
        if nm in by_id:
            print(f"[警告] characters 中 ID 重复: {nm}, 以第一个为准")
            continue
        by_id[nm] = (s, e)

    # 引用的原角色缺失 -> 回滚相关头衔插入(避免引用不存在的角色)
    missing = [o for o in need if o not in by_id]
    if missing:
        bad = set()
        for o in missing:
            print(f"[警告] 角色 {o} 不存在于 characters 文件, 取消相关头衔新条目: {', '.join(need[o][1])}")
            bad.update(need[o][1])
        inserts = [x for x in inserts if x[3] not in bad]
        for o in missing:
            need.pop(o)

    # 不同原角色映射到同一新 ID -> 冲突, 报错退出
    owner: Dict[str, str] = {}
    for o, (nh, _) in need.items():
        if nh in owner and owner[nh] != o:
            print(f"错误: 新角色 ID 冲突: {owner[nh]} 与 {o} 均映射到 {nh}; 请改用 --suffix-mode date",
                  file=sys.stderr)
            return 1
        owner[nh] = o

    new_char_blocks: List[List[str]] = []
    for o, (nh, _) in need.items():
        if nh in by_id:
            print(f"[跳过] {nh} 已存在(视为此前已运行过)")
            continue
        s, e = by_id[o]
        new_char_blocks.append(build_char_block(cl, s, e, nh, birth, death))
        print(f"[新增] {nh} <- 复制自 {o} ({fmt_date(birth)} 生 / {fmt_date(death)} 卒)")
    if not need:
        print("(没有需要生成的新角色)")

    # ---------- 写盘 ----------
    print()
    if args.dry_run:
        print(f"[dry-run] 计划: titles 插入 {len(inserts)} 条, characters 新增 "
              f"{len(new_char_blocks)} 个角色; 未写入任何文件")
        return 0
    if not inserts and not new_char_blocks:
        print("无需修改, 未写入文件")
        return 0
    if not args.no_backup:
        shutil.copy2(titles_path, str(titles_path) + ".bak")
        shutil.copy2(chars_path, str(chars_path) + ".bak")
        print(f"已备份: {titles_path}.bak / {chars_path}.bak")

    for at, seq, new_lines, _ in sorted(inserts, key=lambda t: (-t[0], -t[1])):
        tl[at:at] = new_lines
    for nb in new_char_blocks:
        cl.append("")                 # 空行分隔, 与现有风格一致
        cl.extend(nb)

    save_doc(titles_path, tdoc)
    save_doc(chars_path, cdoc)
    print(f"完成: titles 插入 {len(inserts)} 条 -> {titles_path}; "
          f"characters 新增 {len(new_char_blocks)} 个角色 -> {chars_path}")
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="为 titles 历史文件每个头衔块添加新日期条目, 并在 characters 文件生成对应新 holder。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("-d", "--date", default=DEFAULT_DATE, help='目标日期, 如 "310.6.1"')
    p.add_argument("-e", "--exclude", nargs="*", default=[],
                   help="排除的头衔名(空格/逗号分隔), 如 -e h_taga_hanjin")
    p.add_argument("--mod-root", default=MOD_ROOT, help="mod 根目录")
    p.add_argument("--titles-file", default=None, help=f"覆盖 titles 文件路径(默认 <mod_root>/{DEFAULT_TITLES_FILE})")
    p.add_argument("--characters-file", default=None, help=f"覆盖 characters 文件路径(默认 <mod_root>/{DEFAULT_CHARACTERS_FILE})")
    p.add_argument("--suffix-mode", choices=("year", "date"), default=DEFAULT_SUFFIX_MODE,
                   help="holder 新后缀: year=_310 / date=_310_6_1")
    p.add_argument("--birth-offset", type=int, default=DEFAULT_BIRTH_OFFSET, help="出生年份偏移")
    p.add_argument("--death-offset", type=int, default=DEFAULT_DEATH_OFFSET, help="死亡年份偏移")
    p.add_argument("--dry-run", action="store_true", help="只打印计划, 不写文件")
    p.add_argument("--no-backup", action="store_true", help="不生成 .bak 备份")
    ns = p.parse_args(argv)
    excl: List[str] = []
    for tok in ns.exclude:
        excl.extend(t for t in tok.replace(",", " ").split() if t)
    ns.exclude = excl
    return ns


if __name__ == "__main__":
    sys.exit(run())