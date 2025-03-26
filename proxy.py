import json
from zabbix_api import ZabbixAPI

class Proxy:
    def __init__(self):
        """初始化 Zabbix API 连接"""
        self.zabbix_api = ZabbixAPI()

    def get_proxy_info(self, agent_name: str) -> str:
        """
        获取指定代理服务器的信息（通过代理名称查询）。
        """
        try:
            params = {
                "filter": {"host": agent_name},
                "output": ["proxyid", "host", "proxy_address"]
            }
            response = self.zabbix_api.call_api("proxy.get", params)
            if response.get("result"):
                proxy_info = {
                    "agent_name": agent_name,
                    "proxy_id": response["result"][0]["proxyid"],
                    "host": response["result"][0]["host"],
                    "proxy_address": response["result"][0]["proxy_address"]
                }
                return json.dumps(proxy_info, indent=4)
            else:
                return json.dumps({}, indent=4)
        except Exception as e:
            print(f"Error retrieving proxy info: {e}")
            return json.dumps({}, indent=4)

    def get_proxy_info_by_id(self, proxy_id: str) -> dict:
        """
        根据 proxyid 获取代理信息，返回字典格式数据。
        """
        try:
            params = {
                "filter": {"proxyid": proxy_id},
                "output": ["proxyid", "host", "proxy_address"]
            }
            response = self.zabbix_api.call_api("proxy.get", params)
            if response.get("result"):
                return response["result"][0]
            else:
                return {}
        except Exception as e:
            print(f"Error retrieving proxy info by id: {e}")
            return {}
