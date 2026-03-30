"""Tests for MqttClient — TC-010~015."""

from unittest.mock import MagicMock, patch

import pytest

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.exceptions import MqttConnectionError
from yarbo_robot_sdk.mqtt_client import MqttClient


@pytest.fixture
def auth_manager(api_base_url, rsa_key_pair, mock_tokens):
    auth = AuthManager(api_base_url, rsa_key_pair["public_key"])
    auth.restore(mock_tokens["token"], mock_tokens["refresh_token"])
    return auth


@pytest.fixture
def mqtt_client(auth_manager, mqtt_config):
    return MqttClient(
        auth_manager=auth_manager,
        host=mqtt_config["mqtt_host"],
        port=mqtt_config["mqtt_port"],
        use_tls=mqtt_config["mqtt_use_tls"],
    )


class TestMqttConnect:
    """TC-010, TC-011."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_connect_uses_token_as_username(self, MockClient, mqtt_client, mock_tokens):
        """TC-010: JWT auth via username field."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()

        mock_instance.username_pw_set.assert_called_once_with(
            username=mock_tokens["token"], password=""
        )
        mock_instance.connect.assert_called_once_with(
            "test-mqtt.yarbo.com", 8883, 60
        )
        mock_instance.loop_start.assert_called_once()

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_tls_enabled(self, MockClient, mqtt_client):
        """TC-011: TLS is set when use_tls=True."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()
        mock_instance.tls_set.assert_called_once()

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_tls_disabled(self, MockClient, auth_manager):
        """TLS not set when use_tls=False."""
        client = MqttClient(auth_manager, "host", 1883, use_tls=False)
        mock_instance = MockClient.return_value
        client.connect()
        mock_instance.tls_set.assert_not_called()

    def test_connect_without_auth_raises(self, api_base_url, rsa_key_pair):
        """Boundary: not authenticated."""
        auth = AuthManager(api_base_url, rsa_key_pair["public_key"])
        client = MqttClient(auth, "host", 8883)
        with pytest.raises(MqttConnectionError):
            client.connect()


class TestMqttSubscribe:
    """TC-012, TC-015."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_subscribe_registers_callback(self, MockClient, mqtt_client):
        """TC-012: subscribe calls paho subscribe and stores callback."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()

        cb = MagicMock()
        mqtt_client.subscribe("snowbot/SN123/status", cb)

        mock_instance.subscribe.assert_called_with("snowbot/SN123/status")
        assert "snowbot/SN123/status" in mqtt_client._callbacks
        assert cb in mqtt_client._callbacks["snowbot/SN123/status"]

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_duplicate_subscribe_appends_callback(self, MockClient, mqtt_client):
        """Boundary: subscribing same topic twice appends callback, doesn't re-subscribe."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()

        cb1, cb2 = MagicMock(), MagicMock()
        mqtt_client.subscribe("snowbot/SN123/status", cb1)
        mqtt_client.subscribe("snowbot/SN123/status", cb2)

        # paho subscribe called only once for the topic
        assert mock_instance.subscribe.call_count == 1
        assert len(mqtt_client._callbacks["snowbot/SN123/status"]) == 2

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_unsubscribe(self, MockClient, mqtt_client):
        """TC-015: unsubscribe removes topic and callbacks."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()
        mqtt_client.subscribe("snowbot/SN123/status", MagicMock())
        mqtt_client.unsubscribe("snowbot/SN123/status")

        mock_instance.unsubscribe.assert_called_with("snowbot/SN123/status")
        assert "snowbot/SN123/status" not in mqtt_client._callbacks

    def test_subscribe_without_connect_raises(self, mqtt_client):
        """Boundary: subscribe before connect."""
        with pytest.raises(MqttConnectionError):
            mqtt_client.subscribe("topic", MagicMock())


class TestMqttMessageDispatch:
    """TC-013."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_message_dispatched_to_callback(self, MockClient, mqtt_client):
        """TC-013: on_message dispatches to registered callback."""
        mqtt_client.connect()

        cb = MagicMock()
        mqtt_client.subscribe("snowbot/SN123/status", cb)

        # Simulate incoming message
        msg = MagicMock()
        msg.topic = "snowbot/SN123/status"
        msg.payload = b'{"battery": 80}'
        mqtt_client._on_message(None, None, msg)

        cb.assert_called_once_with("snowbot/SN123/status", b'{"battery": 80}')

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_wildcard_topic_matching(self, MockClient, mqtt_client):
        """Wildcard subscription dispatches correctly."""
        mqtt_client.connect()

        cb = MagicMock()
        mqtt_client.subscribe("snowbot/SN123/#", cb)

        msg = MagicMock()
        msg.topic = "snowbot/SN123/status"
        msg.payload = b"data"
        mqtt_client._on_message(None, None, msg)

        cb.assert_called_once_with("snowbot/SN123/status", b"data")


class TestMqttReconnect:
    """TC-014."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_on_connect_resubscribes(self, MockClient, mqtt_client):
        """TC-014: reconnect re-subscribes all topics."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()

        mqtt_client.subscribe("topic1", MagicMock())
        mqtt_client.subscribe("topic2", MagicMock())
        mock_instance.subscribe.reset_mock()

        # Simulate reconnect
        mqtt_client._on_connect(mock_instance, None, None, 0)

        assert mock_instance.subscribe.call_count == 2
