"""Tests for MqttClient — TC-010~015, TC-021~023, TC-111~114."""

import re
from unittest.mock import MagicMock, patch

import pytest

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.exceptions import MqttConnectionError
from yarbo_robot_sdk.mqtt_client import (
    LegacyCredentialsProvider,
    MqttClient,
    NewBrokerCredentialsProvider,
)


@pytest.fixture
def auth_manager(api_base_url, rsa_key_pair, mock_tokens):
    auth = AuthManager(api_base_url, rsa_key_pair["public_key"])
    auth.restore("user@test.com", mock_tokens["token"], mock_tokens["refresh_token"])
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
    """TC-010, TC-011, TC-021, TC-022."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_connect_uses_jwt_as_username(self, MockClient, mqtt_client, mock_tokens):
        """TC-022: HTTP AUTH via username=JWT, password=""."""
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
    def test_client_id_format(self, MockClient, mqtt_client):
        """TC-021: client_id format is HA_{email}_{timestamp}_{rand4}.

        The random suffix prevents same-second reconnects from colliding on
        client_id (which makes the broker kick the older session).
        """
        mqtt_client.connect()

        call_kwargs = MockClient.call_args
        client_id = call_kwargs.kwargs.get("client_id") or call_kwargs[1].get("client_id", "")

        assert client_id.startswith("HA_"), f"client_id should start with 'HA_', got '{client_id}'"
        assert "user@test.com" in client_id, f"client_id should contain email, got '{client_id}'"
        # Format: HA_{email}_{timestamp}_{rand4} — email has no underscore.
        parts = client_id.split("_")
        assert len(parts) == 4, f"client_id should have 4 parts, got '{client_id}'"
        timestamp_part, rand_part = parts[2], parts[3]
        assert timestamp_part.isdigit(), f"3rd part should be timestamp, got '{timestamp_part}'"
        assert rand_part.isdigit() and len(rand_part) == 4, (
            f"4th part should be a 4-digit random suffix, got '{rand_part}'"
        )

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_reconnect_tears_down_previous_client(self, MockClient, mqtt_client):
        """A second connect() stops and disconnects the prior paho client so no
        orphaned loop_start() thread keeps auto-reconnecting in the background."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()
        mqtt_client.connect()

        mock_instance.loop_stop.assert_called_once()
        mock_instance.disconnect.assert_called_once()
        assert mock_instance.loop_start.call_count == 2

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_custom_client_id_prefix(self, MockClient, auth_manager, mqtt_config):
        """Custom client_id prefix is used when provided."""
        client = MqttClient(
            auth_manager=auth_manager,
            host=mqtt_config["mqtt_host"],
            port=mqtt_config["mqtt_port"],
            client_id_prefix="Custom_",
        )
        client.connect()

        call_kwargs = MockClient.call_args
        client_id = call_kwargs.kwargs.get("client_id") or call_kwargs[1].get("client_id", "")
        assert client_id.startswith("Custom_")

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
    """TC-014, TC-023."""

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

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_on_disconnect_refreshes_token_as_username(self, MockClient, mqtt_client, mock_tokens):
        """TC-023: on unexpected disconnect, refresh token and set username=JWT."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()

        # Mock auth refresh to update token
        new_token = "new_refreshed_jwt_token"
        mqtt_client._auth._token = new_token

        # Simulate unexpected disconnect (rc != 0)
        with patch.object(mqtt_client._auth, "refresh"):
            mqtt_client._on_disconnect(mock_instance, None, None, 1)

        # Verify username_pw_set called with new token as username
        last_call = mock_instance.username_pw_set.call_args
        assert last_call.kwargs.get("username") == new_token or last_call[0][0] == new_token
        assert last_call.kwargs.get("password") == "" or last_call[0][1] == ""


class TestMqttPublish:
    """TC-007, TC-008."""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_publish_success(self, MockClient, mqtt_client):
        """TC-007: publish calls paho publish with correct topic, payload, qos."""
        mock_instance = MockClient.return_value
        mqtt_client.connect()
        payload = b'{"state":0}'
        mqtt_client.publish("snowbot/SN123/app/set_working_state", payload, qos=0)
        mock_instance.publish.assert_called_once_with(
            "snowbot/SN123/app/set_working_state", payload, 0
        )

    def test_publish_without_connect_raises(self, mqtt_client):
        """TC-008: publish before connect raises MqttConnectionError."""
        with pytest.raises(MqttConnectionError):
            mqtt_client.publish("snowbot/SN123/app/set_working_state", b"data")


class TestNewBrokerCredentials:
    """TC-111 ~ TC-114: new EMQX Dedicated broker credentials strategy."""

    def test_client_id_format_is_email_with_rand4(self, auth_manager):
        """TC-111: client_id is HA_{email}_{4-digit-zero-padded}."""
        provider = NewBrokerCredentialsProvider(auth_manager)
        pattern = re.compile(r"^HA_user@test\.com_\d{4}$")
        for _ in range(50):
            assert pattern.match(provider.client_id())

    def test_initial_credentials_is_email_and_token(self, auth_manager, mock_tokens):
        """TC-112: username=email, password=JWT."""
        provider = NewBrokerCredentialsProvider(auth_manager)
        username, password = provider.initial_credentials()
        assert username == "user@test.com"
        assert password == mock_tokens["token"]

    def test_legacy_credentials_unchanged(self, auth_manager, mock_tokens):
        """TC-113: regression — legacy provider is HA_{email}_{ts}_{rand4}, JWT/empty.

        The trailing rand4 prevents same-second reconnects from colliding on
        client_id (which makes the broker kick the older session).
        """
        provider = LegacyCredentialsProvider(auth_manager)
        client_id = provider.client_id()
        assert re.match(r"^HA_user@test\.com_\d+_\d{4}$", client_id)
        ts, rand = client_id.rsplit("_", 2)[-2:]
        assert ts.isdigit()
        assert len(ts) >= 10  # Unix timestamp, much longer than 4 digits.
        assert rand.isdigit() and len(rand) == 4

        username, password = provider.initial_credentials()
        assert username == mock_tokens["token"]
        assert password == ""

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_new_broker_mqtt_client_connects_with_correct_credentials(
        self, MockClient, auth_manager, mock_tokens
    ):
        """End-to-end: MqttClient with NewBrokerCredentialsProvider uses email+JWT."""
        client = MqttClient(
            auth_manager=auth_manager,
            host="c4750009.ala.dedicated.aws.emqxcloud.com",
            port=8883,
            credentials_provider=NewBrokerCredentialsProvider(auth_manager),
        )
        mock_instance = MockClient.return_value
        client.connect()

        mock_instance.username_pw_set.assert_called_once_with(
            username="user@test.com",
            password=mock_tokens["token"],
        )

        call_kwargs = MockClient.call_args
        client_id = call_kwargs.kwargs.get("client_id", "")
        assert re.match(r"^HA_user@test\.com_\d{4}$", client_id)

    @patch("yarbo_robot_sdk.mqtt_client.mqtt.Client")
    def test_new_broker_refresh_keeps_email_username(
        self, MockClient, auth_manager
    ):
        """TC-114: after refresh, username stays email, password becomes new token."""
        client = MqttClient(
            auth_manager=auth_manager,
            host="c4750009.ala.dedicated.aws.emqxcloud.com",
            port=8883,
            credentials_provider=NewBrokerCredentialsProvider(auth_manager),
        )
        mock_instance = MockClient.return_value
        client.connect()

        new_token = "refreshed-jwt-token"
        auth_manager._token = new_token

        with patch.object(client._auth, "refresh"):
            client._on_disconnect(mock_instance, None, None, 1)

        last_call = mock_instance.username_pw_set.call_args
        assert last_call.kwargs.get("username") == "user@test.com"
        assert last_call.kwargs.get("password") == new_token
