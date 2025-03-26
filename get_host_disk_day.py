import pandas as pd
import re
from datetime import datetime
import logging
from tqdm import tqdm
from zabbix_api import ZabbixAPI, ZabbixAPIException
from host_management import ExportHostManagement

# 设置全局日志格式和级别（INFO 及以上）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# 过滤掉 urllib3 和 zabbix_api 模块的 DEBUG 日志
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("zabbix_api").setLevel(logging.WARNING)

class ExportDiskUsed:
    def __init__(self):
        """初始化 Zabbix API 连接"""
        try:
            self.zabbix_api = ZabbixAPI()
            logging.info("Zabbix API 登录成功")
        except ZabbixAPIException as e:
            logging.error(f"Zabbix API 登录失败: {str(e)}")
            raise

    def get_daily_disk_peak(self, start_date_str, end_date_str, output_file):
        """
        获取每日磁盘使用峰值报告

        参数:
            start_date_str: 开始日期 (格式: YYYYMMDD)
            end_date_str: 结束日期 (格式: YYYYMMDD)
            output_file: 输出 Excel 文件路径
        """
        try:
            start_date = datetime.strptime(start_date_str, "%Y%m%d")
            # 将结束日期拼接时间字符串，确保包含当天全部数据
            end_date = datetime.strptime(end_date_str + " 23:59:59", "%Y%m%d %H:%M:%S")
            start_ts, end_ts = int(start_date.timestamp()), int(end_date.timestamp())
        except ValueError as e:
            logging.error(f"日期格式错误: {e}")
            return False

        templates = [
            "Envision_Temp_ZBX_Windows_Baseline",
            "Envision_Temp_ZBX_Linux_Baseline",
            "Envision_Temp_ZBX_Windows_Baseline_active"
        ]
        
        # 通过模板查找所有主机
        host_map = self.get_all_hosts_by_templates(templates)
        logging.info(f"根据模板获取到 {len(host_map)} 台主机，开始获取磁盘监控项...")

        # 遍历每个主机，通过 hostid 获取监控项数据
        for host_id, host_info in tqdm(host_map.items(), desc="获取监控项"):
            try:
                params = {
                    "hostids": host_id,
                    "search": {"key_": "vfs.fs.size"},
                    "output": ["itemid", "key_", "name"]
                }
                items_response = self.zabbix_api.call_api("item.get", params)
                items = items_response.get("result", [])
                for item in items:
                    key_val = item.get('key_')
                    match = re.match(r'vfs\.fs\.size\[(.*?),(pused|total)\]', key_val)
                    if match:
                        mount_point, metric = match.groups()
                        if metric == "pused":
                            host_info['items'][mount_point] = item['itemid']
                        elif metric == "total":
                            host_info['total'][mount_point] = item['itemid']
            except Exception as e:
                logging.error(f"获取主机 {host_info['ip']} 监控项失败: {e}")

        results = []
        total_items = sum(len(h['items']) for h in host_map.values())
        logging.info(f"开始获取历史数据，共 {total_items} 项监控项...")

        with tqdm(total=total_items, desc="处理进度") as pbar:
            for host_id, host_info in host_map.items():
                for mount_point, item_id in host_info['items'].items():
                    pbar.update(1)
                    pbar.set_postfix_str(f"当前主机: {host_info['ip']}")
                    try:
                        # 获取监控项历史数据（磁盘使用率）
                        params_history = {
                            "itemids": item_id,
                            "time_from": start_ts,
                            "time_till": end_ts,
                            "output": ['clock', 'value'],
                            "history": 0,
                            "sortfield": 'clock',
                            "sortorder": 'ASC'
                        }
                        history_response = self.zabbix_api.call_api("history.get", params_history)
                        history = history_response.get("result", [])
                        
                        total_size = None
                        # 如果存在对应的磁盘总大小监控项，获取最新记录（假定历史类型为 3）
                        if mount_point in host_info['total']:
                            params_total = {
                                "itemids": host_info['total'][mount_point],
                                "time_from": start_ts,
                                "time_till": end_ts,
                                "output": ['clock', 'value'],
                                "history": 3,
                                "sortfield": 'clock',
                                "sortorder": 'DESC',
                                "limit": 1
                            }
                            total_history_response = self.zabbix_api.call_api("history.get", params_total)
                            total_history = total_history_response.get("result", [])
                            if total_history:
                                total_size = round(float(total_history[0]['value']) / (1024 ** 3), 2)
                    except Exception as e:
                        logging.error(f"获取 {mount_point} 历史数据失败: {e}")
                        continue
                    
                    if not history:
                        continue
                    
                    # 处理历史数据，计算每日最大使用率
                    df = pd.DataFrame(history)
                    df['clock'] = pd.to_numeric(df['clock'])
                    df['value'] = pd.to_numeric(df['value'])
                    df['date'] = pd.to_datetime(df['clock'], unit='s').dt.strftime('%Y%m%d')
                    daily_max = df.groupby('date')['value'].max().reset_index()
                    
                    for _, row in daily_max.iterrows():
                        results.append({
                            "IP地址": host_info['ip'],
                            "日期": row['date'],
                            "目录名称": mount_point,
                            "磁盘使用率峰值(%)": round(row['value'], 2),
                            "目录磁盘大小(GB)": total_size if total_size is not None else "N/A"
                        })
        
        if results:
            try:
                df_result = pd.DataFrame(results).sort_values(by=['IP地址', '日期', '目录名称'])
                df_result.drop_duplicates(inplace=True)
                df_result.to_excel(output_file, index=False)
                logging.info(f"报告生成成功，共 {len(df_result)} 条记录，保存至: {output_file}")
                return True
            except Exception as e:
                logging.error(f"生成报告失败: {e}")
                return False
        else:
            logging.warning("未找到符合条件的监控数据")
            return False

    def get_all_hosts_by_templates(self, templates: list) -> dict:
        """
        通过模板名称获取所有主机信息，返回一个字典，
        键为 hostid，值为包含 IP 地址、items 和 total 字段的字典
        """
        host_map = {}
        try:
            ehm = ExportHostManagement()
            hosts = ehm.get_host_map_by_templates(templates)
            for host_id, host_info in hosts.items():
                host_map[host_id] = {
                    'ip': host_info.get("IP地址", "N/A"),
                    'items': {},
                    'total': {}
                }
        except Exception as e:
            logging.error(f"获取模板主机失败: {e}")
        return host_map

if __name__ == "__main__":
    try:
        exporter = ExportDiskUsed()
        success = exporter.get_daily_disk_peak(
            start_date_str="20250323",
            end_date_str="20250324",
            output_file=r"C:\software\daily_disk_peak.xlsx"
        )
        print("操作成功完成" if success else "操作未完成，请检查日志")
    except Exception as e:
        logging.error(f"程序初始化失败: {e}")
