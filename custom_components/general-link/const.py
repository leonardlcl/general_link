"""Constants used by multiple MQTT modules."""

DOMAIN = "general-link"

CONF_BROKER = "broker"

CONF_LIGHT_DEVICE_TYPE = "light_device_type"

FLAG_IS_INITIALIZED = "flag_is_initialized"

CACHE_ENTITY_STATE_UPDATE_KEY_DICT = "general-link_entity_state_update_dict"

EVENT_ENTITY_STATE_UPDATE = "general-link_entity_state_update_{}"

EVENT_ENTITY_REGISTER = "general-link_entity_register_{}"

MQTT_CLIENT_INSTANCE = "mqtt_client_instance"

MQTT_TOPIC_PREFIX = DOMAIN

DEVICE_COUNT_MAX = 100

PLATFORMS: list[str] = [
    "cover",
    "light",
    "scene",
    "climate"
]
