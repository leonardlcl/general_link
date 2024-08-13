import asyncio
import logging
import aiohttp
import json
import re
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class HttpRequest:

    def __init__(self, hass: HomeAssistant, username: str, password: str, url: str,manufacturer:str):
        self.hass = hass
        self.username = username
        self.password = password
        self.response_data = None
        self.url = url
        self.headers = {
            "Accept-Language": "zh-CN",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/4.9.3"
        }
        self.params = {
            "appOs": "android",
            "appVersion": "3.9",
            "appVersionNum": "30900",
            "manufacturer": manufacturer
        }

    async def _send_http_request(self, url: str, method: str, params: dict = None, headers: dict = None, data: str = None):
        session = async_get_clientsession(self.hass)
        try:
            if method.lower() == 'get':
                async with session.get(url, params=params, headers=headers) as response:
                    await self._handle_response(response)
            elif method.lower() == 'post':
                async with session.post(url, params=params, headers=headers, data=data) as response:
                    await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to send request: {e}")

    async def _handle_response(self, response):
        if response.status == 200:
            self.response_data = await response.json()
            # _LOGGER.warning("Response: %s", self.response_data)

            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie is not None:
                match = re.search(r'IOT-CLOUD=([^;]+)', set_cookie)
                if match:
                    self.cookie = match.group(1)
                    #self.headers["Cookie"] = self.cookie

        else:
            _LOGGER.error(
                "Failed to get a successful response. Status code: %d", response.status)

# 登陆验证
    async def _server_login(self):
        await self._send_http_request(f"https://{self.url}/loginPassword", "POST",
                                      params=self.params,
                                      headers=self.headers,
                                      data=f"username={self.username}&password={
                                          self.password}"
                                      )
        # if self.response_data ["code"] == 200:
        #   return True
        # else:
        #  return False

    async def start(self):
        await self._server_login()

    async def get_envkey(self):
        dict_data_by_envKey = {}
        # await self._server_login()
        # response_env  = None

        if self.response_data["code"] == 200:
            await self._send_http_request(f"https://{self.url}/env/queryEnvList", "GET",
                                          params=self.params,
                                          headers=self.headers
                                          )
            if self.response_data is not None:
                dict_data_by_envKey = {
                    item['envKey']: item for item in self.response_data["data"]}
                return dict_data_by_envKey
            else:
                _LOGGER.error("Failed to get a successful response.")
                return None
        else:
            return self.response_data
