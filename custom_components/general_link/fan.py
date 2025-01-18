"""Business logic for fan entity."""
from __future__ import annotations
import math
import json
import logging
from typing import Any, Optional
from abc import ABC
from homeassistant.components.fan import FanEntity,FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ranged_value_to_percentage, percentage_to_ranged_value

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, \
    EVENT_ENTITY_REGISTER, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "fan"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
    which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            if "a112" in config_payload:
                a112 = int(config_payload["a112"])
                if a112 == 1:
                  async_add_entities([CustomFan(hass, config_payload, config_entry)])
        except Exception:
            raise

    unsub = async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )

    config_entry.async_on_unload(unsub)


class CustomFan(FanEntity, ABC):
    """Custom entity class to handle business logic related to fan"""

    should_poll = False

    device_class = COMPONENT

    supported_features =  FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED

    _attr_preset_modes = ["自动", "关闭自动"]

    _attr_preset_mode = None

    #_attr_speed_count = 3

#    SPEED_RANGE = (1, 5)

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]+"F"

        self._attr_name = config["name"]+"新风"

        self.dname = config["name"]

        self._attr_entity_id = config["unique_id"]+"F"

        self._is_on = True

        self.sn = config["sn"]

        self.hass = hass

        self.config_entry = config_entry

        self._attr_a109 = config["a109"]

        self._attr_speed_count = 3

        #self.current_speed = 1

        self._attr_percentage = 100

        self.update_state(config)

        """Add a device state change event listener, and execute the specified method when the device state changes. 
        Note: It is necessary to determine whether an event listener has been added here to avoid repeated additions."""
        key = EVENT_ENTITY_STATE_UPDATE.format(self.unique_id)
        if key not in hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT]:
            unsub = async_dispatcher_connect(
                hass, key, self.async_discover
            )
            hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT][key] = unsub
            config_entry.async_on_unload(unsub)



    @callback
    def async_discover(self, data: dict) -> None:
        try:
            self.update_state(data)
            self.async_write_ha_state()
        except Exception:
            raise

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.sn)},
            # If desired, the name for the device could be different to the entity
            "name": self.dname,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_on(self):
        """Return true if fan is on."""
        return self._is_on

    def update_state(self, data):
        """fan event reporting changes the fan state in HA"""
        if "a115" in data:
            if data["a115"] == 0:
                self._is_on = False
            else:
                self._is_on = True

        if "a116" in data:
            fan_level = int(data["a116"])
            if fan_level == 0:
                self._attr_preset_mode = "自动"
                self._attr_percentage = 0
            else:
                self._attr_preset_mode = "关闭自动"
                SPEED_RANGE = (1, 5)
                percentage = ranged_value_to_percentage(SPEED_RANGE, fan_level)
                self._attr_percentage = percentage
                #self.current_speed = fan.speed_count

        if "a109" in data:
                curr_a109 = int(data["a109"])
                self._attr_a109 = curr_a109

    async def async_turn_on(self, speed: Optional[str] = None, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn on the fan"""
        if self._attr_a109 != 3:
            await self.exec_command(32, 3)
            self._attr_a109 = 3

        await self.exec_command(35,1)

        self._is_on = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan"""
        if self._attr_a109 != 3:
            await self.exec_command(32, 3)
            self._attr_a109 = 3

        await self.exec_command(35,0)

        self._is_on = False

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        # _LOGGER.warning("set_fan_mode : %s", fan_mode)
        fan_level = 0
        if preset_mode == "自动":
            fan_level = 0
        if self._attr_a109 != 3:
            await self.exec_command(32, 3)
            self._attr_a109 = 3
        await self.exec_command(36, fan_level)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage != 0:
          await self.async_turn_on()
        SPEED_RANGE = (1, 3)
        value_in_range = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        if (value_in_range == 3):
            value_in_range = 5
        elif (value_in_range == 2):
            value_in_range = 3
        await self.exec_command(36, value_in_range)
        self._attr_percentage = percentage
        self.async_write_ha_state()

    async def exec_command(self, i: int, p):
        """Execute MQTT commands"""
        if i == 35:
            m = "a115"
        elif i == 32:
            m = "a109"
        else:
            m = "a116"
        message = {
            "seq": 1,
            "s": {
                "t": 101
            },
            "data": {
                "sn": self.sn,
                "i": i,
                "p": {
                    m: p
                }
            }
        }

        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q74",
            json.dumps(message),
            0,
            False
        )
