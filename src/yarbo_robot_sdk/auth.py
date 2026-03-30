"""Authentication manager — login, token refresh, RSA password encryption."""

import base64

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from yarbo_robot_sdk import endpoints
from yarbo_robot_sdk.config import REQUEST_TIMEOUT
from yarbo_robot_sdk.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    YarboSDKError,
)


class AuthManager:
    """Manages authentication lifecycle: login, token storage, refresh."""

    def __init__(self, api_base_url: str, rsa_public_key: str):
        self._api_base_url = api_base_url
        self._rsa_public_key = rsa_public_key
        self._username: str | None = None
        self._token: str | None = None
        self._refresh_token: str | None = None

    def login(self, username: str, password: str) -> None:
        """Encrypt password with RSA and call the login endpoint."""
        if not username:
            raise AuthenticationError("Username must not be empty")
        if not password:
            raise AuthenticationError("Password must not be empty")

        encrypted_password = self._encrypt_password(password)
        try:
            resp = requests.post(
                f"{self._api_base_url}{endpoints.AUTH_LOGIN}",
                json={"username": username, "password": encrypted_password},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise YarboSDKError(f"Login request failed: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid username or password")
        if not resp.ok:
            raise YarboSDKError(f"Login failed with status {resp.status_code}: {resp.text}")

        data = resp.json()
        payload = data.get("data", data)  # Support {"code":0,"data":{...}} wrapper
        self._username = username.lower()
        self._token = payload.get("accessToken") or payload.get("token")
        self._refresh_token = payload.get("refreshToken") or payload.get("refresh_token")

    def refresh(self) -> None:
        """Use refresh_token to obtain a new token."""
        if not self._refresh_token:
            raise TokenExpiredError("No refresh token available, please login again")

        try:
            resp = requests.post(
                f"{self._api_base_url}{endpoints.AUTH_REFRESH}",
                json={"refresh_token": self._refresh_token},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise YarboSDKError(f"Token refresh request failed: {exc}") from exc

        if resp.status_code == 401:
            raise TokenExpiredError("Refresh token expired, please login again")
        if not resp.ok:
            raise YarboSDKError(f"Token refresh failed with status {resp.status_code}")

        data = resp.json()
        payload = data.get("data", data)  # Support {"code":0,"data":{...}} wrapper
        self._token = payload.get("accessToken") or payload.get("token")
        new_refresh = payload.get("refreshToken") or payload.get("refresh_token")
        if new_refresh:
            self._refresh_token = new_refresh  # Auth0 Refresh Token Rotation

    def restore(self, username: str, token: str, refresh_token: str) -> None:
        """Restore a previous session from saved tokens."""
        self._username = username.lower()
        self._token = token
        self._refresh_token = refresh_token

    @property
    def username(self) -> str | None:
        return self._username

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def _encrypt_password(self, password: str) -> str:
        """Encrypt password using RSA-OAEP + SHA-256, return base64-encoded ciphertext."""
        try:
            public_key = serialization.load_pem_public_key(
                self._rsa_public_key.encode()
            )
        except Exception as exc:
            raise YarboSDKError(f"Invalid RSA public key: {exc}") from exc

        ciphertext = public_key.encrypt(
            password.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode()
