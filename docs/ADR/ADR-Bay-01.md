# ADR-Bay-01: Yarbo Robot SDK 技术方案

| 字段 | 值 |
|------|----|
| 编号 | ADR-Bay-01 |
| 创建日期 | 2026-03-25 |
| 关联 PRD | PRD-Bay-01 |
| 状态 | 草稿 |

## 1. 背景

基于 PRD-Bay-01，需要开发一个 Python SDK，封装 Yarbo 云端 REST API 和 MQTT 通信能力。本阶段聚焦基础建设：认证登录、REST API 公共层、MQTT 连接管理、设备发现、设备能力注册表框架。

## 2. 现状分析

- 项目为全新空仓库，无既有代码
- 云端中转层 API 尚未开发，SDK 需基于 API 契约先行开发
- EMQX 云服务已部署，JWT AUTH 配置已就绪（from=username, ACL claim name=acl）

## 3. 方案设计

### 3.1 整体架构

```
用户代码
  │
  ▼
YarboClient (对外入口)
  ├── AuthManager        ← 登录、token 管理、自动刷新
  ├── RestClient         ← REST API 公共层（自动注入 token）
  ├── MqttClient         ← MQTT 连接、订阅、回调管理
  └── DeviceRegistry     ← 设备能力注册表（查询用）
      │
      ▼
  config.py              ← 集中配置（URL、公钥等）
  endpoints.py           ← REST API 端点定义
  device_registry.py     ← 设备类型能力声明
```

### 3.2 包结构

```
yarbo_robot_sdk/
├── pyproject.toml              # 项目元数据、依赖、构建配置
├── README.md                   # 使用文档
├── src/
│   └── yarbo_robot_sdk/
│       ├── __init__.py         # 包入口，导出 YarboClient
│       ├── client.py           # YarboClient 主类
│       ├── auth.py             # AuthManager 认证管理
│       ├── rest_client.py      # RestClient REST API 公共层
│       ├── mqtt_client.py      # MqttClient MQTT 连接管理
│       ├── config.py           # SDK 内部常量（超时、重试等）
│       ├── config_provider.py  # 配置获取（构造参数 > 云端接口）
│       ├── endpoints.py        # REST API 端点集中定义
│       ├── device_registry.py  # 设备能力注册表
│       ├── exceptions.py       # 自定义异常类
│       └── models.py           # 数据模型（Device 等）
└── tests/
    ├── __init__.py
    ├── conftest.py             # pytest fixtures
    ├── test_auth.py
    ├── test_rest_client.py
    ├── test_mqtt_client.py
    ├── test_client.py
    ├── test_device_registry.py
    └── test_config.py
```

采用 `src` layout，这是 Python 打包的推荐结构，避免开发时意外导入本地源码而非安装的包。

### 3.3 详细设计

#### 3.3.1 config.py — SDK 内部常量

```python
"""SDK 内部常量。环境相关配置（API URL、MQTT 地址、公钥）不在此文件中，
通过构造参数传入或从云端公开接口获取。"""

# 超时与重试
REQUEST_TIMEOUT = 30          # REST API 请求超时（秒）
TOKEN_REFRESH_MAX_RETRIES = 1 # token 刷新最大重试次数

# MQTT
MQTT_KEEPALIVE = 60           # MQTT keepalive 间隔（秒）
MQTT_RECONNECT_DELAY = 5      # MQTT 断线重连延迟（秒）

# 云端配置接口（用于获取 RSA 公钥、MQTT 地址等）
SDK_CONFIG_ENDPOINT = "/sdk/config"
```

#### 3.3.2 exceptions.py — 异常体系

```python
class YarboSDKError(Exception):
    """SDK 基础异常"""

class AuthenticationError(YarboSDKError):
    """登录失败（凭证错误）"""

class TokenExpiredError(YarboSDKError):
    """Token 和 refresh_token 均已过期，需重新登录"""

class APIError(YarboSDKError):
    """REST API 调用失败"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"API error {status_code}: {message}")

class MqttConnectionError(YarboSDKError):
    """MQTT 连接失败"""
```

#### 3.3.3 auth.py — AuthManager

职责：
- 使用 RSA 公钥加密密码
- 调用登录接口获取 token + refresh_token
- 提供 token 刷新能力
- 管理 token 生命周期

```python
class AuthManager:
    def __init__(self, api_base_url: str, rsa_public_key: str):
        self._api_base_url = api_base_url
        self._rsa_public_key = rsa_public_key
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._refreshing = False  # 防止并发刷新

    def login(self, username: str, password: str) -> None:
        """加密密码并调用登录接口"""
        encrypted_password = self._encrypt_password(password)
        response = requests.post(
            f"{self._api_base_url}/auth/login",
            json={"username": username, "password": encrypted_password}
        )
        # 解析 token 和 refresh_token ...

    def refresh(self) -> None:
        """使用 refresh_token 刷新 token"""

    def _encrypt_password(self, password: str) -> str:
        """RSA 公钥加密密码，返回 base64 编码的密文"""

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None
```

RSA 加密方案：
- 算法: RSA-OAEP + SHA-256
- 公钥格式: PEM (PKCS#8)
- 输出: base64 编码的密文字符串
- 依赖: `cryptography` 库

**RSA 密钥生成命令**（提供给用户执行）：
```bash
# 生成 2048 位 RSA 私钥
openssl genrsa -out yarbo_private.pem 2048

# 从私钥导出公钥
openssl rsa -in yarbo_private.pem -pubout -out yarbo_public.pem

# 查看公钥内容（复制到 config.py 中）
cat yarbo_public.pem
```

#### 3.3.4 rest_client.py — RestClient

职责：
- 封装所有 REST API 调用
- 自动注入 Authorization header
- 401 响应时自动触发 token 刷新并重试（最多重试 1 次）
- 统一错误处理

```python
class RestClient:
    def __init__(self, auth_manager: AuthManager, api_base_url: str):
        self._auth = auth_manager
        self._base_url = api_base_url
        self._session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> dict:
        """
        发送 REST API 请求。
        自动注入 token，遇到 401 自动刷新并重试一次。
        """
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._auth.token}"}

        response = self._session.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            self._auth.refresh()
            headers["Authorization"] = f"Bearer {self._auth.token}"
            response = self._session.request(method, url, headers=headers, **kwargs)

        if not response.ok:
            raise APIError(response.status_code, response.text)

        return response.json()

    def get(self, path: str, **kwargs) -> dict:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> dict:
        return self.request("POST", path, **kwargs)
```

#### 3.3.5 endpoints.py — API 端点集中定义

```python
"""REST API 端点集中管理。新增接口只需在此文件添加。"""

# 认证相关
AUTH_LOGIN = "/auth/login"
AUTH_REFRESH = "/auth/refresh"

# 设备相关
DEVICES_LIST = "/devices"
DEVICE_DETAIL = "/devices/{sn}"  # 使用 .format(sn=xxx) 填充
```

#### 3.3.6 mqtt_client.py — MqttClient

职责：
- 使用 token 作为 username 建立 MQTT 连接（EMQX JWT AUTH, from=username）
- 管理 topic 订阅
- 分发消息到用户注册的回调
- 断线自动重连

```python
import paho.mqtt.client as mqtt

class MqttClient:
    def __init__(self, auth_manager: AuthManager, host: str, port: int,
                 use_tls: bool = True, keepalive: int = 60):
        self._auth = auth_manager
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._keepalive = keepalive
        self._client: mqtt.Client | None = None
        self._callbacks: dict[str, list[Callable]] = {}  # topic -> [callback]

    def connect(self) -> None:
        """
        建立 MQTT 连接。
        username = token (JWT AUTH, from=username)
        password = 空字符串
        """
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self._client.username_pw_set(username=self._auth.token, password="")

        if self._use_tls:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.enable_logger()

        self._client.connect(self._host, self._port, self._keepalive)
        self._client.loop_start()

    def subscribe(self, topic: str, callback: Callable) -> None:
        """
        订阅 topic 并注册回调。
        SDK 不校验 topic 格式，权限由 EMQX ACL 控制。
        """
        if topic not in self._callbacks:
            self._callbacks[topic] = []
            self._client.subscribe(topic)
        self._callbacks[topic].append(callback)

    def unsubscribe(self, topic: str) -> None:
        """取消订阅"""
        self._client.unsubscribe(topic)
        self._callbacks.pop(topic, None)

    def disconnect(self) -> None:
        """断开 MQTT 连接"""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """连接成功后重新订阅所有 topic（断线重连场景）"""
        if rc == 0:
            for topic in self._callbacks:
                client.subscribe(topic)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """断线时 paho-mqtt 会自动重连（loop_start 模式下）"""
        pass

    def _on_message(self, client, userdata, msg):
        """收到消息时分发到对应 topic 的回调"""
        topic = msg.topic
        for registered_topic, callbacks in self._callbacks.items():
            if mqtt.topic_matches_sub(registered_topic, topic):
                for cb in callbacks:
                    cb(topic, msg.payload)
```

**MQTT 鉴权说明**：
- EMQX JWT AUTH 配置 `from=username`，即从 MQTT CONNECT 包的 username 字段读取 JWT
- SDK 将 token（即 JWT）设置为 MQTT 的 username
- password 设为空字符串
- EMQX 验证 JWT 签名后，根据 JWT 中的 `acl` claim 控制 topic 权限

#### 3.3.7 device_registry.py — 设备能力注册表

```python
"""
设备能力注册表。
集中声明每种设备类型支持的能力（topic、API、状态字段、控制指令）。
新增设备类型只需在 DEVICE_REGISTRY 中添加条目。
"""
from dataclasses import dataclass, field


@dataclass
class TopicDefinition:
    """Topic 定义"""
    name: str           # 可读名称，如 "设备状态"
    template: str       # topic 模板，如 "snowbot/{sn}/status"
    description: str    # 用途说明


@dataclass
class ApiDefinition:
    """REST API 定义"""
    name: str           # 可读名称
    method: str         # HTTP 方法
    path_template: str  # 路径模板，如 "/devices/{sn}"
    description: str


@dataclass
class DeviceType:
    """设备类型定义"""
    type_id: str                            # 类型标识，如 "mower"
    name: str                               # 可读名称，如 "割草机器人"
    topics: list[TopicDefinition] = field(default_factory=list)
    apis: list[ApiDefinition] = field(default_factory=list)
    status_fields: list[str] = field(default_factory=list)
    control_commands: list[str] = field(default_factory=list)  # 下阶段填充


# ============================================================
# 设备能力注册表 — 新增设备类型在此添加
# ============================================================
DEVICE_REGISTRY: dict[str, DeviceType] = {
    "mower": DeviceType(
        type_id="mower",
        name="割草机器人",
        topics=[
            # 下阶段定义具体 topic
        ],
        apis=[],
        status_fields=[],
        control_commands=[],
    ),
    "snowbot": DeviceType(
        type_id="snowbot",
        name="扫雪机器人",
        topics=[],
        apis=[],
        status_fields=[],
        control_commands=[],
    ),
}


def get_device_type(type_id: str) -> DeviceType | None:
    """查询设备类型定义"""
    return DEVICE_REGISTRY.get(type_id)


def list_device_types() -> list[DeviceType]:
    """列出所有已注册的设备类型"""
    return list(DEVICE_REGISTRY.values())
```

#### 3.3.8 models.py — 数据模型

```python
from dataclasses import dataclass


@dataclass
class Device:
    """设备基本信息"""
    sn: str             # 设备序列号
    type_id: str        # 设备类型标识（对应 device_registry 中的 type_id）
    name: str           # 设备名称
    model: str          # 设备型号
    online: bool        # 是否在线
```

#### 3.3.9 config_provider.py — 配置获取

```python
class ConfigProvider:
    """
    配置获取器。
    优先级：构造参数 > 云端公开接口。
    云端配置在 SDK 生命周期内只拉取一次（内存缓存）。
    """
    def __init__(self, api_base_url: str | None = None, **overrides):
        self._overrides = {"api_base_url": api_base_url, **overrides}
        self._cloud_config: dict | None = None

    def get(self, key: str) -> str | int | bool | None:
        """获取配置项。构造参数优先，否则从云端获取。"""
        if self._overrides.get(key) is not None:
            return self._overrides[key]
        return self._get_cloud_config().get(key)

    def _get_cloud_config(self) -> dict:
        """从云端拉取配置（带内存缓存）"""
        if self._cloud_config is None:
            self._cloud_config = self._fetch_cloud_config()
        return self._cloud_config

    def _fetch_cloud_config(self) -> dict:
        """GET /sdk/config — 无需鉴权"""
        api_base = self._overrides.get("api_base_url")
        if not api_base:
            raise YarboSDKError("api_base_url is required (pass via constructor or set cloud config endpoint)")
        resp = requests.get(f"{api_base}{SDK_CONFIG_ENDPOINT}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
```

**注意**: `api_base_url` 是唯一必须通过构造参数传入的配置（因为云端配置接口本身需要知道 API 地址）。其余配置（MQTT 地址、公钥等）可从云端获取。

#### 3.3.10 client.py — YarboClient 主入口

```python
class YarboClient:
    """
    Yarbo Robot SDK 主入口。

    用法:
        # 开发阶段：全部通过构造参数传入
        client = YarboClient(
            api_base_url="https://api.yarbo.com",
            mqtt_host="mqtt.yarbo.com",
            mqtt_port=8883,
            rsa_public_key="-----BEGIN PUBLIC KEY-----\n..."
        )

        # 生产环境：只需传 api_base_url，其余从云端获取
        client = YarboClient(api_base_url="https://api.yarbo.com")

        client.login("user@email.com", "password")
        devices = client.get_devices()

        # 宿主应用可读取 token 用于持久化
        saved = {"token": client.token, "refresh_token": client.refresh_token}

        # 下次启动恢复会话
        client.restore_session(token=saved["token"], refresh_token=saved["refresh_token"])
    """
    def __init__(
        self,
        api_base_url: str | None = None,
        mqtt_host: str | None = None,
        mqtt_port: int | None = None,
        mqtt_use_tls: bool | None = None,
        rsa_public_key: str | None = None,
    ):
        self._config = ConfigProvider(
            api_base_url=api_base_url,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_use_tls=mqtt_use_tls,
            rsa_public_key=rsa_public_key,
        )

        _api_base = self._config.get("api_base_url")
        _rsa_key = self._config.get("rsa_public_key")

        self._auth = AuthManager(_api_base, _rsa_key)
        self._rest = RestClient(self._auth, _api_base)
        self._mqtt: MqttClient | None = None  # 延迟初始化，连接时才需要 MQTT 配置

    # --- Auth ---
    def login(self, username: str, password: str) -> None:
        self._auth.login(username, password)

    def restore_session(self, token: str, refresh_token: str) -> None:
        """从宿主应用持久化的 token 恢复会话"""
        self._auth.restore(token, refresh_token)

    @property
    def token(self) -> str | None:
        return self._auth.token

    @property
    def refresh_token(self) -> str | None:
        return self._auth.refresh_token

    # --- REST API ---
    def get_devices(self) -> list[Device]:
        data = self._rest.get(endpoints.DEVICES_LIST)
        return [Device(**d) for d in data["devices"]]

    # --- MQTT ---
    def mqtt_connect(self) -> None:
        if self._mqtt is None:
            self._mqtt = MqttClient(
                auth_manager=self._auth,
                host=self._config.get("mqtt_host"),
                port=self._config.get("mqtt_port"),
                use_tls=self._config.get("mqtt_use_tls"),
            )
        self._mqtt.connect()

    def mqtt_subscribe(self, topic: str, callback: Callable) -> None:
        self._mqtt.subscribe(topic, callback)

    def mqtt_unsubscribe(self, topic: str) -> None:
        self._mqtt.unsubscribe(topic)

    def mqtt_disconnect(self) -> None:
        if self._mqtt:
            self._mqtt.disconnect()

    # --- Device Registry ---
    def get_device_type(self, type_id: str) -> DeviceType | None:
        return get_device_type(type_id)

    def list_device_types(self) -> list[DeviceType]:
        return list_device_types()

    # --- Lifecycle ---
    def close(self) -> None:
        self.mqtt_disconnect()
```

### 3.4 打包与发布

采用 `pyproject.toml` + `hatchling` 构建：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "yarbo-robot-sdk"
version = "0.1.0"
description = "Python SDK for Yarbo robot devices"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
dependencies = [
    "requests>=2.28",
    "paho-mqtt>=2.0",
    "cryptography>=41.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-mock>=3.0",
    "responses>=0.23",   # mock HTTP requests
]
```

发布流程：
```bash
pip install build twine
python -m build          # 生成 dist/yarbo_robot_sdk-0.1.0.tar.gz + .whl
twine upload dist/*      # 上传到 PyPI
```

## 4. 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| HTTP 客户端 | `requests` | 标准库级别认知度，同步接口，简单可靠 |
| MQTT 客户端 | `paho-mqtt` v2 | MQTT Python 生态事实标准，EMQX 官方推荐 |
| RSA 加密库 | `cryptography` | Python 加密领域标准库，维护活跃 |
| RSA 算法 | RSA-OAEP + SHA-256 | OAEP 是当前推荐的 RSA 填充方式，比 PKCS1v15 更安全 |
| 包结构 | src layout | 避免开发时意外导入本地源码 |
| 构建工具 | hatchling | 现代 Python 构建工具，配置简洁 |
| 配置管理 | 构造参数 > 云端接口 | 无需硬编码环境配置，支持公钥轮换 |

## 5. 实现步骤

1. 初始化项目结构（pyproject.toml、src layout、tests）
2. 实现 config.py、endpoints.py、exceptions.py、models.py（基础模块）
3. 实现 config_provider.py（构造参数 > 云端配置获取 + 内存缓存）
4. 实现 auth.py（RSA 加密 + 登录 + token 刷新 + restore_session）
5. 实现 rest_client.py（REST 公共层 + 自动刷新重试）
6. 实现 mqtt_client.py（MQTT 连接 + 订阅 + 回调分发 + 重连）
7. 实现 device_registry.py（设备能力注册表框架）
8. 实现 client.py（YarboClient 主入口，组装各模块）
9. 实现 __init__.py（对外导出）
10. 编写单元测试
11. 验证 pip install 可用性

## 6. 涉及文件清单

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `pyproject.toml` | 新增 | 项目配置、依赖、构建 |
| `README.md` | 新增 | 使用文档 |
| `src/yarbo_robot_sdk/__init__.py` | 新增 | 包入口 |
| `src/yarbo_robot_sdk/client.py` | 新增 | YarboClient 主类 |
| `src/yarbo_robot_sdk/auth.py` | 新增 | 认证管理 |
| `src/yarbo_robot_sdk/rest_client.py` | 新增 | REST API 公共层 |
| `src/yarbo_robot_sdk/mqtt_client.py` | 新增 | MQTT 连接管理 |
| `src/yarbo_robot_sdk/config.py` | 新增 | SDK 内部常量 |
| `src/yarbo_robot_sdk/config_provider.py` | 新增 | 配置获取（构造参数 > 云端） |
| `src/yarbo_robot_sdk/endpoints.py` | 新增 | API 端点定义 |
| `src/yarbo_robot_sdk/device_registry.py` | 新增 | 设备能力注册表 |
| `src/yarbo_robot_sdk/exceptions.py` | 新增 | 自定义异常 |
| `src/yarbo_robot_sdk/models.py` | 新增 | 数据模型 |
| `tests/conftest.py` | 新增 | 测试 fixtures |
| `tests/test_auth.py` | 新增 | 认证测试 |
| `tests/test_rest_client.py` | 新增 | REST 客户端测试 |
| `tests/test_mqtt_client.py` | 新增 | MQTT 客户端测试 |
| `tests/test_client.py` | 新增 | 主客户端测试 |
| `tests/test_device_registry.py` | 新增 | 设备注册表测试 |
| `tests/test_config.py` | 新增 | 配置测试 |

## 7. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 云端 API 契约变更 | 中 | SDK 需要同步修改 | endpoints.py 集中管理，变更影响可控 |
| paho-mqtt v2 API 不稳定 | 低 | 需适配 API 变化 | 锁定最低版本，关注 changelog |
| RSA 加密与后端解密不兼容 | 中 | 登录流程不通 | ADR 明确算法和填充方式（OAEP+SHA256），双端对齐 |
