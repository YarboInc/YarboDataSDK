"""Tests for AuthManager — TC-001~004, TC-021, TC-022 + boundary cases."""

import base64
import json

import pytest
import responses
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    YarboSDKError,
)


@pytest.fixture
def auth(api_base_url, rsa_key_pair):
    return AuthManager(api_base_url, rsa_key_pair["public_key"])


class TestEncryptPassword:
    """TC-001: RSA public key encrypts password."""

    def test_returns_base64_string(self, auth):
        result = auth._encrypt_password("test_password")
        assert isinstance(result, str)
        # Must be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_each_encryption_differs(self, auth):
        """OAEP padding includes random factor."""
        r1 = auth._encrypt_password("same_password")
        r2 = auth._encrypt_password("same_password")
        assert r1 != r2

    def test_can_decrypt_with_private_key(self, auth, rsa_key_pair):
        encrypted = auth._encrypt_password("hello_world")
        ciphertext = base64.b64decode(encrypted)
        private_key = rsa_key_pair["_private_key_obj"]
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        assert plaintext.decode() == "hello_world"


class TestLogin:
    """TC-002, TC-003, TC-004."""

    @responses.activate
    def test_login_success(self, auth, api_base_url, mock_tokens):
        """TC-002: Successful login stores token and refresh_token."""
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/login",
            json=mock_tokens,
            status=200,
        )
        auth.login("user@test.com", "password123")
        assert auth.token == mock_tokens["token"]
        assert auth.refresh_token == mock_tokens["refresh_token"]
        assert auth.is_authenticated is True

        # Verify password was encrypted (not plaintext) in request body
        body = json.loads(responses.calls[0].request.body)
        assert body["password"] != "password123"
        assert body["username"] == "user@test.com"

    @responses.activate
    def test_login_invalid_credentials(self, auth, api_base_url):
        """TC-003: Login with wrong credentials raises AuthenticationError."""
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/login",
            json={"error": "invalid credentials"},
            status=401,
        )
        with pytest.raises(AuthenticationError):
            auth.login("wrong@test.com", "wrongpass")
        assert auth.is_authenticated is False

    @responses.activate
    def test_login_network_error(self, auth, api_base_url):
        """TC-004: Network error raises YarboSDKError."""
        import requests as req
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/login",
            body=req.ConnectionError("network down"),
        )
        with pytest.raises(YarboSDKError):
            auth.login("user@test.com", "password123")


class TestRefresh:
    """TC-005 partial, TC-006."""

    @responses.activate
    def test_refresh_success(self, auth, api_base_url, mock_tokens):
        """Refresh returns new token."""
        # Login first
        responses.add(responses.POST, f"{api_base_url}/auth/login", json=mock_tokens, status=200)
        auth.login("user@test.com", "pass")

        new_token = "new_token_after_refresh"
        responses.add(
            responses.POST,
            f"{api_base_url}/auth/refresh",
            json={"token": new_token},
            status=200,
        )
        auth.refresh()
        assert auth.token == new_token

    @responses.activate
    def test_refresh_token_expired(self, auth, api_base_url, mock_tokens):
        """TC-006: refresh_token expired raises TokenExpiredError."""
        responses.add(responses.POST, f"{api_base_url}/auth/login", json=mock_tokens, status=200)
        auth.login("user@test.com", "pass")

        responses.add(
            responses.POST,
            f"{api_base_url}/auth/refresh",
            json={"error": "expired"},
            status=401,
        )
        with pytest.raises(TokenExpiredError):
            auth.refresh()


class TestRestoreSession:
    """TC-021: restore_session."""

    def test_restore_sets_tokens(self, auth):
        auth.restore("user@test.com", "saved_token", "saved_refresh")
        assert auth.username == "user@test.com"
        assert auth.token == "saved_token"
        assert auth.refresh_token == "saved_refresh"
        assert auth.is_authenticated is True


class TestTokenExport:
    """TC-022: Token property export."""

    @responses.activate
    def test_tokens_readable_after_login(self, auth, api_base_url):
        tokens = {"token": "jwt_abc", "refresh_token": "ref_xyz"}
        responses.add(responses.POST, f"{api_base_url}/auth/login", json=tokens, status=200)
        auth.login("user@test.com", "pass")
        assert auth.token == "jwt_abc"
        assert auth.refresh_token == "ref_xyz"


class TestBoundary:
    """Boundary condition tests."""

    def test_empty_username(self, auth):
        with pytest.raises(AuthenticationError):
            auth.login("", "password")

    def test_empty_password(self, auth):
        with pytest.raises(AuthenticationError):
            auth.login("user@test.com", "")

    def test_invalid_public_key(self, api_base_url):
        bad_auth = AuthManager(api_base_url, "not-a-valid-key")
        with pytest.raises(YarboSDKError, match="Invalid RSA public key"):
            bad_auth._encrypt_password("test")
