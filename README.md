# Yarbo Robot SDK

Python SDK，用于与 Yarbo 机器人设备进行集成开发。负责处理云端认证、Token 刷新、REST 设备 API、MQTT 实时数据、MQTT 命令下发、模块化设备抽象，以及地图坐标转换等功能。

- **包名**：`yarbo-data-sdk`
- **导入名**：`yarbo_robot_sdk`
- **Python**：`>= 3.10`
- **类型支持**：PEP 561 typed package（含 `py.typed`）
- **协议**：MIT

## 安装

```bash
pip install yarbo-data-sdk
```

本地开发：

```bash
git clone https://github.com/YarboInc/YarboDataSDK.git
cd YarboDataSDK
pip install -e ".[dev]"
pytest
```

---

## 快速上手

```python
from yarbo_robot_sdk import YarboClient

# 创建客户端并登录
client = YarboClient()
client.login("user@example.com", "password")

# 获取设备列表
devices = client.get_devices()
device = devices[0]
print(f"{device.name}  SN={device.sn}")

# 清理资源
client.close()
```

---

## 设备模块架构

Yarbo 采用模块化设计，Core 主体可搭配 Mower、Snow Blower、Blower、Trimmer、Plow、SAM 等附件头。

SDK 提供三种调用方式，推荐使用 BoundYarboDevice：

```python
# ① 推荐：绑定设备，无需重复传 sn/type_id，支持附件头类型校验
yarbo = client.device(device, data=snapshot)
yarbo.core.return_to_charge()
yarbo.mower.set_blade_height(60)          # head_type 不匹配时自动报错

# ② 模块门面：需显式传 sn
client.mower.set_blade_height(device.sn, 60, device.type_id)

# ③ 兜底：发送 typed 方法未覆盖的原始命令
yarbo.core.publish_command("wireless_charging_cmd", {"cmd": 1})
```

### 模块与附件头对应关系

| 模块 | `HeadMsg.head_type` | 说明 |
|------|---------------------|------|
| `core` / `snow_bot` | 全部 | 计划控制、返回充电、声音、灯光、安全设置等 |
| `mower` | `3`（Mower）、`5`（Mower Pro） | 刀片高度、刀片转速 |
| `snow_blower` | `1` | 导雪管角度 |
| `blower` | `2` | 吹风相关命令 |
| `trimmer` / `plow` / `sam` | — | 对应附件命令 |

---

## 完整生命周期

各步骤必须按顺序执行，跳步或乱序会导致运行时错误。

### Step 1–3：初始化

创建客户端 → 登录 → 获取设备列表，均为 REST 调用，不依赖 MQTT。

```python
from yarbo_robot_sdk import YarboClient

client = YarboClient()
client.login("user@example.com", "password")
device = client.get_devices()[0]
```

### Step 4：建立 MQTT 连接

必须在所有 `subscribe_*` 调用之前执行。

```python
client.mqtt_connect()
```

### Step 5：注册订阅

`subscribe_data_feedback` 必须在 `get_device_msg` 等数据请求之前调用。

```python
from yarbo_robot_sdk import extract_field

def on_status(topic: str, data: dict) -> None:
    """设备状态实时推送（DeviceMSG）"""
    battery = extract_field(data, "BatteryMSG.capacity")
    state   = extract_field(data, "StateMSG.working_state")
    print(f"电量={battery}%  工作状态={state}")

def on_heartbeat(topic: str, data: dict) -> None:
    """心跳推送（每 30 秒左右一次）"""
    print(f"心跳: working_state={data.get('working_state')}")

def on_feedback(topic: str, data: dict) -> None:
    """命令响应回调（data_feedback channel）"""
    print(f"反馈: topic={data.get('topic')}  result={data.get('result')}")

yarbo = client.device(device)
yarbo.core.subscribe_data_feedback(on_feedback)    # ⚠️ 必须最先订阅
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

### Step 6：拉取设备数据

同步阻塞调用，依赖 Step 5 已完成。在 Home Assistant 等异步框架中，建议用 `loop.run_in_executor()` 包装。

```python
snapshot = yarbo.core.get_device_msg(timeout=10.0)   # 完整设备状态
gps      = yarbo.core.read_gps_ref(timeout=10.0)     # GPS 参考原点
plans    = yarbo.core.read_all_plan(timeout=10.0)    # 所有自动计划
map_data = yarbo.core.get_map(timeout=30.0)          # 地图和区域数据
```

### Step 7：下发命令

传入最新快照后，SDK 会在发送前自动校验附件头类型。

```python
from yarbo_robot_sdk.exceptions import YarboSDKError

yarbo = client.device(device, data=snapshot)

try:
    yarbo.core.return_to_charge()
    yarbo.core.start_plan(plan_id=1)
    yarbo.core.set_headlight(True)
    yarbo.mower.set_blade_height(60)       # head_type 不匹配时抛出 YarboSDKError
    yarbo.snow_blower.set_chute_angle(90)
except YarboSDKError as e:
    print(f"命令被拒绝: {e}")
```

### Step 8：断线重连

MQTT 是长连接，断线后需重新调用 `mqtt_connect()` 并重新注册所有订阅——订阅关系不会自动恢复。

```python
# 重连后重新注册订阅
client.mqtt_connect()
yarbo.core.subscribe_data_feedback(on_feedback)
yarbo.core.subscribe_device_message(on_status)
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

### Step 9：清理资源

断开 MQTT 并释放所有内部资源，进程退出前务必调用。

```python
client.close()
```

### 常见错误顺序

| ❌ 错误写法 | ✅ 正确写法 |
|-----------|-----------|
| 先 `subscribe_*` 再 `mqtt_connect()` | 先 `mqtt_connect()` 再 `subscribe_*` |
| 先 `get_device_msg()` 再 `subscribe_data_feedback()` | 先 `subscribe_data_feedback()` 再 `get_device_msg()` |
| 发命令时不传 `data=snapshot` | `client.device(device, data=snapshot)` 启用附件头校验 |
| 进程退出不调 `close()` | 在 `finally` 里调用 `client.close()` |

---

## 错误处理

SDK 所有异常均继承自 `YarboSDKError`：

| 异常 | 触发场景 |
|------|---------|
| `AuthenticationError` | 用户名或密码错误 |
| `TokenExpiredError` | refresh token 过期，需重新登录 |
| `APIError` | REST 请求返回非 2xx，含 `status_code` 属性 |
| `MqttConnectionError` | MQTT 连接失败 |


---

## Session 持久化

保存 token 后，下次启动可跳过登录。REST 请求收到 `401` 时会自动刷新一次 token；refresh token 过期时抛出 `TokenExpiredError`，需重新登录。

```python
# 登录后保存
client.login("user@example.com", "password")
saved_token   = client.token
saved_refresh = client.refresh_token

# 下次启动时恢复
client.restore_session("user@example.com", saved_token, saved_refresh)
```

---

## Helper 工具函数

```python
from yarbo_robot_sdk import (
    extract_field,            # 从 DeviceMSG 字典中按 dot-path 提取字段值
    extract_active_network,   # 解析当前活跃网络类型（Halow / Wifi / 4G）
    convert_local_to_gps,     # 设备本地坐标 → GPS 经纬度
    convert_map_to_geojson,   # 地图数据 → GeoJSON FeatureCollection
    get_field_definitions,         # 获取设备类型的所有数据字段定义
    get_control_field_definitions, # 获取设备类型的所有控制字段定义
)

# 提取字段值
battery = extract_field(snapshot, "BatteryMSG.capacity")   # → 85
head    = extract_field(snapshot, "HeadMsg.head_type")      # → 3

# 解析活跃网络
network = extract_active_network(snapshot.get("RoutePriority"))  # → "Wifi"

# 坐标转换
lat, lon = convert_local_to_gps(
    x=10.5, y=-3.2,
    ref_lat=gps["data"]["ref"]["latitude"],
    ref_lon=gps["data"]["ref"]["longitude"],
)

# 地图转 GeoJSON
geojson = convert_map_to_geojson(map_data["data"], gps["data"])
```

---

## 文档

- [API Reference](docs/api.md) — 完整方法参考、命令表、数据模型
- [MQTT Topics](docs/mqtt-topics.md) — 订阅/发布 topic 列表
- [Device Fields](docs/device-fields.md) — 设备字段路径与说明

---

## License

MIT
