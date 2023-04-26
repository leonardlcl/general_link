"""Constants used by multiple MQTT modules."""

DOMAIN = "general_link"

MANUFACTURER = "GeneralLink"

CONF_BROKER = "broker"

CONF_LIGHT_DEVICE_TYPE = "light_device_type"

FLAG_IS_INITIALIZED = "flag_is_initialized"

CACHE_ENTITY_STATE_UPDATE_KEY_DICT = "general_link_entity_state_update_dict"

EVENT_ENTITY_STATE_UPDATE = "general_link_entity_state_update_{}"

EVENT_ENTITY_REGISTER = "general_link_entity_register_{}"

MQTT_CLIENT_INSTANCE = "mqtt_client_instance"

MQTT_TOPIC_PREFIX = DOMAIN

DEVICE_COUNT_MAX = 100

MDNS_SCAN_SERVICE = "_mqtt._tcp.local."

PLATFORMS: list[str] = [
    "cover",
    "light",
    "scene",
    "switch",
    "climate",
    "media_player"
]
