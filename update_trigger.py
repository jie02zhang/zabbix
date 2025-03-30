import logging
import pandas as pd
from typing import List, Dict, Optional, Any
from zabbix_api import ZabbixAPI, ZabbixAPIException
from host_management import ExportHostManagement

# 设置日志格式
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EXCEL_FILE_PATH = "C:\\software\\监控主机.xlsx"

class UpdateTrigger:
    def __init__(self):
        """初始化 Zabbix API 连接"""
        try:
            self.zabbix_api = ZabbixAPI()
            logging.info("✅ Zabbix API 登录成功")
        except ZabbixAPIException as e:
            logging.error(f"❌ Zabbix API 登录失败: {str(e)}")
            raise

        self.host_mgmt = ExportHostManagement()

    def read_excel(self) -> List[Dict[str, str]]:
        """读取 Excel 文件"""
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
        """根据 APP_ID 或 IP 地址筛选主机"""
        all_hosts = self.host_mgmt.get_host_info()
        return [
            host for host in all_hosts
            if (not app_id or host.get("APP_ID") == app_id) and (not ip_address or host.get("IP地址") == ip_address)
        ]

    def get_trigger_by_name(self, host_id: str, trigger_name: str) -> Optional[str]:
        """获取主机上名称包含 trigger_name 的触发器 ID"""
        try:
            triggers = self.zabbix_api.call_api("trigger.get", {
                "hostids": host_id,
                "output": ["triggerid", "description"],
                "search": {"description": trigger_name}
            }).get("result", [])
            return triggers[0]["triggerid"] if triggers else None
        except ZabbixAPIException as e:
            return None

    def get_trigger_item_value(self, trigger_id: str) -> Optional[Any]:
        """获取触发器对应监控项的最新值"""
        try:
            items = self.zabbix_api.call_api("item.get", {
                "triggerids": trigger_id,
                "output": ["itemid", "value_type"]
            }).get("result", [])

            if not items:
                return None  # 无监控项

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
        """判断是否需要更新触发器"""
        try:
            if condition.startswith((">", "<", "=")):
                return eval(f"{float(trigger_value)} {condition}")  # 安全执行条件判断
            return condition in str(trigger_value)  # 文本匹配
        except ValueError:
            return False

    def update_trigger_status(self, trigger_id: str, enable: bool) -> bool:
        """启用或禁用触发器"""
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
        """读取 Excel 并批量更新触发器"""
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
                continue  # 不打印未找到主机的警告

            total_hosts += len(matching_hosts)

            for host in matching_hosts:
                trigger_id = self.get_trigger_by_name(host["主机ID"], trigger_name)
                if not trigger_id:
                    continue  # 不打印未找到触发器的警告

                total_triggers += 1
                trigger_value = self.get_trigger_item_value(trigger_id)
                if trigger_value is None:
                    continue

                if self.should_update_trigger(trigger_value, condition):
                    if self.update_trigger_status(trigger_id, enable):
                        updated_triggers += 1

        # **最终日志输出**
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
