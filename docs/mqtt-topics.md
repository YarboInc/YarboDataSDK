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

## Control Topics (Publish)

### set_working_state — Control Working State

| Field | Value |
|-------|-------|
| **Topic pattern** | `snowbot/{sn}/app/set_working_state` |
| **Direction** | Client → Device (publish) |

```python
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1})
```

**Payload**:

```json
{"state": 0}
```

| Value | Meaning |
|-------|---------|
| `0` | Standby |
| `1` | Working |

## Payload Compression

Devices with firmware >= 3.9.0 use zlib compression for MQTT payloads.

- **Subscribe**: The SDK automatically detects and decompresses zlib payloads. Falls back to plaintext JSON if decompression fails.
- **Publish**: The SDK automatically compresses payloads if the device firmware version (cached from `device_msg` messages) is >= 3.9.0. Otherwise sends plaintext JSON.

This is handled transparently — no action required from the user.

## Topic Resolution

Topics are defined in the device registry JSON files and resolved internally by the SDK. You don't need to construct topic strings manually — use the high-level client methods (`subscribe_device_message`, `subscribe_heart_beat`, `mqtt_publish_command`) which handle topic resolution automatically.
