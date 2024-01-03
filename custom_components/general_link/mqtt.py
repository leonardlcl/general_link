import asyncio
import logging
import random
import time
from functools import lru_cache
from typing import Any, Iterable, Callable

from homeassistant.components.mqtt import MQTT_DISCONNECTED, PublishPayloadType, ReceiveMessage, CONF_KEEPALIVE, \
    MQTT_CONNECTED
from homeassistant.components.mqtt.client import _raise_on_error, TIMEOUT_ACK, SubscribePayloadType, Subscription, \
    _matcher_for_topic
from homeassistant.components.mqtt.models import AsyncMessageCallbackType, MessageCallbackType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback, HassJob
from homeassistant.exceptions import HomeAssistantError
from operator import attrgetter
from itertools import groupby
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from paho.mqtt import client
from paho.mqtt.client import MQTTMessage

from .const import CONF_BROKER

_LOGGER = logging.getLogger(__name__)


def _raise_on_errors(result_codes: Iterable[int | None]) -> None:
    """Raise error if error result."""
    # pylint: disable-next=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if messages := [
        mqtt.error_string(result_code)
        for result_code in result_codes
        if result_code != 0
    ]:
        raise HomeAssistantError(f"Error talking to MQTT: {', '.join(messages)}")


class MqttClient:

    def __init__(
            self,
            hass: HomeAssistant,
            config_entry: ConfigEntry,
            conf: ConfigType,
    ) -> None:
        self._client = client.Client(f'python-mqtt-{random.randint(0, 1000)}')
        self.hass = hass
        self.config_entry = config_entry
        self.conf = conf
        self._broker = conf[CONF_BROKER]
        self._port = conf[CONF_PORT]
        self._username = conf[CONF_USERNAME]
        self._password = conf[CONF_PASSWORD]
        self.connected = False
        self._pending_operations: dict[int, asyncio.Event] = {}
        self.subscriptions: list[Subscription] = []
        self._pending_operations_condition = asyncio.Condition()
        self._client.username_pw_set(self._username, password=self._password)
        self._paho_lock = asyncio.Lock()

    def init_client(self) -> None:
        """Initialize paho client."""
        self._client.on_connect = self._mqtt_on_connect
        self._client.on_disconnect = self._mqtt_on_disconnect
        self._client.on_message = self._mqtt_on_message
        self._client.on_publish = self._mqtt_on_callback
        self._client.on_subscribe = self._mqtt_on_callback
        self._client.on_unsubscribe = self._mqtt_on_callback

    async def async_connect(self):
        """Connect to the host. Does not process messages yet."""
        # pylint: disable-next=import-outside-toplevel
        self._username = self.conf[CONF_USERNAME]
        self._password = self.conf[CONF_PASSWORD]
        self._client.username_pw_set(self._username, password=self._password)
        result: int | None = None
        try:
            result = await self.hass.async_add_executor_job(
                self._client.connect,
                self.conf[CONF_BROKER],
                self.conf[CONF_PORT],
                self.conf[CONF_KEEPALIVE],
            )
        except OSError as err:
            _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)

        if result is not None and result != 0:
            _LOGGER.error(
                "Failed to connect to MQTT server: %s", client.error_string(result)
            )

        self._client.loop_start()

    async def async_disconnect(self) -> None:
        """Stop the MQTT client."""

        def stop() -> None:
            """Stop the MQTT client."""
            # Do not disconnect, we want the broker to always publish will
            self._client.loop_stop()

        def no_more_acks() -> bool:
            """Return False if there are unprocessed ACKs."""
            return not bool(self._pending_operations)

        # wait for ACKs to be processed
        async with self._pending_operations_condition:
            await self._pending_operations_condition.wait_for(no_more_acks)

        # stop the MQTT loop
        async with self._paho_lock:
            await self.hass.async_add_executor_job(stop)

    def _mqtt_on_connect(
            self, _mqttc: client, _userdata: None, _flags: dict[str, Any], result_code: int
    ) -> None:
        """On connect callback.

        Resubscribe to all topics we were subscribed to and publish birth
        message.
        """

        if result_code != client.CONNACK_ACCEPTED:
            _LOGGER.error(
                "Unable to connect to the MQTT broker: %s",
                client.connack_string(result_code),
            )
            return

        self.connected = True
        dispatcher_send(self.hass, MQTT_CONNECTED)
        _LOGGER.warning(
            "Connected to MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf[CONF_PORT],
            result_code,
        )

        # Group subscriptions to only re-subscribe once for each topic.
        keyfunc = attrgetter("topic")
        self.hass.add_job(
            self._async_perform_subscriptions,
            [
                # Re-subscribe with the highest requested qos
                (topic, max(subscription.qos for subscription in subs))
                for topic, subs in groupby(
                sorted(self.subscriptions, key=keyfunc), keyfunc
            )
            ],
        )

    async def async_subscribe(
            self,
            topic: str,
            msg_callback: AsyncMessageCallbackType | MessageCallbackType,
            qos: int,
            encoding: str | None = None,
    ) -> Callable[[], None]:
        """Set up a subscription to a topic with the provided qos.

        This method is a coroutine.
        """
        if not isinstance(topic, str):
            raise HomeAssistantError("Topic needs to be a string!")

        subscription = Subscription(
            topic, _matcher_for_topic(topic), HassJob(msg_callback), qos, encoding
        )
        self.subscriptions.append(subscription)
        self._matching_subscriptions.cache_clear()

        # Only subscribe if currently connected.
        if self.connected:
            self._last_subscribe = time.time()
            await self._async_perform_subscriptions(((topic, qos),))

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            if subscription not in self.subscriptions:
                raise HomeAssistantError("Can't remove subscription twice")
            self.subscriptions.remove(subscription)
            self._matching_subscriptions.cache_clear()

            # Only unsubscribe if currently connected
            if self.connected:
                self.hass.async_create_task(self._async_unsubscribe(topic))

        return async_remove

    async def _async_perform_subscriptions(
            self, subscriptions: Iterable[tuple[str, int]]
    ) -> None:
        """Perform MQTT client subscriptions."""

        def _process_client_subscriptions() -> list[tuple[int, int]]:
            """Initiate all subscriptions on the MQTT client and return the results."""
            subscribe_result_list = []
            for topic, qos in subscriptions:
                result, mid = self._client.subscribe(topic, qos)
                subscribe_result_list.append((result, mid))
                _LOGGER.debug("Subscribing to %s, mid: %s", topic, mid)
            return subscribe_result_list

        async with self._paho_lock:
            results = await self.hass.async_add_executor_job(
                _process_client_subscriptions
            )

        tasks = []
        errors = []
        for result, mid in results:
            if result == 0:
                tasks.append(self._wait_for_mid(mid))
            else:
                errors.append(result)

        if tasks:
            await asyncio.gather(*tasks)
        if errors:
            _raise_on_errors(errors)

    def _mqtt_on_disconnect(
            self, _mqttc: client, _userdata: None, result_code: int
    ) -> None:
        """Disconnected callback."""
        _LOGGER.warning("Disconnected ===============================================================")
        self.connected = False
        dispatcher_send(self.hass, MQTT_DISCONNECTED)
        _LOGGER.warning(
            "Disconnected from MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf[CONF_PORT],
            result_code,
        )

    def _mqtt_on_message(
            self, _mqttc: client, _userdata: None, msg: MQTTMessage
    ) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    async def _async_unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic.

        This method is a coroutine.
        """

        def _client_unsubscribe(topic: str) -> int:
            result: int | None = None
            mid: int | None = None
            result, mid = self._client.unsubscribe(topic)
            _LOGGER.debug("Unsubscribing from %s, mid: %s", topic, mid)
            _raise_on_error(result)
            assert mid
            return mid

        if any(other.topic == topic for other in self.subscriptions):
            # Other subscriptions on topic remaining - don't unsubscribe.
            return

        async with self._paho_lock:
            mid = await self.hass.async_add_executor_job(_client_unsubscribe, topic)
            await self._register_mid(mid)

        self.hass.async_create_task(self._wait_for_mid(mid))

    @lru_cache(2048)
    def _matching_subscriptions(self, topic: str) -> list[Subscription]:
        subscriptions: list[Subscription] = []
        for subscription in self.subscriptions:
            if subscription.matcher(topic):
                subscriptions.append(subscription)
        return subscriptions

    @callback
    def _mqtt_handle_message(self, msg: MQTTMessage) -> None:
        _LOGGER.debug(
            "Received%s message on %s: %s",
            " retained" if msg.retain else "",
            msg.topic,
            msg.payload[0:8192],
        )
        timestamp = dt_util.utcnow()

        subscriptions = self._matching_subscriptions(msg.topic)

        for subscription in subscriptions:

            payload: SubscribePayloadType = msg.payload
            if subscription.encoding is not None:
                try:
                    payload = msg.payload.decode(subscription.encoding)
                except (AttributeError, UnicodeDecodeError):
                    _LOGGER.warning(
                        "Can't decode payload %s on %s with encoding %s (for %s)",
                        msg.payload[0:8192],
                        msg.topic,
                        subscription.encoding,
                        subscription.job,
                    )
                    continue
            self.hass.async_run_hass_job(
                subscription.job,
                ReceiveMessage(
                    msg.topic,
                    payload,
                    msg.qos,
                    msg.retain,
                    subscription.topic,
                    timestamp,
                ),
            )

    def _mqtt_on_callback(
            self,
            _mqttc: client,
            _userdata: None,
            mid: int,
            _granted_qos: tuple[Any, ...] | None = None,
    ) -> None:
        """Publish / Subscribe / Unsubscribe callback."""
        self.hass.add_job(self._mqtt_handle_mid, mid)

    async def _mqtt_handle_mid(self, mid: int) -> None:
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        await self._register_mid(mid)
        self._pending_operations[mid].set()

    async def async_publish(
            self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish a MQTT message."""
        async with self._paho_lock:
            msg_info = await self.hass.async_add_executor_job(
                self._client.publish, topic, payload, qos, retain
            )
            _raise_on_error(msg_info.rc)
        await self._wait_for_mid(msg_info.mid)

    async def _wait_for_mid(self, mid: int) -> None:
        """Wait for ACK from broker."""
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        await self._register_mid(mid)
        try:
            await asyncio.wait_for(self._pending_operations[mid].wait(), TIMEOUT_ACK)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "No ACK from MQTT server in %s seconds (mid: %s)", TIMEOUT_ACK, mid
            )
        finally:
            async with self._pending_operations_condition:
                # Cleanup ACK sync buffer
                del self._pending_operations[mid]
                self._pending_operations_condition.notify_all()

    async def _register_mid(self, mid: int) -> None:
        """Create Event for an expected ACK."""
        async with self._pending_operations_condition:
            if mid not in self._pending_operations:
                self._pending_operations[mid] = asyncio.Event()
