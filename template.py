import json
from zabbix_api import ZabbixAPI

class Template:
    def __init__(self):
        self.zabbix_api = ZabbixAPI()

    def get_template_info(self, template_name):
        """
        根据模板名称查询模板信息

        Args:
            template_name (str): 模板名称

        Returns:
            str: 包含模板信息的 JSON 格式字符串
        """
        try:
            # 获取模板信息
            params = {
                "filter": {"host": template_name},  # 过滤模板名称
                "output": ["templateid", "host"]  # 只返回 templateid 和 host
            }
            response = self.zabbix_api.call_api("template.get", params)

            if response.get("result"):  # 确保返回了有效的结果
                template_info = {
                    "template_id": response["result"][0]["templateid"],
                    "name": response["result"][0]["host"]  # 这里返回的是 host（即模板名称）
                }
                return json.dumps(template_info, indent=4)  # 格式化输出 JSON
            else:
                return json.dumps({})  # 返回空 JSON 对象
        except Exception as e:
            print(f"Failed to get template info: {e}")
            return json.dumps({})  # 出错时返回空 JSON 对象

# # 调用示例
# if __name__ == "__main__":
#     template = Template()
#     template_name = "Template_Envision_ICMPPing_Standard"  # 需要查询的模板名称
#     template_info_json = template.get_template_info(template_name)
#     print(f"Template Info: {template_info_json}")
