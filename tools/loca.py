from loc_mapobjects import LocMapProcessor

def get_all_centers_flat(processor, title_keys):
    """
    对多个头衔键，提取所有省份的最大内切圆圆心（取第一个圆心），
    返回一个扁平的坐标列表（不区分来源头衔）。

    参数:
        processor: LocMapProcessor 实例
        title_keys: 头衔键列表，如 ['b_taga_henan', 'b_taga_shanxi']

    返回:
        list of tuple: 所有坐标的扁平列表，如 [(x1,y1), (x2,y2), (x3,y3)]
    """
    all_coords = []
    for title_key in title_keys:
        try:
            province_ids = processor.get_province_ids(title_key)
        except ValueError as e:
            print(f"错误：头衔 '{title_key}' 不存在，跳过。原因：{e}")
            continue

        if not province_ids:
            print(f"警告：头衔 '{title_key}' 下无省份，跳过。")
            continue

        processor.generate_masks()
        if not processor.masks:
            print(f"警告：头衔 '{title_key}' 无法生成任何掩码，跳过。")
            continue

        circle_results = processor.get_max_inscribed_circle_centers()
        for res in circle_results:
            centers = res.get('centers', [])
            if centers:
                x, y = centers[0]
                all_coords.append((int(x), int(y)))   # 强制转为 Python int

    return all_coords


# ========== 使用示例 ==========
if __name__ == '__main__':
    processor = LocMapProcessor(
        landed_titles_path="TheAshenGoldenAge/common/landed_titles/TAGA_china.txt",
        definition_csv_path="TheAshenGoldenAge/map_data/definition.csv",
        provinces_png_path="TheAshenGoldenAge/map_data/provinces.png"
    )

    title_list = ["b_taga_kaifeng", "b_taga_danyang", "b_taga_chengdu"]
    flat_coords = get_all_centers_flat(processor, title_list)

    print("所有坐标（扁平列表）：")
    print(flat_coords)

    # 验证类型
    if flat_coords:
        print(f"第一个坐标类型：{type(flat_coords[0][0])}")  # 输出 <class 'int'>