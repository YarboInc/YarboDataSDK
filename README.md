# Yarbo Robot SDK

Python SDK for Yarbo robot devices. Enables integration with smart home platforms and custom applications.

## Installation

```bash
pip install yarbo-robot-sdk
```

## Quick Start

```python
from yarbo_robot_sdk import YarboClient

# Initialize client
client = YarboClient(api_base_url="https://api.yarbo.com")

# Login
client.login("user@email.com", "password")

# Get devices
devices = client.get_devices()
for device in devices:
    print(f"{device.name} ({device.sn}) - Online: {device.online}")

# Subscribe to MQTT updates
def on_status(topic, payload):
    print(f"Received: {topic} -> {payload}")

client.mqtt_connect()
client.mqtt_subscribe("snowbot/SN123/status", on_status)

# Save tokens for later session restore
saved_token = client.token
saved_refresh_token = client.refresh_token

# Restore session (no need to login again)
client2 = YarboClient(api_base_url="https://api.yarbo.com")
client2.restore_session(token=saved_token, refresh_token=saved_refresh_token)

# Query device capabilities
device_types = client.list_device_types()
```

## Requirements

- Python >= 3.10
