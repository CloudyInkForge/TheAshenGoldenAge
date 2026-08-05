import os
import re

def get_ordered_keys(landed_path):
    """从领地文件中按出现顺序提取所有头衔键（去重）"""
    with open(landed_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    pattern = re.compile(r'^\s*([a-z]_[a-zA-Z0-9_]+)\s*=', re.MULTILINE)
    matches = pattern.findall(content)
    seen = set()
    ordered = []
    for key in matches:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered

def regenerate_localization(landed_titles_path, loc_file_path, keep_empty=True):
    """
    根据领地文件重新生成本地化文件，保持头衔定义顺序，
    保留已有翻译，缺失键补空引号。

    :param keep_empty: 若为 True，保留空翻译项（显示为 ""）；若为 False，则删除所有空翻译项
    """
    ordered_keys = get_ordered_keys(landed_titles_path)

    # 读取原有翻译
    existing_translations = {}
    if os.path.exists(loc_file_path):
        with open(loc_file_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^([a-zA-Z0-9_]+):"([^"]*)"', line)
                if m:
                    existing_translations[m.group(1)] = m.group(2)

    translations = {k: existing_translations.get(k, "") for k in ordered_keys}

    # ---- 统计 b_ 头衔翻译进度（带百分比和鞭策） ----
    b_all = [k for k in ordered_keys if k.startswith('b_')]
    b_translated = [k for k in b_all if translations.get(k, '') != '']
    if b_all:
        total = len(b_all)
        done = len(b_translated)
        undone = total - done
        percent = done / total * 100

        # 输出进度
        print(f"男爵领 (b_) 翻译进度: {done} / {total} ({percent:.1f}%)")

        # 鞭策性评语
        if percent >= 100:
            print("🎉 完美！所有男爵领已翻译！")
        elif percent >= 80:
            print(f"✅ 快完成了！还剩 {undone} 个，再加把劲！")
        elif percent >= 60:
            print(f"💪 进度不错，但还有 {undone} 个未翻译，继续加油！")
        elif percent >= 40:
            print(f"⏳ 刚过半，仍需努力！剩余 {undone} 个，别偷懒！")
        elif percent >= 20:
            print(f"🐢 才完成 {percent:.0f}%？还有 {undone} 个，提速啊！")
        else:
            print(f"🔥 翻译进度严重不足！只剩 {undone} 个未翻，快动手！")
    else:
        print("没有以 b_ 开头的头衔。")
    # -----------------------------------------

    # 如果 keep_empty 为 False，过滤掉翻译为空的键
    if not keep_empty:
        ordered_keys = [k for k in ordered_keys if translations[k] != ""]

    # 如果过滤后没有键，只写文件头
    if not ordered_keys:
        with open(loc_file_path, 'w', encoding='utf-8-sig') as f:
            f.write("l_simp_chinese:\n")
        print("所有头衔均为空翻译，已清空本地化文件。")
        return

    # 构建块（blocks），每个块是一个列表，存放该块的所有键
    blocks = []
    i = 0
    n = len(ordered_keys)
    while i < n:
        key = ordered_keys[i]
        prefix = key[0]  # 层级前缀
        if prefix in ('h', 'e', 'k'):
            # 高级头衔：单独一块
            blocks.append([key])
            i += 1
        elif prefix == 'd':
            # d_ 头衔与其后的 c_、b_ 组成一块
            block = [key]
            i += 1
            while i < n and ordered_keys[i][0] in ('c', 'b'):
                block.append(ordered_keys[i])
                i += 1
            blocks.append(block)
        else:
            # 意外情况（c_/b_ 单独出现），作为单独块
            blocks.append([key])
            i += 1

    # 写入文件（严格遵循原格式）
    with open(loc_file_path, 'w', encoding='utf-8-sig') as f:
        f.write("l_simp_chinese:\n")
        for idx, block in enumerate(blocks):
            for key in block:
                val = translations[key]
                f.write(f' {key}:"{val}"\n')
            # 每个块后加空行（最后一个块除外）
            if idx != len(blocks) - 1:
                f.write("\n")

    print(f"已更新本地化文件: {loc_file_path}")
    print(f"共处理 {len(ordered_keys)} 个头衔键（其中空翻译已{'保留' if keep_empty else '删除'}）。")

if __name__ == "__main__":
    # 请替换为你的实际路径
    LANDED = r"TheAshenGoldenAge\\common\\landed_titles\\TAGA_china.txt"
    LOC_FILE = r"TheAshenGoldenAge\\localization\\simp_chinese\\TAGAtitle_l_simp_chinese.yml"

    # 设置 keep_empty 为 False 可删除所有空翻译项
    regenerate_localization(LANDED, LOC_FILE, keep_empty=False)   # 改为 False 则删除空项