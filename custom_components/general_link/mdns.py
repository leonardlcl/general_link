import time

from homeassistant.components.zeroconf import info_from_service
from zeroconf import ServiceBrowser, Zeroconf
from typing import Dict

from .const import MDNS_SCAN_SERVICE
from .util import format_connection


class MdnsScanner:
    def __init__(self):
        self.services: Dict[str, Dict] = {}

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        discovery_info = zeroconf.get_service_info(service_type, name)

        if discovery_info is not None:
            discovery_info = info_from_service(discovery_info)
            service_type = service_type[:-1]
            name = name.replace(f".{service_type}.", "")
            connection = format_connection(discovery_info)
            self.services[name] = connection

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str):
        pass

    def scan_all(self, timeout: float = 5.0) -> Dict[str, Dict]:
        self.services = {}
        zeroconf = Zeroconf()
        browser = ServiceBrowser(zeroconf, MDNS_SCAN_SERVICE, self)
        time.sleep(timeout)
        browser.cancel()
        zeroconf.close()
        return self.services

    def scan_single(self, name: str, timeout: float = 5.0):
        connections = self.scan_all(timeout)
        if name in connections:
            return connections[name]
        else:
            return None
