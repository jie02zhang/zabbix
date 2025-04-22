import pandas as pd

# 定义输入和输出文件路径
input_file = r"C:\software\监控数据.xlsx"
output_file = r"C:\software\处理后监控数据.xlsx"

# 读取 Excel 数据
df = pd.read_excel(input_file)

# 用于按 (IP地址, APP_ID) 分组，存储各监控项信息
groups = {}

for index, row in df.iterrows():
    ip = str(row['IP地址']).strip()
    app_id = str(row['APP_ID']).strip()
    proxy = str(row['代理名称']).strip()
    trigger = str(row['触发器描述']).strip()
    
    key = (ip, app_id)
    if key not in groups:
        groups[key] = {
            'ping': None,      # 主机不可达监控，只保存一次IP
            'disk': None,      # 主机磁盘最大使用率监控，只保存一次IP
            'shared': [],      # 主机挂载的共享盘不可达监控（可能多行）
            'process': [],     # 关键进程状态监控（可能多行）
            'port': []         # 关键端口状态监控（可能多行）
        }
    
    # 主机不可达监控：包含 "Ping"
    if "Ping" in trigger and groups[key]['ping'] is None:
        groups[key]['ping'] = ip
        
    # 主机磁盘最大使用率监控：包含 "磁盘"
    if "磁盘" in trigger and groups[key]['disk'] is None:
        groups[key]['disk'] = ip
        
    # 主机挂载的共享盘不可达监控：包含 "共享磁盘"
    if "共享磁盘" in trigger:
        groups[key]['shared'].append(f"{ip} | {trigger}")
        
    # 关键进程状态监控：包含 "进程" 或 "服务中断"
    if "进程" in trigger or "服务中断" in trigger:
        groups[key]['process'].append(f"{ip} | {trigger}")
        
    # 关键端口状态监控（仅支持TCP）：包含 "端口" 或 "监听"
    if "端口" in trigger or "监听" in trigger:
        groups[key]['port'].append(f"{proxy} | {ip} | {trigger}")

# 构造输出行
output_rows = []

# 对于每个 (IP, APP_ID) 组合，确定多行输出的行数
for (ip, app_id), info in groups.items():
    # 多行输出的行数取决于共享盘、进程、端口中数量的最大值，至少1行
    n_rows = max(1, len(info['shared']), len(info['process']), len(info['port']))
    
    for i in range(n_rows):
        row_data = {
            'IP地址': ip,
            'APP_ID': app_id,
            # 只有第一行填写单值监控数据，其它行为空
            '主机不可达监控': info['ping'] if i == 0 else "",
            '主机磁盘最大使用率监控': info['disk'] if i == 0 else "",
            # 对于可能多行的项，若索引超出列表则留空
            '主机挂载的共享盘不可达监控': info['shared'][i] if i < len(info['shared']) else "",
            '关键进程状态监控': info['process'][i] if i < len(info['process']) else "",
            '关键端口状态监控': info['port'][i] if i < len(info['port']) else ""
        }
        output_rows.append(row_data)

# 构造 DataFrame，指定列的顺序
output_df = pd.DataFrame(output_rows, columns=[
    'IP地址', 'APP_ID', '主机不可达监控', '主机磁盘最大使用率监控',
    '主机挂载的共享盘不可达监控', '关键进程状态监控', '关键端口状态监控'
])

# 写出到 Excel 文件
output_df.to_excel(output_file, index=False)

print(f"处理完成，生成文件：{output_file}")
