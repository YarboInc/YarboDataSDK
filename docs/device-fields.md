# Device Fields

## Accessing Fields

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions, extract_field

# List all monitored fields
for f in get_field_definitions("yarbo_Y"):
    print(f"{f.name} ({f.entity_type}): {f.path}")

# List all control fields
for c in get_control_field_definitions("yarbo_Y"):
    print(f"{c.name} ({c.entity_type}): {c.path}")

# Extract specific values from a device snapshot
battery = extract_field(snapshot, "BatteryMSG.capacity")   # → 85
head    = extract_field(snapshot, "HeadMsg.head_type")      # → 3
```

---

## Yarbo Y Series — Monitored Data

### Battery

| Field path | Name | Type | Unit | Description |
|------------|------|------|------|-------------|
| `BatteryMSG.capacity` | Battery | sensor | % | Battery level |
| `BatteryMSG.voltage` | Battery Voltage | sensor | V | Battery voltage (disabled by default) |
| `BatteryMSG.current` | Battery Current | sensor | A | Battery current (disabled by default) |
| `BatteryMSG.health` | Battery Health | sensor | % | Battery health |
| `BatteryMSG.temperature1` | Battery Cell Temperature 1 | sensor | °C | Cell temperature 1 (disabled by default) |
| `BatteryMSG.temperature2` | Battery Cell Temperature 2 | sensor | °C | Cell temperature 2 (disabled by default) |
| `BatteryMSG.temperature3` | Battery Cell Temperature 3 | sensor | °C | Cell temperature 3 (disabled by default) |
| `BatteryMSG.temperature4` | Battery Cell Temperature 4 | sensor | °C | Cell temperature 4 (disabled by default) |
| `BatteryMSG.temperature5` | Battery Cell Temperature 5 | sensor | °C | Cell temperature 5 (disabled by default) |
| `BatteryMSG.temperature6` | Battery Cell Temperature 6 | sensor | °C | Cell temperature 6 (disabled by default) |
| `__computed__.charging_power` | Charging Power | sensor | W | Computed charging power (disabled by default) |
| `BatteryMSG.status` | Charging | binary_sensor | — | Whether the battery is charging |
| `BatteryMSG.temp_err` | Battery Temp Error | binary_sensor | — | Battery temperature fault |

### Status

| Field path | Name | Type | Description |
|------------|------|------|-------------|
| `StateMSG.working_state` | Activity | sensor | Working state: `standby` / `working` |
| `HeartBeatMSG.working_state` | Heart Beat State | sensor | Working state from the heartbeat: `standby` / `working` |
| `StateMSG.error_code` | Error Code | sensor | Current error code (0 = normal) |
| `HeadAndVersionCheck.head_firmware_version` | Head Firmware Version | sensor | Attachment firmware version |
| `BodyVersionMsg.body_fw_version` | Body Firmware Version | sensor | Robot body firmware version |
| `StateMSG.stuck` | Stuck | binary_sensor | Whether the robot is stuck |
| `StateMSG.obstacle` | Obstacle Detected | binary_sensor | Whether an obstacle was detected (disabled by default) |
| `StateMSG.person_detect_status` | Person Detection | binary_sensor | Whether a person was detected |
| `StateMSG.robot_follow_state` | Follow Mode | binary_sensor | Whether follow mode is active |

### Plans and Charging

| Field path | Name | Type | Description |
|------------|------|------|-------------|
| `StateMSG.on_going_planning` | Auto Plan Status | sensor | Plan execution status, including detailed error codes (WP002–WP025) |
| `StateMSG.on_going_planning` | Problem | binary_sensor | Whether the plan has an error |
| `StateMSG.planning_paused` | Auto Plan Pause Status | sensor | Pause reason, such as `Manual Pause`, `Low Battery Recharging`, or `Stuck` |
| `StateMSG.on_going_recharging` | Recharging Status | sensor | Return-to-charge status, including detailed error codes such as REC005 |

### Network

| Field path | Name | Type | Unit | Description |
|------------|------|------|------|-------------|
| `WifiInfo.signal` | WiFi RSSI | sensor | dBm | Wi-Fi signal strength |
| `net_module_status.lte_rssi` | 4G RSSI | sensor | dBm | 4G signal strength |
| `halow_status.strength` | HaLow RSSI | sensor | dBm | HaLow signal strength (disabled by default) |
| `route_priority` | Network | sensor | — | Active network: `Halow` / `Wifi` / `4G` |

### Attachment

| Field path | Name | Type | Description |
|------------|------|------|-------------|
| `HeadMsg.head_type` | Head Type | sensor | Current attachment: `None(0)` / `Snow Blower(1)` / `Blower(2)` / `Mower(3)` / `Smart Cover(4)` / `Mower Pro(5)` |
| `HeadSerialMsg.head_sn` | Head Serial Number | sensor | Attachment serial number |

### Sound and Lights

| Field path | Name | Type | Description |
|------------|------|------|-------------|
| `StateMSG.enable_sound` | Sound Enabled | binary_sensor | Whether sound is enabled |
| `StateMSG.volume` | Volume | sensor | Current volume (%) |
| `LedInfoMSG.led_head` | Head Light | binary_sensor | Whether the headlight is on |

### Position

| Field path | Name | Type | Unit | Description |
|------------|------|------|------|-------------|
| `CombinedOdom.x` | Position X | sensor | m | Device-local X coordinate (disabled by default) |
| `CombinedOdom.y` | Position Y | sensor | m | Device-local Y coordinate (disabled by default) |
| `CombinedOdom.phi` | Heading | sensor | ° | Robot heading (disabled by default) |
| `RTKMSG.status` | RTK Signal | sensor | — | GPS signal quality: `Strong` / `Medium` / `Weak` |
| `RTKMSG.sat_num` | GPS Satellites | sensor | — | Number of GPS satellites in use (disabled by default) |

### Environment

| Field path | Name | Type | Unit | Description |
|------------|------|------|------|-------------|
| `EletricMSG.body_ambient_ntc_temp` | Ambient Temperature | sensor | °C | Ambient temperature around the robot body |
| `RunningStatusMSG.rain_sensor_data` | Rain Sensor | sensor | — | Raw rain sensor reading (disabled by default) |
| `mower_head_info01.rain_sensor` | Rain Detected | binary_sensor | — | Whether rain was detected |

---

## Yarbo Y Series — Control Fields

### Motion Control

| Name | Type | MQTT Topic | Description |
|------|------|------------|-------------|
| Working State | select | `set_working_state` | Switch working state: `standby(0)` / `working(1)` |

### Sound

| Name | Type | MQTT Topic | Description |
|------|------|------------|-------------|
| Sound Switch | switch | `set_sound_param` | Toggle sound |
| Volume | number (0–100%) | `set_sound_param` | Adjust volume |
| Play Sound | button | `song_cmd` | Play a locating sound |

### Lights

| Name | Type | MQTT Topic | Description |
|------|------|------------|-------------|
| Head Light | switch | `light_ctrl` | Toggle the headlight |

### Safety

| Name | Type | MQTT Topic | Description |
|------|------|------------|-------------|
| Person Detection | switch | `set_person_detect` | Toggle person detection (disabled by default) |
| Follow Mode | switch | `set_follow_state` | Toggle follow mode (disabled by default) |
| Child Lock | switch | `set_child_lock` | Toggle child lock |
| Geo Fence | switch | `save_global_params` | Toggle the electronic fence (disabled by default) |
| Ignore Obstacles | switch | `set_map_obstacle_switch` | Toggle obstacle ignoring (disabled by default) |
| Ignore Obstacle Zones | button | `ignore_obstacles` | Clear all obstacle zones (disabled by default) |
| Emergency Stop | button | `stop` | Stop immediately |

### Mower (head_type 3 / 5)

| Name | Type | MQTT Topic | Range | Description |
|------|------|------------|-------|-------------|
| Blade Height | number | `mower_target_cmd` | 20–100 mm | Target blade height (disabled by default) |
| Blade Speed | number | `mower_speed_cmd` | 0–100% | Blade speed (disabled by default) |

### Snow Blower (head_type 1)

| Name | Type | MQTT Topic | Range | Description |
|------|------|------------|-------|-------------|
| Chute Angle | number | `cmd_set_chute_angle` | 0–180° | Chute angle (disabled by default) |

---

## Data Requested On Demand

The following data is requested explicitly rather than received through
real-time updates:

| Data | SDK method | Description |
|------|------------|-------------|
| Full device status | `yarbo.core.get_device_msg()` | Complete snapshot of all fields |
| Automatic plans | `yarbo.core.read_all_plan()` | All configured automatic plans |
| GPS reference origin | `yarbo.core.read_gps_ref()` | Converts local coordinates to GPS latitude/longitude |
| Map data | `yarbo.core.get_map()` | Work areas, pathways, charging station, and restricted zones |
| Wi-Fi information | `yarbo.core.get_connect_wifi_name()` | Connected Wi-Fi name and signal |
