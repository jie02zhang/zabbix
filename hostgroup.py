import json
from zabbix_api import ZabbixAPI

class Hostgroup:
    def __init__(self):
        self.zabbix_api = ZabbixAPI()

    def get_hostgroup_info(self, group_name):
        """获取主机组信息"""
        params = {
            "filter": {"name": group_name},
            "output": ["groupid", "name"]
        }
        response = self.zabbix_api.call_api("hostgroup.get", params)

        if response.get("result"):  # 确保返回了有效的结果
            group_info = {
                "group_id": response["result"][0]["groupid"],
                "name": response["result"][0]["name"]
            }
            return json.dumps(group_info, indent=4)  # 返回格式化的JSON字符串
        else:
            return json.dumps({})  # 返回空的JSON对象

# # 调用示例
# if __name__ == "__main__":
#     hostgroup = Hostgroup()
#     group_name = "硬件_Dell"  # 需要查询的主机组名称
#     group_info_json = hostgroup.get_hostgroup_info(group_name)
#     print(group_info_json)
