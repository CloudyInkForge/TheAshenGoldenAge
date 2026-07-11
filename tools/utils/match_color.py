class CSVLookup:
    """根据CSV第一列查询第二、三、四列，返回整数元组"""

    def __init__(self, csv_path: str, encoding: str = 'utf-8'):
        """
        初始化并加载CSV文件
        :param csv_path: CSV文件路径（作为实例变量）
        :param encoding: 文件编码，默认utf-8
        """
        self.csv_path = csv_path
        self.encoding = encoding
        self.data = {}
        self._load()

    def _load(self):
        """加载CSV文件，构建键到元组的映射"""
        try:
            with open(self.csv_path, 'r', encoding=self.encoding) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(';')
                    if len(parts) < 4:
                        # 若字段不足，跳过该行（可自行决定是否警告）
                        continue
                    key = parts[0].strip()
                    try:
                        # 取第2、3、4列（索引1,2,3）转为整数
                        value = (int(parts[1]), int(parts[2]), int(parts[3]))
                    except ValueError:
                        # 转换失败则跳过
                        continue
                    self.data[key] = value
        except FileNotFoundError:
            print(f"错误：文件 '{self.csv_path}' 未找到，数据将为空。")
            self.data = {}
        except Exception as e:
            print(f"加载CSV时发生异常: {e}")
            self.data = {}

    def get(self, key):
        """
        根据键查询对应的元组
        :param key: 第一列的值（字符串）
        :return: 若存在则返回 (int, int, int)，否则返回 None
        """
        return self.data.get(key)

    def __getitem__(self, key):
        """支持 obj[key] 语法，若键不存在则抛出 KeyError"""
        return self.data[key]

    def __contains__(self, key):
        """支持 'key in obj' 判断"""
        return key in self.data
    
'''
lookup = CSVLookup('TheAshenGoldenAge/map_data/definition.csv')

# 查询第一列为 '841' 的行
result = lookup.get('9768')
print(result)          # 输出: (42, 180, 148)
'''