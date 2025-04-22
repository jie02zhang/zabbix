import json
import traceback
from zabbix_api import ZabbixAPI

class Templateid:
    def __init__(self):
        self.zabbix_api = ZabbixAPI()

def get_template_info(template_name, zapi=None):
    """
    根据模板名称查询模板信息
    """
    self.zabbix_api = ZabbixAPI()
        
        templates = zapi.template.get(filter={"host": template_name}, output=["templateid", "name"])

        if templates:
            template_info = {
                "template_id": templates[0]["templateid"],
                "name": templates[0]["name"]
            }
            return json.dumps(template_info)
        else:
            return json.dumps({})
    except Exception as e:
        print(f"Failed to get template info: {e}")
        traceback.print_exc()
        return json.dumps({})

# 示例查询
template_name = "Template_Envision_ICMPPing_Standard"
template_info_json = get_template_info(template_name)
print(f"Template Info: {template_info_json}")
