"""YarboClient — main SDK entry point."""

import json
import logging
import threading

_LOGGER = logging.getLogger(__name__)

from yarbo_robot_sdk import endpoints
from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.codec import (
    decode_mqtt_payload,
    encode_mqtt_payload,
    parse_version,
    should_compress,
)
from yarbo_robot_sdk.config import DEFAULT_API_BASE_URL
from yarbo_robot_sdk.config_provider import ConfigProvider
from yarbo_robot_sdk.device_helpers import (
    resolve_device_msg_topic,
    resolve_topic_by_name,
)
from yarbo_robot_sdk.device_registry import resolve_control_topic
from yarbo_robot_sdk.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    YarboSDKError,
)
from yarbo_robot_sdk.migration_client import EmqxMigrationClient
from yarbo_robot_sdk.models import Device
from yarbo_robot_sdk.modules import (
    BlowerModule,
    BoundYarboDevice,
    CoreModule,
    MowerModule,
    PlowModule,
    SmartAssistModule,
    SnowBlowerModule,
    TrimmerModule,
)
from yarbo_robot_sdk.mqtt_client import (
    LegacyCredentialsProvider,
    MqttClient,
    NewBrokerCredentialsProvider,
)
from yarbo_robot_sdk.public_types import (
    CommandPayload,
    DataFeedbackCallback,
    DeviceData,
    RawMqttCallback,
    StatusCallback,
)
from yarbo_robot_sdk.rest_client import RestClient


class YarboClient:
    """Yarbo Robot SDK client.

    Usage::

        # Dev — pass all config explicitly
        client = YarboClient(
            api_base_url="https://api.yarbo.com",
            mqtt_host="mqtt.yarbo.com",
            mqtt_port=8883,
            rsa_public_key="-----BEGIN PUBLIC KEY-----\\n..."
        )

        # Production — only api_base_url required, rest fetched from cloud
        client = YarboClient(api_base_url="https://api.yarbo.com")

        client.login("user@email.com", "password")
        devices = client.get_devices()

        client.mqtt_connect()
        client.subscribe_device_message("SN123", "snowbot", my_callback)
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        mqtt_host: str | None = None,
        mqtt_port: int | None = None,
        mqtt_use_tls: bool | None = None,
        rsa_public_key: str | None = None,
        new_mqtt_host: str | None = None,
        new_mqtt_port: int | None = None,
        new_mqtt_use_tls: bool | None = None,
        emqx_migration_query_url: str | None = None,
    ):
        self._config = ConfigProvider(
            api_base_url=api_base_url or DEFAULT_API_BASE_URL,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_use_tls=mqtt_use_tls,
            rsa_public_key=rsa_public_key,
            new_mqtt_host=new_mqtt_host,
            new_mqtt_port=new_mqtt_port,
            new_mqtt_use_tls=new_mqtt_use_tls,
            emqx_migration_query_url=emqx_migration_query_url,
        )

        _api_base = self._config.get("api_base_url")
        if not _api_base:
            raise YarboSDKError("api_base_url is required")

        _rsa_key = self._config.get("rsa_public_key")
        if not _rsa_key:
            raise YarboSDKError(
                "rsa_public_key is required: pass via constructor or ensure cloud config provides it"
            )

        self._api_base_url = _api_base
        self._auth = AuthManager(_api_base, _rsa_key)
        self._rest = RestClient(self._auth, _api_base)

        # MQTT router: at most two connections, one per broker. Lazily
        # established on the first per-SN subscribe / publish.
        self._migration = EmqxMigrationClient(
            query_url=self._config.get("emqx_migration_query_url"),
            auth_manager=self._auth,
        )
        self._legacy_mqtt: MqttClient | None = None
        self._new_mqtt: MqttClient | None = None

        # Per-device firmware version cache: {sn: (major, minor, patch)}
        self._firmware_versions: dict[str, tuple[int, int, int]] = {}

        # data_feedback listeners: {sn: [(topic_filter, callback), ...]}
        self._feedback_listeners: dict[
            str, list[tuple[str, DataFeedbackCallback]]
        ] = {}
        self._feedback_lock = threading.Lock()

        # Typed module facades. These keep the public API explicit about Yarbo's
        # Core + attachment architecture while reusing the existing transport.
        self.core = CoreModule(self)
        self.snow_bot = self.core
        self.mower = MowerModule(self)
        self.snow_blower = SnowBlowerModule(self)
        self.blower = BlowerModule(self)
        self.trimmer = TrimmerModule(self)
        self.plow = PlowModule(self)
        self.sam = SmartAssistModule(self)

    # --- Auth ---

    def login(self, username: str, password: str) -> None:
        """Login with username and password (password is RSA-encrypted internally)."""
        self._auth.login(username, password)

    def restore_session(self, username: str, token: str, refresh_token: str) -> None:
        """Restore a previous session from saved tokens (no login needed)."""
        self._auth.restore(username, token, refresh_token)

    @property
    def token(self) -> str | None:
        """Current JWT token. Host apps can read this for persistence."""
        return self._auth.token

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token. Host apps can read this for persistence."""
        return self._auth.refresh_token

    # --- REST API ---

    def get_devices(self) -> list[Device]:
        """Get all devices linked to the current account."""
        data = self._rest.get(endpoints.DEVICES_LIST)
        return [Device(**d) for d in data["devices"]]

    def device(
        self, device: Device, data: DeviceData | None = None
    ) -> BoundYarboDevice:
        """Return a typed module hierarchy bound to one device.

        This lets callers use module-specific APIs without repeatedly passing
        the device serial number and type ID, e.g.
        ``client.device(device).mower.set_blade_height(60)``.

        Pass the latest DeviceMSG-like payload as ``data`` to enable SDK-side
        head/module compatibility checks for attachment-specific commands.
        """
        return BoundYarboDevice(self, device, data)

    # --- MQTT ---

    def mqtt_connect(self) -> None:
        """Initialise the MQTT router. Lazy: no network call here.

        Actual TCP / TLS / MQTT connections are established on the first
        per-SN ``subscribe_*`` or ``mqtt_publish_command``. The call is kept
        for backward compatibility with the HA coordinator and is a no-op
        when invoked multiple times.
        """
        # No-op by design. The router decides which broker(s) to connect to
        # only once it knows the target SN (legacy vs new EMQX cluster).
        return

    def _ensure_legacy_mqtt(self) -> MqttClient:
        """Get or create the legacy-broker MqttClient, connecting if needed."""
        if self._legacy_mqtt is None:
            mqtt_host = self._config.get("mqtt_host")
            mqtt_port = self._config.get("mqtt_port")
            mqtt_use_tls = self._config.get("mqtt_use_tls")
            if not mqtt_host or not mqtt_port:
                raise YarboSDKError(
                    "legacy broker config missing: "
                    "mqtt_host/mqtt_port not provided via constructor or /sdk/config"
                )
            self._legacy_mqtt = MqttClient(
                auth_manager=self._auth,
                host=mqtt_host,
                port=mqtt_port,
                use_tls=mqtt_use_tls if mqtt_use_tls is not None else True,
                credentials_provider=LegacyCredentialsProvider(self._auth),
                name="legacy",
            )
            self._wire_disconnect_invalidation(self._legacy_mqtt)
        if not self._legacy_mqtt.is_connected:
            self._legacy_mqtt.connect()
        return self._legacy_mqtt

    def _ensure_new_mqtt(self) -> MqttClient:
        """Get or create the new-broker MqttClient. Refreshes token first to
        avoid the new EMQX Dedicated cluster rejecting an expired JWT.
        """
        if self._new_mqtt is None:
            new_host = self._config.get("new_mqtt_host")
            new_port = self._config.get("new_mqtt_port")
            new_use_tls = self._config.get("new_mqtt_use_tls")
            self._new_mqtt = MqttClient(
                auth_manager=self._auth,
                host=new_host,
                port=new_port,
                use_tls=new_use_tls if new_use_tls is not None else True,
                credentials_provider=NewBrokerCredentialsProvider(self._auth),
                name="new",
            )
            self._wire_disconnect_invalidation(self._new_mqtt)
        if not self._new_mqtt.is_connected:
            # New broker won't accept an expired token at connect time, so
            # proactively refresh. Already-established sessions are not
            # affected by token expiry (EMQX does not actively kick them).
            try:
                self._auth.refresh()
            except TokenExpiredError:
                # Let connect() bubble up the authentication failure so the
                # host (HA) can drive the reauth flow.
                pass
            except YarboSDKError:
                pass
            self._new_mqtt.connect()
        return self._new_mqtt

    def _ensure_mqtt_for(self, sn: str) -> MqttClient:
        """Pick a broker for ``sn`` based on its migration status and return
        an already-connected MqttClient.
        """
        if not self._auth.is_authenticated:
            raise YarboSDKError("Not authenticated. Call login() first.")
        migrated = self._migration.query(sn)
        _LOGGER.info(
            "MQTT route sn=%s -> %s broker", sn, "new" if migrated else "legacy"
        )
        return self._ensure_new_mqtt() if migrated else self._ensure_legacy_mqtt()

    def _wire_disconnect_invalidation(self, mqtt: MqttClient) -> None:
        """Wrap an MqttClient's ``_on_disconnect`` to invalidate the migration
        cache on unexpected disconnects so the next subscribe / publish
        re-queries every SN's migration status.
        """
        original = mqtt._on_disconnect

        def wrapped(client, userdata, flags, rc, properties=None):
            try:
                original(client, userdata, flags, rc, properties)
            finally:
                if rc != 0:
                    self._migration.invalidate_all()

        mqtt._on_disconnect = wrapped  # type: ignore[assignment]
        if mqtt._client is not None:
            mqtt._client.on_disconnect = wrapped

    def mqtt_disconnect(self) -> None:
        """Disconnect both brokers (if any) and clear the migration cache."""
        for client in (self._legacy_mqtt, self._new_mqtt):
            if client is not None:
                client.disconnect()
        self._migration.invalidate_all()

    # --- High-level device methods ---

    def subscribe_device_message(
        self,
        sn: str,
        type_id: str,
        callback: StatusCallback,
    ) -> None:
        """Subscribe to device real-time message (snowbot/{sn}/device/DeviceMSG).

        Callback receives (topic: str, data: dict) where data is the parsed JSON payload.
        Automatically decompresses zlib-compressed messages and falls back to plaintext.
        Also extracts and caches the device firmware version from the 'version' field.
        """
        topic = resolve_device_msg_topic(sn, type_id)

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}
                callback(topic_str, data)
                return
            # Auto-extract and cache firmware version
            version_str = data.get("version", "")
            if version_str:
                parsed = parse_version(str(version_str))
                if parsed is not None:
                    self._firmware_versions[sn] = parsed
            callback(topic_str, data)

        self._ensure_mqtt_for(sn).subscribe(topic, _wrapper)

    def subscribe_heart_beat(
        self,
        sn: str,
        type_id: str,
        callback: StatusCallback,
    ) -> None:
        """Subscribe to device heart beat topic (snowbot/{sn}/device/heart_beat).

        Callback receives (topic: str, data: dict) where data is the parsed payload,
        e.g. {"working_state": 0}. Automatically handles zlib-compressed messages.
        """
        topic = resolve_topic_by_name(sn, type_id, "heart_beat")

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}
            callback(topic_str, data)

        self._ensure_mqtt_for(sn).subscribe(topic, _wrapper)

    def subscribe_data_feedback(
        self,
        sn: str,
        type_id: str,
        callback: DataFeedbackCallback | None = None,
    ) -> None:
        """Subscribe to device data_feedback topic (snowbot/{sn}/device/data_feedback).

        This topic receives responses to app commands (e.g. read_gps_ref).
        Response format: {"topic": "...", "msg": "...", "state": 0, "data": {...}}

        The callback receives (topic: str, data: dict). Internally, messages are
        also dispatched to one-time listeners registered by request_with_feedback().

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            callback: Optional callback for all data_feedback messages.
        """
        topic = resolve_topic_by_name(sn, type_id, "data_feedback")

        def _wrapper(topic_str: str, payload: bytes) -> None:
            try:
                data = decode_mqtt_payload(payload)
            except Exception:
                data = {"_raw": payload.decode(errors="replace")}

            # Dispatch to one-time listeners registered by request_with_feedback
            response_topic = data.get("topic", "")
            with self._feedback_lock:
                listeners = self._feedback_listeners.get(sn, [])
                for topic_filter, listener_cb in listeners:
                    if topic_filter == response_topic:
                        listener_cb(topic_str, data)

            # Also invoke the general callback if provided
            if callback is not None:
                callback(topic_str, data)

        self._ensure_mqtt_for(sn).subscribe(topic, _wrapper)

    def subscribe_topic(
        self,
        sn: str,
        topic: str,
        callback: RawMqttCallback,
    ) -> None:
        """Subscribe to an arbitrary device topic on its MQTT connection.

        Lower-level than the named subscribe_* helpers: the caller supplies the
        full topic string and the callback receives the raw
        ``(topic_str, payload_bytes)`` — no decoding. Use for device push
        topics that have no dedicated helper (e.g. plan_feedback,
        cloud_points_feedback).

        Blocking (may open the per-device MQTT connection); in HA call via
        async_add_executor_job.
        """
        self._ensure_mqtt_for(sn).subscribe(topic, callback)

    def request_with_feedback(
        self,
        sn: str,
        type_id: str,
        command_topic_name: str,
        payload: CommandPayload,
        response_topic_filter: str,
        timeout: float = 10.0,
    ) -> DeviceData:
        """Publish a command and wait for the matching data_feedback response.

        This is a synchronous blocking method. In HA, call via async_add_executor_job.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            command_topic_name: Control topic name to publish to.
            payload: Command payload dict.
            response_topic_filter: Expected 'topic' field value in the data_feedback response.
            timeout: Maximum seconds to wait for response.

        Returns:
            The full response dict from data_feedback.

        Raises:
            TimeoutError: If no matching response arrives within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        event = threading.Event()
        result: DeviceData = {}

        def _on_match(topic_str: str, data: DeviceData) -> None:
            result.update(data)
            event.set()

        # Register one-time listener
        with self._feedback_lock:
            if sn not in self._feedback_listeners:
                self._feedback_listeners[sn] = []
            entry = (response_topic_filter, _on_match)
            self._feedback_listeners[sn].append(entry)

        try:
            # Publish the command
            self.mqtt_publish_command(sn, type_id, command_topic_name, payload)

            # Wait for matching response
            if not event.wait(timeout):
                raise TimeoutError(
                    f"No data_feedback response for '{response_topic_filter}' "
                    f"within {timeout}s"
                )

            # Check response state
            state = result.get("state")
            if state is not None and state != 0:
                raise YarboSDKError(
                    f"Command '{response_topic_filter}' failed with state={state}: "
                    f"{result.get('msg', '')}"
                )

            return result
        finally:
            # Clean up one-time listener
            with self._feedback_lock:
                listeners = self._feedback_listeners.get(sn, [])
                if entry in listeners:
                    listeners.remove(entry)

    def read_gps_ref(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData:
        """Request GPS reference origin coordinates from the device.

        Sends read_gps_ref command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing data.ref.latitude, data.ref.longitude,
            data.rtkFixType, etc.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "read_gps_ref", {}, "read_gps_ref", timeout
        )

    def get_map(self, sn: str, type_id: str, timeout: float = 30.0) -> DeviceData:
        """Request map/zone data from the device.

        Sends get_map command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response (default 30s due to
                large payload size).

        Returns:
            Response dict containing data.areas, data.pathways, data.sidewalks,
            data.deadends, data.chargingData, etc.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "get_map", {}, "get_map", timeout
        )

    def read_all_plan(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData:
        """Request all auto plans from the device.

        Sends read_all_plan command and waits for the response via data_feedback.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing data.data (list of plans with id, name,
            areaIds, enable_self_order).

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "read_all_plan", {}, "read_all_plan", timeout
        )

    def get_device_msg(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData:
        """Request full DeviceMSG snapshot from the device.

        Sends get_device_msg command and waits for the response via data_feedback.
        The response structure is identical to the real-time DeviceMSG push but
        contains all fields (some fields are omitted in real-time push for
        bandwidth savings).

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            timeout: Maximum seconds to wait for response.

        Returns:
            Response dict containing the full DeviceMSG snapshot.

        Raises:
            TimeoutError: If no response within timeout.
            YarboSDKError: If the response state is non-zero.
        """
        return self.request_with_feedback(
            sn, type_id, "get_device_msg", {}, "get_device_msg", timeout
        )

    def get_connect_wifi_name(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData:
        """Request connected Wi-Fi information from the device.

        The response data includes the current Wi-Fi signal strength in
        ``data.signal``.
        """
        return self.request_with_feedback(
            sn,
            type_id,
            "get_connect_wifi_name",
            {},
            "get_connect_wifi_name",
            timeout,
        )

    def mqtt_publish_command(
        self,
        sn: str,
        type_id: str,
        command_topic_name: str,
        payload: CommandPayload,
    ) -> None:
        """Publish a command to a device control topic.

        Automatically compresses the payload with zlib if the device firmware
        version is >= 3.9.0; otherwise sends plaintext JSON.

        Args:
            sn: Device serial number.
            type_id: Device type ID.
            command_topic_name: Name of the control topic (from control_topics[].name).
            payload: Command payload dict to send.

        Raises:
            YarboSDKError: If MQTT is not connected or the topic name is unknown.
        """
        mqtt = self._ensure_mqtt_for(sn)

        topic = resolve_control_topic(sn, type_id, command_topic_name)
        fw = self._firmware_versions.get(sn)
        if should_compress(fw):
            encoded = encode_mqtt_payload(payload)
        else:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        _LOGGER.debug(
            "MQTT publish → topic=%s payload=%s compressed=%s",
            topic, payload, should_compress(fw),
        )
        mqtt.publish(topic, encoded)

    # --- Lifecycle ---

    def close(self) -> None:
        """Clean up resources."""
        self.mqtt_disconnect()
