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

        # MQTT connect + subscribe
        client.mqtt_connect()
        cb = MagicMock()
        client.mqtt_subscribe("snowbot/SN123/status", cb)

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

    def test_mqtt_subscribe_before_connect(self, client):
        with pytest.raises(YarboSDKError, match="MQTT not connected"):
            client.mqtt_subscribe("topic", MagicMock())


@pytest.fixture
def authed_client(client, mock_tokens):
    """YarboClient with a restored session (authenticated)."""
    client.restore_session("user@test.com", mock_tokens["token"], mock_tokens["refresh_token"])
    return client


class TestSubscribeDeviceMessage:
    """TC-009: subscribe_device_message decodes payload and caches firmware version."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_compressed_payload_decoded(self, MockClient, authed_client):
        """TC-009a: compressed payload is decoded and passed to callback as dict."""
        import json, zlib
        authed_client.mqtt_connect()
        received = []
        authed_client.subscribe_device_message("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload_dict = {"BatteryMSG": {"capacity": 75}, "version": "3.9.1"}
        compressed = zlib.compress(json.dumps(payload_dict).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/DeviceMSG"
        msg.payload = compressed
        authed_client._mqtt._on_message(None, None, msg)

        assert len(received) == 1
        assert received[0]["BatteryMSG"]["capacity"] == 75

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_firmware_version_cached(self, MockClient, authed_client):
        """TC-009b: firmware version from 'version' field is cached per SN."""
        import json, zlib
        authed_client.mqtt_connect()
        authed_client.subscribe_device_message("SN001", "yarbo_Y", lambda t, d: None)

        payload_dict = {"version": "3.9.1"}
        compressed = zlib.compress(json.dumps(payload_dict).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/DeviceMSG"
        msg.payload = compressed
        authed_client._mqtt._on_message(None, None, msg)

        assert authed_client._firmware_versions.get("SN001") == (3, 9, 1)

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_plaintext_payload_decoded(self, MockClient, authed_client):
        """TC-009c: plaintext JSON fallback also works."""
        import json
        authed_client.mqtt_connect()
        received = []
        authed_client.subscribe_device_message("SN002", "yarbo_Y", lambda t, d: received.append(d))

        payload_dict = {"StateMSG": {"working_state": 0}, "version": "3.8.0"}
        msg = MagicMock()
        msg.topic = "snowbot/SN002/device/DeviceMSG"
        msg.payload = json.dumps(payload_dict).encode()
        authed_client._mqtt._on_message(None, None, msg)

        assert received[0]["StateMSG"]["working_state"] == 0
        assert authed_client._firmware_versions.get("SN002") == (3, 8, 0)


class TestSubscribeHeartBeat:
    """TC-010: subscribe_heart_beat decodes payload and passes to callback."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_heart_beat_decoded(self, MockClient, authed_client):
        """TC-010: heart beat payload decoded to dict and passed to callback."""
        import json
        authed_client.mqtt_connect()
        received = []
        authed_client.subscribe_heart_beat("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload = json.dumps({"working_state": 1}).encode()
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/heart_beat"
        msg.payload = payload
        authed_client._mqtt._on_message(None, None, msg)

        assert received[0]["working_state"] == 1

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_heart_beat_compressed_decoded(self, MockClient, authed_client):
        """TC-010b: compressed heart beat payload decoded correctly."""
        import json, zlib
        authed_client.mqtt_connect()
        received = []
        authed_client.subscribe_heart_beat("SN001", "yarbo_Y", lambda t, d: received.append(d))

        payload = zlib.compress(json.dumps({"working_state": 0}).encode())
        msg = MagicMock()
        msg.topic = "snowbot/SN001/device/heart_beat"
        msg.payload = payload
        authed_client._mqtt._on_message(None, None, msg)

        assert received[0]["working_state"] == 0


class TestMqttPublishCommand:
    """TC-011, TC-012: mqtt_publish_command sends correct payload."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_plaintext_when_no_fw_version(self, MockClient, authed_client):
        """TC-011: no fw version → plaintext JSON."""
        import json
        mock_instance = MockClient.return_value
        authed_client.mqtt_connect()

        authed_client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 0})

        call_args = mock_instance.publish.call_args
        topic = call_args[0][0]
        payload_bytes = call_args[0][1]
        assert topic == "snowbot/SN001/app/set_working_state"
        assert json.loads(payload_bytes) == {"state": 0}

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_compressed_when_fw_above_threshold(self, MockClient, authed_client):
        """TC-012: fw >= 3.9.0 → zlib-compressed payload."""
        import zlib
        mock_instance = MockClient.return_value
        authed_client.mqtt_connect()
        authed_client._firmware_versions["SN001"] = (3, 9, 0)

        authed_client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 1})

        call_args = mock_instance.publish.call_args
        payload_bytes = call_args[0][1]
        decompressed = zlib.decompress(payload_bytes)
        import json
        assert json.loads(decompressed) == {"state": 1}

    def test_publish_command_without_mqtt_connect_raises(self, client):
        """TC-011b: MQTT not connected raises YarboSDKError."""
        with pytest.raises(YarboSDKError, match="MQTT not connected"):
            client.mqtt_publish_command("SN001", "yarbo_Y", "set_working_state", {"state": 0})

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_unknown_topic_raises(self, MockClient, authed_client):
        """TC-011c: unknown command_topic_name raises YarboSDKError."""
        authed_client.mqtt_connect()
        with pytest.raises(YarboSDKError):
            authed_client.mqtt_publish_command("SN001", "yarbo_Y", "nonexistent_topic", {"x": 1})


