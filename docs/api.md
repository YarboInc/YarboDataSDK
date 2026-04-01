# API Reference

## YarboClient

Main SDK entry point. All device operations are accessed through this class.

### Constructor

```python
YarboClient(
    api_base_url: str | None = None,
    mqtt_host: str | None = None,
    mqtt_port: int | None = None,
    mqtt_use_tls: bool | None = None,
    rsa_public_key: str | None = None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_base_url` | `str \| None` | Cloud default | REST API base URL |
| `mqtt_host` | `str \| None` | From cloud config | MQTT broker hostname |
| `mqtt_port` | `int \| None` | From cloud config | MQTT broker port |
| `mqtt_use_tls` | `bool \| None` | `True` | Enable TLS for MQTT |
| `rsa_public_key` | `str \| None` | From cloud config | RSA public key for password encryption |

In production, only `api_base_url` is required. Other parameters are fetched from the cloud config endpoint (`/sdk/config`). Pass them explicitly to override.

---

### Authentication

#### `login(username, password)`

Login with email and password. Password is RSA-encrypted internally before sending.

```python
client.login("user@email.com", "password")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `username` | `str` | Email address |
| `password` | `str` | Plain text password (encrypted internally) |

**Raises**: `AuthenticationError` on invalid credentials.

---

#### `restore_session(username, token, refresh_token)`

Restore a previous session from saved tokens. No network call needed.

```python
client.restore_session(
    username="user@email.com",
    token="eyJ...",
    refresh_token="v1.xxx...",
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `username` | `str` | Email address |
| `token` | `str` | JWT access token |
| `refresh_token` | `str` | Refresh token |

---

#### `token` (property)

Returns the current JWT access token, or `None` if not logged in.

```python
saved_token = client.token  # str | None
```

---

#### `refresh_token` (property)

Returns the current refresh token, or `None` if not logged in.

```python
saved_refresh = client.refresh_token  # str | None
```

---

### REST API

#### `get_devices()`

Get all devices linked to the current account.

```python
devices = client.get_devices()  # list[Device]
```

**Returns**: `list[Device]` — See [Device model](#device).

---

### MQTT

#### `mqtt_connect()`

Connect to the MQTT broker using JWT token auth.

```python
client.mqtt_connect()
```

**Raises**: `YarboSDKError` if `mqtt_host` or `mqtt_port` are not configured.

---

#### `subscribe_device_message(sn, type_id, callback)`

Subscribe to device real-time status messages. Automatically decompresses zlib payloads (firmware >= 3.9.0) and parses JSON.

```python
def on_device_message(topic: str, data: dict):
    print(data)

client.subscribe_device_message("SN123", "yarbo_Y", on_device_message)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sn` | `str` | Device serial number |
| `type_id` | `str` | Device type ID (e.g. `"yarbo_Y"`) |
| `callback` | `Callable[[str, dict], Any]` | Called with `(topic, parsed_data)` |

**MQTT topic resolved**: `snowbot/{sn}/device/DeviceMSG`

---

#### `subscribe_heart_beat(sn, type_id, callback)`

Subscribe to device heart beat messages.

```python
def on_heart_beat(topic: str, data: dict):
    print(data)  # e.g. {"working_state": 0}

client.subscribe_heart_beat("SN123", "yarbo_Y", on_heart_beat)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sn` | `str` | Device serial number |
| `type_id` | `str` | Device type ID |
| `callback` | `Callable[[str, dict], Any]` | Called with `(topic, parsed_data)` |

**MQTT topic resolved**: `snowbot/{sn}/device/heart_beat`

---

#### `mqtt_publish_command(sn, type_id, command_topic_name, payload)`

Publish a command to a device control topic. Automatically compresses with zlib if firmware >= 3.9.0.

```python
client.mqtt_publish_command("SN123", "yarbo_Y", "set_working_state", {"state": 1})
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `sn` | `str` | Device serial number |
| `type_id` | `str` | Device type ID |
| `command_topic_name` | `str` | Control topic name (from device registry) |
| `payload` | `dict` | Command payload |

**Raises**: `YarboSDKError` if MQTT is not connected or topic name is unknown.

---

### Lifecycle

#### `close()`

Clean up resources. Disconnects MQTT.

```python
client.close()
```

---

## Module-level Functions

These functions are also available as direct imports:

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions, extract_field
```

#### `get_field_definitions(type_id) → list[FieldDefinition]`

Return status field definitions for a device type. Returns `[]` if not found.

#### `get_control_field_definitions(type_id) → list[ControlFieldDefinition]`

Return control field definitions for a device type. Returns `[]` if not found.

#### `extract_field(data, field_path) → Any`

Extract a value from a nested dict using dot-separated path. E.g. `extract_field(data, "BatteryMSG.capacity")`.

---

## Data Models

### Device

```python
@dataclass
class Device:
    sn: str            # Serial number
    type_id: str       # Device type ID
    name: str          # Display name
    model: str         # Model name
    online: bool       # Online status
    user_type: str     # User role (default: "")
```

### FieldDefinition

```python
@dataclass
class FieldDefinition:
    path: str                              # Dot-separated path (e.g. "BatteryMSG.capacity")
    name: str                              # Display name
    entity_type: str                       # "sensor", "binary_sensor", or "device_tracker"
    device_class: str | None = None        # HA device_class
    unit: str | None = None                # Unit of measurement
    icon: str | None = None                # MDI icon
    value_map: dict[str, str] | None = None  # Raw value → display string
    enabled_by_default: bool = True
    category: str | None = None
```

### ControlFieldDefinition

```python
@dataclass
class ControlFieldDefinition:
    path: str                              # State value path (e.g. "HeartBeatMSG.working_state")
    name: str                              # Display name
    entity_type: str                       # "select"
    command_topic: str                     # Control topic name reference
    command_key: str                       # Payload key (e.g. "state")
    options: list[str]                     # Human-readable options
    value_map: dict[str, int]              # Option → raw command value
    state_value_map: dict[str, str]        # Raw state → option string
    icon: str | None = None
    enabled_by_default: bool = True
    category: str | None = None
```

---

## Exceptions

```python
from yarbo_robot_sdk import (
    YarboSDKError,           # Base exception
    AuthenticationError,     # Login failed (invalid credentials)
    TokenExpiredError,       # Token and refresh token both expired
)
```

| Exception | When | Attributes |
|-----------|------|------------|
| `YarboSDKError` | Base class for all SDK errors | — |
| `AuthenticationError` | Invalid credentials during `login()` | — |
| `TokenExpiredError` | Both tokens expired, must re-login | — |
