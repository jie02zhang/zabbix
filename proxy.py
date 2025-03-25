import json
from zabbix_api import ZabbixAPI

class Proxy:
    def __init__(self):
        """初始化 Zabbix API 连接"""
        self.zabbix_api = ZabbixAPI()

    def get_proxy_info(self, agent_name):
        """
        获取指定代理服务器的信息

        Args:
            agent_name (str): 代理服务器名称

        Returns:
            str: 包含代理服务器信息的 JSON 格式字符串
        """
        try:
            params = {
                "filter": {"host": agent_name},  
                "output": ["proxyid", "host"]
            }
            response = self.zabbix_api.call_api("proxy.get", params)

            if response.get("result"):
                proxy_info = {
                    "agent_name": agent_name,
                    "proxy_id": response["result"][0]["proxyid"],
                    "host": response["result"][0]["host"]
                }
                return json.dumps(proxy_info, indent=4)  # 美化输出 JSON
            else:
                return json.dumps({}, indent=4)  # 返回空 JSON
        except Exception as e:
            print(f"Error retrieving proxy info: {e}")
            return json.dumps({}, indent=4)  # 出错时返回空 JSON

# # 调用示例
# if __name__ == "__main__":
#     proxy = Proxy()
#     agent_name = "Proxy_JY_RD001"  # 需要查询的代理名称
#     proxy_info_json = proxy.get_proxy_info(agent_name)
#     print(f"Proxy Info: {proxy_info_json}")
