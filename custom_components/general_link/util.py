"""Utility functions for the MHTZN integration."""
import logging
import math
import socket

from homeassistant.const import CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_PROTOCOL

from .const import CONF_BROKER

_LOGGER = logging.getLogger(__name__)


def get_connection_name(discovery_info):
    """Parse mdns data to obtain gateway name"""

    service_type = discovery_info.type[:-1]
    return discovery_info.name.replace(f".{service_type}.", "")


def color_temp_to_rgb(color_temp) -> tuple[int, int, int]:
    if color_temp < 1000:
        color_temp = 1000.0

    if color_temp > 40000:
        color_temp = 40000.0

    tempera = color_temp / 100.0
    if tempera <= 66:
        red = 255.0
    else:
        red = tempera - 60
        red = 329.698727446 * math.pow(red, -0.1332047592)
        if red < 0:
            red = 0.0
        elif red > 255.0:
            red = 255.0

    if tempera <= 66:
        green = tempera
        green = 99.4708025861 * math.log(green) - 161.1195681661
        if green < 0:
            green = 0.0

        if green > 255:
            green = 255.0
    else:
        green = tempera - 60
        green = 288.1221695283 * math.pow(green, -0.0755148492)
        if green < 0:
            green = 0.0

        if green > 255:
            green = 255.0

    if tempera >= 66:
        blue = 255.0
    else:
        if tempera <= 19:
            blue = 0.0
        else:
            blue = tempera - 10
            blue = 138.5177312231 * math.log(blue) - 305.0447927307
            if blue < 0:
                blue = 0.0
            if blue > 255:
                blue = 255.0

    color_rgb = (int(red), int(green), int(blue))

    return color_rgb


def format_connection(discovery_info) -> dict:
    """Parse and format mdns data"""

    name = get_connection_name(discovery_info)
    host = None
    if hasattr(discovery_info, 'host'):
        host = discovery_info.host
    elif hasattr(discovery_info, 'server'):
        host = discovery_info.server
        ipv4_list = [
            socket.inet_ntoa(addr)
            for addr in discovery_info.addresses
            if len(addr) == 4
        ]
        if ipv4_list:
            host = ipv4_list[0]
    port = discovery_info.port
    username = None
    password = None

    for key, value in discovery_info.properties.items():
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if isinstance(key, bytes):
            key = key.decode('utf-8')

        if key == 'username':
            username = value
        elif key == 'password':
            password = value
        elif key == 'host':
            host = value

    connection = {
        CONF_NAME: name,
        CONF_BROKER: host,
        CONF_PORT: port,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        CONF_PROTOCOL: "3.1.1",
        "keepalive": 60
    }

    _LOGGER.warning("Formatted connection: %s", connection)

    return connection
