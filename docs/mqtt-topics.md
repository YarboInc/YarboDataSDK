# MQTT Topics

## Overview

Yarbo devices communicate via MQTT. The SDK handles connection, authentication, and payload encoding/decoding automatically.

## Connection

```python
client = YarboClient(api_base_url="https://api.yarbo.com")
client.login("user@email.com", "password")
client.mqtt_connect()  # Connects using JWT token auth
```

- **Authentication**: JWT token as MQTT password, email as username
- **TLS**: Enabled by default (`mqtt_use_tls=True`)
- **Auto-reconnect**: Token is refreshed on reconnection

## Subscribe Topics

### device_msg — Device Status

Real-time device status messages containing battery, position, working state, sensors, etc.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/device/DeviceMSG` |
| **Direction** | Device → Client (subscribe) |
| **Frequency** | Continuous during operation |

```python
def on_device_message(topic: str, data: dict):
    # data contains all device status fields
    battery = data.get("BatteryMSG", {}).get("capacity")
    state = data.get("StateMSG", {}).get("working_state")
    position = data.get("CombinedOdom", {})
    print(f"Battery: {battery}%, State: {state}, Pos: {position}")

client.subscribe_device_message("SN123", "yarbo_Y", on_device_message)
```

**Example payload** (parsed dict):

```json
{
  "version": "3.9.1",
  "BatteryMSG": {
    "capacity": 85,
    "status": 1,
    "temp_err": 0
  },
  "StateMSG": {
    "working_state": 1,
    "charging_status": 0,
    "error_code": 0
  },
  "CombinedOdom": {
    "x": 1.23,
    "y": 4.56,
    "phi": 0.78
  },
  "RTKMSG": {
    "status": 4,
    "heading_status": 1
  },
  "HeadMsg": {
    "head_type": 1
  },
  "HeadSerialMsg": {
    "head_sn": "HD001"
  },
  "RunningStatusMSG": {
    "chute_angle": 45
  },
  "ultrasonic_msg": {
    "lf_dis": 1200,
    "mt_dis": 800,
    "rf_dis": 1100
  }
}
```

### heart_beat — Heart Beat

Periodic heart beat with working state.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/device/heart_beat` |
| **Direction** | Device → Client (subscribe) |
| **Frequency** | Periodic interval |

```python
def on_heart_beat(topic: str, data: dict):
    state = data.get("working_state")
    print(f"Heart beat — working_state: {state}")

client.subscribe_heart_beat("SN123", "yarbo_Y", on_heart_beat)
```

**Example payload**:

```json
{
  "working_state": 0
}
```

### data_feedback — Command Response Feedback

Receives responses to app-initiated commands (e.g. `read_gps_ref`). Each response includes a `topic` field identifying which command it responds to, enabling safe filtering when multiple clients send concurrent commands.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/device/data_feedback` |
| **Direction** | Device → Client (subscribe) |
| **Frequency** | On demand (in response to commands) |

```python
def on_feedback(topic: str, data: dict):
    cmd = data.get("topic")       # Which command this responds to
    state = data.get("state")     # 0 = success
    payload = data.get("data")    # Response payload
    print(f"Feedback for {cmd}: state={state}, data={payload}")

client.subscribe_data_feedback("SN123", "yarbo_Y", on_feedback)
```

**Example payload** (parsed dict):

```json
{
  "topic": "read_gps_ref",
  "msg": "",
  "state": 0,
  "data": {
    "ref": {
      "latitude": 22.612830272709957,
      "longitude": 114.04917769041668
    },
    "rtkFixType": 1,
    "hgt": 108.635,
    "lat_lon_hight": "22.61278 114.04920 92.838"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `topic` | `str` | Command name this response corresponds to |
| `msg` | `str` | Human-readable message (may be empty) |
| `state` | `int` | Status code: `0` = success |
| `data` | `dict` | Response payload (varies by command) |

## Control Topics (Publish)

### set_working_state — Control Working State

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/set_working_state` |
| **Direction** | Client → Device (publish) |

```python
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1, "source": "smart_home"})
```

**Payload**:

```json
{"state": 0, "source": "smart_home"}
```

| Value | Meaning |
|-------|---------|
| `0` | Standby |
| `1` | Working |

### read_gps_ref — Request GPS Reference Origin

Request the GPS reference origin coordinates from the device. Response arrives via `data_feedback`.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/read_gps_ref` |
| **Direction** | Client → Device (publish) |
| **Response via** | `data_feedback` (topic=`"read_gps_ref"`) |

```python
# Using the high-level method (blocking, use with async_add_executor_job in HA):
result = client.read_gps_ref("SN123", "yarbo_Y", timeout=10.0)
ref = result["data"]["ref"]
print(f"GPS origin: {ref['latitude']}, {ref['longitude']}")
print(f"RTK fix type: {result['data']['rtkFixType']}")
```

**Response `data` fields**:

| Field | Type | Description |
|-------|------|-------------|
| `ref.latitude` | `float` | Reference origin latitude (degrees) |
| `ref.longitude` | `float` | Reference origin longitude (degrees) |
| `rtkFixType` | `int` | RTK fix type (`1` = valid/fixed) |
| `hgt` | `float` | Height (meters) |
| `lat_lon_hight` | `str` | Lat/lon/height as space-separated string |

**Note**: `rtkFixType` must be `1` for the GPS reference to be usable. Other values indicate the device has not completed RTK initialization via the Yarbo app.

### get_map — Request Map/Zone Data

Request the map data (work zones, pathways, charging stations, etc.) from the device. Response arrives via `data_feedback`.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/get_map` |
| **Direction** | Client → Device (publish) |
| **Response via** | `data_feedback` (topic=`"get_map"`) |

```python
# Using the high-level method (blocking, use with async_add_executor_job in HA):
result = client.get_map("SN123", "yarbo_Y", timeout=30.0)
data = result["data"]
areas = data.get("areas", [])
pathways = data.get("pathways", [])
print(f"Areas: {len(areas)}, Pathways: {len(pathways)}")
```

**Response `data` fields**:

| Field | Type | Description |
|-------|------|-------------|
| `areas` | `list[Area]` | Work area polygons (mowing/snow zones) |
| `pathways` | `list[Pathway]` | Pathway line segments |
| `sidewalks` | `list[Sidewalk]` | Sidewalk zones |
| `deadends` | `list[Deadend]` | Dead-end zones |
| `nogozones` | `list[NoGoZone]` | No-go zone polygons |
| `novisionzones` | `list[NoVisionZone]` | No-vision zone polygons |
| `elec_fence` | `list[ElecFence]` | Electric fence boundaries |
| `chargingData` | `ChargingData` | Primary charging station |
| `allchargingData` | `list[ChargingData]` | All charging stations |

Each area/pathway/zone contains a `range` field with local coordinate points `{x, y, phi}` and a `ref` GPS reference `{latitude, longitude}` for coordinate conversion.

**Note**: The default timeout is 30 seconds (larger than other commands) because map payloads can be significantly larger.

### read_all_plan — Request Auto Plan List

Request all auto plans from the device. Response arrives via `data_feedback`.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/read_all_plan` |
| **Direction** | Client → Device (publish) |
| **Response via** | `data_feedback` (topic=`"read_all_plan"`) |

```python
result = client.read_all_plan("SN123", "yarbo_Y", timeout=10.0)
plans = result["data"]["data"]
for plan in plans:
    print(f"Plan {plan['id']}: {plan['name']}")
```

### get_device_msg — Request Full DeviceMSG Snapshot

Request a full DeviceMSG snapshot (same structure as real-time push but with all fields). Response arrives via `data_feedback`.

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/get_device_msg` |
| **Direction** | Client → Device (publish) |
| **Response via** | `data_feedback` (topic=`"get_device_msg"`) |

```python
result = client.get_device_msg("SN123", "yarbo_Y", timeout=10.0)
full_msg = result["data"]
```

### start_plan — Start Auto Plan

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/start_plan` |
| **Direction** | Client → Device (publish) |

**Payload**: `{"id": <plan_id>, "percent": <start_percent>}` (`percent` is optional)

### pause — Pause Current Plan

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/pause` |
| **Direction** | Client → Device (publish) |

**Payload**: `{}`

### resume — Resume Paused Plan

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/resume` |
| **Direction** | Client → Device (publish) |

**Payload**: `{}`

### stop — Stop Current Plan

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/stop` |
| **Direction** | Client → Device (publish) |

**Payload**: `{}`

### cmd_recharge — Return to Charging Station

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/cmd_recharge` |
| **Direction** | Client → Device (publish) |

**Payload**: `{"cmd": "2"}`

### set_sound_param — Set Sound Parameters

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/set_sound_param` |
| **Direction** | Client → Device (publish) |

**Payload**: `{"enable": <boolean>, "vol": <0-100>}`

### light_ctrl — Control Headlight

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/light_ctrl` |
| **Direction** | Client → Device (publish) |

**Payload** (all lights on/off together):

```json
{
  "body_left_r": 255,
  "body_right_r": 255,
  "led_head": 255,
  "led_left_w": 255,
  "led_right_w": 255,
  "tail_left_r": 255,
  "tail_right_r": 255
}
```

Use `0` for off, `255` for on.

## Payload Compression

Devices with firmware >= 3.9.0 use zlib compression for MQTT payloads.

- **Subscribe**: The SDK automatically detects and decompresses zlib payloads. Falls back to plaintext JSON if decompression fails.
- **Publish**: The SDK automatically compresses payloads if the device firmware version (cached from `device_msg` messages) is >= 3.9.0. Otherwise sends plaintext JSON.

This is handled transparently — no action required from the user.

## Topic Resolution

Topics are defined in the device registry JSON files and resolved internally by the SDK. You don't need to construct topic strings manually — use the high-level client methods (`subscribe_device_message`, `subscribe_heart_beat`, `mqtt_publish_command`) which handle topic resolution automatically.
