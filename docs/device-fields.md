# Available Data

## How to Access

All data fields can be discovered programmatically:

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions, extract_field

# List all available monitoring data
fields = get_field_definitions("yarbo_Y")
for f in fields:
    print(f"{f.name} ({f.entity_type}): {f.path}")

# List all available controls
controls = get_control_field_definitions("yarbo_Y")
for c in controls:
    print(f"{c.name} ({c.entity_type}): {c.path}")

# Extract a specific value from device status data
def on_status(topic, data):
    battery = extract_field(data, "BatteryMSG.capacity")
    print(f"Battery: {battery}%")
```

---

## Yarbo Y Series — Monitoring Data

| Name | Type | Unit | Description |
|------|------|------|-------------|
| Battery | sensor | % | Battery capacity level |
| Charging | binary_sensor | - | Whether the device is charging |
| Error Code | sensor | - | Current error code (0 = normal) |
| Heart Beat State | sensor | - | Working state: standby or working |
| Network | sensor | - | Active network: Halow, Wifi, or 4G |
| Head Type | sensor | - | Attached head: None, Snow Blower, Blower, Mower, Smart Cover, Mower Pro |
| Head Serial Number | sensor | - | Serial number of attached head |
| Auto Plan Status | sensor | - | Plan execution status with detailed error info |
| Auto Plan Pause Status | sensor | - | Reason why plan is paused |
| Recharging Status | sensor | - | Return-to-charge status with detailed error info |
| Sound Enabled | binary_sensor | - | Whether sound is on |
| Headlight | binary_sensor | - | Whether headlight is on |
| Volume | sensor | % | Current sound volume |
| RTK Signal | sensor | - | GPS signal strength: Strong, Medium, or Weak |
| Position X | sensor | m | Device local X coordinate |
| Position Y | sensor | m | Device local Y coordinate |
| Heading | sensor | ° | Device heading angle |

## Yarbo Y Series — Controls

| Name | Type | Description |
|------|------|-------------|
| Working State | select | Switch between standby and working |
| Sound Switch | switch | Turn sound on/off |
| Volume | number (0-100%) | Adjust sound volume |
| Headlight | switch | Turn headlight on/off |

## Yarbo Y Series — Data Requests

These are fetched on demand via SDK methods:

| Data | Method | Description |
|------|--------|-------------|
| Full Device Status | `get_device_msg()` | Complete snapshot of all device data |
| Auto Plans | `read_all_plan()` | List of all configured auto plans |
| GPS Reference | `read_gps_ref()` | GPS origin coordinates for coordinate conversion |
| Map Data | `get_map()` | Work areas, pathways, charging stations, no-go zones |
