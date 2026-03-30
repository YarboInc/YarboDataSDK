"""REST API client — common layer with auto token injection and refresh."""

import requests

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.config import REQUEST_TIMEOUT
from yarbo_robot_sdk.exceptions import APIError, AuthenticationError, YarboSDKError


class RestClient:
    """Sends REST API requests with automatic token injection and 401 retry."""

    def __init__(self, auth_manager: AuthManager, api_base_url: str):
        self._auth = auth_manager
        self._base_url = api_base_url
        self._session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> dict:
        """Send an API request. Auto-injects token; retries once on 401."""
        if not self._auth.is_authenticated:
            raise AuthenticationError("Not authenticated. Call login() first.")

        url = f"{self._base_url}{path}"
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)

        # First attempt
        resp = self._do_request(method, url, **kwargs)

        # 401 → refresh token and retry once
        if resp.status_code == 401:
            self._auth.refresh()
            resp = self._do_request(method, url, **kwargs)

        if not resp.ok:
            raise APIError(resp.status_code, resp.text)

        result = resp.json()

        # Unwrap Lambda response format: {"code": 0, "data": {...}}
        if isinstance(result, dict) and "code" in result and "data" in result:
            if result["code"] != 0:
                raise APIError(result["code"], result.get("message", "Unknown error"))
            return result["data"]

        return result

    def get(self, path: str, **kwargs) -> dict:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> dict:
        return self.request("POST", path, **kwargs)

    def _do_request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._auth.token}"
        try:
            return self._session.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise YarboSDKError(f"Request failed: {exc}") from exc
