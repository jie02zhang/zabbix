import json
import pandas as pd
import requests
from zabbix_api import ZabbixAPI
from hostgroup import Hostgroup
from template import Template
from proxy import Proxy

# 接口类型常量
INTERFACE_AGENT = 1
INTERFACE_SNMP = 2

CONFIG = {
    "excel_columns": {
        "host_ip": "IP地址",
        "proxy_name": "Proxy代理主机",
        "brand": "品牌",
        "model": "型号",
        "system_type": "系统类型"
    },
    "interface_ports": {
        "agent": "10050",
        "snmp": "161"
    },
    "snmp_community": "{$SNMP_COMMUNITY}",
}


class HostManagement:
    def __init__(self):
        """初始化 Zabbix API 连接"""
        self.zabbix_api = ZabbixAPI()
        self.auth = self.zabbix_api.login()  # 确保 auth 被存储

    def create_host(self, hostname, ip, group_ids, template_ids, host_type, proxy_id=None):
        """创建 Zabbix 主机"""
        interface = {
            "type": INTERFACE_AGENT if host_type == "agent" else INTERFACE_SNMP,
            "main": 1,
            "useip": 1,
            "ip": ip,
            "dns": "",
            "port": CONFIG["interface_ports"][host_type]
        }
        if host_type == "snmp":
            interface["details"] = {
                "version": 2,
                "bulk": 1,
                "community": CONFIG["snmp_community"]
            }

        params = {
            "host": ip,
            "name": hostname,
            "interfaces": [interface],
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            "status": 0
        }
        if proxy_id:
            params["proxy_hostid"] = proxy_id  # 绑定代理 ID

        return self.zabbix_api.call_api("host.create", params)

    def get_host_info(self, host_ids):
        """获取主机信息"""
        params = {
            "output": ["hostid", "name"],
            "hostids": host_ids
        }
        return self.zabbix_api.call_api("host.get", params)


def read_host_info_from_excel(file_path):
    """读取 Excel 数据"""
    try:
        df = pd.read_excel(file_path)
        required_cols = [CONFIG["excel_columns"][col] for col in ["host_ip", "proxy_name", "system_type", "brand"]]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {', '.join(missing)}")
        return df.where(pd.notnull(df), None)  # 转换 NaN 为 None
    except Exception as e:
        raise RuntimeError(f"读取 Excel 失败: {e}")


def create_hosts(file_path, group_name, snmp_template, agent_template):
    """批量创建主机"""
    try:
        host_management = HostManagement()
    except Exception as e:
        return [{"status": "error", "message": f"API 登录失败: {e}"}]

    try:
        # 获取主机组 ID
        hostgroup = Hostgroup()
        group_info = json.loads(hostgroup.get_hostgroup_info(group_name))
        group_id = group_info["group_id"]

        # 获取模板 ID
        template = Template()
        snmp_info = json.loads(template.get_template_info(snmp_template))
        snmp_tid = snmp_info["template_id"]
        agent_info = json.loads(template.get_template_info(agent_template))
        agent_tid = agent_info["template_id"]
    except Exception as e:
        return [{"status": "error", "message": f"配置验证失败: {e}"}]

    try:
        df = read_host_info_from_excel(file_path)
    except Exception as e:
        return [{"status": "error", "message": str(e)}]

    results = []
    for index, row in df.iterrows():
        host_ip = row.get(CONFIG["excel_columns"]["host_ip"], "未知主机")
        try:
            sys_type_raw = row[CONFIG["excel_columns"]["system_type"]]
            sys_type = sys_type_raw.strip().lower() if sys_type_raw else None
            if sys_type not in ["snmp", "agent"]:
                raise ValueError(f"无效监控类型: {sys_type_raw}")

            template_id = snmp_tid if sys_type == "snmp" else agent_tid

            proxy_name = row.get(CONFIG["excel_columns"]["proxy_name"], None)
            proxy_id = None
            if proxy_name:
                proxy = Proxy()
                proxy_info = json.loads(proxy.get_proxy_info(proxy_name))
                if "proxy_id" not in proxy_info:
                    raise ValueError(f"代理 {proxy_name} 不存在")
                proxy_id = proxy_info["proxy_id"]

            brand = row.get(CONFIG["excel_columns"]["brand"], "Unknown") or "Unknown"
            model = row.get(CONFIG["excel_columns"]["model"], "") or ""
            visible_name = f"{host_ip}_{brand}_{model}" if model else f"{host_ip}_{brand}"

            resp = host_management.create_host(
                hostname=visible_name,
                ip=host_ip,
                group_ids=[group_id],
                template_ids=[template_id],
                host_type=sys_type,
                proxy_id=proxy_id
            )

            if "error" in resp:
                error_msg = f"{resp['error']['code']}: {resp['error']['data']}"
                results.append({"status": "error", "host": host_ip, "message": error_msg})
            else:
                results.append({"status": "success", "host": host_ip, "hostid": resp["result"]["hostids"][0]})
        except Exception as e:
            results.append({"status": "error", "host": host_ip, "message": f"第 {index+2} 行处理失败: {str(e)}"})
    
    return results


if __name__ == "__main__":
    results = create_hosts(
        file_path="C:\\software\\host_info-20240325.xlsx",
        group_name="Poly话机",
        snmp_template="Template_Envision_SNMPGeneral",
        agent_template="Envision_Temp_ICMPPing_Baseline"
    )

    print("\n创建结果:")
    for res in results:
        status_icon = "✅" if res.get("status") == "success" else "❌"
        host = res.get('host', '未知主机')
        message = res.get('message', '创建成功')
        print(f"{status_icon} {host}: {message}")