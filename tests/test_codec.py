"""Tests for codec — TC-001 to TC-006."""

import json
import zlib

import pytest

from yarbo_robot_sdk.codec import (
    decode_mqtt_payload,
    encode_mqtt_payload,
    is_zlib_compressed,
    parse_version,
    should_compress,
)


class TestDecodePayload:
    """TC-001, TC-002."""

    def test_decode_compressed_payload(self):
        """TC-001: Decode a zlib-compressed JSON payload."""
        data = {"working_state": 1}
        compressed = zlib.compress(json.dumps(data).encode("utf-8"))
        result = decode_mqtt_payload(compressed)
        assert result == data

    def test_decode_plaintext_payload(self):
        """TC-002: Decode a plaintext JSON payload (fallback path)."""
        data = {"version": "3.8.0"}
        payload = json.dumps(data).encode("utf-8")
        result = decode_mqtt_payload(payload)
        assert result == data

    def test_decode_invalid_raises(self):
        with pytest.raises(Exception):
            decode_mqtt_payload(b"not json and not zlib")

    def test_decode_complex_nested_payload(self):
        data = {"BatteryMSG": {"capacity": 80}, "version": "3.9.1"}
        compressed = zlib.compress(json.dumps(data).encode("utf-8"))
        assert decode_mqtt_payload(compressed) == data


class TestEncodePayload:
    """TC-003."""

    def test_encode_roundtrip(self):
        """TC-003: Encoded bytes can be decompressed and parsed back."""
        data = {"state": 0, "key": "value"}
        encoded = encode_mqtt_payload(data)
        decoded = json.loads(zlib.decompress(encoded).decode("utf-8"))
        assert decoded == data

    def test_encode_produces_zlib_bytes(self):
        encoded = encode_mqtt_payload({"a": 1})
        assert is_zlib_compressed(encoded)


class TestIsZlibCompressed:
    """TC-004."""

    def test_zlib_bytes_returns_true(self):
        assert is_zlib_compressed(zlib.compress(b"test")) is True

    def test_plaintext_returns_false(self):
        assert is_zlib_compressed(b'{"a":1}') is False

    def test_empty_bytes_returns_false(self):
        assert is_zlib_compressed(b"") is False

    def test_single_byte_returns_false(self):
        assert is_zlib_compressed(b"\x78") is False

    def test_all_zlib_second_bytes(self):
        for second in (0x01, 0x5E, 0x9C, 0xDA):
            assert is_zlib_compressed(bytes([0x78, second])) is True


class TestParseVersion:
    """TC-005."""

    def test_parse_valid(self):
        assert parse_version("3.9.0") == (3, 9, 0)
        assert parse_version("3.9.51") == (3, 9, 51)
        assert parse_version("3.8.99") == (3, 8, 99)
        assert parse_version("10.0.1") == (10, 0, 1)

    def test_parse_empty_returns_none(self):
        assert parse_version("") is None

    def test_parse_invalid_returns_none(self):
        assert parse_version("invalid") is None
        assert parse_version("3.9") is None
        assert parse_version("3.9.0.1") is None


class TestShouldCompress:
    """TC-006."""

    def test_exactly_threshold_returns_true(self):
        assert should_compress((3, 9, 0)) is True

    def test_above_threshold_returns_true(self):
        assert should_compress((3, 9, 1)) is True
        assert should_compress((4, 0, 0)) is True

    def test_below_threshold_returns_false(self):
        assert should_compress((3, 8, 99)) is False
        assert should_compress((3, 0, 0)) is False

    def test_none_returns_false(self):
        assert should_compress(None) is False
