# Yarbo Data SDK

Python SDK for Yarbo robot devices. Enables integration with smart home platforms and custom applications.

## Features

- **Authentication** — Login with email/password (RSA-encrypted), token refresh, session restore
- **Device Management** — Query device list via REST API
- **MQTT Real-time Data** — Subscribe to device messages and heart beats with automatic zlib decompression (firmware >= 3.9.0)
- **Device Control** — Publish commands via MQTT with automatic compression and debug logging
- **Request with Feedback** — Send commands and wait for device response via data_feedback topic
- **Device Registry** — JSON-driven device capability definitions with structured field and control metadata
- **Custom Extractors** — Extensible field extraction logic (network priority, volume scaling, RTK signal, planning/recharging status)

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
```

## Device Control

```python
# Set working state
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1, "source": "smart_home"})

# Sound control
client.mqtt_publish_command("SN123", "yarbo_Y", "set_sound_param", {"enable": True, "vol": 0.5, "mode": 0})

# Headlight control (all 7 light fields required)
client.mqtt_publish_command("SN123", "yarbo_Y", "light_ctrl", {
    "body_left_r": 255, "body_right_r": 255, "led_head": 255,
    "led_left_w": 255, "led_right_w": 255, "tail_left_r": 255, "tail_right_r": 255
})

# Start auto plan
client.mqtt_publish_command("SN123", "yarbo_Y", "start_plan", {"id": 123, "percent": 0})

# Pause / Resume / Stop plan
client.mqtt_publish_command("SN123", "yarbo_Y", "pause", {})
client.mqtt_publish_command("SN123", "yarbo_Y", "resume", {})
client.mqtt_publish_command("SN123", "yarbo_Y", "stop", {})

# Return to charge (disable wireless charging first)
client.mqtt_publish_command("SN123", "yarbo_Y", "wireless_charging_cmd", {"cmd": 0})
client.mqtt_publish_command("SN123", "yarbo_Y", "cmd_recharge", {"cmd": 2})
```

## Request with Feedback

Some commands return data via the `data_feedback` MQTT topic:

```python
# Fetch full device status snapshot
device_msg = client.get_device_msg("SN123", "yarbo_Y", timeout=10.0)

# Fetch all auto plans
plans = client.read_all_plan("SN123", "yarbo_Y", timeout=10.0)

# Fetch GPS reference origin
gps_ref = client.read_gps_ref("SN123", "yarbo_Y", timeout=10.0)
```

## Device Registry

Access device field definitions programmatically:

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions

# Sensor/binary_sensor field definitions
fields = get_field_definitions("yarbo_Y")
for f in fields:
    print(f"{f.path} -> {f.name} ({f.entity_type})")

# Control field definitions (select/switch/number)
controls = get_control_field_definitions("yarbo_Y")
for c in controls:
    print(f"{c.path} -> {c.name} ({c.entity_type})")
```

### Supported Control Topics

| Topic | Description | Payload Example |
|-------|-------------|-----------------|
| set_working_state | Set working state | `{"state": 1, "source": "smart_home"}` |
| set_sound_param | Sound control | `{"enable": true, "vol": 0.5, "mode": 0}` |
| light_ctrl | Headlight control | `{"body_left_r": 255, ...}` (7 fields) |
| start_plan | Start auto plan | `{"id": 123, "percent": 0}` |
| pause | Pause plan | `{}` |
| resume | Resume plan | `{}` |
| stop | Stop plan | `{}` |
| cmd_recharge | Return to charge | `{"cmd": 2}` |
| wireless_charging_cmd | Wireless charging | `{"cmd": 0}` |
| read_all_plan | Request plans | `{}` (response via data_feedback) |
| get_device_msg | Request full status | `{}` (response via data_feedback) |
| read_gps_ref | Request GPS ref | `{}` (response via data_feedback) |
| get_map | Request map data | `{}` (response via data_feedback) |

### Network Helper

```python
from yarbo_robot_sdk import extract_active_network

# Determine active network from route_priority data
# Returns the interface with the lowest non-negative priority value
result = extract_active_network({"hg0": 10, "wlan0": 600, "wwan0": -1})
# result = "Halow" (hg0 has lowest priority value)
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
