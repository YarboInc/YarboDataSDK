# Device Fields

## 如何访问

```python
from yarbo_robot_sdk import get_field_definitions, get_control_field_definitions, extract_field

# 遍历所有监控字段
for f in get_field_definitions("yarbo_Y"):
    print(f"{f.name} ({f.entity_type}): {f.path}")

# 遍历所有控制字段
for c in get_control_field_definitions("yarbo_Y"):
    print(f"{c.name} ({c.entity_type}): {c.path}")

# 从设备状态中提取具体字段值
battery = extract_field(snapshot, "BatteryMSG.capacity")   # → 85
head    = extract_field(snapshot, "HeadMsg.head_type")      # → 3
```

---

## Yarbo Y Series — 监控数据

### 电池

| 字段路径 | 名称 | 类型 | 单位 | 说明 |
|---------|------|------|------|------|
| `BatteryMSG.capacity` | Battery | sensor | % | 电池电量 |
| `BatteryMSG.voltage` | Battery Voltage | sensor | V | 电池电压（默认禁用）|
| `BatteryMSG.current` | Battery Current | sensor | A | 电池电流（默认禁用）|
| `BatteryMSG.health` | Battery Health | sensor | % | 电池健康度 |
| `BatteryMSG.temperature1` | Battery Cell Temperature 1 | sensor | °C | 电芯温度 1（默认禁用）|
| `BatteryMSG.temperature2` | Battery Cell Temperature 2 | sensor | °C | 电芯温度 2（默认禁用）|
| `BatteryMSG.temperature3` | Battery Cell Temperature 3 | sensor | °C | 电芯温度 3（默认禁用）|
| `BatteryMSG.temperature4` | Battery Cell Temperature 4 | sensor | °C | 电芯温度 4（默认禁用）|
| `BatteryMSG.temperature5` | Battery Cell Temperature 5 | sensor | °C | 电芯温度 5（默认禁用）|
| `BatteryMSG.temperature6` | Battery Cell Temperature 6 | sensor | °C | 电芯温度 6（默认禁用）|
| `__computed__.charging_power` | Charging Power | sensor | W | 充电功率，计算值（默认禁用）|
| `BatteryMSG.status` | Charging | binary_sensor | — | 是否正在充电 |
| `BatteryMSG.temp_err` | Battery Temp Error | binary_sensor | — | 电池温度异常 |

### 状态

| 字段路径 | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `StateMSG.working_state` | Activity | sensor | 工作状态：`standby` / `working` |
| `HeartBeatMSG.working_state` | Heart Beat State | sensor | 心跳携带的工作状态：`standby` / `working` |
| `StateMSG.error_code` | Error Code | sensor | 当前错误码（0 = 正常）|
| `HeadAndVersionCheck.head_firmware_version` | Head Firmware Version | sensor | 附件头固件版本 |
| `BodyVersionMsg.body_fw_version` | Body Firmware Version | sensor | 机身固件版本 |
| `StateMSG.stuck` | Stuck | binary_sensor | 设备是否卡住 |
| `StateMSG.obstacle` | Obstacle Detected | binary_sensor | 是否检测到障碍物（默认禁用）|
| `StateMSG.person_detect_status` | Person Detection | binary_sensor | 是否检测到人员 |
| `StateMSG.robot_follow_state` | Follow Mode | binary_sensor | 是否处于跟随模式 |

### 计划与充电

| 字段路径 | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `StateMSG.on_going_planning` | Auto Plan Status | sensor | 计划执行状态，含详细错误码（WP002–WP025）|
| `StateMSG.on_going_planning` | Problem | binary_sensor | 计划是否存在错误 |
| `StateMSG.planning_paused` | Auto Plan Pause Status | sensor | 暂停原因：`Manual Pause` / `Low Battery Recharging` / `Stuck` 等 |
| `StateMSG.on_going_recharging` | Recharging Status | sensor | 返回充电状态，含详细错误码（REC005 等）|

### 网络

| 字段路径 | 名称 | 类型 | 单位 | 说明 |
|---------|------|------|------|------|
| `WifiInfo.signal` | WiFi RSSI | sensor | dBm | Wi-Fi 信号强度 |
| `net_module_status.lte_rssi` | 4G RSSI | sensor | dBm | 4G 信号强度 |
| `halow_status.strength` | HaLow RSSI | sensor | dBm | HaLow 信号强度（默认禁用）|
| `route_priority` | Network | sensor | — | 当前活跃网络：`Halow` / `Wifi` / `4G` |

### 附件头

| 字段路径 | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `HeadMsg.head_type` | Head Type | sensor | 当前附件类型：`None(0)` / `Snow Blower(1)` / `Blower(2)` / `Mower(3)` / `Smart Cover(4)` / `Mower Pro(5)` |
| `HeadSerialMsg.head_sn` | Head Serial Number | sensor | 附件序列号 |

### 声音与灯光

| 字段路径 | 名称 | 类型 | 说明 |
|---------|------|------|------|
| `StateMSG.enable_sound` | Sound Enabled | binary_sensor | 声音是否开启 |
| `StateMSG.volume` | Volume | sensor | 当前音量（%）|
| `LedInfoMSG.led_head` | Head Light | binary_sensor | 车头灯是否开启 |

### 位置

| 字段路径 | 名称 | 类型 | 单位 | 说明 |
|---------|------|------|------|------|
| `CombinedOdom.x` | Position X | sensor | m | 设备本地坐标 X（默认禁用）|
| `CombinedOdom.y` | Position Y | sensor | m | 设备本地坐标 Y（默认禁用）|
| `CombinedOdom.phi` | Heading | sensor | ° | 设备朝向角（默认禁用）|
| `RTKMSG.status` | RTK Signal | sensor | — | GPS 信号质量：`Strong` / `Medium` / `Weak` |
| `RTKMSG.sat_num` | GPS Satellites | sensor | — | 当前使用的 GPS 卫星数量（默认禁用）|

### 环境

| 字段路径 | 名称 | 类型 | 单位 | 说明 |
|---------|------|------|------|------|
| `EletricMSG.body_ambient_ntc_temp` | Ambient Temperature | sensor | °C | 机身环境温度 |
| `RunningStatusMSG.rain_sensor_data` | Rain Sensor | sensor | — | 雨量传感器原始数据（默认禁用）|
| `mower_head_info01.rain_sensor` | Rain Detected | binary_sensor | — | 是否检测到降雨 |

---

## Yarbo Y Series — 控制字段

### 运动控制

| 名称 | 类型 | MQTT Topic | 说明 |
|------|------|-----------|------|
| Working State | select | `set_working_state` | 工作状态切换：`standby(0)` / `working(1)` |

### 声音

| 名称 | 类型 | MQTT Topic | 说明 |
|------|------|-----------|------|
| Sound Switch | switch | `set_sound_param` | 声音开关 |
| Volume | number (0–100%) | `set_sound_param` | 音量调节 |
| Play Sound | button | `song_cmd` | 播放定位音效 |

### 灯光

| 名称 | 类型 | MQTT Topic | 说明 |
|------|------|-----------|------|
| Head Light | switch | `light_ctrl` | 车头灯开关 |

### 安全

| 名称 | 类型 | MQTT Topic | 说明 |
|------|------|-----------|------|
| Person Detection | switch | `set_person_detect` | 人员检测开关（默认禁用）|
| Follow Mode | switch | `set_follow_state` | 跟随模式开关（默认禁用）|
| Child Lock | switch | `set_child_lock` | 童锁开关 |
| Geo Fence | switch | `save_global_params` | 电子围栏开关（默认禁用）|
| Ignore Obstacles | switch | `set_map_obstacle_switch` | 忽略障碍物开关（默认禁用）|
| Ignore Obstacle Zones | button | `ignore_obstacles` | 清除所有障碍区域（默认禁用）|
| Emergency Stop | button | `stop` | 紧急停止 |

### 割草头（head_type 3 / 5）

| 名称 | 类型 | MQTT Topic | 范围 | 说明 |
|------|------|-----------|------|------|
| Blade Height | number | `mower_target_cmd` | 20–100 mm | 刀片目标高度（默认禁用）|
| Blade Speed | number | `mower_speed_cmd` | 0–100% | 刀片转速（默认禁用）|

### 除雪头（head_type 1）

| 名称 | 类型 | MQTT Topic | 范围 | 说明 |
|------|------|-----------|------|------|
| Chute Angle | number | `cmd_set_chute_angle` | 0–180° | 导雪管角度（默认禁用）|

---

## 按需拉取的数据

以下数据不通过实时推送获取，需主动发起请求：

| 数据 | SDK 方法 | 说明 |
|------|---------|------|
| 完整设备状态 | `yarbo.core.get_device_msg()` | 所有字段的完整快照 |
| 自动计划列表 | `yarbo.core.read_all_plan()` | 所有已配置的自动计划 |
| GPS 参考原点 | `yarbo.core.read_gps_ref()` | 用于本地坐标转 GPS 经纬度 |
| 地图数据 | `yarbo.core.get_map()` | 工作区域、路径、充电站、禁区 |
| Wi-Fi 信息 | `yarbo.core.get_connect_wifi_name()` | 当前连接的 Wi-Fi 名称与信号 |
