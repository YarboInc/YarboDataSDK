# MQTT Topics

## 订阅实时数据

### 设备状态（DeviceMSG）

设备运行时持续推送，包含电量、位置、传感器、计划执行状态等完整信息。

```python
def on_status(topic, data):
    battery = extract_field(data, "BatteryMSG.capacity")
    state   = extract_field(data, "StateMSG.working_state")

yarbo.core.subscribe_device_message(on_status)
```

> **底层写法**：`client.subscribe_device_message(device.sn, device.type_id, on_status)`

---

### 心跳（HeartBeat）

定期推送（约每 30 秒），用于判断设备是否在线。

```python
yarbo.core.subscribe_heart_beat(on_heartbeat)
```

> **底层写法**：`client.subscribe_heart_beat(device.sn, device.type_id, on_heartbeat)`

---

### 命令反馈（data_feedback）

`get_device_msg`、`read_all_plan` 等数据请求的响应通道。**必须在发起任何数据请求之前订阅。**

```python
yarbo.core.subscribe_data_feedback(on_feedback)
```

> **底层写法**：`client.subscribe_data_feedback(device.sn, device.type_id, on_feedback)`  
> 不传 `on_feedback` 时，SDK 内部仍会处理响应用于同步等待，仅在需要自定义处理时传入回调。

---

## Topic 地址

| 名称 | Topic |
|------|-------|
| DeviceMSG | `snowbot/{sn}/device/DeviceMSG` |
| HeartBeat | `snowbot/{sn}/device/heart_beat` |
| data_feedback | `snowbot/{sn}/device/data_feedback` |
| 命令下发 | `snowbot/{sn}/app/{command}` |

---

## 数据压缩

固件 >= 3.9.0 的设备会对 MQTT payload 进行 zlib 压缩，SDK 自动处理压缩与解压，无需额外操作。

---

## EMQX 迁移期连接策略

为配合 EMQX 共享集群向 EMQX Dedicated 集群顺切迁移，SDK 在内部按 **SN 维度** 自动选择 broker：

- 调用任意 `subscribe_*(sn, ...)` 或 `mqtt_publish_command(sn, ...)` 时，SDK 先查询 `GET /yarbo/emqx-migration/query?sn=<SN>`（携带 `Authorization: Bearer <JWT>`）
- 若返回 `migrated=true` → 设备已迁移，连接到新 EMQX Dedicated 集群
- 若返回 `migrated=false` → 设备未迁移，连接到旧共享集群
- 两类设备同时存在时，SDK 同时维护两条物理连接，最多两条

### 两个 broker 的连接形态

| 维度 | 旧集群（未迁移设备） | 新 EMQX Dedicated（已迁移设备） |
|------|-------------------|------------------------------|
| Host | 由 `/sdk/config` 提供（默认 `t9db1d91.us-east-1.emqx.cloud:15525`）| `c4750009.ala.dedicated.aws.emqxcloud.com:8883` |
| TLS | 启用 | 启用，与旧集群相同的系统 CA |
| ClientID | `HA_{email}_{unix_ts}` | `HA_{email}_{rand4}` |
| username | JWT | email |
| password | `""` | JWT |

### 行为细节

- `client.mqtt_connect()` 是 **lazy** 的：调用本身不发起网络通信，等到第一个 `subscribe_*(sn,...)` 或 `mqtt_publish_command(sn,...)` 时才建立对应 broker 的连接
- 新 broker 建连前 SDK 主动调一次 `auth.refresh()`，避免 EMQX 因 token 过期拒绝认证；已经建立的连接不主动干预
- 任意 broker 断线（`_on_disconnect` 触发）后，SDK 清空所有 SN 的迁移状态缓存——下次订阅 / 发布会重新查询，自动覆盖"断线期间设备发生迁移"的情况
- `migration query` 用当前 JWT 鉴权；若 token 失效（HTTP 401 或 `success=false` 且 `code=A0230`），SDK 自动 `auth.refresh()` 并重试一次（恢复的存量 token 可能已过期）。刷新失败抛 `TokenExpiredError`，由宿主（HA）驱动重新登录
- `migration query` 失败（HTTP 非 2xx / `success=false` / 网络异常）一律抛 `YarboSDKError`，**不静默回退** —— 静默回退会导致已迁移设备连到旧 broker 后收不到数据
- 路由配置参数（`new_mqtt_host` / `new_mqtt_port` / `new_mqtt_use_tls` / `emqx_migration_query_url`）支持三级优先级：构造参数 → `/sdk/config` 云端 → SDK 内嵌默认值

### 日志区分 broker

每个 `MqttClient` 实例带一个 broker 标签（`legacy` / `new`），连接相关日志统一以 `MQTT[<label>]` 前缀输出，便于在两个 broker 并存时区分某条连接 / 订阅属于哪个集群；路由判定单独打一行 `MQTT route`。关键事件均为 `info` 级：

```
MQTT route sn=<SN> -> new broker
MQTT[new] connecting → <host>:<port> (tls=True) client_id=HA_<email>_<rand4>
MQTT[new] connected to <host>:<port> (rc=0); re-subscribing <N> topic(s)
MQTT[new] subscribe → snowbot/<SN>/device/DeviceMSG
MQTT[new] disconnected from <host>:<port> (rc=...)
```

未迁移设备对应 `MQTT[legacy] ...` 及旧集群 host。开启方式（HA）：

```yaml
logger:
  logs:
    yarbo_robot_sdk.client: info
    yarbo_robot_sdk.mqtt_client: info
```

迁移完成后，路由器层和迁移查询调用会作为单独工单清理。
