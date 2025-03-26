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
        # 增加代理信息缓存，避免重复调用接口
        self.proxy_cache = {}

    def get_host_info(
        self, 
        proxy_name: Optional[str] = None,
        tag_name: Optional[str] = None,
        tag_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取主机信息，支持通过代理名称与主机 tag 信息进行过滤：
            --proxy-name="xxx" 
            --tag-name="APP_ID" --tag-value="A02205"
        返回字段包括：
            主机ID、主机名称、可见名称、是否启用、IP地址、接口类型、
            主机组、关联模板、代理名称、触发器描述、标签列表、APP_ID
        """
        params = {
            "output": ["hostid", "host", "name", "status", "proxy_hostid"],
            "selectInterfaces": ["ip", "type"],
            "selectGroups": ["name"],
            "selectParentTemplates": ["name"],
            "selectTriggers": ["triggerid", "description"],
            "selectTags": ["tag", "value"],
        }

        # 如果传入了 proxy_name，则先查询代理信息获取 proxy_id，再过滤主机
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
            interface_type = (
                "Agent" if interface.get("type") == "1"
                else "SNMP" if interface.get("type") == "2"
                else "N/A"
            )

            triggers = host.get("triggers", [])
            # 触发器描述以 JSON 格式返回，确保中文不被转义
            trigger_descriptions = json.dumps(
                {t.get("triggerid", "N/A"): t.get("description", "N/A") for t in triggers},
                ensure_ascii=False
            )

            groups = [g["name"] for g in host.get("groups", [])]
            templates = [t["name"] for t in host.get("parentTemplates", [])]
            tags = [f"{t['tag']}:{t['value']}" for t in host.get("tags", [])]

            # 从 tags 中提取 APP_ID 值
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

    def _filter_by_tag(
        self,
        host: Dict[str, Any],
        tag_name: Optional[str],
        tag_value: Optional[str]
    ) -> bool:
        """
        当 tag_name 与 tag_value 均存在时，
        检查主机的 tags 列表是否存在匹配的记录；
        如果任一参数未提供，则不过滤
        """
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
