# zabbix_api.py

import requests
import json
from config import ZABBIX_URL, ZABBIX_USER, ZABBIX_PASSWORD

class ZabbixAPI:
    def __init__(self):
        self.url = ZABBIX_URL + "/api_jsonrpc.php"
        self.headers = {"Content-Type": "application/json"}
        self.auth_token = None
        self.login()

    def login(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "user": ZABBIX_USER,
                "password": ZABBIX_PASSWORD
            },
            "id": 1
        }
        response = self._send_request(payload)
        self.auth_token = response["result"]

    def _send_request(self, payload):
        response = requests.post(self.url, data=json.dumps(payload), headers=self.headers)
        return response.json()

    def call_api(self, method, params=None):
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
