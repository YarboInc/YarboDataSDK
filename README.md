# Yarbo Data SDK

Python SDK for Yarbo robot devices. Enables integration with smart home platforms and custom applications.

## Features

- **Authentication** — Login with email/password (RSA-encrypted), token refresh, session restore
- **Device Management** — Query device list via REST API
- **MQTT Real-time Data** — Subscribe to device messages and heart beats with automatic zlib decompression (firmware >= 3.9.0)
- **Device Control** — Publish commands via MQTT with automatic compression
- **Device Registry** — JSON-driven device capability definitions with structured field metadata

## Installation

```bash
pip install yarbo-data-sdk
```

**Requirements**: Python >= 3.10

## Quick Start

```python
from yarbo_robot_sdk import YarboClient

client = YarboClient(api_base_url="https://api.yarbo.com")
client.login("user@email.com", "password")

devices = client.get_devices()
for device in devices:
    print(f"{device.name} ({device.sn}) - Online: {device.online}")
```

## MQTT Real-time Updates

```python
client.mqtt_connect()

# Subscribe to device status messages
def on_device_message(topic, data):
    print(f"Status update: {data}")

client.subscribe_device_message("SN123", "yarbo_Y", on_device_message)

# Subscribe to heart beat
def on_heart_beat(topic, data):
    print(f"Heart beat: {data}")

client.subscribe_heart_beat("SN123", "yarbo_Y", on_heart_beat)

# Control device via MQTT command
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1})

# Clean up
client.close()
```

## Session Persistence

```python
# Save tokens
saved_token = client.token
saved_refresh_token = client.refresh_token

# Restore in a new client (no re-login needed)
client2 = YarboClient(api_base_url="https://api.yarbo.com")
client2.restore_session(
    username="user@email.com",
    token=saved_token,
    refresh_token=saved_refresh_token,
)
```

## Documentation

- [API Reference](docs/api.md) — All methods, parameters, and return types
- [MQTT Topics](docs/mqtt-topics.md) — Topic formats, payload structures, compression
- [Device Fields](docs/device-fields.md) — Complete field definitions for all device types

## License

MIT
