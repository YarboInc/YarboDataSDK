"""Configuration provider. Priority: constructor params > cloud config endpoint."""

import requests

from yarbo_robot_sdk.config import REQUEST_TIMEOUT, SDK_CONFIG_ENDPOINT
from yarbo_robot_sdk.exceptions import YarboSDKError


class ConfigProvider:
    """Resolves SDK configuration.

    Constructor parameters take priority. For any key not provided,
    the value is fetched from the cloud config endpoint (once, then cached).
    """

    _CLOUD_CONFIG_KEYS = ("rsa_public_key", "mqtt_host", "mqtt_port", "mqtt_use_tls")

    def __init__(
        self,
        api_base_url: str | None = None,
        rsa_public_key: str | None = None,
        mqtt_host: str | None = None,
        mqtt_port: int | None = None,
        mqtt_use_tls: bool | None = None,
    ):
        self._overrides: dict = {
            "api_base_url": api_base_url,
            "rsa_public_key": rsa_public_key,
            "mqtt_host": mqtt_host,
            "mqtt_port": mqtt_port,
            "mqtt_use_tls": mqtt_use_tls,
        }
        self._cloud_config: dict | None = None

    def get(self, key: str):
        """Get a config value. Constructor param takes priority, else cloud config."""
        value = self._overrides.get(key)
        if value is not None:
            return value

        if key in self._CLOUD_CONFIG_KEYS:
            cloud = self._get_cloud_config()
            return cloud.get(key)

        return None

    def _get_cloud_config(self) -> dict:
        """Fetch cloud config with in-memory cache (fetched only once)."""
        if self._cloud_config is None:
            self._cloud_config = self._fetch_cloud_config()
        return self._cloud_config

    def _fetch_cloud_config(self) -> dict:
        """GET {api_base_url}/sdk/config — unauthenticated."""
        api_base = self._overrides.get("api_base_url")
        if not api_base:
            raise YarboSDKError(
                "api_base_url is required: pass it via the YarboClient constructor"
            )
        try:
            resp = requests.get(
                f"{api_base}{SDK_CONFIG_ENDPOINT}",
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            # Support Lambda {"code": 0, "data": {...}} wrapper
            if "data" in result and isinstance(result["data"], dict):
                return result["data"]
            return result
        except requests.RequestException as exc:
            raise YarboSDKError(f"Failed to fetch cloud config: {exc}") from exc
