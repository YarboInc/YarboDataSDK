# MQTT Topics

## Subscribe to Real-Time Data

### Device Status (DeviceMSG)

Published continuously while the device runs, including battery, position,
sensor, and plan status information.

```python
def on_status(topic, data):
    battery = extract_field(data, "BatteryMSG.capacity")
    state   = extract_field(data, "StateMSG.working_state")

yarbo.core.subscribe_device_message(on_status)
```

> **Low-level API:** `client.subscribe_device_message(device.sn, device.type_id, on_status)`

---

### Heartbeat (HeartBeat)

Published approximately every 30 seconds to indicate whether the device is online.

```python
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

> **Low-level API:** `client.subscribe_heart_beat(device.sn, device.type_id, on_heartbeat)`

---

### Command Feedback (data_feedback)

Response channel for data requests such as `get_device_msg` and
`read_all_plan`. **Subscribe before making any data request.**

```python
yarbo.core.subscribe_data_feedback(on_feedback)
```

> **Low-level API:** `client.subscribe_data_feedback(device.sn, device.type_id, on_feedback)`
> Without `on_feedback`, the SDK still processes responses for synchronous
> requests. Pass a callback only when custom handling is needed.

---

## Topic Addresses

| Name | Topic |
|------|-------|
| DeviceMSG | `snowbot/{sn}/device/DeviceMSG` |
| HeartBeat | `snowbot/{sn}/device/heart_beat` |
| data_feedback | `snowbot/{sn}/device/data_feedback` |
| Command publishing | `snowbot/{sn}/app/{command}` |

---

## Data Compression

Devices running firmware 3.9.0 or later compress MQTT payloads with zlib.
The SDK compresses and decompresses them automatically.

---

## Connection Strategy During EMQX Migration

As devices move from the shared EMQX cluster to EMQX Dedicated, the SDK chooses
a broker for each **serial number (SN)**:

- On `subscribe_*(sn, ...)` or `mqtt_publish_command(sn, ...)`, the SDK calls `GET /yarbo/emqx-migration/query?sn=<SN>` with `Authorization: Bearer <JWT>`.
- `migrated=true` routes the device to EMQX Dedicated.
- `migrated=false` routes the device to the legacy shared cluster.
- When both device types are present, the SDK maintains up to two broker connections.

### Broker Connection Settings

| Setting | Legacy cluster (unmigrated devices) | EMQX Dedicated (migrated devices) |
|------|-------------------|------------------------------|
| Host | Supplied by `/sdk/config` (default: `t9db1d91.us-east-1.emqx.cloud:15525`) | `c4750009.ala.dedicated.aws.emqxcloud.com:8883` |
| TLS | Enabled | Enabled, using the same system CA |
| ClientID | `HA_{email}_{unix_ts}` | `HA_{email}_{rand4}` |
| username | JWT | email |
| password | `""` | JWT |

### Connection Behavior

- `client.mqtt_connect()` is **lazy**: it makes no network request until the first `subscribe_*(sn, ...)` or `mqtt_publish_command(sn, ...)` call needs a broker connection.
- Before connecting to the new broker, the SDK calls `auth.refresh()` to avoid rejection due to an expired token. Existing connections are left alone.
- After either broker disconnects (`_on_disconnect`), the SDK clears the migration cache for every SN. The next subscription or command queries again, including for devices migrated during the disconnection.
- The migration query uses the current JWT. On HTTP 401, or `success=false` with `code=A0230`, the SDK calls `auth.refresh()` and retries once. If refresh fails, it raises `TokenExpiredError` so the host (HA) can prompt for login.
- On any other migration query failure (non-2xx HTTP status, `success=false`, or network error), the SDK raises `YarboSDKError`. It does **not** silently use the legacy broker, which could leave migrated devices without data.
- Routing settings (`new_mqtt_host`, `new_mqtt_port`, `new_mqtt_use_tls`, `emqx_migration_query_url`) follow this priority: constructor arguments → `/sdk/config` response → SDK built-in defaults.

### Broker-Specific Logs

Each `MqttClient` has a `legacy` or `new` broker label. Connection logs use
the `MQTT[<label>]` prefix; routing decisions use `MQTT route`. Key events are
logged at the `info` level:

```
MQTT route sn=<SN> -> new broker
MQTT[new] connecting → <host>:<port> (tls=True) client_id=HA_<email>_<rand4>
MQTT[new] connected to <host>:<port> (rc=0); re-subscribing <N> topic(s)
MQTT[new] subscribe → snowbot/<SN>/device/DeviceMSG
MQTT[new] disconnected from <host>:<port> (rc=...)
```

Unmigrated devices use `MQTT[legacy] ...` and the legacy host. Enable these
logs in HA with:

```yaml
logger:
  logs:
    yarbo_robot_sdk.client: info
    yarbo_robot_sdk.mqtt_client: info
```

After migration completes, the routing layer and migration query calls will
be removed in a separate change.
