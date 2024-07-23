import asyncio
import logging
from typing import Dict, Optional

from homeassistant.components.zeroconf import info_from_service

from homeassistant.components import zeroconf

from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

from homeassistant.core import HomeAssistant, callback

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
            discovery_info = info_from_service(discovery_info)
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


    async def scan_single(self, name: str, timeout: float = 5.0)-> Optional[Dict] :
    
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
       #_LOGGER.warning("self.services  %s", self.services)      
       if name in self.services:
         return self.services[name]
       else:
         return {}
       
