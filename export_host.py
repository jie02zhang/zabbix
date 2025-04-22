import logging
import argparse
import pandas as pd
from typing import List, Dict
from host_management import ExportHostManagement

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", encoding='utf-8')

class ExportHostData:
    def __init__(self):
        self.manager = ExportHostManagement()

    def export_to_excel(self, data: List[Dict], output_path: str) -> None:
        """导出数据到Excel，每个触发器单独一行，其它信息保持不变"""
        if not data:
            logging.warning("没有符合条件的主机信息")
            return

        # 确保列顺序一致
        columns = [
            "主机ID", "主机名称", "可见名称", "是否启用",
            "IP地址", "接口类型", "主机组", "关联模板",
            "代理名称", "触发器描述", "标签列表", "APP_ID"
        ]

        # 处理每个主机数据，将“触发器描述”字段拆分成多行
        processed_data = []
        for record in data:
            triggers = record.get("触发器描述")
            # 如果触发器描述存在且为列表或以逗号分隔的字符串，则拆分
            if triggers:
                if isinstance(triggers, list):
                    trigger_list = triggers
                elif isinstance(triggers, str) and ',' in triggers:
                    trigger_list = [item.strip() for item in triggers.split(',') if item.strip()]
                else:
                    trigger_list = [triggers]
                # 对于每个触发器，复制一份记录，仅更改触发器描述
                for trig in trigger_list:
                    new_record = record.copy()
                    new_record["触发器描述"] = trig
                    processed_data.append(new_record)
            else:
                processed_data.append(record)

        try:
            df = pd.DataFrame(processed_data, columns=columns)
            df.to_excel(output_path, index=False)
            logging.info(f"成功导出 {len(processed_data)} 条数据到: {output_path}")
        except Exception as e:
            logging.error(f"导出Excel失败: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zabbix主机数据导出工具")
    parser.add_argument("--output", default=r"C:\software\应用系统监控管理-Zabbix-03.xlsx",
                        help="输出文件路径（默认：C:\\software\\应用系统监控管理-Zabbix-03.xlsx）")
    parser.add_argument("--proxy", help="按代理名称过滤（示例：Proxy_JY_RD001）")
    parser.add_argument("--tag-name", help="标签名称（需配合--tag-value使用）")
    parser.add_argument("--tag-value", help="标签值（需配合--tag-name使用）")

    args = parser.parse_args()

    exporter = ExportHostData()
    host_data = exporter.manager.get_host_info(
        proxy_name=args.proxy,
        tag_name=args.tag_name,
        tag_value=args.tag_value
    )
    exporter.export_to_excel(host_data, args.output)
