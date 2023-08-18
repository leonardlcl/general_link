"""Business logic for switch entity."""
from __future__ import annotations

import json
import logging
from abc import ABC
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, \
    EVENT_ENTITY_REGISTER, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "switch"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
    which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            if "relaysNum" in config_payload:
                relays = config_payload["relays"]
                relaysNames = config_payload["relaysNames"]
                sn = config_payload["sn"]
                name = config_payload["name"]
                for relay, state in enumerate(relays):
                    relaysName = relaysNames[relay]
                    if relaysName.strip() == "":
                        relaysName = f"按键{relay+1}"
                    config_payload["unique_id"] = f"switch{sn}{relay}"
                    config_payload["relay"] = relay
                    config_payload["name"] = f"{name}-{relaysName}"
                    config_payload["on"] = state
                    async_add_entities([CustomSwitch(hass, config_payload, config_entry)])
        except Exception:
            raise

    unsub = async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )

    config_entry.async_on_unload(unsub)


class CustomSwitch(SwitchEntity, ABC):
    """Custom entity class to handle business logic related to switchs"""

    should_poll = False

    device_class = COMPONENT

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]

        self._attr_name = config["name"]

        self._state = True

        self._is_on = True

        self.sn = config["sn"]

        self.hass = hass

        self.relay = config["relay"]

        self.config_entry = config_entry

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
            "identifiers": {(DOMAIN, self.unique_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def update_state(self, data):
        """Switch event reporting changes the switch state in HA"""
        if "on" in data:
            if data["on"] == 0:
                self._state = False
            else:
                self._state = True

    async def async_turn_on(self, **kwargs):
        """Turn on the switch"""
        await self.exec_command(on=1)

        self._state = True

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch"""
        await self.exec_command(on=0)

        self._state = False

        self.async_write_ha_state()

    async def exec_command(self, on=None):
        message = {
            "seq": 1,
            "data": {}
        }
        message["data"]["relay"] = self.relay
        message["data"]["sn"] = self.sn
        message["data"]["state"] = int(on)
        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q68",
            json.dumps(message),
            0,
            False
        )
