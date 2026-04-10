# Yarbo Data SDK

Python SDK for Yarbo robot devices. Enables integration with smart home platforms and custom applications.

**Requirements**: Python >= 3.10

## Installation

```bash
pip install yarbo-data-sdk
```

## Quick Start

```python
from yarbo_robot_sdk import YarboClient

client = YarboClient()
client.login("user@email.com", "password")

devices = client.get_devices()
for device in devices:
    print(f"{device.name} ({device.sn})")
```

## Features

### Authentication

Login with email/password (RSA-encrypted), automatic token refresh, and session save/restore.

```python
client.login("user@email.com", "password")

# Save session
token, refresh_token = client.token, client.refresh_token

# Restore session (no re-login needed)
client.restore_session(username="user@email.com", token=token, refresh_token=refresh_token)
```

### MQTT Real-time Data

Subscribe to device status messages and heartbeat with automatic zlib decompression (firmware >= 3.9.0).

```python
client.mqtt_connect()
client.subscribe_device_message("SN123", "yarbo_Y", callback)
client.subscribe_heart_beat("SN123", "yarbo_Y", callback)
```

### Device Control

Publish commands via MQTT with automatic compression.

```python
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1})
```

### Request with Feedback

Send commands and wait for device response via data_feedback topic.

```python
client.get_device_msg("SN123", "yarbo_Y")
client.read_all_plan("SN123", "yarbo_Y")
client.read_gps_ref("SN123", "yarbo_Y")
```

### Device Registry

JSON-driven device capability definitions with structured field and control metadata.

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions

fields = get_field_definitions("yarbo_Y")
controls = get_control_field_definitions("yarbo_Y")
```

## Documentation

- [API Reference](docs/api.md)
- [MQTT Topics](docs/mqtt-topics.md)
- [Device Fields](docs/device-fields.md)

## License

MIT
