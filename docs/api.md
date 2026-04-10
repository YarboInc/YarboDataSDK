# API Reference

## Getting Started

### 1. Login and Get Your Devices

```python
from yarbo_robot_sdk import YarboClient

client = YarboClient()
client.login("your@email.com", "password")

devices = client.get_devices()
for device in devices:
    print(f"{device.name} (SN: {device.sn}, Type: {device.type_id})")
```

Each device has a `sn` (serial number) and `type_id` (device model identifier, e.g. `"yarbo_Y"` for Y Series). These two values are used in all subsequent API calls.

### 2. Connect and Subscribe to Real-time Data

```python
client.mqtt_connect()

def on_status(topic, data):
    print(f"Battery: {data.get('BatteryMSG', {}).get('capacity')}%")

device = devices[0]
client.subscribe_device_message(device.sn, device.type_id, on_status)
client.subscribe_heart_beat(device.sn, device.type_id, on_heartbeat)
```

### 3. Request Data On Demand

```python
# Full device status snapshot
status = client.get_device_msg(device.sn, device.type_id)

# GPS reference origin
gps = client.read_gps_ref(device.sn, device.type_id)

# Map/zone data
map_data = client.get_map(device.sn, device.type_id)

# All auto plans
plans = client.read_all_plan(device.sn, device.type_id)
```

### 4. Send Control Commands

```python
client.mqtt_publish_command(device.sn, device.type_id, "set_working_state", {"state": 1})
```

### 5. Session Persistence

```python
# Save tokens (avoid re-login on next startup)
saved_token = client.token
saved_refresh = client.refresh_token

# Restore later
client.restore_session(username="your@email.com", token=saved_token, refresh_token=saved_refresh)
```

---

## Complete Method Reference

### Authentication

| Method | Description |
|--------|-------------|
| `login(username, password)` | Login with email and password |
| `restore_session(username, token, refresh_token)` | Restore session from saved tokens |
| `token` / `refresh_token` (properties) | Current tokens for persistence |

### Device Management

| Method | Description |
|--------|-------------|
| `get_devices()` → `list[Device]` | Get all devices on the account |

### Real-time Subscription

| Method | Description |
|--------|-------------|
| `subscribe_device_message(sn, type_id, callback)` | Real-time device status updates |
| `subscribe_heart_beat(sn, type_id, callback)` | Device heartbeat (connectivity) |
| `subscribe_data_feedback(sn, type_id, callback)` | Command response messages |

### Data Requests

| Method | Description |
|--------|-------------|
| `get_device_msg(sn, type_id)` | Full device status snapshot |
| `read_all_plan(sn, type_id)` | All auto plans |
| `read_gps_ref(sn, type_id)` | GPS reference origin |
| `get_map(sn, type_id)` | Map/zone data |

### Device Control

| Method | Description |
|--------|-------------|
| `mqtt_publish_command(sn, type_id, command_name, payload)` | Send control command |

### Lifecycle

| Method | Description |
|--------|-------------|
| `mqtt_connect()` | Connect to MQTT |
| `close()` | Clean up all resources |

---

## Helper Functions

```python
from yarbo_robot_sdk import (
    get_field_definitions,          # List all available data fields for a device type
    get_control_field_definitions,  # List all available control fields for a device type
    extract_field,                  # Extract value from status data by field path
    extract_active_network,         # Get active network type (Halow/Wifi/4G)
    convert_local_to_gps,           # Convert device local coordinates to GPS
    convert_map_to_geojson,         # Convert map data to GeoJSON format
)
```

---

## Data Models

### Device

| Field | Type | Description |
|-------|------|-------------|
| `sn` | `str` | Serial number (unique device identifier) |
| `type_id` | `str` | Device model (e.g. `"yarbo_Y"` for Y Series) |
| `name` | `str` | Display name |
| `model` | `str` | Model name |
| `online` | `bool` | Online status |

---

## Exceptions

| Exception | When |
|-----------|------|
| `YarboSDKError` | Base class for all SDK errors |
| `AuthenticationError` | Invalid credentials |
| `TokenExpiredError` | Tokens expired, must re-login |
