"""Tests for YarboClient — TC-009, TC-024 + boundary cases."""

from unittest.mock import MagicMock, patch

import pytest
import responses

from yarbo_robot_sdk.client import YarboClient
from yarbo_robot_sdk.exceptions import YarboSDKError
from yarbo_robot_sdk.models import Device


@pytest.fixture
def client(api_base_url, rsa_key_pair):
    """Create a YarboClient with all config passed via constructor."""
    return YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )


class TestGetDevices:
    """TC-009: Get device list."""

    @responses.activate
    def test_get_devices(self, client, api_base_url, mock_tokens, mock_devices_response):
        responses.add(
            responses.POST, f"{api_base_url}/auth/login", json=mock_tokens, status=200
        )
        responses.add(
            responses.GET,
            f"{api_base_url}/devices",
            json=mock_devices_response,
            status=200,
        )

        client.login("user@test.com", "pass")
        devices = client.get_devices()

        assert len(devices) == 2
        assert all(isinstance(d, Device) for d in devices)
        assert devices[0].sn == "SN001"
        assert devices[0].type_id == "mower"
        assert devices[1].sn == "SN002"
        assert devices[1].online is False


class TestRestoreSession:
    """TC-021 via client, TC-022 via client."""

    @responses.activate
    def test_restore_and_use(self, client, api_base_url, mock_devices_response):
        client.restore_session(username="user@test.com", token="saved_token", refresh_token="saved_refresh")
        assert client.token == "saved_token"
        assert client.refresh_token == "saved_refresh"

        responses.add(
            responses.GET,
            f"{api_base_url}/devices",
            json=mock_devices_response,
            status=200,
        )
        devices = client.get_devices()
        assert len(devices) == 2
        assert responses.calls[0].request.headers["Authorization"] == "Bearer saved_token"


class TestFullFlow:
    """TC-024: Full workflow."""

    @responses.activate
    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_full_flow(self, MockMqttClient, client, api_base_url, mock_tokens, mock_devices_response):
        # Login
        responses.add(
            responses.POST, f"{api_base_url}/auth/login", json=mock_tokens, status=200
        )
        client.login("user@test.com", "pass")
        assert client.token == mock_tokens["token"]

        # Get devices
        responses.add(
            responses.GET,
            f"{api_base_url}/devices",
            json=mock_devices_response,
            status=200,
        )
        devices = client.get_devices()
        assert len(devices) == 2

        # MQTT connect is now lazy — no-op until a per-SN subscribe happens.
        client.mqtt_connect()
        # Route SN001 through the legacy broker.
        with patch.object(client._migration, "query", return_value=False):
            client.subscribe_device_message("SN001", "snowbot", lambda t, d: None)

        # Close
        client.close()


class TestBoundary:
    """Boundary cases."""

    def test_missing_api_base_url(self, rsa_key_pair):
        """No explicit api_base_url uses DEFAULT_API_BASE_URL — no error raised."""
        # Client falls back to DEFAULT_API_BASE_URL when api_base_url is omitted
        # rsa key is provided so construction succeeds
        client = YarboClient(rsa_public_key=rsa_key_pair["public_key"])
        assert client is not None

    def test_missing_rsa_key_without_cloud(self):
        """No rsa key and no cloud config → error."""
        with pytest.raises(YarboSDKError):
            YarboClient(api_base_url="https://api.yarbo.com")

    def test_subscribe_before_login_raises(self, client):
        """Subscribing without being authenticated must fail loudly."""
        with pytest.raises(YarboSDKError, match="Not authenticated"):
            client.subscribe_device_message("SN001", "snowbot", lambda t, d: None)


@pytest.fixture
def authed_client(client, mock_tokens):
    """YarboClient with a restored session (authenticated)."""
    client.restore_session("user@test.com", mock_tokens["token"], mock_tokens["refresh_token"])
    return client


@pytest.fixture
def legacy_only_client(authed_client):
    """authed_client whose migration query always returns False (legacy broker).

    Use this for tests that exercise the existing per-SN subscribe/publish
    logic without re-testing the routing decision itself.
    """
    with patch.object(authed_client._migration, "query", return_value=False):
        yield authed_client


class TestSubscribeDeviceMessage:
    """TC-009: subscribe_device_message decodes payload and caches firmware version."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_compressed_payload_decoded(self, MockClient, legacy_only_client):
        """TC-009a: compressed payload is decoded and passed to callback as dict."""
        import json, zlib
        legacy_only_client.mqtt_connect()
        received = []
        legacy_only_client.subscribe_device_message("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload_dict = {"BatteryMSG": {"capacity": 75}, "version": "3.9.1"}
        compressed = zlib.compress(json.dumps(payload_dict).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/DeviceMSG"
        msg.payload = compressed
        legacy_only_client._legacy_mqtt._on_message(None, None, msg)

        assert len(received) == 1
        assert received[0]["BatteryMSG"]["capacity"] == 75

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_firmware_version_cached(self, MockClient, legacy_only_client):
        """TC-009b: firmware version from 'version' field is cached per SN."""
        import json, zlib
        legacy_only_client.mqtt_connect()
        legacy_only_client.subscribe_device_message("SN001", "yarbo_Y", lambda t, d: None)

        payload_dict = {"version": "3.9.1"}
        compressed = zlib.compress(json.dumps(payload_dict).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/DeviceMSG"
        msg.payload = compressed
        legacy_only_client._legacy_mqtt._on_message(None, None, msg)

        assert legacy_only_client._firmware_versions.get("SN001") == (3, 9, 1)

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_plaintext_payload_decoded(self, MockClient, legacy_only_client):
        """TC-009c: plaintext JSON fallback also works."""
        import json
        legacy_only_client.mqtt_connect()
        received = []
        legacy_only_client.subscribe_device_message("SN002", "yarbo_Y", lambda t, d: received.append(d))

        payload_dict = {"StateMSG": {"working_state": 0}, "version": "3.8.0"}
        msg = MagicMock()
        msg.topic = "snowbot/SN002/device/DeviceMSG"
        msg.payload = json.dumps(payload_dict).encode()
        legacy_only_client._legacy_mqtt._on_message(None, None, msg)

        assert received[0]["StateMSG"]["working_state"] == 0
        assert legacy_only_client._firmware_versions.get("SN002") == (3, 8, 0)


class TestSubscribeHeartBeat:
    """TC-010: subscribe_heart_beat decodes payload and passes to callback."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_heart_beat_decoded(self, MockClient, legacy_only_client):
        """TC-010: heart beat payload decoded to dict and passed to callback."""
        import json
        legacy_only_client.mqtt_connect()
        received = []
        legacy_only_client.subscribe_heart_beat("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload = json.dumps({"working_state": 1}).encode()
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/heart_beat"
        msg.payload = payload
        legacy_only_client._legacy_mqtt._on_message(None, None, msg)

        assert received[0]["working_state"] == 1

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_heart_beat_compressed_decoded(self, MockClient, legacy_only_client):
        """TC-010b: compressed heart beat payload decoded correctly."""
        import json, zlib
        legacy_only_client.mqtt_connect()
        received = []
        legacy_only_client.subscribe_heart_beat("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload = zlib.compress(json.dumps({"working_state": 0}).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/heart_beat"
        msg.payload = payload
        legacy_only_client._legacy_mqtt._on_message(None, None, msg)

        assert received[0]["working_state"] == 0


class TestMqttPublishCommand:
    """TC-011, TC-012: mqtt_publish_command sends correct payload."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_plaintext_when_no_fw_version(self, MockClient, legacy_only_client):
        """TC-011: no fw version → plaintext JSON."""
        import json
        mock_instance = MockClient.return_value
        legacy_only_client.mqtt_connect()

        legacy_only_client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 0})

        call_args = mock_instance.publish.call_args
        topic = call_args[0][0]
        payload_bytes = call_args[0][1]
        assert topic == "snowbot/SN001/app/set_working_state"
        assert json.loads(payload_bytes) == {"state": 0}

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_compressed_when_fw_above_threshold(self, MockClient, legacy_only_client):
        """TC-012: fw >= 3.9.0 → zlib-compressed payload."""
        import zlib
        mock_instance = MockClient.return_value
        legacy_only_client.mqtt_connect()
        legacy_only_client._firmware_versions["SN001"] = (3, 9, 0)

        legacy_only_client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 1})

        call_args = mock_instance.publish.call_args
        payload_bytes = call_args[0][1]
        decompressed = zlib.decompress(payload_bytes)
        import json
        assert json.loads(decompressed) == {"state": 1}

    def test_publish_command_without_login_raises(self, client):
        """TC-011b: publishing without authentication raises YarboSDKError."""
        with pytest.raises(YarboSDKError, match="Not authenticated"):
            client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 0})

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_unknown_topic_raises(self, MockClient, legacy_only_client):
        """TC-011c: unknown command_topic_name raises YarboSDKError."""
        legacy_only_client.mqtt_connect()
        with pytest.raises(YarboSDKError):
            legacy_only_client.mqtt_publish_command("SN001", "yarbo_Y", "nonexistent_topic", {"x": 1})


class TestLazyConnect:
    """TC-104: mqtt_connect() is a no-op until a per-SN op happens."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_mqtt_connect_does_not_create_clients(self, MockClient, authed_client):
        authed_client.mqtt_connect()
        assert MockClient.call_count == 0
        assert authed_client._legacy_mqtt is None
        assert authed_client._new_mqtt is None

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_mqtt_connect_does_not_query_migration(self, MockClient, authed_client):
        with patch.object(authed_client._migration, "query") as mock_query:
            authed_client.mqtt_connect()
            mock_query.assert_not_called()


class TestBrokerRouting:
    """TC-101 / TC-102 / TC-103 / TC-116: per-SN routing decisions."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_unmigrated_sn_uses_legacy_broker(
        self, MockClient, authed_client, mock_tokens
    ):
        """TC-101: migrated=false → legacy broker, JWT username, empty password."""
        with patch.object(authed_client._migration, "query", return_value=False):
            authed_client.subscribe_device_message(
                "SN001", "snowbot", lambda t, d: None
            )

        assert authed_client._legacy_mqtt is not None
        assert authed_client._new_mqtt is None

        mock_instance = MockClient.return_value
        mock_instance.connect.assert_called_with("test-mqtt.yarbo.com", 8883, 60)
        mock_instance.username_pw_set.assert_called_with(
            username=mock_tokens["token"], password=""
        )
        call_kwargs = MockClient.call_args
        client_id = call_kwargs.kwargs.get("client_id", "")
        assert client_id.startswith("HA_user@test.com_")
        # Legacy ClientID is HA_{email}_{ts}_{rand4}: a Unix timestamp (≥10
        # digits) plus a 4-digit random suffix to avoid same-second collisions.
        ts, rand = client_id.rsplit("_", 2)[-2:]
        assert ts.isdigit() and len(ts) >= 10
        assert rand.isdigit() and len(rand) == 4

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_migrated_sn_uses_new_broker(
        self, MockClient, authed_client, mock_tokens
    ):
        """TC-102: migrated=true → new broker, email username, JWT password,
        ClientID HA_{email}_{4-digit-rand}, auth.refresh() called once.
        """
        import re

        with patch.object(authed_client._migration, "query", return_value=True), \
             patch.object(authed_client._auth, "refresh") as mock_refresh:
            authed_client.subscribe_device_message(
                "SN002", "snowbot", lambda t, d: None
            )

        assert authed_client._new_mqtt is not None
        assert authed_client._legacy_mqtt is None

        mock_instance = MockClient.return_value
        mock_instance.connect.assert_called_with(
            "c4750009.ala.dedicated.aws.emqxcloud.com", 8883, 60
        )
        mock_instance.username_pw_set.assert_called_with(
            username="user@test.com", password=mock_tokens["token"]
        )
        call_kwargs = MockClient.call_args
        client_id = call_kwargs.kwargs.get("client_id", "")
        assert re.match(r"^HA_user@test\.com_\d{4}$", client_id)
        mock_refresh.assert_called_once()

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_mixed_devices_open_two_separate_connections(
        self, MockClient, authed_client
    ):
        """TC-103: mixed SNs result in two MqttClient instances, one per broker."""
        def side_effect(sn):
            return sn == "SN_NEW"

        with patch.object(
            authed_client._migration, "query", side_effect=side_effect
        ), patch.object(authed_client._auth, "refresh"):
            authed_client.subscribe_device_message(
                "SN_OLD", "snowbot", lambda t, d: None
            )
            authed_client.subscribe_device_message(
                "SN_NEW", "snowbot", lambda t, d: None
            )

        # Both clients created, two distinct paho.mqtt.Client instances.
        assert authed_client._legacy_mqtt is not None
        assert authed_client._new_mqtt is not None
        assert authed_client._legacy_mqtt is not authed_client._new_mqtt
        assert MockClient.call_count == 2

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_command_routes_per_sn(self, MockClient, authed_client):
        """TC-116: mqtt_publish_command(sn,...) picks broker by SN."""
        # Two distinct paho mock instances, one per MqttClient.
        mock_legacy = MagicMock()
        mock_new = MagicMock()
        MockClient.side_effect = [mock_legacy, mock_new]

        def side_effect(sn):
            return sn == "SN_NEW"

        with patch.object(
            authed_client._migration, "query", side_effect=side_effect
        ), patch.object(authed_client._auth, "refresh"):
            authed_client.mqtt_publish_command(
                "SN_OLD", "yarbo_Y", "set_working_state", {"state": 0}
            )
            authed_client.mqtt_publish_command(
                "SN_NEW", "yarbo_Y", "set_working_state", {"state": 1}
            )

        # Each underlying paho client received exactly one publish call.
        assert mock_legacy.publish.call_count == 1
        assert mock_new.publish.call_count == 1
        assert (
            mock_legacy.publish.call_args[0][0]
            == "snowbot/SN_OLD/app/set_working_state"
        )
        assert (
            mock_new.publish.call_args[0][0]
            == "snowbot/SN_NEW/app/set_working_state"
        )


class TestRoutingFailure:
    """TC-105 at the YarboClient layer: migration query failure propagates."""

    def test_migration_failure_propagates_on_subscribe(self, authed_client):
        with patch.object(
            authed_client._migration,
            "query",
            side_effect=YarboSDKError("emqx-migration query failed for sn=SN001"),
        ):
            with pytest.raises(YarboSDKError, match="emqx-migration query failed"):
                authed_client.subscribe_device_message(
                    "SN001", "snowbot", lambda t, d: None
                )
        # Routing failed → no client should have been created.
        assert authed_client._legacy_mqtt is None
        assert authed_client._new_mqtt is None


class TestReconnectInvalidation:
    """TC-109: unexpected disconnect clears the migration cache so the next
    subscribe / publish re-queries every SN.
    """

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_on_disconnect_invalidates_migration_cache(
        self, MockClient, authed_client
    ):
        with patch.object(
            authed_client._migration, "query", return_value=False
        ) as mock_query:
            authed_client.subscribe_device_message(
                "SN001", "snowbot", lambda t, d: None
            )
            # The cache is populated by query during _ensure_mqtt_for.
            authed_client._migration._cache["SN001"] = False
            assert authed_client._migration._cache == {"SN001": False}

            # Simulate unexpected disconnect — wrapped _on_disconnect should clear cache.
            authed_client._legacy_mqtt._on_disconnect(
                MockClient.return_value, None, None, 1
            )

        assert authed_client._migration._cache == {}


class TestMqttDisconnect:
    """TC-115: mqtt_disconnect closes both clients and clears cache."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_disconnect_closes_both_and_clears_cache(
        self, MockClient, authed_client
    ):
        mock_legacy = MagicMock()
        mock_new = MagicMock()
        MockClient.side_effect = [mock_legacy, mock_new]

        def side_effect(sn):
            return sn == "SN_NEW"

        with patch.object(
            authed_client._migration, "query", side_effect=side_effect
        ), patch.object(authed_client._auth, "refresh"):
            authed_client.subscribe_device_message(
                "SN_OLD", "snowbot", lambda t, d: None
            )
            authed_client.subscribe_device_message(
                "SN_NEW", "snowbot", lambda t, d: None
            )

        # Seed the cache so we can verify invalidate_all.
        authed_client._migration._cache.update({"SN_OLD": False, "SN_NEW": True})

        authed_client.mqtt_disconnect()

        mock_legacy.disconnect.assert_called_once()
        mock_new.disconnect.assert_called_once()
        assert authed_client._migration._cache == {}


