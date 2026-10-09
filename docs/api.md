# API Reference

## How to Use This Reference

### Recommended API and Low-Level Fallback

Commands can be sent in two ways:

- **Recommended:** Use typed methods on the `BoundYarboDevice` returned by `client.device(device)`. The SDK handles the lower-level details.
- **Low-level fallback:** Use `mqtt_publish_command` or `publish_command` with an explicit topic name and payload for commands without typed methods or for debugging.

```python
# Recommended
yarbo.mower.set_blade_height(60)

# Low-level fallback for commands without a typed method
yarbo.mower.publish_command("mower_target_cmd", {"target": 60})
client.mqtt_publish_command(device.sn, device.type_id, "mower_target_cmd", {"target": 60})
```

### Command Table Columns

The `BoundYarboDevice` and `YarboClient` command tables use these columns:

| Column | Meaning |
|------|------|
| **Method** | Typed method name; the SDK constructs its payload |
| **MQTT topic** | Command name sent to `snowbot/{sn}/app/{topic}` |
| **Payload** | Raw MQTT message data; constructed by typed methods or supplied manually for low-level calls |
| **Feedback** | `Yes`: the device confirms on `data_feedback`, and `request_with_feedback` can wait for it; `No`: call `get_device_msg()` to query the latest state |
| **Risk** | `Low`: reversible without motion; `Medium`: changes motion or attachment state; `High`: irreversible or changes safety settings |

---

## Getting Started

> **Lifecycle overview**
>
> Follow these six steps in order to avoid runtime errors:
>
> ```
> 1. YarboClient()          ← create the client
> 2. login() / restore_session()  ← authenticate over REST; MQTT not required
> 3. get_devices()          ← get the device list over REST
> 4. mqtt_connect()         ← initialize MQTT routing; no connection yet
> 5. subscribe_data_feedback()    ← first subscription routes by SN and connects to its broker
>    subscribe_device_message()   ← optional status updates
>    subscribe_heart_beat()       ← optional heartbeat updates
> 6. get_device_msg() / send commands / close()
> ```
>
> **During EMQX migration:** The SDK routes each serial number to the legacy or new broker (see [mqtt-topics.md](mqtt-topics.md)). The call order stays the same regardless of which cluster hosts a device.

### 1. Create a Client

```python
from yarbo_robot_sdk import YarboClient

# Default — production URL is built-in; mqtt/rsa settings fetched from cloud
client = YarboClient()

# Explicit — provide all settings directly, no cloud fetch
client = YarboClient(
    api_base_url="https://data-api.yarbo.ai",
    mqtt_host="mqtt.yarbo.ai",
    mqtt_port=8883,
    mqtt_use_tls=True,
    rsa_public_key="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
    # Optional — new EMQX Dedicated cluster (for devices migrated off the
    # legacy shared broker). Sensible production defaults are baked in;
    # override only for staging or local dev.
    new_mqtt_host="c4750009.ala.dedicated.aws.emqxcloud.com",
    new_mqtt_port=8883,
    new_mqtt_use_tls=True,
    emqx_migration_query_url=(
        "https://gu7e5n9ef4.execute-api.us-east-1.amazonaws.com"
        "/Stage/yarbo/emqx-migration/query"
    ),
)
```

`api_base_url` defaults to `https://data-api.yarbo.ai`. The remaining settings
(`mqtt_host`, `mqtt_port`, `mqtt_use_tls`, `rsa_public_key`) are fetched once
from `GET /sdk/config` if not passed to the constructor.

The `new_mqtt_*` and `emqx_migration_query_url` parameters control the
new EMQX Dedicated cluster used by migrated devices. They follow the same
three-tier priority: **constructor arg → `/sdk/config` cloud → SDK built-in
default**. You almost never need to set them — built-in defaults point at the
production new broker and Lambda query endpoint.

### 2. Login and Get Devices

```python
client.login("your@email.com", "password")

devices = client.get_devices()
device = devices[0]
print(f"{device.name}  SN={device.sn}  type={device.type_id}")
```

### 3. Connect and Subscribe to Real-time Data

```python
client.mqtt_connect()

def on_status(topic, data):
    print(f"Battery: {data.get('BatteryMSG', {}).get('capacity')}%")

def on_heartbeat(topic, data):
    print(f"Working state: {data.get('working_state')}")

yarbo = client.device(device)
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

> **💡 Recommended:** `client.device(device)` returns a `BoundYarboDevice` — a typed handle bound to one robot. You never need to pass `sn` or `type_id` again.
>
> **⚙️ Low-level fallback:** `client.subscribe_device_message(device.sn, device.type_id, callback)`

### 4. Request Data On Demand

Data requests are **synchronous and blocking**. Call `subscribe_data_feedback` once before using any of them.

```python
yarbo.core.subscribe_data_feedback()

status   = yarbo.core.get_device_msg()
gps      = yarbo.core.read_gps_ref()
map_data = yarbo.core.get_map()          # default timeout 30 s
plans    = yarbo.core.read_all_plan()
wifi     = yarbo.core.get_connect_wifi_name()
```

> **⚙️ Low-level fallback:** `client.subscribe_data_feedback(device.sn, device.type_id)` then `client.get_device_msg(device.sn, device.type_id)`

### 5. Send Commands

Pass the latest snapshot to `client.device()` so attachment commands validate the current head type before sending.

```python
yarbo = client.device(device, data=status)

# Core platform
yarbo.core.set_working_state(1)
yarbo.core.start_plan(plan_id=3, start_percent=50)
yarbo.core.pause()
yarbo.core.resume()
yarbo.core.stop()
yarbo.core.return_to_charge()

# Sound & lights
yarbo.core.song_cmd("find yarbo")
yarbo.core.set_sound_param(enable=True, vol=0.7)
yarbo.core.set_headlight(True)

# Safety & boundary
yarbo.core.set_child_lock(True)
yarbo.core.set_person_detect(True)
yarbo.core.set_follow_state(True)
yarbo.core.save_global_params(enable_elec_fence=True)
yarbo.core.set_map_obstacle_switch(True)
yarbo.core.clear_obstacle_zones()

# Attachment-specific (SDK validates head_type when data is supplied)
yarbo.mower.set_blade_height(60)        # head_type 3 or 5
yarbo.mower.set_blade_speed(85)
yarbo.snow_blower.set_chute_angle(120)  # head_type 1
```

> **⚙️ Fallback for unlisted commands:** `yarbo.core.publish_command("wireless_charging_cmd", {"cmd": 0})`
>
> **⚙️ Low-level fallback:** `client.mqtt_publish_command(device.sn, device.type_id, "pause", {})`

### 6. Session Persistence and Clean Up

```python
# Persist tokens across restarts
saved_token   = client.token
saved_refresh = client.refresh_token

client.restore_session(username="your@email.com",
                       token=saved_token,
                       refresh_token=saved_refresh)

client.close()
```

### 7. Reconnect on Drop

MQTT connections may drop during network interruptions. Call `mqtt_connect()`
again and register all subscriptions again; they are not restored automatically.

```python
client.mqtt_connect()
yarbo.core.subscribe_data_feedback(on_feedback)
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

### 8. Error Handling

All SDK exceptions below inherit from `YarboSDKError`:

| Exception | When raised |
|------|---------|
| `AuthenticationError` | Invalid username or password |
| `TokenExpiredError` | Refresh token expired; log in again |
| `APIError` | REST request returned a non-2xx status; includes `status_code` |
| `MqttConnectionError` | MQTT connection failed |

```python
from yarbo_robot_sdk.exceptions import (
    YarboSDKError, AuthenticationError, TokenExpiredError,
    APIError, MqttConnectionError,
)

try:
    client.login("user@example.com", "password")
    client.mqtt_connect()
    yarbo.core.return_to_charge()
except AuthenticationError:
    print("Invalid username or password")
except TokenExpiredError:
    client.login("user@example.com", "password")  # Log in again
except MqttConnectionError as e:
    print(f"MQTT connection failed: {e}")
except APIError as e:
    print(f"REST request failed: HTTP {e.status_code}")
except YarboSDKError as e:
    print(f"SDK error: {e}")  # Fallback for other SDK errors
```

---

## `BoundYarboDevice` Reference

Returned by `client.device(device, data=None)`. No `sn` or `type_id` needed on any call.
Passing `data` (a DeviceMSG snapshot) enables SDK-side head-type validation for attachment commands.

> **Risk levels** — `Low`: no motion, reversible. `Medium`: changes motion or attachment state. `High`: irreversible or modifies safety configuration.

### `yarbo.core` / `yarbo.snow_bot`

**Subscriptions & data requests:**

| Method | MQTT topic | Description |
|--------|-----------|-------------|
| `subscribe_device_message(callback)` | `snowbot/{sn}/device/DeviceMSG` | Real-time DeviceMSG updates |
| `subscribe_heart_beat(callback)` | `snowbot/{sn}/device/heart_beat` | Heartbeat updates |
| `subscribe_data_feedback(callback=None)` | `snowbot/{sn}/device/data_feedback` | Command-response channel — required before data requests |
| `get_device_msg(timeout=10.0)` | — | Full DeviceMSG snapshot (`BatteryMSG`, `HeadMsg`, …) |
| `read_gps_ref(timeout=10.0)` | — | GPS reference origin (`data.ref.latitude/longitude`) |
| `get_map(timeout=30.0)` | — | Map and zone data (`data.areas`, `data.pathways`) |
| `read_all_plan(timeout=10.0)` | — | All auto plans (`data.data[].id/name/areaIds`) |
| `get_connect_wifi_name(timeout=10.0)` | — | Wi-Fi info (`data.signal`) |

**Core platform commands:**

| Method | MQTT topic | Payload | Feedback | Risk |
|--------|-----------|---------|----------|------|
| `set_working_state(state, source="smart_home")` | `set_working_state` | `{"state": 0\|1, "source": "smart_home"}` | No | Medium |
| `start_plan(plan_id, start_percent=0)` | `start_plan` | `{"id": <id>}` or `{"id": <id>, "percent": <0–100>}` | No | Medium |
| `pause()` | `pause` | `{}` | No | Low |
| `resume()` | `resume` | `{}` | No | Low |
| `stop()` | `stop` | `{}` | No | Medium |
| `return_to_charge()` | `cmd_recharge` | `{}` | No | Medium |

**Sound & lights:**

| Method | MQTT topic | Payload | Feedback | Risk |
|--------|-----------|---------|----------|------|
| `song_cmd(song_name="find yarbo")` | `song_cmd` | `{"song_name": "find yarbo"}` | No | Low |
| `set_sound_param(enable, vol, mode=0)` | `set_sound_param` | `{"enable": bool, "vol": 0.0–1.0, "mode": 0}` | No | Low |
| `set_headlight(on)` | `light_ctrl` | `{"led_head": 1\|0}` | No | Low |

> `vol` is `0.0–1.0`. The Home Assistant UI scales this to `0–100 %`.

**Safety & boundary:**

| Method | MQTT topic | Payload | Feedback | Risk |
|--------|-----------|---------|----------|------|
| `set_child_lock(enabled)` | `set_child_lock` | `{"state": true\|false}` | No | Medium |
| `set_person_detect(enabled)` | `set_person_detect` | `{"state": 1\|0}` | No | Low |
| `set_follow_state(enabled)` | `set_follow_state` | `{"state": 1\|0}` | No | Medium |
| `save_global_params(enable_elec_fence, id=1)` | `save_global_params` | `{"id": 1, "enable_elec_fence": bool}` | No | High |
| `set_map_obstacle_switch(enabled)` | `set_map_obstacle_switch` | `{"switch": 1\|0}` | No | High |
| `clear_obstacle_zones()` | `ignore_obstacles` | `{"zone": []}` | No | High |
| `wireless_charging_cmd(cmd=0)` | `wireless_charging_cmd` | `{"cmd": 0\|1}` | No | Medium |

> `wireless_charging_cmd`: `cmd=0` stops charging; `cmd=1` starts charging.

**Fallback:**

| Method | Description |
|--------|-------------|
| `publish_command(command, payload)` | Send any raw command not covered by a typed method |

### `yarbo.mower` — head_type 3 (Mower) or 5 (Mower Pro)

SDK raises `YarboSDKError` if called with a non-mower head type when `data` was supplied to `client.device()`.
Includes all `yarbo.core` methods plus:

| Method | MQTT topic | Payload | Range | Feedback | Risk |
|--------|-----------|---------|-------|----------|------|
| `set_blade_height(height_mm)` | `mower_target_cmd` | `{"target": <mm>}` | 20–100 mm | No | Medium |
| `set_blade_speed(speed_percent)` | `mower_speed_cmd` | `{"state": <percent>}` | 0–100 % | No | Medium |
| `publish_command(command, payload)` | — | — | — | — | — |

### `yarbo.snow_blower` — head_type 1

SDK raises `YarboSDKError` if called with a non-snow-blower head type when `data` was supplied to `client.device()`.
Includes all `yarbo.core` methods plus:

| Method | MQTT topic | Payload | Range | Feedback | Risk |
|--------|-----------|---------|-------|----------|------|
| `set_chute_angle(angle)` | `cmd_set_chute_angle` | `{"cmd": <degrees>}` | 0–180 ° | No | Medium |
| `publish_command(command, payload)` | — | — | — | — | — |

### `yarbo.blower` / `yarbo.trimmer` / `yarbo.plow` / `yarbo.sam`

Includes all `yarbo.core` methods plus `publish_command(command, payload)`.

### Head Type Reference

| `HeadMsg.head_type` | Attachment |
|---------------------|-----------|
| `0` | None |
| `1` | Snow Blower |
| `2` | Blower |
| `3` | Mower |
| `4` | Smart Cover |
| `5` | Mower Pro |

---

## `YarboClient` Reference

### Constructor

```python
YarboClient(
    api_base_url: str | None = None,        # default: "https://data-api.yarbo.ai"
    mqtt_host: str | None = None,           # legacy broker host, cloud-fetched if omitted
    mqtt_port: int | None = None,           # legacy broker port, cloud-fetched if omitted
    mqtt_use_tls: bool | None = None,       # legacy broker TLS, cloud-fetched if omitted
    rsa_public_key: str | None = None,      # cloud-fetched if omitted
    new_mqtt_host: str | None = None,       # new EMQX Dedicated host, SDK default applies
    new_mqtt_port: int | None = None,       # new broker port, SDK default applies
    new_mqtt_use_tls: bool | None = None,   # new broker TLS, SDK default applies
    emqx_migration_query_url: str | None = None,  # Lambda query URL, SDK default applies
)
```

All `new_mqtt_*` and `emqx_migration_query_url` parameters follow three-tier
priority: constructor arg → `/sdk/config` cloud → SDK built-in defaults.
Production-ready defaults are baked in; override only for staging / local dev.

### Authentication

| Method | Description |
|--------|-------------|
| `login(username, password)` | Login (password RSA-encrypted internally) |
| `restore_session(username, token, refresh_token)` | Restore a previous session from saved tokens |
| `token` *(property)* | Current JWT token |
| `refresh_token` *(property)* | Current refresh token |

### Devices

| Method | Returns | Description |
|--------|---------|-------------|
| `get_devices()` | `list[Device]` | All devices on the account |
| `device(device, data=None)` | `BoundYarboDevice` | Bind the command API to one device; pass a DeviceMSG snapshot to enable head-type validation |

### MQTT Lifecycle

| Method | Description |
|--------|-------------|
| `mqtt_connect()` | Connect to the MQTT broker |
| `mqtt_disconnect()` | Disconnect from the broker |
| `close()` | Disconnect and clean up all resources |

### Low-Level API (Direct Access)

Use these when you do not want to call `client.device()` first. All methods require `sn` and `type_id` explicitly.

**Subscriptions:**

| Method | Description |
|--------|-------------|
| `subscribe_device_message(sn, type_id, callback)` | Real-time DeviceMSG updates |
| `subscribe_heart_beat(sn, type_id, callback)` | Heartbeat updates |
| `subscribe_data_feedback(sn, type_id, callback=None)` | Command-response channel — required before data requests |

**Data requests** (blocking, require `subscribe_data_feedback` first):

| Method | Timeout | Description |
|--------|---------|-------------|
| `get_device_msg(sn, type_id, timeout=10.0)` | 10 s | Full DeviceMSG snapshot |
| `read_all_plan(sn, type_id, timeout=10.0)` | 10 s | All auto plans |
| `read_gps_ref(sn, type_id, timeout=10.0)` | 10 s | GPS reference origin |
| `get_map(sn, type_id, timeout=30.0)` | 30 s | Map and zone data |
| `get_connect_wifi_name(sn, type_id, timeout=10.0)` | 10 s | Wi-Fi name and signal |

**Commands:**

| Method | Description |
|--------|-------------|
| `mqtt_publish_command(sn, type_id, command_name, payload)` | Send any command; auto-compresses payload for firmware ≥ 3.9.0 |

**Module facades** — same typed methods as `BoundYarboDevice` but `sn` is the first argument and `type_id` defaults to `"yarbo_Y"`:

| Module | Description |
|--------|-------------|
| `client.core` / `client.snow_bot` | All core platform commands |
| `client.mower` | `set_blade_height(sn, ...)`, `set_blade_speed(sn, ...)` |
| `client.snow_blower` | `set_chute_angle(sn, ...)` |
| `client.blower` / `client.trimmer` / `client.plow` / `client.sam` | `publish_command(sn, command, payload)` |

**Advanced — send a command and block for its response:**

```python
result = client.request_with_feedback(
    sn, type_id,
    command_topic_name,     # command topic name
    payload,                # payload dict
    response_topic_filter,  # expected "topic" in data_feedback
    timeout=10.0,
)
```

---

## Helper Functions

```python
from yarbo_robot_sdk import (
    get_field_definitions,          # all data fields for a device type
    get_control_field_definitions,  # all control fields for a device type
    extract_field,                  # extract a value by dot-path from a DeviceMSG dict
    extract_active_network,         # active network type (Halow / Wifi / 4G)
    convert_local_to_gps,           # device-local coordinates → GPS lat/lon
    convert_map_to_geojson,         # map payload → GeoJSON FeatureCollection
)
```

**`extract_field(data, field_path)`**

```python
battery   = extract_field(status, "BatteryMSG.capacity")   # → 85
head_type = extract_field(status, "HeadMsg.head_type")      # → 3
```

**`extract_active_network(route_priority)`** — pass `data.get("RoutePriority")` from a DeviceMSG; returns `"Halow"`, `"Wifi"`, `"4G"`, or `None`.

**`convert_local_to_gps(x, y, ref_lat, ref_lon)`**

```python
lat, lon = convert_local_to_gps(
    x=10.5, y=-3.2,
    ref_lat=gps["data"]["ref"]["latitude"],
    ref_lon=gps["data"]["ref"]["longitude"],
)
```

**`convert_map_to_geojson(map_data, gps_ref)`**

```python
geojson = convert_map_to_geojson(map_data["data"], gps["data"])
```

**`get_field_definitions(type_id)` / `get_control_field_definitions(type_id)`**

```python
for f in get_field_definitions("yarbo_Y"):
    print(f.path, f.unit)
```

---

## Data Models

### Device

| Field | Type | Description |
|-------|------|-------------|
| `sn` | `str` | Serial number |
| `type_id` | `str` | Device model (e.g. `"yarbo_Y"`) |
| `name` | `str` | Display name |
| `model` | `str` | Model name |
| `online` | `bool` | Online status |

---

## Exceptions

| Exception | When raised |
|-----------|------------|
| `YarboSDKError` | Base class for all SDK errors |
| `AuthenticationError` | Invalid credentials |
| `TokenExpiredError` | Tokens expired — must re-login |
| `TimeoutError` *(built-in)* | Data request got no response within timeout |
