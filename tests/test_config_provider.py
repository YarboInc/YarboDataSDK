"""Tests for ConfigProvider — TC-018, TC-019, TC-020."""

import pytest
import responses

from yarbo_robot_sdk.config_provider import ConfigProvider
from yarbo_robot_sdk.exceptions import YarboSDKError


CLOUD_CONFIG_RESPONSE = {
    "rsa_public_key": "-----BEGIN PUBLIC KEY-----\nCLOUD_KEY\n-----END PUBLIC KEY-----",
    "mqtt_host": "cloud-mqtt.yarbo.com",
    "mqtt_port": 8883,
    "mqtt_use_tls": True,
}


class TestConstructorPriority:
    """TC-018: Constructor params take priority over cloud config."""

    @responses.activate
    def test_constructor_param_used(self):
        responses.add(
            responses.GET,
            "https://api.yarbo.com/sdk/config",
            json=CLOUD_CONFIG_RESPONSE,
        )
        provider = ConfigProvider(
            api_base_url="https://api.yarbo.com",
            mqtt_host="custom-mqtt.yarbo.com",
        )
        assert provider.get("mqtt_host") == "custom-mqtt.yarbo.com"
        # Cloud endpoint should NOT be called for keys that were provided
        assert len(responses.calls) == 0

    @responses.activate
    def test_api_base_url_from_constructor(self):
        provider = ConfigProvider(api_base_url="https://staging.yarbo.com")
        assert provider.get("api_base_url") == "https://staging.yarbo.com"


class TestCloudConfig:
    """TC-019: Fetch from cloud when constructor param not provided."""

    @responses.activate
    def test_fetches_from_cloud(self):
        responses.add(
            responses.GET,
            "https://api.yarbo.com/sdk/config",
            json=CLOUD_CONFIG_RESPONSE,
        )
        provider = ConfigProvider(api_base_url="https://api.yarbo.com")
        assert provider.get("mqtt_host") == "cloud-mqtt.yarbo.com"
        assert len(responses.calls) == 1

    @responses.activate
    def test_cloud_config_failure_raises(self):
        responses.add(
            responses.GET,
            "https://api.yarbo.com/sdk/config",
            status=500,
        )
        provider = ConfigProvider(api_base_url="https://api.yarbo.com")
        with pytest.raises(YarboSDKError, match="Failed to fetch cloud config"):
            provider.get("mqtt_host")


class TestCloudConfigCache:
    """TC-020: Cloud config is cached in memory (fetched only once)."""

    @responses.activate
    def test_fetched_only_once(self):
        responses.add(
            responses.GET,
            "https://api.yarbo.com/sdk/config",
            json=CLOUD_CONFIG_RESPONSE,
        )
        provider = ConfigProvider(api_base_url="https://api.yarbo.com")
        provider.get("mqtt_host")
        provider.get("mqtt_port")
        provider.get("rsa_public_key")
        # Only 1 HTTP call despite 3 get() calls
        assert len(responses.calls) == 1


class TestMissingApiBaseUrl:
    """Boundary: api_base_url not provided and cloud key requested."""

    def test_raises_without_api_base_url(self):
        provider = ConfigProvider()
        with pytest.raises(YarboSDKError, match="api_base_url is required"):
            provider.get("mqtt_host")
