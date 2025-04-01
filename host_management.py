import logging
import json
from typing import List, Dict, Optional, Any
from zabbix_api import ZabbixAPI, ZabbixAPIException
from proxy import Proxy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)

class ExportHostManagement:
    def __init__(self):
        try:
            self.zabbix_api = ZabbixAPI()
            logging.info("Zabbix API 登录成功")
        except ZabbixAPIException as e:
            logging.error(f"Zabbix API 登录失败: {str(e)}")
            raise
        self.proxy = Proxy()
        self.proxy_cache = {}

    def get_host_info(
        self, 
        proxy_name: Optional[str] = None,
        tag_name: Optional[str] = None,
        tag_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {
            "output": ["hostid", "host", "name", "status", "proxy_hostid"],
            "selectInterfaces": ["ip", "type"],
            "selectGroups": ["name"],
            "selectParentTemplates": ["name"],
            "selectTriggers": ["description", "status"],
            "selectTags": ["tag", "value"],
        }

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
                tag_value=tag_value
            )
        except ZabbixAPIException as e:
            logging.error(f"主机查询失败: {str(e)}")
            return []

    def _process_hosts(
        self, 
        raw_hosts: List[Dict[str, Any]],
        tag_name: Optional[str],
        tag_value: Optional[str]
    ) -> List[Dict[str, Any]]:
        processed_hosts = []
        for host in raw_hosts:
            if not self._filter_by_tag(host, tag_name, tag_value):
                continue

            interface = host.get("interfaces", [{}])[0]
            ip_address = interface.get("ip", "N/A")
            interface_type = "Agent" if interface.get("type") == "1" else "SNMP" if interface.get("type") == "2" else "N/A"

            triggers = host.get("triggers", [])
            trigger_descriptions = json.dumps(
                {t.get("description", "N/A"): "启用" if t.get("status") == "0" else "禁用" for t in triggers},
                ensure_ascii=False
            )

            groups = [g["name"] for g in host.get("groups", [])]
            templates = [t["name"] for t in host.get("parentTemplates", [])]
            tags = [f"{t['tag']}:{t['value']}" for t in host.get("tags", [])]

            app_id = next((t.get("value", "") for t in host.get("tags", []) if t.get("tag") == "APP_ID"), "")

            proxy_hostid = host.get("proxy_hostid")
            proxy_name_value = self._get_proxy_name(proxy_hostid)

            processed_hosts.append({
                "主机ID": host.get("hostid", "N/A"),
                "主机名称": host.get("host", "N/A").strip(),
                "可见名称": host.get("name", "N/A").strip(),
                "是否启用": "启用" if host.get("status") == "0" else "禁用",
                "IP地址": ip_address,
                "接口类型": interface_type,
                "主机组": groups,
                "关联模板": templates,
                "代理名称": [proxy_name_value] if proxy_name_value != "N/A" else [],
                "触发器描述": trigger_descriptions,
                "标签列表": tags,
                "APP_ID": app_id
            })
        return processed_hosts

    def _get_proxy_name(self, proxy_hostid: Optional[str]) -> str:
        if not proxy_hostid:
            return "N/A"
        if proxy_hostid in self.proxy_cache:
            proxy_info = self.proxy_cache[proxy_hostid]
        else:
            proxy_info = self.proxy.get_proxy_info_by_id(proxy_hostid)
            self.proxy_cache[proxy_hostid] = proxy_info
        return proxy_info.get("host", "N/A") if proxy_info else "N/A"

    def _filter_by_tag(
        self,
        host: Dict[str, Any],
        tag_name: Optional[str],
        tag_value: Optional[str]
    ) -> bool:
        if not tag_name or not tag_value:
            return True
        return any(
            tag.get("tag") == tag_name and tag.get("value") == tag_value
            for tag in host.get("tags", [])
        )

    def get_host_map_by_templates(self, template_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        根据模板名称获取主机信息，返回一个字典，
        key 为主机ID，value 为主机详细信息（字段格式与 get_host_info 保持一致）
        """
        params = {
            "output": ["hostid", "host", "name", "status", "proxy_hostid"],
            "selectInterfaces": ["ip", "type"],
            "selectGroups": ["name"],
            "selectParentTemplates": ["name"],
            "selectTriggers": ["triggerid", "description"],
            "selectTags": ["tag", "value"],
            "filter": {"parentTemplates": template_names},
        }

        try:
            response = self.zabbix_api.call_api("host.get", params)
            hosts = response.get("result", [])
            
            host_map = {}
            for host in hosts:
                host_map[host["hostid"]] = self._process_single_host(host)
            logging.info(f"根据模板获取到 {len(host_map)} 个主机")
            return host_map
        except ZabbixAPIException as e:
            logging.error(f"获取模板关联主机失败: {str(e)}")
            return {}

    def _process_single_host(self, host: Dict[str, Any]) -> Dict[str, Any]:
        interface = host.get("interfaces", [{}])[0]
        ip_address = interface.get("ip", "N/A")
        groups = [g["name"] for g in host.get("groups", [])]
        templates = [t["name"] for t in host.get("parentTemplates", [])]
        tags = [f"{t['tag']}:{t['value']}" for t in host.get("tags", [])]
        triggers = host.get("triggers", [])
        trigger_descriptions = json.dumps(
            {t.get("triggerid", "N/A"): t.get("description", "N/A") for t in triggers},
            ensure_ascii=False
        )
        # 提取 APP_ID 值
        app_id = ""
        for t in host.get("tags", []):
            if t.get("tag") == "APP_ID":
                app_id = t.get("value", "")
                break

        proxy_hostid = host.get("proxy_hostid")
        if proxy_hostid:
            if proxy_hostid in self.proxy_cache:
                proxy_info = self.proxy_cache[proxy_hostid]
            else:
                proxy_info = self.proxy.get_proxy_info_by_id(proxy_hostid)
                self.proxy_cache[proxy_hostid] = proxy_info
            proxy_name_value = proxy_info.get("host", "N/A") if proxy_info else "N/A"
        else:
            proxy_name_value = "N/A"

        return {
            "主机ID": host.get("hostid", "N/A"),
            "主机名称": host.get("host", "N/A"),
            "可见名称": host.get("name", "N/A"),
            "是否启用": "启用" if host.get("status") == "0" else "禁用",
            "IP地址": ip_address,
            "接口类型": "Agent" if interface.get("type") == "1" else "SNMP" if interface.get("type") == "2" else "N/A",
            "主机组": groups,
            "关联模板": templates,
            "代理名称": [proxy_name_value] if proxy_name_value != "N/A" else [],
            "触发器描述": trigger_descriptions,
            "标签列表": tags,
            "APP_ID": app_id
        }
