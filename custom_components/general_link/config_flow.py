"""Config flow for MHTZN integration."""
from __future__ import annotations
from .listener import sender_receiver
import logging
from collections import OrderedDict
import re
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_URL,
    CONF_ADDRESS,
)
from .mdns import MdnsScanner
from .const import (
    DOMAIN, CONF_BROKER, CONF_LIGHT_DEVICE_TYPE, CONF_ENVKEY, CONF_PLACE
)
from .scan import scan_and_get_connection_dict
from .util import format_connection
from .aiohttp import HttpRequest

connection_dict = {}
temp_envkey = None
temp_place = None
temp_envpassword = "gAAAAABmuFUSYdkfaAGSUz1fmcpkGal4SFeyrQpixXsM3qsQvhZQIJLadZmizUSVa4R8pkm0a8_WeW37Im_LSNjcS0hf5UGSsrR7912wLHrHNnxjF-PlxqI="
light_device_type = None
scan_flag = False
reconfigure = False

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MHTZN."""

    VERSION = 1

    async def async_step_zeroconf(
            self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        global scan_flag

        """Format the connection information reported by mdns"""
        connection = format_connection(discovery_info)
        # _LOGGER.warning("这个东西触发的扫描 %s", connection)
        """Realize the change of gateway connection information and trigger HA to reconnect to the gateway"""
        # for entry in self._async_current_entries():
        #     entry_data = entry.data
        #     if entry_data[CONF_NAME] == connection[CONF_NAME]:
        #         if connection[CONF_BROKER] != entry_data[CONF_BROKER] \
        #                 or connection[CONF_PORT] != entry_data[CONF_PORT] \
        #                 or connection[CONF_USERNAME] != entry_data[CONF_USERNAME] \
        #                 or connection[CONF_PASSWORD] != entry_data[CONF_PASSWORD]:
        #             if CONF_LIGHT_DEVICE_TYPE in entry_data:
        #                 connection[CONF_LIGHT_DEVICE_TYPE] = entry_data[CONF_LIGHT_DEVICE_TYPE]
        #                 connection["random"] = time.time()
        #             _LOGGER.warning("扫描到连接匹配的网关，配置一改变，准备开始更新")
        #             self.hass.config_entries.async_update_entry(
        #                 entry,
        #                 data=connection,
        #             )
        #         else:
        #             _LOGGER.warning("扫描到连接匹配的网关，但配置没有变化，所以不更新")

        """When an available gateway connection is found, the configuration card is displayed"""
        if (not self._async_current_entries()
                and not scan_flag
                and connection[CONF_NAME] is not None
                and connection[CONF_BROKER] is not None
                and connection[CONF_PORT] is not None
                and connection[CONF_USERNAME] is not None
                and connection[CONF_PASSWORD] is not None):
            scan_flag = True
            return await self.async_step_option()

        return self.async_abort(reason="single_instance_allowed")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        """Only one integration instance is allowed to be added"""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_option()

    async def async_step_reconfigure(self, user_input=None):
        global reconfigure
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        reconfigure = True
        return await self.async_step_option()

    async def async_step_option(self, user_input=None):
        """Configure the lighting control method"""

        global light_device_type
        errors = {}

        if user_input is not None:
            if user_input[CONF_LIGHT_DEVICE_TYPE] == "单灯":
                light_device_type = "single"
            else:
                light_device_type = "group"
            if user_input["scanmode"] == "手动":
                return await self.async_step_manual()
            else:
                return await self.async_step_scan()

        fields = OrderedDict()
        fields[vol.Required(CONF_LIGHT_DEVICE_TYPE, default="灯组")] = vol.In(
            ["单灯", "灯组"])
        fields[vol.Required("scanmode", default="自动")] = vol.In(["自动", "手动"])

        return self.async_show_form(
            step_id="option",
            data_schema=vol.Schema(fields),
            errors=errors
        )

    async def async_step_scan(self, user_input=None):
        """Select a gateway from the list of discovered gateways to connect to"""
        global scan_flag
        global connection_dict
        global light_device_type
        global reconfigure
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            connection = connection_dict.get(name)
            if connection is not None:
                can_connect = self._try_mqtt_connect(connection)
                if can_connect:
                    connection[CONF_LIGHT_DEVICE_TYPE] = light_device_type
                    scan_flag = False
                    if reconfigure:
                        reconfigure = False
                        return self.async_update_reload_and_abort(
                            self.reauth_entry,
                            data=connection,
                        )
                    else:
                        """Create an integration based on selected configuration information"""
                        return self.async_create_entry(
                            title=connection[CONF_NAME], data=connection
                        )
                else:
                    errors["base"] = "cannot_connect"
            else:
                return self.async_abort(reason="select_error")

        """Search the LAN's gateway list"""
        scanner = MdnsScanner(self.hass)
        connection_dict = await scanner.scan_all(timeout=6.0)
        connection_name_list = []

        if connection_dict is not None:
            for connection_name in list(connection_dict.keys()):
                connection_name_list.append(connection_name)

        if len(connection_name_list) < 1:
            return self.async_abort(reason="not_found_device")

        fields = OrderedDict()
        fields[vol.Optional(CONF_NAME)] = vol.In(connection_name_list)

        return self.async_show_form(
            step_id="scan", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_envkey(self, user_input=None):
        global connection_dict
        errors = {}
        if user_input is not None:
            name = user_input[CONF_NAME]
            password = user_input[CONF_PASSWORD]
            url = user_input[CONF_URL]
            manufacturer = user_input["manufacturer"]
            if name == "manual":
                return await self.async_step_manual()

            hr = HttpRequest(self.hass, name, password, url, manufacturer)

            self.hass.data.setdefault("http_request", hr)

            # _LOGGER.warning("hass data %s",hr)
            await hr.start()

            connection_dict = await hr.get_envkey()

            if connection_dict is not None:
                if "code" in connection_dict:
                    errors["base"] = connection_dict["msg"]
                else:
                    return await self.async_step_token()
            else:

                return self.async_abort(reason="not_found_device")

        fields = OrderedDict()
        fields[vol.Required(CONF_URL, default="xxx.xxx.com")] = str
        fields[vol.Required("manufacturer", default="Xxxx")] = str
        fields[vol.Required(CONF_NAME, default="manual")] = str
        fields[vol.Required(CONF_PASSWORD, default="0")] = str

        return self.async_show_form(
            step_id="envkey", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_token(self, user_input=None):
        global connection_dict
        global temp_envkey
        global temp_place
        errors = {}
        connection = []
        connection_name_list = []
        if user_input is not None:
            envkey = user_input[CONF_ENVKEY]
            pattern = r"场所ID:(\w+)"
            match = re.search(pattern, envkey).group(1)
            connection = connection_dict.get(match)
            if connection is not None:
                temp_envkey = connection["token"]
                temp_place = connection["envKey"]
                return await self.async_step_manual()
            else:
                return self.async_abort(reason="select_error")

        if connection_dict is not None:
            for connection_name in list(connection_dict.keys()):
                connection_name_list.append(f"场所ID:{connection_name}  |  场所名称:{
                                            connection_dict[connection_name]['envName']}")

        # _LOGGER.warning("gateway list %s", connection_dict)

        fields = OrderedDict()
        fields[vol.Optional(CONF_ENVKEY)] = vol.In(connection_name_list)

        return self.async_show_form(
            step_id="token", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_manual(self, user_input=None):
        """Select a gateway from the list of discovered gateways to connect to"""
        global scan_flag
        global temp_envkey
        global temp_place
        global connection_dict
        global light_device_type
        global reconfigure
        errors = {}
        connection = []

        if user_input is not None:
            userid = user_input[CONF_ENVKEY]
            password = user_input[CONF_PASSWORD]
            place = user_input[CONF_PLACE]
            if CONF_ADDRESS not in user_input:
                address = None
            else:
                address = user_input[CONF_ADDRESS]
            connection = await sender_receiver(self.hass, userid, password, place, dest_address=address)

            if connection is not None and len(connection) == 10:

                can_connect = self._try_mqtt_connect(connection)
                if can_connect:
                    connection[CONF_LIGHT_DEVICE_TYPE] = light_device_type
                    scan_flag = False
                    """Create an integration based on selected configuration information"""
                    if reconfigure:
                        reconfigure = False
                        return self.async_update_reload_and_abort(
                            self.reauth_entry,
                            data=connection,
                        )
                    else:
                        return self.async_create_entry(
                            title=connection[CONF_NAME], data=connection
                        )
                else:
                    errors["base"] = "cannot_connect"
            elif len(connection) > 40:
                errors["base"] = f"新秘钥  {connection}"
            else:
                return self.async_abort(reason="not_found_device")

        """Search the LAN's gateway list"""

        fields = OrderedDict()
        fields[vol.Required(CONF_PLACE, default=temp_place)] = str
        fields[vol.Required(CONF_ENVKEY, default=temp_envkey)] = str
        fields[vol.Required(CONF_PASSWORD, default=temp_envpassword)] = str
        fields[vol.Optional(CONF_ADDRESS)] = str

        return self.async_show_form(
            step_id="manual", data_schema=vol.Schema(fields), errors=errors
        )

    def _try_mqtt_connect(self, connection):
        return self.hass.async_add_executor_job(
            try_connection,
            self.hass,
            connection[CONF_BROKER],
            connection[CONF_PORT],
            connection[CONF_USERNAME],
            connection[CONF_PASSWORD],
        )


def try_connection(hass, broker, port, username, password, protocol="3.1.1"):
    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
