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

        self._aiozc: AsyncZeroconf | None = None


    
    @callback
    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        _LOGGER.warning("state_change : %s", self)
        service_type = service_type[:-1]
        name = name.replace(f".{service_type}.", "")
        del self.services[name]



    @callback
    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        """Handle service updated."""
        _LOGGER.warning("update_service %s", name)
        self.hass.async_create_task(self._add_update_service(service_type, name))

        

   
    @callback

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):

        """Handle service updated."""
        #_LOGGER.warning("add_service %s", name)
        self.hass.async_create_task(self._add_update_service(service_type, name))


    async def _add_update_service(self,service_type: str, name: str):
        service = None
        tries = 0
        while service is None and tries < 8:
            service = await self._aiozc.async_get_service_info(service_type, name)
            tries += 1
        if not service:
            _LOGGER.warning("_add_update_service failed to add %s, %s", service_type, name)
            return
        

        if service is not None:
            discovery_info = info_from_service(service)
            #_LOGGER.warning("_add_update_service2 : %s", discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            self.services[name] = connection
            #_LOGGER.warning("change update_service : %s", connection)




    async def scan_all(self, timeout: float = 5.0) -> dict:
        """Scan for all services on the network."""
        try:    
                self._aiozc = await zeroconf.async_get_async_instance(self.hass)
                
                await self._aiozc.async_add_service_listener(MDNS_SCAN_SERVICE, self)
                await asyncio.sleep(1)
        except Exception as e:
                # 日志记录具体的错误，考虑在实际应用中使用更具体的日志记录方式
                _LOGGER.error(f"初始化Zeroconf实例或sync_add_service_listener时发生错误: {e}")
                return None
        finally:
            await self._aiozc.async_remove_service_listener(self)

        return self.services



    async def scan_single(self, name: str, timeout: float = 5.0) -> dict:
            self.services = {}

            try:
                self._aiozc = await zeroconf.async_get_async_instance(self.hass)
                await self._aiozc.async_add_service_listener(MDNS_SCAN_SERVICE, self)
            except Exception as e:
                # 日志记录具体的错误，考虑在实际应用中使用更具体的日志记录方式
                _LOGGER.error(f"初始化Zeroconf实例或sync_add_service_listener时发生错误: {e}")
                return None
            finally:
                await self._aiozc.async_remove_service_listener(self)
            if name in self.services:
                return self.services[name]
            else:
                return None


       
