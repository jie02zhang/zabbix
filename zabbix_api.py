import requests
import json
import logging
from config import ZABBIX_URL, ZABBIX_USER, ZABBIX_PASSWORD

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ZabbixAPIException(Exception):
    """自定义异常类，用于处理Zabbix API相关的错误"""
    def __init__(self, message, response=None):
        self.message = message
        self.response = response
        super().__init__(self.message)

class ZabbixAPI:
    def __init__(self):
        self.url = ZABBIX_URL + "/api_jsonrpc.php"
        self.headers = {"Content-Type": "application/json"}
        self.auth_token = None
        self.session = requests.Session()
        self.session.timeout = 30  # 设置请求超时为30秒
        self.login()

    def login(self):
        """自动登录并获取认证token"""
        logger.debug("Attempting to log in to Zabbix API")
        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "user": ZABBIX_USER,
                "password": ZABBIX_PASSWORD
            },
            "id": 1
        }
        try:
            response = self._send_request(payload)
            if "result" in response:
                self.auth_token = response["result"]
                logger.info("Login successful")
            else:
                raise ZabbixAPIException("Login failed", response)
        except requests.exceptions.RequestException as e:
            raise ZabbixAPIException(f"Request error during login: {e}")

    def _send_request(self, payload):
        """发送请求并返回响应"""
        try:
            logger.debug(f"Sending request with payload: {payload}")
            response = self.session.post(self.url, data=json.dumps(payload), headers=self.headers, timeout=self.session.timeout)
            response.raise_for_status()  # 检查请求是否成功
            response_data = response.json()

            if "error" in response_data:
                raise ZabbixAPIException(f"Zabbix API error: {response_data['error']}", response_data)

            return response_data
        except requests.exceptions.RequestException as e:
            raise ZabbixAPIException(f"Request error: {e}")
        except ValueError as e:
            raise ZabbixAPIException(f"Invalid JSON response: {e}")

    def call_api(self, method, params=None):
        """调用Zabbix API方法"""
        if params is None:
            params = {}
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "auth": self.auth_token,
            "id": 1
        }
        return self._send_request(payload)

    def __getattr__(self, name):
        """动态生成API方法（如调用host.get()）"""
        def api_method(*args, **kwargs):
            return self.call_api(name, *args, **kwargs)
        return api_method

# 示例用法：
# zabbix_api = ZabbixAPI()
# response = zabbix_api.host.get()
# print(response)
