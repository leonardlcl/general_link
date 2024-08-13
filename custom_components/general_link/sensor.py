"""业务逻辑用于表示光照水平传感器的传感器实体"""

import logging
from homeassistant.components.sensor import SensorEntity,SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import LIGHT_LUX

from .const import DOMAIN, EVENT_ENTITY_REGISTER, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

COMPONENT = "sensor"

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置入口设置传感器实体"""

    async def async_discover(config_payload):
        try:
            if "a14" in config_payload:
                async_add_entities([LightSensor(hass, config_payload, config_entry)])
        except Exception :
            raise

    unsub = async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )

    config_entry.async_on_unload(unsub)


class LightSensor(SensorEntity):
    """用于处理光照传感器相关的业务逻辑的自定义实体类"""

    should_poll = False
    device_class = SensorDeviceClass.ILLUMINANCE

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"]+"L"
        self._attr_name = config["name"]+"_光照"
        #self._attr_entity_id = config["unique_id"]+"L"
        self.dname = config["name"]
        self._device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_native_unit_of_measurement = LIGHT_LUX
        self._attr_native_value = config["a14"]
        self.sn = config["sn"]
        self.hass = hass
        self.config_entry = config_entry
        self.update_state(config)

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
        except Exception as e:
            _LOGGER.error(f"更新传感器状态时出错: {e}")

    @property
    def device_info(self) -> DeviceInfo:
        """关于此实体/设备的信息"""
        return {
            "identifiers": {(DOMAIN, self.sn)},
            "name": self.dname,
            "manufacturer": MANUFACTURER,
        }

    def update_state(self, data):
        """传感器事件报告更改HA中的传感器状态"""
        if "a14" in data:
            self._attr_native_value = data["a14"]

