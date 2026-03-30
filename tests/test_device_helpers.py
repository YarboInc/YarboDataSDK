"""Tests for device_helpers — TC-015 to TC-023."""

import json
from unittest.mock import MagicMock, patch

import pytest

from yarbo_robot_sdk.device_helpers import extract_field, resolve_status_topic
from yarbo_robot_sdk.device_registry import get_device_type
from yarbo_robot_sdk.exceptions import YarboSDKError


class TestDeviceRegistryData:
    """TC-015, TC-016: Device registry has real data."""

    def test_mower_has_status_topic(self):
        """TC-015: Mower has status topic and fields."""
        dt = get_device_type("mower")
        assert dt is not None
        assert dt.name == "割草机器人"

        topic_names = [t.name for t in dt.topics]
        assert "status" in topic_names

        status_topic = next(t for t in dt.topics if t.name == "status")
        assert status_topic.template == "mower/{sn}/status"

        assert "BatteryMSG.capacity" in dt.status_fields
        assert "StateMSG.working_state" in dt.status_fields

    def test_snowbot_has_status_topic(self):
        """TC-016: Snowbot has status topic and snowbot-specific fields."""
        dt = get_device_type("snowbot")
        assert dt is not None
        assert dt.name == "扫雪机器人"

        status_topic = next(t for t in dt.topics if t.name == "status")
        assert status_topic.template == "snowbot/{sn}/status"

        assert "RTKMSG.status" in dt.status_fields
        assert "HeadMsg.head_type" in dt.status_fields


class TestExtractField:
    """TC-017: Nested field extraction."""

    def test_extract_nested_value(self):
        data = {"BatteryMSG": {"capacity": 42, "status": 1}}
        assert extract_field(data, "BatteryMSG.capacity") == 42

    def test_extract_missing_nested_key(self):
        data = {"BatteryMSG": {"capacity": 42}}
        assert extract_field(data, "BatteryMSG.nonexistent") is None

    def test_extract_missing_top_key(self):
        data = {"BatteryMSG": {"capacity": 42}}
        assert extract_field(data, "NonExistent.field") is None

    def test_extract_top_level_key(self):
        data = {"timestamp": 123456}
        assert extract_field(data, "timestamp") == 123456

    def test_extract_from_empty_dict(self):
        assert extract_field({}, "any.path") is None


class TestResolveStatusTopic:
    """TC-018: Topic resolution."""

    def test_resolve_snowbot(self):
        assert resolve_status_topic("SN001", "snowbot") == "snowbot/SN001/status"

    def test_resolve_mower(self):
        assert resolve_status_topic("SN002", "mower") == "mower/SN002/status"

    def test_resolve_unknown_type(self):
        with pytest.raises(YarboSDKError, match="Unknown device type"):
            resolve_status_topic("SN003", "unknown_type")


class TestClientHighLevelMethods:
    """TC-019, TC-020, TC-022, TC-023: Client high-level methods."""

    def _make_client(self, rsa_public_key):
        from yarbo_robot_sdk.client import YarboClient
        return YarboClient(
            api_base_url="https://api.test.yarbo.com",
            mqtt_host="mqtt.test.com",
            mqtt_port=8883,
            rsa_public_key=rsa_public_key,
        )

    def test_subscribe_device_status_parses_json(self, rsa_key_pair):
        """TC-019: subscribe_device_status delivers parsed dict to callback."""
        client = self._make_client(rsa_key_pair["public_key"])

        # Mock MQTT
        mock_mqtt = MagicMock()
        client._mqtt = mock_mqtt
        mock_mqtt.subscribe = MagicMock()

        received = []
        client.subscribe_device_status("SN001", "snowbot", lambda t, d: received.append((t, d)))

        # The wrapper was passed to mqtt_subscribe
        assert mock_mqtt.subscribe.called
        topic, wrapper = mock_mqtt.subscribe.call_args[0]
        assert topic == "snowbot/SN001/status"

        # Simulate message
        payload = json.dumps({"BatteryMSG": {"capacity": 42}}).encode()
        wrapper("snowbot/SN001/status", payload)

        assert len(received) == 1
        assert received[0] == ("snowbot/SN001/status", {"BatteryMSG": {"capacity": 42}})

    def test_subscribe_device_status_handles_non_json(self, rsa_key_pair):
        """TC-020: Non-JSON payload wrapped in {'_raw': ...}."""
        client = self._make_client(rsa_key_pair["public_key"])

        mock_mqtt = MagicMock()
        client._mqtt = mock_mqtt

        received = []
        client.subscribe_device_status("SN001", "snowbot", lambda t, d: received.append((t, d)))

        topic, wrapper = mock_mqtt.subscribe.call_args[0]
        wrapper("snowbot/SN001/status", b"not json")

        assert received[0][1] == {"_raw": "not json"}

    @patch("yarbo_robot_sdk.rest_client.RestClient.get")
    def test_get_battery(self, mock_get, rsa_key_pair):
        """TC-022: get_battery returns BatteryMSG dict."""
        mock_get.return_value = {
            "BatteryMSG": {"capacity": 85, "status": 1},
            "StateMSG": {"working_state": 0},
        }
        client = self._make_client(rsa_key_pair["public_key"])
        client._auth._token = "fake_token"

        result = client.get_battery("SN001")
        assert result == {"capacity": 85, "status": 1}

    @patch("yarbo_robot_sdk.rest_client.RestClient.get")
    def test_get_position(self, mock_get, rsa_key_pair):
        """TC-023: get_position returns CombinedOdom dict."""
        mock_get.return_value = {
            "CombinedOdom": {"x": -2.836, "y": 9.515, "phi": -0.033},
        }
        client = self._make_client(rsa_key_pair["public_key"])
        client._auth._token = "fake_token"

        result = client.get_position("SN001")
        assert result == {"x": -2.836, "y": 9.515, "phi": -0.033}


class TestMqttAutoRefreshReconnect:
    """TC-021: MQTT token refresh on disconnect."""

    def test_disconnect_triggers_refresh(self, rsa_key_pair):
        """TC-021: Non-normal disconnect triggers auth refresh."""
        from yarbo_robot_sdk.auth import AuthManager
        from yarbo_robot_sdk.mqtt_client import MqttClient

        auth = AuthManager("https://api.test.com", rsa_key_pair["public_key"])
        auth._token = "old_token"
        auth._refresh_token = "refresh_token"

        mqtt_client = MqttClient(auth, "mqtt.test.com", 8883)

        mock_paho = MagicMock()
        mqtt_client._client = mock_paho
        mqtt_client._connected = True

        # Mock auth.refresh to update token
        with patch.object(auth, "refresh") as mock_refresh:
            mqtt_client._on_disconnect(mock_paho, None, None, 1)  # rc=1 = unexpected

            mock_refresh.assert_called_once()
            mock_paho.username_pw_set.assert_called_once()

    def test_normal_disconnect_no_refresh(self, rsa_key_pair):
        """Normal disconnect (rc=0) does not trigger refresh."""
        from yarbo_robot_sdk.auth import AuthManager
        from yarbo_robot_sdk.mqtt_client import MqttClient

        auth = AuthManager("https://api.test.com", rsa_key_pair["public_key"])
        auth._token = "token"

        mqtt_client = MqttClient(auth, "mqtt.test.com", 8883)
        mqtt_client._client = MagicMock()
        mqtt_client._connected = True

        with patch.object(auth, "refresh") as mock_refresh:
            mqtt_client._on_disconnect(mqtt_client._client, None, None, 0)  # rc=0 = normal
            mock_refresh.assert_not_called()
