import logging
import json
from typing import List, Dict, Optional, Any
from zabbix_api import ZabbixAPI, ZabbixAPIException
from proxy import Proxy

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

class ExportHostManagement:
    def __init__(self):
        try:
            self.zabbix_api = ZabbixAPI()
            logging.info("Zabbix API 登录成功")
        except ZabbixAPIException as e:
            logging.error(f"Zabbix API 登录失败: {str(e)}")
            raise
        self.proxy = Proxy()

    def get_host_info(
        self, 
        proxy_name: Optional[str] = None,
        tag_name: Optional[str] = None,
        tag_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取主机信息并支持条件过滤"""
        params = {
            "output": ["hostid", "host", "name", "status"],
            "selectInterfaces": ["ip", "type"],
            "selectGroups": ["name"],
            "selectParentTemplates": ["name"],
            "selectTriggers": ["description"],
            "selectTags": ["tag", "value"],
        }

        # 代理过滤逻辑
        proxy_id = None
        if proxy_name:
            try:
                proxy_info = json.loads(self.proxy.get_proxy_info(proxy_name))
                proxy_id = proxy_info.get("proxy_id")
                if not proxy_id:
                    logging.error(f"代理 '{proxy_name}' 不存在")
                    return []
                params["proxyids"] = [proxy_id]
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"代理信息解析失败: {str(e)}")
                return []

        try:
            response = self.zabbix_api.call_api("host.get", params)
            return self._process_hosts(
                raw_hosts=response.get("result", []), 
                tag_name=tag_name,
                tag_value=tag_value,
                proxy_name=proxy_name  # 直接传递代理名称
            )
        except ZabbixAPIException as e:
            logging.error(f"主机查询失败: {str(e)}")
            return []

    def _process_hosts(
        self, 
        raw_hosts: List[Dict[str, Any]],
        tag_name: Optional[str],
        tag_value: Optional[str],
        proxy_name: Optional[str]  # 新增参数
    ) -> List[Dict[str, Any]]:
        """处理主机数据"""
        processed_hosts = []
        for host in raw_hosts:
            # 标签过滤
            if not self._filter_by_tag(host, tag_name, tag_value):
                continue

            # 处理接口信息
            interface = host.get("interfaces", [{}])[0]
            ip_address = interface.get("ip", "N/A")
            interface_type = "Agent" if interface.get("type") == "1" else "SNMP" if interface.get("type") == "2" else "N/A"

            # 处理触发器
            triggers = host.get("triggers", [{"description": "N/A"}])

            # 构建记录
            for trigger in triggers:
                processed_hosts.append({
                    "主机ID": host.get("hostid", "N/A"),
                    "主机名称": host.get("host", "N/A").strip(),
                    "可见名称": host.get("name", "N/A").strip(),
                    "是否启用": "启用" if host.get("status") == "0" else "禁用",
                    "IP地址": ip_address,
                    "接口类型": interface_type,
                    "主机组": ", ".join([g["name"] for g in host.get("groups", [])]),
                    "关联模板": ", ".join([t["name"] for t in host.get("parentTemplates", [])]),
                    "代理名称": proxy_name or "N/A",  # 直接使用传入的代理名称
                    "触发器描述": trigger.get("description", "N/A"),
                    "标签列表": ", ".join([f"{t['tag']}:{t['value']}" for t in host.get("tags", [])])
                })
        return processed_hosts

    def _filter_by_tag(
        self,
        host: Dict[str, Any],
        tag_name: Optional[str],
        tag_value: Optional[str]
    ) -> bool:
        """标签过滤逻辑"""
        if not tag_name or not tag_value:
            return True
        return any(
            tag.get("tag") == tag_name and tag.get("value") == tag_value
            for tag in host.get("tags", [])
        )