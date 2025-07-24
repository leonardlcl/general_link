import asyncio
import logging
from typing import Dict, Optional

import re

from homeassistant.components.zeroconf import info_from_service

from homeassistant.components import zeroconf

from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

from homeassistant.core import HomeAssistant

from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from .const import MDNS_SCAN_SERVICE

from .util import format_connection

_LOGGER = logging.getLogger(__name__)

class MdnsScanner:

    def __init__(self, hass: HomeAssistant):

        self.services: Dict[str, Dict] = {}

        self._hass = hass

        #self.original_add_service = self.add_service

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass

   # @callback

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        discovery_info = zeroconf.get_service_info(service_type, name)

        if discovery_info is not None:
            # discovery_info = info_from_service(discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            self.services[name] = connection


    async def scan_all(self, timeout: float = 5.0) :

        self.services = {}

        zeroconf_instance = await zeroconf.async_get_instance(self._hass)

        browser = ServiceBrowser(zeroconf_instance, MDNS_SCAN_SERVICE, self)

        time1=1

        while True:
            if time1 > timeout:
               break

            await asyncio.sleep(1)

            time1 = time1 + 1

        if browser is not None:
              browser.cancel()

        return self.services





    async def scan_single(self, name: str, timeout: float = 5.0) -> Optional[Dict]:
            self.services = {}

            try:
                zeroconf_instance = await zeroconf.async_get_instance(self._hass)
                browser = ServiceBrowser(zeroconf_instance, MDNS_SCAN_SERVICE, self)
            except Exception as e:
                # 日志记录具体的错误，考虑在实际应用中使用更具体的日志记录方式
                print(f"初始化Zeroconf实例或ServiceBrowser时发生错误: {e}")
                return None

            try:
                # 使用 asyncio.wait_for 替代内部计时器和循环
                await asyncio.wait_for(self._scan_services(browser), timeout)
            except asyncio.TimeoutError:
                pass
            finally:
                if browser is not None:
                    browser.cancel()

            # 使用日志记录服务状态，而不是直接返回值
            # _LOGGER.warning("self.services  %s", self.services)
            if name in self.services:
                return self.services[name]
            else:
                # 考虑在服务未找到时返回 None 而不是一个空字典
                return None

    async def _scan_services(self, browser):
            # 这个辅助异步函数负责实际的服务扫描逻辑
            elapsed_time = 0
            while True:
                await asyncio.sleep(1)
                elapsed_time += 1
                # 假设这里有相应的逻辑来处理发现的服务并更新 self.services
                # 注意，具体的处理逻辑依赖于ServiceBrowser的实现和使用
                if elapsed_time > 10:  # 使用变量而不是魔法数字
                    break


