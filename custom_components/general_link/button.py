
import json
import logging
from abc import ABC
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_CLIENT_INSTANCE, \
    EVENT_ENTITY_REGISTER, EVENT_ENTITY_STATE_UPDATE, CACHE_ENTITY_STATE_UPDATE_KEY_DICT, MANUFACTURER


_LOGGER = logging.getLogger(__name__)
R_identifiers="reboot_button"
COMPONENT = "button"

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置入口设置按钮实体"""

    async def async_discover(config_payload):
        async_add_entities([RebootButton(hass, config_payload, config_entry)])

    unsub = async_dispatcher_connect(
        hass, EVENT_ENTITY_REGISTER.format(COMPONENT), async_discover
    )

    config_entry.async_on_unload(unsub)


class RebootButton(ButtonEntity,ABC):
    """自定义按钮实体类"""

    def __init__(self, hass: HomeAssistant, config: dict, config_entry: ConfigEntry) -> None:
        self._attr_unique_id = config["unique_id"] + "Reboot"
        self._attr_name = config["name"] + "-重启"
        self._attr_device_class = "custom_button"
        self.dname = config["name"]
        self.sn = config["sn"]
        self.hass = hass
        self.config_entry = config_entry

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
            # 在这里可以处理按钮的状态更新
            pass
        except Exception as e:
            _LOGGER.error(f"更新按钮状态时出错: {e}")

    @property
    def device_info(self) -> DeviceInfo:
        """关于此实体/设备的信息"""
        return {
            "identifiers": {(DOMAIN, R_identifiers)},
            "name": "重启设备",
            "manufacturer": MANUFACTURER,
        }

    async def async_press(self) -> None:
        """按下按钮时调用的方法"""
        try:
            # 在这里可以实现按钮被按下时的操作
            await self.exec_command()
            _LOGGER.info(f"按钮 {self.name} 被按下")
        except Exception as e:
            _LOGGER.error(f"处理按钮按下时出错: {e}")

    async def exec_command(self):
        message = {
            "seq": 1,
            "data": {
                "sns": [self.sn]
            }
        }
        #message["data"]["sns"] = self.sn
        await self.hass.data[MQTT_CLIENT_INSTANCE].async_publish(
            "P/0/center/q57",
            json.dumps(message),
            0,
            False
        )
        _LOGGER.warning(f"按钮 {message} 被按下")


            # "usr": "34943",
           # "rspTo": "A/1234",