"""Shared pytest fixtures for Yarbo Robot SDK tests."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


@pytest.fixture
def rsa_key_pair():
    """Generate a fresh RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    return {"public_key": public_pem, "private_key": private_pem, "_private_key_obj": private_key}


@pytest.fixture
def api_base_url():
    return "https://test-api.yarbo.com"


@pytest.fixture
def mqtt_config():
    return {
        "mqtt_host": "test-mqtt.yarbo.com",
        "mqtt_port": 8883,
        "mqtt_use_tls": True,
    }


@pytest.fixture
def mock_tokens():
    return {
        "token": "mock_jwt_token_abc123",
        "refresh_token": "mock_refresh_token_xyz789",
    }


@pytest.fixture
def mock_devices_response():
    return {
        "devices": [
            {
                "sn": "SN001",
                "type_id": "mower",
                "name": "My Mower",
                "model": "M100",
                "online": True,
            },
            {
                "sn": "SN002",
                "type_id": "snowbot",
                "name": "My Snowbot",
                "model": "S200",
                "online": False,
            },
        ]
    }
