"""Tests for RestClient — TC-005, TC-007, TC-008."""

import pytest
import responses

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.exceptions import APIError, AuthenticationError, TokenExpiredError
from yarbo_robot_sdk.rest_client import RestClient


@pytest.fixture
def rest_client(api_base_url, rsa_key_pair, mock_tokens):
    auth = AuthManager(api_base_url, rsa_key_pair["public_key"])
    auth.restore("user@test.com", mock_tokens["token"], mock_tokens["refresh_token"])
    return RestClient(auth, api_base_url), auth


class TestTokenInjection:
    """TC-007: Auto-inject token in Authorization header."""

    @responses.activate
    def test_bearer_token_in_header(self, rest_client, api_base_url, mock_tokens):
        client, auth = rest_client
        responses.add(responses.GET, f"{api_base_url}/devices", json={"devices": []}, status=200)
        client.get("/devices")

        assert responses.calls[0].request.headers["Authorization"] == f"Bearer {mock_tokens['token']}"


class TestAutoRefresh:
    """TC-005: 401 triggers auto refresh and retry."""

    @responses.activate
    def test_401_triggers_refresh_and_retry(self, rest_client, api_base_url):
        client, auth = rest_client

        # First call returns 401
        responses.add(responses.GET, f"{api_base_url}/devices", status=401)
        # Refresh endpoint returns new token
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/refresh",
            json={"token": "new_token"},
            status=200,
        )
        # Retry returns success
        responses.add(
            responses.GET,
            f"{api_base_url}/devices",
            json={"devices": []},
            status=200,
        )

        result = client.get("/devices")
        assert result == {"devices": []}
        assert auth.token == "new_token"
        # 3 calls: GET(401) + POST(refresh) + GET(200)
        assert len(responses.calls) == 3

    @responses.activate
    def test_401_refresh_also_fails(self, rest_client, api_base_url):
        """TC-006 via RestClient: both token and refresh expired."""
        client, auth = rest_client

        responses.add(responses.GET, f"{api_base_url}/devices", status=401)
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/refresh",
            status=401,
        )

        with pytest.raises(TokenExpiredError):
            client.get("/devices")


class TestErrorHandling:
    """TC-008: HTTP error handling."""

    @responses.activate
    def test_500_raises_api_error(self, rest_client, api_base_url):
        client, _ = rest_client
        responses.add(
            responses.GET,
            f"{api_base_url}/some-endpoint",
            body="Internal Server Error",
            status=500,
        )
        with pytest.raises(APIError) as exc_info:
            client.get("/some-endpoint")
        assert exc_info.value.status_code == 500

    def test_not_authenticated_raises_error(self, api_base_url, rsa_key_pair):
        auth = AuthManager(api_base_url, rsa_key_pair["public_key"])
        client = RestClient(auth, api_base_url)
        with pytest.raises(AuthenticationError):
            client.get("/devices")
