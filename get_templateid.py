import json
import traceback
from zabbix_api import ZabbixAPI

class Templateid:
    def __init__(self):
        self.zabbix_api = ZabbixAPI()

    def get_template_info(self, template_name):
        """
        根据模板名称查询模板信息
        """
        try:
            response = self.zabbix_api.call_api('template.get', {
                "filter": {"host": template_name},
                "output": ["templateid", "name"]
            })

            templates = response.get("result", [])
            if templates:
                template_info = {
                    "template_id": templates[0]["templateid"],
                    "name": templates[0]["name"]
                }
                return json.dumps(template_info, indent=2)
            else:
                return json.dumps({})
        except Exception as e:
            print(f"Failed to get template info: {e}")
            traceback.print_exc()
            return json.dumps({})


# ✅ 示例使用
if __name__ == "__main__":
    template_api = Templateid()
    template_name = "Template_Envision_ICMPPing_Standard"
    result = template_api.get_template_info(template_name)
    print(f"Template Info:\n{result}")
