# Yarbo Robot SDK

Python SDK for integrating with Yarbo robots. It handles cloud authentication,
token refresh, REST device APIs, MQTT telemetry and commands, device modules,
and map coordinate conversion.

- **Package name:** `yarbo-data-sdk`
- **Import name:** `yarbo_robot_sdk`
- **Python:** `>= 3.10`
- **Type support:** PEP 561 typed package (includes `py.typed`)
- **License**: PolyForm Noncommercial 1.0.0

## Installation

```bash
pip install yarbo-data-sdk
```

For local development:

```bash
git clone https://github.com/YarboInc/YarboDataSDK.git
cd YarboDataSDK
pip install -e ".[dev]"
pytest
```

---

## Quick Start

```python
from yarbo_robot_sdk import YarboClient

# Create a client and log in
client = YarboClient()
client.login("user@example.com", "password")

# Get the device list
devices = client.get_devices()
device = devices[0]
print(f"{device.name}  SN={device.sn}")

# Release resources
client.close()
```

---

## Device Modules

The Yarbo Core can be fitted with a Mower, Snow Blower, Blower, Trimmer,
Plow, SAM, or other attachment.

The SDK offers three ways to send commands. `BoundYarboDevice` is recommended:

```python
# Recommended: bind a device for automatic attachment type checks
yarbo = client.device(device, data=snapshot)
yarbo.core.return_to_charge()
yarbo.mower.set_blade_height(60)          # Raises on an incompatible head_type

# Module facade: pass the serial number explicitly
client.mower.set_blade_height(device.sn, 60, device.type_id)

# Fallback: send a raw command when no typed method exists
yarbo.core.publish_command("wireless_charging_cmd", {"cmd": 1})
```

### Modules and Attachments

| Module | `HeadMsg.head_type` | Description |
|------|---------------------|------|
| `core` / `snow_bot` | All | Plans, charging, sound, lights, safety settings, and more |
| `mower` | `3` (Mower), `5` (Mower Pro) | Blade height and speed |
| `snow_blower` | `1` | Chute angle |
| `blower` | `2` | Blower commands |
| `trimmer` / `plow` / `sam` | — | Attachment commands |

---

## Complete Lifecycle

Follow these steps in order to avoid runtime errors.

### Steps 1–3: Initialize

Create a client, log in, and get the device list. These are REST calls and do
not require MQTT.

```python
from yarbo_robot_sdk import YarboClient

client = YarboClient()
client.login("user@example.com", "password")
device = client.get_devices()[0]
```

### Step 4: Connect to MQTT

Call this before any `subscribe_*` method.

```python
client.mqtt_connect()
```

### Step 5: Register Subscriptions

Call `subscribe_data_feedback` before data requests such as `get_device_msg`.

```python
from yarbo_robot_sdk import extract_field

def on_status(topic: str, data: dict) -> None:
    """Handle real-time device status (DeviceMSG)."""
    battery = extract_field(data, "BatteryMSG.capacity")
    state   = extract_field(data, "StateMSG.working_state")
    print(f"Battery={battery}%  working_state={state}")

def on_heartbeat(topic: str, data: dict) -> None:
    """Handle heartbeats (approximately every 30 seconds)."""
    print(f"Heartbeat: working_state={data.get('working_state')}")

def on_feedback(topic: str, data: dict) -> None:
    """Handle command responses on the data_feedback channel."""
    print(f"Feedback: topic={data.get('topic')}  result={data.get('result')}")

yarbo = client.device(device)
yarbo.core.subscribe_data_feedback(on_feedback)    # Subscribe to this first
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

### Step 6: Request Device Data

These calls are synchronous and blocking, and require Step 5. In asynchronous
frameworks such as Home Assistant, run them with `loop.run_in_executor()`.

```python
snapshot = yarbo.core.get_device_msg(timeout=10.0)   # Full device status
gps      = yarbo.core.read_gps_ref(timeout=10.0)     # GPS reference origin
plans    = yarbo.core.read_all_plan(timeout=10.0)    # All automatic plans
map_data = yarbo.core.get_map(timeout=30.0)          # Map and zones
```

### Step 7: Send Commands

Pass the latest snapshot so the SDK validates the attachment type before
sending a command.

```python
from yarbo_robot_sdk.exceptions import YarboSDKError

yarbo = client.device(device, data=snapshot)

try:
    yarbo.core.return_to_charge()
    yarbo.core.start_plan(plan_id=1)
    yarbo.core.set_headlight(True)
    yarbo.mower.set_blade_height(60)       # Raises YarboSDKError on head mismatch
    yarbo.snow_blower.set_chute_angle(90)
except YarboSDKError as e:
    print(f"Command rejected: {e}")
```

### Step 8: Reconnect After a Drop

MQTT is a long-lived connection. After a disconnect, call `mqtt_connect()`
again and register all subscriptions again; they are not restored automatically.

```python
# Register subscriptions again after reconnecting
client.mqtt_connect()
yarbo.core.subscribe_data_feedback(on_feedback)
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

### Step 9: Release Resources

Disconnect MQTT and release internal resources before the process exits.

```python
client.close()
```

### Common Ordering Mistakes

| Incorrect | Correct |
|-----------|-----------|
| Call `subscribe_*` before `mqtt_connect()` | Call `mqtt_connect()` before `subscribe_*` |
| Call `get_device_msg()` before `subscribe_data_feedback()` | Subscribe to data feedback first |
| Send attachment commands without `data=snapshot` | Use `client.device(device, data=snapshot)` for head checks |
| Exit without calling `close()` | Call `client.close()` in `finally` |

---

## Error Handling

All SDK exceptions inherit from `YarboSDKError`:

| Exception | When raised |
|------|---------|
| `AuthenticationError` | Invalid username or password |
| `TokenExpiredError` | Refresh token expired; log in again |
| `APIError` | REST request returned a non-2xx status; includes `status_code` |
| `MqttConnectionError` | MQTT connection failed |


---

## Session Persistence

Save tokens to skip login on the next start. The SDK refreshes the access token
once after a REST `401`; an expired refresh token raises `TokenExpiredError`
and requires a new login.

```python
# Save after login
client.login("user@example.com", "password")
saved_token   = client.token
saved_refresh = client.refresh_token

# Restore on the next start
client.restore_session("user@example.com", saved_token, saved_refresh)
```

---

## Helper Functions

```python
from yarbo_robot_sdk import (
    extract_field,            # Extract a DeviceMSG value by dot-path
    extract_active_network,   # Active network type (Halow / Wifi / 4G)
    convert_local_to_gps,     # Local coordinates to GPS latitude/longitude
    convert_map_to_geojson,   # Map data to a GeoJSON FeatureCollection
    get_field_definitions,         # All data field definitions for a device type
    get_control_field_definitions, # All control field definitions for a device type
)

# Extract field values
battery = extract_field(snapshot, "BatteryMSG.capacity")   # → 85
head    = extract_field(snapshot, "HeadMsg.head_type")      # → 3

# Resolve the active network
network = extract_active_network(snapshot.get("RoutePriority"))  # → "Wifi"

# Convert coordinates
lat, lon = convert_local_to_gps(
    x=10.5, y=-3.2,
    ref_lat=gps["data"]["ref"]["latitude"],
    ref_lon=gps["data"]["ref"]["longitude"],
)

# Convert map data to GeoJSON
geojson = convert_map_to_geojson(map_data["data"], gps["data"])
```

---

## Documentation

- [API Reference](docs/api.md) — methods, commands, and data models
- [MQTT Topics](docs/mqtt-topics.md) — subscription and publishing topics
- [Device Fields](docs/device-fields.md) — field paths and descriptions

---

## License

PolyForm Noncommercial 1.0.0. Use is limited to the purposes permitted by the
[license](LICENSE); it does not grant general commercial use rights.
