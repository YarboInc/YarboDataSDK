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


class TestDeviceRegistry:
    """Device registry via client."""

    def test_list_device_types(self, client):
        types = client.list_device_types()
        assert len(types) >= 2

    def test_get_device_type(self, client):
        dt = client.get_device_type("mower")
        assert dt is not None
        assert dt.type_id == "mower"


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
        with pytest.raises(YarboSDKError, match="api_base_url is required"):
            YarboClient(rsa_public_key=rsa_key_pair["public_key"])

    def test_missing_rsa_key_without_cloud(self):
        """No rsa key and no cloud config → error."""
        with pytest.raises(YarboSDKError):
            YarboClient(api_base_url="https://api.yarbo.com")

    def test_mqtt_subscribe_before_connect(self, client):
        with pytest.raises(YarboSDKError, match="MQTT not connected"):
            client.mqtt_subscribe("topic", MagicMock())
