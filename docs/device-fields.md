# Device Fields

## Yarbo Y Series (`yarbo_Y`)

### Status Fields

These fields are available from `device_msg` MQTT messages and REST API status responses.

#### Battery

| Field | Path | Entity Type | Device Class | Unit | Values |
|-------|------|-------------|--------------|------|--------|
| Battery | `BatteryMSG.capacity` | sensor | battery | % | 0–100 |
| Battery Status | `BatteryMSG.status` | sensor | enum | — | 0=unknown, 1=normal, 2=low, 3=critical |
| Battery Temp Error | `BatteryMSG.temp_err` | binary_sensor | problem | — | 0=ok, 1=error |
| Charging | `StateMSG.charging_status` | binary_sensor | battery_charging | — | 0=not charging, 1=charging |

#### Status

| Field | Path | Entity Type | Device Class | Unit | Values |
|-------|------|-------------|--------------|------|--------|
| Online | `__device__.online` | binary_sensor | connectivity | — | true/false |
| Working State | `StateMSG.working_state` | sensor | enum | — | 0=idle, 1=working, 2=paused, 3=error, 4=returning |
| Heart Beat State | `HeartBeatMSG.working_state` | sensor | enum | — | 0=standby, 1=working |
| Error Code | `StateMSG.error_code` | sensor | — | — | Error code integer |
| Base Status | `base_status` | sensor | — | — | Base station status |

#### Position

| Field | Path | Entity Type | Unit | Description |
|-------|------|-------------|------|-------------|
| Position X | `CombinedOdom.x` | sensor | m | X coordinate |
| Position Y | `CombinedOdom.y` | sensor | m | Y coordinate |
| Heading | `CombinedOdom.phi` | sensor | ° | Heading angle |
| Position Confidence | `combined_odom_confidence` | sensor | — | Position confidence level |

#### RTK

| Field | Path | Entity Type | Values |
|-------|------|-------------|--------|
| RTK Status | `RTKMSG.status` | sensor | 0=no_fix, 1=single, 2=float, 4=fixed, 5=dead_reckoning |
| RTK Heading Status | `RTKMSG.heading_status` | sensor | Heading status value |
| RTCM Age | `rtcm_age` | sensor | Age in seconds |

#### Head

| Field | Path | Entity Type | Values |
|-------|------|-------------|--------|
| Head Type | `HeadMsg.head_type` | sensor | 0=none, 1=snow_blower, 2=leaf_blower, 3=mower, 4=smart_cover |
| Head Serial Number | `HeadSerialMsg.head_sn` | sensor | Serial number string |
| Chute Angle | `RunningStatusMSG.chute_angle` | sensor | Angle in degrees |

#### Ultrasonic

| Field | Path | Entity Type | Unit | Description |
|-------|------|-------------|------|-------------|
| Ultrasonic Left Front | `ultrasonic_msg.lf_dis` | sensor | mm | Left front distance |
| Ultrasonic Middle | `ultrasonic_msg.mt_dis` | sensor | mm | Middle distance |
| Ultrasonic Right Front | `ultrasonic_msg.rf_dis` | sensor | mm | Right front distance |

### Control Fields

These fields allow sending commands to the device via MQTT.

| Field | State Path | Entity Type | Command Topic | Options | Command Payload |
|-------|-----------|-------------|---------------|---------|-----------------|
| Working State | `HeartBeatMSG.working_state` | select | `set_working_state` | standby, working | `{"state": 0}` or `{"state": 1}` |

### Enabled by Default

Not all fields are enabled by default. Fields with `enabled_by_default: false`:

- Battery Status
- Base Status
- Position X, Position Y, Heading, Position Confidence
- RTK Heading Status, RTCM Age
- Head Serial Number, Chute Angle
- Ultrasonic Left Front, Ultrasonic Middle, Ultrasonic Right Front

## Accessing Fields

### From MQTT messages

```python
from yarbo_robot_sdk import extract_field

def on_device_message(topic, data):
    battery = extract_field(data, "BatteryMSG.capacity")      # 85
    state = extract_field(data, "StateMSG.working_state")      # 1
    head = extract_field(data, "HeadMsg.head_type")            # 1 (snow_blower)
    rtk = extract_field(data, "RTKMSG.status")                 # 4 (fixed)
```

### From the device registry

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions

# Get all status field definitions
fields = get_field_definitions("yarbo_Y")
for f in fields:
    print(f"{f.name}: path={f.path}, type={f.entity_type}, unit={f.unit}")

# Get control field definitions
controls = get_control_field_definitions("yarbo_Y")
for c in controls:
    print(f"{c.name}: options={c.options}, command_topic={c.command_topic}")
```

## Special Path Prefixes

| Prefix | Meaning | Example |
|--------|---------|---------|
| `__device__.` | Value from the `Device` object (REST API), not MQTT | `__device__.online` |
| (none) | Value from MQTT message payload | `BatteryMSG.capacity` |
