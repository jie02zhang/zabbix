import logging
import pandas as pd
from typing import List, Dict, Optional, Any
from zabbix_api import ZabbixAPI, ZabbixAPIException
from host_management import ExportHostManagement

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EXCEL_FILE_PATH = "C:\\software\\监控主机.xlsx"

class UpdateTrigger:
    def __init__(self):
        try:
            self.zabbix_api = ZabbixAPI()
            logging.info("✅ Zabbix API 登录成功")
        except ZabbixAPIException as e:
            logging.error(f"❌ Zabbix API 登录失败: {str(e)}")
            raise
        self.host_mgmt = ExportHostManagement()

    def read_excel(self) -> List[Dict[str, str]]:
        try:
            df = pd.read_excel(EXCEL_FILE_PATH, dtype=str)
            df.fillna("", inplace=True)
            if not {"APP_ID", "IP地址"}.issubset(df.columns):
                logging.error("❌ Excel 缺少 'APP_ID' 或 'IP地址' 列")
                return []
            return df.to_dict(orient="records")
        except Exception as e:
            logging.error(f"❌ 读取 Excel 失败: {str(e)}")
            return []

    def get_matching_hosts(self, app_id: Optional[str], ip_address: Optional[str]) -> List[Dict[str, str]]:
        all_hosts = self.host_mgmt.get_host_info()
        return [
            host for host in all_hosts
            if (not app_id or host.get("APP_ID") == app_id) and (not ip_address or host.get("IP地址") == ip_address)
        ]

    def get_triggers_by_name(self, host_id: str, trigger_name: str) -> List[Dict[str, str]]:
        try:
            triggers = self.zabbix_api.call_api("trigger.get", {
                "hostids": host_id,
                "output": ["triggerid", "description"],
                "search": {"description": trigger_name}
            }).get("result", [])
            return triggers
        except ZabbixAPIException:
            return []

    def get_trigger_item_value(self, trigger_id: str) -> Optional[Any]:
        try:
            items = self.zabbix_api.call_api("item.get", {
                "triggerids": trigger_id,
                "output": ["itemid", "value_type"]
            }).get("result", [])

            if not items:
                return None

            item_id = items[0]["itemid"]
            value_type = int(items[0]["value_type"])
            history_type = {0: "0", 1: "1", 3: "3"}.get(value_type, "0")

            history = self.zabbix_api.call_api("history.get", {
                "itemids": item_id,
                "history": history_type,
                "sortfield": "clock",
                "sortorder": "DESC",
                "limit": 1
            }).get("result", [])

            return history[0]["value"] if history else None
        except ZabbixAPIException:
            return None

    def should_update_trigger(self, trigger_value: Any, condition: str) -> bool:
        try:
            if condition.startswith((">", "<", "=")):
                return eval(f"{float(trigger_value)} {condition}")
            return condition in str(trigger_value)
        except (ValueError, TypeError):
            return False

    def update_trigger_status(self, trigger_id: str, enable: bool) -> bool:
        try:
            status = "0" if enable else "1"
            response = self.zabbix_api.call_api("trigger.update", {
                "triggerid": trigger_id,
                "status": status
            })
            return "result" in response
        except ZabbixAPIException:
            return False

    def process_excel_triggers(self, trigger_name: str, condition: str, enable: bool):
        data = self.read_excel()
        if not data:
            logging.error("❌ Excel 数据为空，无法执行更新")
            return

        total_hosts = 0
        total_triggers = 0
        updated_triggers = 0

        for row in data:
            app_id, ip_address = row.get("APP_ID", "").strip(), row.get("IP地址", "").strip()
            matching_hosts = self.get_matching_hosts(app_id, ip_address)

            if not matching_hosts:
                continue

            total_hosts += len(matching_hosts)

            for host in matching_hosts:
                host_id = host.get("主机ID")
                host_name = host.get("主机名称", "未知主机")
                triggers = self.get_triggers_by_name(host_id, trigger_name)

                if not triggers:
                    continue

                for trig in triggers:
                    trigger_id = trig["triggerid"]
                    description = trig["description"]

                    total_triggers += 1
                    trigger_value = self.get_trigger_item_value(trigger_id)

                    if trigger_value is None:
                        continue

                    if self.should_update_trigger(trigger_value, condition):
                        if self.update_trigger_status(trigger_id, enable):
                            updated_triggers += 1
                            logging.info(f"🔄 主机 [{host_name}] 触发器 [{description}] 状态已更新")

        logging.info("✅ 批量触发器更新完成")
        logging.info(f"📊 处理主机数: {total_hosts}")
        logging.info(f"📌 匹配触发器数: {total_triggers}")
        logging.info(f"🔄 更新触发器数: {updated_triggers}")

if __name__ == "__main__":
    updater = UpdateTrigger()
    TRIGGER_NAME = "UNDO"
    CONDITION = ">0"  # 监控项值 > 80 才执行
    ENABLE_TRIGGER = False  # True: 启用, False: 禁用

    updater.process_excel_triggers(TRIGGER_NAME, CONDITION, ENABLE_TRIGGER)
