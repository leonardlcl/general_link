import asyncio
import logging
from typing import Dict, Optional
import time
import re

from homeassistant.components.zeroconf import info_from_service

from homeassistant.components import zeroconf

from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

from homeassistant.core import HomeAssistant,callback

from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from .const import MDNS_SCAN_SERVICE

from .util import format_connection

_LOGGER = logging.getLogger(__name__)

class MdnsScanner:

    def __init__(self, hass: HomeAssistant):

        self.services: Dict[str, Dict] = {}

        self.hass = hass

        #self.original_add_service = self.add_service
    
    @callback
    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        _LOGGER.warning("state_change : %s", self)
        service_type = service_type[:-1]
        name = name.replace(f".{service_type}.", "")
        del self.services[name]



    @callback
    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        discovery_info = zeroconf.get_service_info(service_type, name, timeout=5000)

        if discovery_info is not None:
            discovery_info = info_from_service(discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            self.services[name] = connection
            #_LOGGER.warning("change update_service : %s", connection)

   
    @callback

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        discovery_info = zeroconf.get_service_info(service_type, name, timeout=5000)

        if discovery_info is not None:
            discovery_info = info_from_service(discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            self.services[name] = connection
            #_LOGGER.warning("change add_service : %s", connection)



    async def scan_all(self, timeout: float = 5.0) -> dict:
        """Scan for all services on the network."""
        try:
                zeroconf_instance = await zeroconf.async_get_instance(self.hass)
                browser = ServiceBrowser(zeroconf_instance, MDNS_SCAN_SERVICE, self)
        except Exception as e:
                # 日志记录具体的错误，考虑在实际应用中使用更具体的日志记录方式
                _LOGGER.error(f"初始化Zeroconf实例或ServiceBrowser时发生错误: {e}")
                return None
        try:
            # 使用 asyncio.wait_for 来优雅地处理超时
            await asyncio.wait_for(self._scan_loop(browser), timeout)
        except asyncio.TimeoutError:
            _LOGGER.info("Scanning timed out.")
        except Exception as e:
            _LOGGER.error(f"An error occurred during scanning: {e}")
        finally:
            if browser is not None:
                browser.cancel()
            #zeroconf_instance.ha_async_close()

        return self.services



    async def scan_single(self, name: str, timeout: float = 5.0) -> Optional[Dict]:
            self.services = {}

            try:
                zeroconf_instance = await zeroconf.async_get_instance(self.hass)
                browser = ServiceBrowser(zeroconf_instance, MDNS_SCAN_SERVICE, self)
            except Exception as e:
                # 日志记录具体的错误，考虑在实际应用中使用更具体的日志记录方式
                _LOGGER.error(f"初始化Zeroconf实例或ServiceBrowser时发生错误: {e}")
                return None
            try:
                # 使用 asyncio.wait_for 替代内部计时器和循环
                await asyncio.wait_for(self._scan_loop(browser), timeout)
            except asyncio.TimeoutError:
                _LOGGER.info("Scanning timed out.")
            except Exception as e:
                _LOGGER.error(f"An error occurred during scanning: {e}")
            finally:
                if browser is not None:
                    browser.cancel()
                #zeroconf_instance.ha_async_close()

            # 使用日志记录服务状态，而不是直接返回值
            # _LOGGER.warning("self.services  %s", self.services)      
            if name in self.services:
                return self.services[name]
            else:
                # 考虑在服务未找到时返回 None 而不是一个空字典
                return None

    async def _scan_loop(self, browser):
        """Internal loop for scanning."""
        timeout = 10  # 20秒超时
        start_time = time.time()

        while True:
          await asyncio.sleep(1)  # 暂时暂停一秒

          # Check if the timeout has been reached
          if time.time() - start_time > timeout:
            print("Timeout reached, exiting scan loop.")
            return


       
