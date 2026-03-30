"""Yarbo Robot SDK custom exceptions."""


class YarboSDKError(Exception):
    """Base exception for all SDK errors."""


class AuthenticationError(YarboSDKError):
    """Login failed due to invalid credentials."""


class TokenExpiredError(YarboSDKError):
    """Both token and refresh_token have expired. User must re-login."""


class APIError(YarboSDKError):
    """REST API call failed."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"API error {status_code}: {message}")


class MqttConnectionError(YarboSDKError):
    """MQTT connection failed."""
