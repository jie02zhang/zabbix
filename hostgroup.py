import json
from zabbix_api import ZabbixAPI

class Hostgroup:
    def __init__(self):
        self.zabbix_api = ZabbixAPI()

    def get_hostgroup_info(self, group_name):
        """获取主机组信息（返回支持中文的 JSON 字符串）"""
        params = {
            "filter": {"name": group_name},
            "output": ["groupid", "name"]
        }
        response = self.zabbix_api.call_api("hostgroup.get", params)
        if response.get("result"):
            group_info = {
                "group_id": response["result"][0]["groupid"],
                "name": response["result"][0]["name"]
            }
            return json.dumps(group_info, indent=4, ensure_ascii=False)
        else:
            return json.dumps({}, ensure_ascii=False)

    def massupdate(self, params):
        """
        将指定主机添加到指定 Zabbix 主机组中。
        params: {
            "hostname": "my-host-name",
            "group": "TargetGroup"
        }
        """
        hostname = params.get("hostname")
        group_name = params.get("group")

        # 1. 获取主机组 ID
        group_resp = self.zabbix_api.call_api("hostgroup.get", {
            "filter": {"name": [group_name]},
            "output": ["groupid"]
        })
        groupid = group_resp["result"][0]["groupid"]  # :contentReference[oaicite:3]{index=3}

        # 2. 获取主机 ID（通过主机名）
        host_resp = self.zabbix_api.call_api("host.get", {
            "filter": {"host": [hostname]},
            "output": ["hostid"]
        })
        hostid = host_resp["result"][0]["hostid"]  # :contentReference[oaicite:4]{index=4}

        # 3. 调用 host.massadd，将主机添加到主机组中
        add_resp = self.zabbix_api.call_api("host.massadd", {
            "hosts": [{"hostid": hostid}],
            "groups": [{"groupid": groupid}]
        })
        return add_resp  # :contentReference[oaicite:5]{index=5}
