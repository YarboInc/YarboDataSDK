# Yarbo Data SDK

Python SDK for Yarbo robot devices. Enables integration with smart home platforms and custom applications.

## Features

- **Authentication** — Login with email/password (RSA-encrypted), token refresh, session restore
- **Device Management** — Query device list, status, battery, position, working state via REST API
- **MQTT Real-time Data** — Subscribe to device messages and heart beats with automatic zlib decompression (firmware >= 3.9.0)
- **Device Control** — Set working state and publish commands via MQTT with automatic compression
- **Device Registry** — JSON-driven device capability definitions with structured field metadata

## Installation

```bash
pip install yarbo-data-sdk
```

**Requirements**: Python >= 3.10

## Quick Start

```python
from yarbo_robot_sdk import YarboClient

# Initialize client (production — config fetched from cloud)
client = YarboClient(api_base_url="https://api.yarbo.com")

# Login
client.login("user@email.com", "password")

# Get devices
devices = client.get_devices()
for device in devices:
    print(f"{device.name} ({device.sn}) - Online: {device.online}")
```

## MQTT Real-time Updates

```python
# Connect to MQTT broker
client.mqtt_connect()

# Subscribe to device status messages
def on_device_message(topic, data):
    print(f"Status update: {data}")

client.subscribe_device_message("SN123", "snowbot", on_device_message)

# Subscribe to heart beat
def on_heart_beat(topic, data):
    print(f"Heart beat: {data}")

client.subscribe_heart_beat("SN123", "snowbot", on_heart_beat)

# Control device — set working state
client.set_working_state("SN123", "snowbot", state=1)  # 1 = working, 0 = standby
```

## REST API Helpers

```python
# Get device status details
status = client.get_device_status("SN123")

# Get battery info
battery = client.get_battery("SN123")
# {'capacity': 85, 'status': 1, ...}

# Get position
position = client.get_position("SN123")
# {'x': 1.23, 'y': 4.56, 'phi': 0.78}

# Get working state
state = client.get_working_state("SN123")
```

## Session Persistence

```python
# Save tokens for later use
saved_token = client.token
saved_refresh_token = client.refresh_token

# Restore session in a new client (no re-login needed)
client2 = YarboClient(api_base_url="https://api.yarbo.com")
client2.restore_session(
    username="user@email.com",
    token=saved_token,
    refresh_token=saved_refresh_token,
)
devices = client2.get_devices()
```

## Device Registry

```python
from yarbo_robot_sdk import get_device_type, list_device_types, get_field_definitions

# List all registered device types
types = list_device_types()

# Query device capabilities
device_type = get_device_type("snowbot")
print(device_type.name)         # "Yarbo Y"
print(device_type.topics)       # MQTT topic definitions
print(device_type.rest_apis)    # REST API endpoints

# Get structured field definitions (for building UIs or integrations)
fields = get_field_definitions("snowbot")
for field in fields:
    print(f"{field.name}: {field.path} ({field.entity_type})")
```

## Error Handling

```python
from yarbo_robot_sdk import (
    YarboSDKError,
    AuthenticationError,
    TokenExpiredError,
    APIError,
    MqttConnectionError,
)

try:
    client.login("user@email.com", "wrong_password")
except AuthenticationError as e:
    print(f"Login failed: {e}")
except TokenExpiredError:
    print("Token expired, please login again")
except APIError as e:
    print(f"API error: {e}")
except MqttConnectionError as e:
    print(f"MQTT connection failed: {e}")
```

## License

MIT
