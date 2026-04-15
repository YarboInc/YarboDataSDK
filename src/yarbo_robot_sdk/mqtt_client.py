"""MQTT client — connection, subscription, callback dispatch, auto-reconnect."""

import logging
import time as _time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

import paho.mqtt.client as mqtt

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.config import MQTT_KEEPALIVE
from yarbo_robot_sdk.exceptions import MqttConnectionError

# Default client_id prefix — used by HA integration.
DEFAULT_CLIENTID_PREFIX = "HA_"


class MqttClient:
    """Manages MQTT connection using HTTP AUTH (username=JWT, password="")."""

    def __init__(
        self,
        auth_manager: AuthManager,
        host: str,
        port: int,
        use_tls: bool = True,
        keepalive: int = MQTT_KEEPALIVE,
        client_id_prefix: str = DEFAULT_CLIENTID_PREFIX,
    ):
        self._auth = auth_manager
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._keepalive = keepalive
        self._client_id_prefix = client_id_prefix
        self._client: mqtt.Client | None = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._connected = False

    def connect(self) -> None:
        """Establish MQTT connection. username=JWT, password=""."""
        if not self._auth.is_authenticated:
            raise MqttConnectionError("Not authenticated. Call login() first.")

        try:
            client_id = (
                f"{self._client_id_prefix}"
                f"{self._auth.username}_{int(_time.time())}"
            )
            self._client = mqtt.Client(
                client_id=client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
            self._client.username_pw_set(
                username=self._auth.token,
                password="",
            )

            if self._use_tls:
                self._client.tls_set()

            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            self._client.reconnect_delay_set(min_delay=1, max_delay=60)
            self._client.connect(self._host, self._port, self._keepalive)
            self._client.loop_start()
        except Exception as exc:
            raise MqttConnectionError(f"MQTT connection failed: {exc}") from exc

    def subscribe(self, topic: str, callback: Callable[[str, bytes], Any]) -> None:
        """Subscribe to a topic and register a callback.

        SDK does not validate topic format — unsupported topics will be
        rejected by EMQX ACL on the server side.
        """
        if self._client is None:
            raise MqttConnectionError("MQTT not connected. Call mqtt_connect() first.")

        if topic not in self._callbacks:
            self._callbacks[topic] = []
            self._client.subscribe(topic)
        self._callbacks[topic].append(callback)

    def publish(self, topic: str, payload: bytes, qos: int = 0) -> None:
        """Publish a message to an MQTT topic.

        Args:
            topic: MQTT topic string.
            payload: Raw bytes to publish.
            qos: Quality of service level (default 0 = AT_MOST_ONCE).

        Raises:
            MqttConnectionError: If not connected.
        """
        if self._client is None:
            raise MqttConnectionError("MQTT not connected. Call mqtt_connect() first.")
        self._client.publish(topic, payload, qos)

    def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic and remove all its callbacks."""
        if self._client is None:
            raise MqttConnectionError("MQTT not connected.")

        self._client.unsubscribe(topic)
        self._callbacks.pop(topic, None)

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        """On connect/reconnect, re-subscribe to all registered topics."""
        if isinstance(rc, int):
            success = rc == 0
        elif hasattr(rc, "is_failure"):
            success = not rc.is_failure
        else:
            success = rc == 0

        if success:
            self._connected = True
            logger.info(f"MQTT connected (rc={rc})")
            for topic in self._callbacks:
                client.subscribe(topic)
        else:
            logger.warning(f"MQTT connect failed (rc={rc})")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        self._connected = False
        logger.warning(f"MQTT disconnected (rc={rc})")
        # rc != 0 means unexpected disconnect (possibly token expired, kicked by EMQX)
        if rc != 0:
            try:
                self._auth.refresh()
                client.username_pw_set(
                    username=self._auth.token,
                    password="",
                )
                # paho will auto-reconnect via loop_start background thread
            except Exception:
                pass  # Refresh failed; will retry on next reconnect attempt

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Dispatch incoming message to matching topic callbacks."""
        for registered_topic, callbacks in self._callbacks.items():
            if mqtt.topic_matches_sub(registered_topic, msg.topic):
                for cb in callbacks:
                    cb(msg.topic, msg.payload)
