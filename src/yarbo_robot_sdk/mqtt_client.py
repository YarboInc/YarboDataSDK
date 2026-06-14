"""MQTT client — connection, subscription, callback dispatch, auto-reconnect."""

import logging
import secrets
import threading
import time as _time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

import paho.mqtt.client as mqtt

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.config import MQTT_KEEPALIVE
from yarbo_robot_sdk.exceptions import MqttConnectionError

# Default client_id prefix — used by HA integration.
DEFAULT_CLIENTID_PREFIX = "HA_"


class CredentialsProvider(ABC):
    """Strategy for MQTT client_id + (username, password) and post-refresh values.

    Two concrete implementations exist:
      * ``LegacyCredentialsProvider`` — old shared EMQX broker. username=JWT,
        password="", client_id=``HA_{email}_{unix_ts}``.
      * ``NewBrokerCredentialsProvider`` — new EMQX Dedicated broker.
        username=email, password=JWT, client_id=``HA_{email}_{rand4}``.

    The provider is injected into ``MqttClient`` so the transport layer remains
    broker-agnostic and the two routing paths can share the same code.
    """

    @abstractmethod
    def client_id(self) -> str:
        """Generate a fresh client_id for a new MQTT connection."""

    @abstractmethod
    def initial_credentials(self) -> tuple[str, str]:
        """Return ``(username, password)`` for the first connection attempt."""

    @abstractmethod
    def credentials_after_refresh(self) -> tuple[str, str]:
        """Return ``(username, password)`` after ``AuthManager.refresh()``."""


class LegacyCredentialsProvider(CredentialsProvider):
    """Old broker: HTTP AUTH via username=JWT, password=""."""

    def __init__(self, auth: AuthManager):
        self._auth = auth

    def client_id(self) -> str:
        # Append a random suffix in addition to the timestamp: rapid reconnects
        # within the same second would otherwise collide on client_id, and the
        # broker kicks the older session — producing connect/disconnect churn.
        rand4 = f"{secrets.randbelow(10000):04d}"
        return (
            f"{DEFAULT_CLIENTID_PREFIX}{self._auth.username}"
            f"_{int(_time.time())}_{rand4}"
        )

    def initial_credentials(self) -> tuple[str, str]:
        return (self._auth.token or "", "")

    def credentials_after_refresh(self) -> tuple[str, str]:
        return (self._auth.token or "", "")


class NewBrokerCredentialsProvider(CredentialsProvider):
    """New EMQX Dedicated broker: username=email, password=JWT."""

    def __init__(self, auth: AuthManager):
        self._auth = auth

    def client_id(self) -> str:
        rand4 = f"{secrets.randbelow(10000):04d}"
        return f"{DEFAULT_CLIENTID_PREFIX}{self._auth.username}_{rand4}"

    def initial_credentials(self) -> tuple[str, str]:
        return (self._auth.username or "", self._auth.token or "")

    def credentials_after_refresh(self) -> tuple[str, str]:
        return (self._auth.username or "", self._auth.token or "")


class MqttClient:
    """Manages an MQTT connection. Credentials and client_id come from a
    ``CredentialsProvider`` so a single transport supports multiple brokers.
    """

    def __init__(
        self,
        auth_manager: AuthManager,
        host: str,
        port: int,
        use_tls: bool = True,
        keepalive: int = MQTT_KEEPALIVE,
        client_id_prefix: str = DEFAULT_CLIENTID_PREFIX,
        credentials_provider: CredentialsProvider | None = None,
        name: str = "mqtt",
    ):
        self._auth = auth_manager
        # Human-readable broker label (e.g. "legacy" / "new") used to make
        # connection logs distinguishable when two brokers run side by side.
        self._name = name
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._keepalive = keepalive
        # ``client_id_prefix`` is retained for backward compatibility with tests
        # that pass a custom prefix. It is honoured only when no explicit
        # ``credentials_provider`` is supplied (i.e. the default legacy path).
        self._client_id_prefix = client_id_prefix
        self._credentials: CredentialsProvider = (
            credentials_provider
            if credentials_provider is not None
            else LegacyCredentialsProvider(auth_manager)
        )
        self._client: mqtt.Client | None = None
        self._callbacks: dict[str, list[Callable]] = {}
        # Guards _callbacks. Mutated by subscribe()/unsubscribe() on caller
        # (executor) threads, and iterated by _on_connect()/_on_message() on
        # paho's network thread. Without this, a concurrent subscribe during a
        # reconnect raised "dictionary changed size during iteration" and broke
        # the connection. Snapshots are taken under the lock; callbacks run
        # outside it so a callback may safely (re)subscribe.
        self._callbacks_lock = threading.Lock()
        self._connected = False

    def connect(self) -> None:
        """Establish MQTT connection using the configured credentials provider."""
        if not self._auth.is_authenticated:
            raise MqttConnectionError("Not authenticated. Call login() first.")

        # Tear down any existing client first so a reconnect attempt never
        # leaves an orphaned paho loop_start() thread auto-reconnecting in the
        # background. Without this, repeated connect() calls (e.g. from
        # _ensure_*_mqtt while is_connected is briefly False) accumulate
        # multiple live connections to the same broker.
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._connected = False

        try:
            client_id = self._credentials.client_id()
            # Honour the legacy ``client_id_prefix`` constructor arg if a caller
            # overrode it AND we're using the default legacy provider.
            if (
                isinstance(self._credentials, LegacyCredentialsProvider)
                and self._client_id_prefix != DEFAULT_CLIENTID_PREFIX
            ):
                rand4 = f"{secrets.randbelow(10000):04d}"
                client_id = (
                    f"{self._client_id_prefix}"
                    f"{self._auth.username}_{int(_time.time())}_{rand4}"
                )

            username, password = self._credentials.initial_credentials()
            logger.info(
                "MQTT[%s] connecting → %s:%s (tls=%s) client_id=%s",
                self._name,
                self._host,
                self._port,
                self._use_tls,
                client_id,
            )
            self._client = mqtt.Client(
                client_id=client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
            self._client.username_pw_set(
                username=username,
                password=password,
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

        with self._callbacks_lock:
            is_new = topic not in self._callbacks
            if is_new:
                self._callbacks[topic] = []
            self._callbacks[topic].append(callback)
        # Talk to the broker outside the lock so network I/O never blocks
        # _on_message/_on_connect waiting on the same lock.
        if is_new:
            self._client.subscribe(topic)
            logger.info("MQTT[%s] subscribe → %s", self._name, topic)

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
        with self._callbacks_lock:
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
            with self._callbacks_lock:
                topics = list(self._callbacks)
            logger.info(
                "MQTT[%s] connected to %s:%s (rc=%s); re-subscribing %d topic(s)",
                self._name,
                self._host,
                self._port,
                rc,
                len(topics),
            )
            for topic in topics:
                client.subscribe(topic)
        else:
            logger.warning(
                "MQTT[%s] connect failed to %s:%s (rc=%s)",
                self._name,
                self._host,
                self._port,
                rc,
            )

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int | mqtt.ReasonCode,
        properties: Any = None,
    ) -> None:
        self._connected = False
        logger.warning(
            "MQTT[%s] disconnected from %s:%s (rc=%s)",
            self._name,
            self._host,
            self._port,
            rc,
        )
        # rc != 0 means unexpected disconnect (possibly token expired, kicked by EMQX)
        if rc != 0:
            try:
                self._auth.refresh()
                username, password = self._credentials.credentials_after_refresh()
                client.username_pw_set(
                    username=username,
                    password=password,
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
        # Snapshot under the lock (copying each callback list too) so a
        # concurrent subscribe()/unsubscribe() can't mutate what we iterate.
        # Callbacks run outside the lock — they may re-subscribe.
        with self._callbacks_lock:
            snapshot = [
                (topic, list(callbacks))
                for topic, callbacks in self._callbacks.items()
            ]
        for registered_topic, callbacks in snapshot:
            if mqtt.topic_matches_sub(registered_topic, msg.topic):
                for cb in callbacks:
                    cb(msg.topic, msg.payload)
