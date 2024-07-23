import logging
import time
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME
from .Gateway import Gateway
from .const import PLATFORMS, MQTT_CLIENT_INSTANCE, CONF_LIGHT_DEVICE_TYPE, DOMAIN, FLAG_IS_INITIALIZED, \
    CACHE_ENTITY_STATE_UPDATE_KEY_DICT, CONF_BROKER
from .mdns import MdnsScanner

_LOGGER = logging.getLogger(__name__)
reconnect_flag = asyncio.Event()

async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    hub = hass.data[DOMAIN][entry.entry_id]
    hass.async_create_task(
        hub.init(entry, False)
    )

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    hub = Gateway(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    hass.data.setdefault(FLAG_IS_INITIALIZED, False)
    hass.data.setdefault(CACHE_ENTITY_STATE_UPDATE_KEY_DICT, {})

    if not hass.data[FLAG_IS_INITIALIZED]:
        hass.data[FLAG_IS_INITIALIZED] = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    else:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hub.reconnect_flag = True

    hass.async_create_task(
        hub.init(entry, True)
    )

    reconnect_flag.clear()

    #reconnect_flag = asyncio.Event()
    
    entry.add_update_listener(_async_config_entry_updated)


    await asyncio.sleep(2)

    hass.async_create_background_task(

        monitor_connection(hass, hub, entry, reconnect_flag),

        "monitor_connection"

    )
    
    return True

async def monitor_connection(hass, hub, entry, reconnect_flag):

    scanner = MdnsScanner(hass)

    last_sync_time = 0  # 用于记录上一次同步的时间


    while not reconnect_flag.is_set():

        try:

            mqtt_connected = hub.hass.data[MQTT_CLIENT_INSTANCE].connected

            current_time = time.time()

            if not mqtt_connected or not hub.init_state:

                hub.reconnect_flag = True

                connection = await scanner.scan_single(entry.data[CONF_NAME], 10)

                _LOGGER.warning("connection bk  %s", connection)

                if connection is not {}:

                    if CONF_LIGHT_DEVICE_TYPE in entry.data:

                        connection[CONF_LIGHT_DEVICE_TYPE] = entry.data[CONF_LIGHT_DEVICE_TYPE]

                        connection["random"] = time.time()

                await hass.config_entries.async_update_entry(entry, data=connection)


            elif current_time - last_sync_time >= 300 :
                
                last_sync_time = current_time

                await hub.sync_group_status(False)


        except Exception as e:

            _LOGGER.error("Error in monitor_connection: %s", e)


        await asyncio.sleep(20)  # 每20秒检测一次


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    reconnect_flag.set()  # Notify monitor_connection to stop

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub = hass.data[DOMAIN].pop(entry.entry_id)

    await hub.disconnect()

    hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT] = {}

    return True
