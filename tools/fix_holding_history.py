import re
from pathlib import Path

# 文件路径，请根据实际情况修改
TITLE_FILE = Path("TheAshenGoldenAge/history/titles/e_taga_hanjin.txt")
CHAR_FILE = Path("TheAshenGoldenAge/history/characters/jin.txt")


def parse_blocks(text):
    """
    解析 Paradox 文件中所有顶级块。
    返回 (块id, 起始行, 结束行) 和 lines 列表。
    顶级块通常无缩进，如 e_taga_si = { ... }
    """
    lines = text.splitlines()
    blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 跳过空行和注释
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # 顶级块无缩进
        if not line.startswith((" ", "\t")):
            m = re.match(r"^([A-Za-z0-9_\.]+)\s*=\s*\{", stripped)
            if m:
                block_id = m.group(1)
                brace_count = stripped.count("{") - stripped.count("}")
                start = i
                i += 1

                while i < n and brace_count > 0:
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    i += 1

                end = i  # 结束行索引（不包含）
                blocks.append((block_id, start, end))
                continue

        i += 1

    return blocks, lines


def extract_first(lines, start, end, key):
    """在指定行范围内提取 key = value 的第一个 value。"""
    for j in range(start, end):
        m = re.match(r"^\s*" + re.escape(key) + r"\s*=\s*(\S+)", lines[j])
        if m:
            return m.group(1)
    return None


def main():
    # 1. 处理 title 文件
    text = TITLE_FILE.read_text(encoding="utf-8-sig")
    blocks, lines = parse_blocks(text)

    liege_map = {}
    holder_map = {}

    for title, start, end in blocks:
        liege = extract_first(lines, start, end, "liege")
        holder = extract_first(lines, start, end, "holder")
        if liege:
            liege_map[title] = liege
        if holder:
            holder_map[title] = holder

    # 构建封臣关系：上级 -> 下级列表
    children_map = {}
    for title, liege in liege_map.items():
        children_map.setdefault(liege, []).append(title)

    def find_c_vassal(title, visited=None):
        """递归查找 title 下属的第一个 c_ 头衔。"""
        if visited is None:
            visited = set()
        if title in visited:
            return None
        visited.add(title)

        if title.startswith("c_"):
            return title

        for child in children_map.get(title, []):
            result = find_c_vassal(child, visited)
            if result:
                return result
        return None

    changed_titles = []

    for title, start, end in blocks:
        if title.startswith("c_"):
            continue  # 只修改非 c_ 头衔

        c_vassal = find_c_vassal(title)
        if not c_vassal:
            print(f"警告：{title} 找不到下属 c_ 头衔，跳过")
            continue

        new_holder = holder_map.get(c_vassal)
        if not new_holder or not new_holder.startswith("c_"):
            print(f"警告：{c_vassal} 的持有者不是 c_ 开头，跳过 {title}")
            continue

        old_holder = holder_map.get(title)
        if old_holder == new_holder:
            continue

        # 替换该块内所有 holder 行
        for j in range(start, end):
            line = lines[j]
            if re.match(r"^\s*holder\s*=", line):
                new_line = re.sub(
                    r"^(\s*holder\s*=\s*)\S+",
                    r"\1" + new_holder,
                    line
                )
                lines[j] = new_line

        changed_titles.append((title, old_holder, new_holder))
        print(f"{title}: holder {old_holder} -> {new_holder}")

    # 写回 title 文件
    TITLE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已修改 {len(changed_titles)} 个 title 的 holder。")

    # 2. 处理角色文件
    ctext = CHAR_FILE.read_text(encoding="utf-8-sig")
    cblocks, clines = parse_blocks(ctext)

    to_delete = []
    for cid, start, end in cblocks:
        # 删除 d_ / k_ / e_ 开头的角色
        if re.match(r"^[dek]_", cid):
            to_delete.append((start, end, cid))

    # 按起始行倒序删除，避免索引错乱
    for start, end, cid in reversed(to_delete):
        del clines[start:end]
        print(f"删除角色：{cid}")

    # 写回角色文件
    CHAR_FILE.write_text("\n".join(clines) + "\n", encoding="utf-8")
    print(f"已删除 {len(to_delete)} 个非 c_ 开头的角色。")


if __name__ == "__main__":
    main()