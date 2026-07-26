from collections import Counter
from utils.get_title import TAGA_Parser 

def check_all_level_duplicates(file_path: str):
    """
    利用 TAGA_Parser 检查领地文件中所有层级的键/ID 是否重复（仅同层级内比较）
    """
    parser = TAGA_Parser(file_path)

    # 定义要检查的层级：显示名称 -> get_items 的参数
    levels = {
        "帝国 (Empires)": "e",
        "王国 (Kingdoms)": "k",
        "公国 (Duchies)": "d",
        "伯爵领 (Counties)": "c",
        "男爵领 (Baronies)": "b",
        "省份 (Provinces)": "province",
    }

    print(f"正在检查文件: {file_path}\n" + "=" * 50)
    has_any_duplicate = False

    for level_name, level_type in levels.items():
        try:
            # 获取该层级的所有条目（字符串或整数）
            items = parser.get_items(level_type)
            
            # 使用 Counter 统计每个条目出现的次数
            counter = Counter(items)
            
            # 筛选出出现次数 > 1 的重复项
            duplicates = {item: count for item, count in counter.items() if count > 1}

            if duplicates:
                has_any_duplicate = True
                print(f"⚠️  【{level_name}】发现重复项 (共 {len(duplicates)} 种重复):")
                for item, count in duplicates.items():
                    # 若为省份 ID，显示为数字；头衔显示为字符串
                    print(f"    - {item} 出现了 {count} 次")
            else:
                print(f"✅ 【{level_name}】无重复 (共 {len(items)} 个条目)")

        except ValueError as e:
            print(f"❌ 【{level_name}】解析失败: {e}")
        except Exception as e:
            print(f"❌ 【{level_name}】未知错误: {e}")

    if not has_any_duplicate:
        print("\n🎉 恭喜！所有层级的头衔和省份均无重复！")
    else:
        print("\n⚠️  请检查上述重复项，重复的头衔键或省份 ID 可能导致游戏识别异常。")

if __name__ == "__main__":
    # 请替换为你实际的领地文件路径
    FILE_PATH = r"TheAshenGoldenAge\\common\\landed_titles\\TAGA_china.txt"
    check_all_level_duplicates(FILE_PATH)