"""MQTT message codec — zlib compress/decompress with plaintext fallback.

All functions use only Python standard library (zlib, json).
"""

import json
import zlib

# Firmware version threshold for enabling zlib compression
MIN_ZLIB_VERSION: tuple[int, int, int] = (3, 9, 0)

# Valid zlib second-byte values (compression level marker)
_ZLIB_SECOND_BYTES = frozenset([0x01, 0x5E, 0x9C, 0xDA])


def is_zlib_compressed(data: bytes) -> bool:
    """Check if bytes look like zlib-compressed data via magic bytes.

    zlib (RFC 1950) starts with 0x78 followed by a level byte.
    This is a quick heuristic — use as an optimization hint, not a guarantee.
    """
    return len(data) >= 2 and data[0] == 0x78 and data[1] in _ZLIB_SECOND_BYTES


def decode_mqtt_payload(raw: bytes) -> dict:
    """Decode an MQTT payload to a dict, compatible with both compressed and plaintext.

    Strategy:
      1. Try zlib decompress → UTF-8 decode → JSON parse
      2. On any failure, fallback: UTF-8 decode → JSON parse (plaintext)

    Raises:
        ValueError: If both decompression and plaintext parsing fail.
    """
    # Try zlib decompression first
    try:
        decompressed = zlib.decompress(raw)
        return json.loads(decompressed.decode("utf-8"))
    except (zlib.error, Exception):
        pass

    # Fallback: treat as plaintext JSON
    return json.loads(raw.decode("utf-8"))


def encode_mqtt_payload(data: dict) -> bytes:
    """Encode a dict to zlib-compressed MQTT payload bytes.

    Flow: dict → JSON string → UTF-8 bytes → zlib compress
    """
    return zlib.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"))


def parse_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse a 'major.minor.patch' version string into an int tuple.

    Returns None if the string is empty or does not match the expected format.

    Examples:
        parse_version("3.9.0")  -> (3, 9, 0)
        parse_version("3.9.51") -> (3, 9, 51)
        parse_version("")       -> None
        parse_version("bad")    -> None
    """
    if not version_str:
        return None
    parts = version_str.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def should_compress(firmware_version: tuple[int, int, int] | None) -> bool:
    """Return True if the firmware version is at or above the compression threshold (3.9.0).

    Returns False when firmware_version is None (unknown version → safe fallback).
    """
    if firmware_version is None:
        return False
    return firmware_version >= MIN_ZLIB_VERSION
