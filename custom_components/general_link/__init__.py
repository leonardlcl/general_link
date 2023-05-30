"""The Detailed MHTZN integration."""
from __future__ import annotations

import logging
import threading
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .Gateway import Gateway
from .const import PLATFORMS, MQTT_CLIENT_INSTANCE, CONF_LIGHT_DEVICE_TYPE, DOMAIN, FLAG_IS_INITIALIZED, \
    CACHE_ENTITY_STATE_UPDATE_KEY_DICT, CONF_BROKER
from .mdns import MdnsScanner

_LOGGER = logging.getLogger(__name__)


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """This method is triggered when the entry configuration changes, and the gateway connection is updated"""
    hub = hass.data[DOMAIN][entry.unique_id]

    """reconnect gateway"""
    # await hub.reconnect(entry)
    """Initialize gateway information and synchronize child device list to HA"""
    hass.async_create_task(
        hub.init(entry, False)
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    hub = Gateway(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = hub

    """Set a flag to record whether the current integration has been initialized"""
    if FLAG_IS_INITIALIZED not in hass.data:
        hass.data[FLAG_IS_INITIALIZED] = False

    """Set a dictionary to record whether the sub-device state change event has been created, 
    to avoid the same device from repeatedly creating state change events"""
    if CACHE_ENTITY_STATE_UPDATE_KEY_DICT not in hass.data:
        hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT] = {}

    """Determine whether the current integration has been initialized to avoid repeated installation of platform list"""
    if not hass.data[FLAG_IS_INITIALIZED]:
        hass.data[FLAG_IS_INITIALIZED] = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hub.reconnect_flag = True

    """Initialize gateway information and synchronize child device list to HA"""
    hass.async_create_task(
        hub.init(entry, True)
    )

    def monitor_connection():
        scanner = MdnsScanner()
        time.sleep(30)

        # 获取当前时间戳
        current_time = time.time()

        # 设置初始时间戳
        start_time = current_time

        # 定义间隔时间（10分钟）
        interval = 5 * 60

        while True:
            try:
                entry_data = entry.data
                # status = connect_mqtt(entry_data[CONF_BROKER], entry_data[CONF_PORT]
                #                      , entry_data[CONF_USERNAME], entry_data[CONF_PASSWORD])
                # _LOGGER.warning("status：%s，hub.init_state：%s", status, hub.init_state)
                mqtt_connected = hub.hass.data[MQTT_CLIENT_INSTANCE].connected
                if not mqtt_connected or not hub.init_state:
                    hub.reconnect_flag = True
                    connection = scanner.scan_single(entry_data[CONF_NAME], 5)
                    _LOGGER.warning("mqtt 连接不上了，需要重新扫描一下，得到连接 %s", connection)
                    if connection is not None:
                        if CONF_LIGHT_DEVICE_TYPE in entry_data:
                            connection[CONF_LIGHT_DEVICE_TYPE] = entry_data[CONF_LIGHT_DEVICE_TYPE]
                            connection["random"] = time.time()
                        hass.config_entries.async_update_entry(
                            entry,
                            data=connection,
                        )
                elif mqtt_connected and hub.init_state:
                    current_time = time.time()
                    if current_time - start_time >= interval:
                        # 执行你的操作
                        hass.async_create_task(
                            hub.sync_group_status(False)
                        )
                        # 更新起始时间戳
                        start_time = current_time
                time.sleep(10)
            except OSError as err:
                _LOGGER.error("ERROR: %s", err)

    monitor_thread = threading.Thread(target=monitor_connection)
    monitor_thread.start()

    """Add an entry configuration change event listener to trigger the specified method 
    when the configuration changes"""
    entry.add_update_listener(_async_config_entry_updated)

    return True


def connect_mqtt(broker: str, port: int, username: str, password: str):
    from paho.mqtt import client
    try:
        client = client.Client("test-connect")
        client.username_pw_set(username, password=password)
        client.connect(broker, port)
        client.disconnect()
        return True
    except OSError as err:
        _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """This method is triggered when the entry is unload"""

    hub = hass.data[DOMAIN].pop(entry.unique_id)
    """Perform a gateway disconnect operation"""
    await hub.disconnect()

    return True
