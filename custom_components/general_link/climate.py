"""Business logic for climate entity."""
from __future__ import annotations

import json
import logging
import time
from abc import ABC

from homeassistant.components.climate import ClimateEntity, HVACMode, ClimateEntityFeature, FAN_LOW, FAN_MEDIUM, \
    FAN_MIDDLE, FAN_HIGH, FAN_TOP, FAN_AUTO, HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT
from homeassistant.components.climate.const import HVAC_MODE_DRY, HVAC_MODE_AUTO, HVAC_MODE_FAN_ONLY

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, \
    EVENT_ENTITY_REGISTER, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "climate"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """This method is executed after the integration is initialized to create an event listener,
    which is used to create a sub-device"""

    async def async_discover(config_payload):
        try:
            async_add_entities([CustomClimate(hass, config_payload, config_entry)])
        except Exception:
            raise

    async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )


class CustomClimate(ClimateEntity, ABC):
    """Custom entity class to handle business logic related to climates"""

    should_poll = False

    device_class = COMPONENT

    supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE

    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_MIDDLE, FAN_HIGH, FAN_TOP]

    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_FAN_ONLY, HVAC_MODE_DRY,
                        HVAC_MODE_AUTO]

    _attr_temperature_unit = TEMP_CELSIUS

    _attr_max_temp = 30

    _attr_min_temp = 16

    _attr_target_temperature_step = PRECISION_WHOLE

    _attr_hvac_mode = HVACMode.AUTO

    hvac_mode_cache = HVACMode.AUTO

    on_off_cache = 1

    _attr_fan_mode = FAN_AUTO

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]

        self._attr_entity_id = config["unique_id"]

        self.sn = config["sn"]

        self._attr_name = config["name"]

        self._attr_device_class = COMPONENT

        self.hass = hass

        self.config_entry = config_entry

        self.update_state(config)

        async def async_discover(data: dict):
            try:
                self.update_state(data)
                self.async_write_ha_state()
            except Exception:
                raise

        """Add a device state change event listener, and execute the specified method when the device state changes. 
        Note: It is necessary to determine whether an event listener has been added here to avoid repeated additions."""
        key = EVENT_ENTITY_STATE_UPDATE.format(self.unique_id)
        if key not in hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT]:
            hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT][key] = async_dispatcher_connect(
                hass, key, async_discover
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "manufacturer": MANUFACTURER,
        }

    def update_state(self, data):
        # _LOGGER.warning("update_state : %s", data)

        if "a64" in data:
            on_off = int(data["a64"])
            self.on_off_cache = int(data["a64"])
            if on_off == 0:
                self._attr_hvac_mode = HVAC_MODE_OFF

        if self.on_off_cache == 1:
            if "a66" in data:
                mode = int(data["a66"])
                if mode == 0:
                    self._attr_hvac_mode = HVAC_MODE_AUTO
                    self.hvac_mode_cache = HVAC_MODE_AUTO
                elif mode == 1:
                    self._attr_hvac_mode = HVAC_MODE_COOL
                    self.hvac_mode_cache = HVAC_MODE_COOL
                elif mode == 2:
                    self._attr_hvac_mode = HVAC_MODE_HEAT
                    self.hvac_mode_cache = HVAC_MODE_HEAT
                elif mode == 3:
                    self._attr_hvac_mode = HVAC_MODE_FAN_ONLY
                    self.hvac_mode_cache = HVAC_MODE_FAN_ONLY
                elif mode == 4:
                    self._attr_hvac_mode = HVAC_MODE_DRY
                    self.hvac_mode_cache = HVAC_MODE_DRY
            else:
                self._attr_hvac_mode = self.hvac_mode_cache

        if "a65" in data:
            target_temp = float(data["a65"])
            self._attr_target_temperature = target_temp

        if "a19" in data:
            curr_temp = float(data["a19"])
            self._attr_current_temperature = curr_temp

        if "a67" in data:
            fan_level = int(data["a67"])
            if fan_level == 0:
                self._attr_fan_mode = FAN_AUTO
            elif fan_level == 1:
                self._attr_fan_mode = FAN_LOW
            elif fan_level == 2:
                self._attr_fan_mode = FAN_MEDIUM
            elif fan_level == 3:
                self._attr_fan_mode = FAN_MIDDLE
            elif fan_level == 4:
                self._attr_fan_mode = FAN_HIGH
            elif fan_level == 5:
                self._attr_fan_mode = FAN_TOP

    async def async_set_temperature(self, **kwargs) -> None:
        # _LOGGER.warning("set_temperature : %s", kwargs)
        if "temperature" in kwargs:
            temperature = float(kwargs["temperature"])
            await self.exec_command(20, temperature)
            self._attr_target_temperature = temperature

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        # _LOGGER.warning("set_fan_mode : %s", fan_mode)
        fan_level = 0
        if fan_mode == FAN_AUTO:
            fan_level = 0
        elif fan_mode == FAN_LOW:
            fan_level = 1
        elif fan_mode == FAN_MEDIUM:
            fan_level = 2
        elif fan_mode == FAN_MIDDLE:
            fan_level = 3
        elif fan_mode == FAN_HIGH:
            fan_level = 4
        elif fan_mode == FAN_TOP:
            fan_level = 5

        await self.exec_command(22, fan_level)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # _LOGGER.warning("set_hvac_mode : %s", hvac_mode)
        if hvac_mode == HVAC_MODE_OFF:
            await self.exec_command(19, 0)
        else:
            if self._attr_hvac_mode == HVAC_MODE_OFF:
                await self.exec_command(19, 1)
                time.sleep(1)
            if hvac_mode == HVAC_MODE_AUTO:
                await self.exec_command(21, 0)
            elif hvac_mode == HVAC_MODE_COOL:
                await self.exec_command(21, 1)
            elif hvac_mode == HVAC_MODE_HEAT:
                await self.exec_command(21, 2)
            elif hvac_mode == HVAC_MODE_FAN_ONLY:
                await self.exec_command(21, 3)
            elif hvac_mode == HVAC_MODE_DRY:
                await self.exec_command(21, 4)

        self._attr_hvac_mode = hvac_mode
        self.hvac_mode_cache = HVAC_MODE_HEAT
        self.async_write_ha_state()

    async def exec_command(self, i: int, v):
        """Execute MQTT commands"""
        message = {
            "seq": 1,
            "data": {
                "sn": self.sn,
                "i": i,
                "v": v
            }
        }

        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q74",
            json.dumps(message),
            0,
            False
        )
