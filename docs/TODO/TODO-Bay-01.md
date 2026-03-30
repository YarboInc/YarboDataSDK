# TODO-Bay-01: Yarbo Robot SDK 开发任务

| 字段 | 值 |
|------|----|
| 编号 | TODO-Bay-01 |
| 创建日期 | 2026-03-25 |
| 关联 PRD | PRD-Bay-01 |
| 关联 ADR | ADR-Bay-01 |
| 进度 | 13/13 |

## 任务清单

### 阶段一: 项目初始化
- [x] T1: 初始化项目结构
  - 文件: `pyproject.toml`, `README.md`, `src/yarbo_robot_sdk/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
  - 验收: `pip install -e ".[dev]"` 成功，`from yarbo_robot_sdk import YarboClient` 可执行
  - 依赖: 无

### 阶段二: 基础模块
- [x] T2: 实现 exceptions.py — 自定义异常体系
  - 文件: `src/yarbo_robot_sdk/exceptions.py`
  - 验收: 定义 YarboSDKError、AuthenticationError、TokenExpiredError、APIError、MqttConnectionError
  - 依赖: T1
- [x] T3: 实现 models.py — 数据模型
  - 文件: `src/yarbo_robot_sdk/models.py`
  - 验收: Device dataclass 定义完整（sn, type_id, name, model, online）
  - 依赖: T1
- [x] T4: 实现 config.py — SDK 内部常量
  - 文件: `src/yarbo_robot_sdk/config.py`
  - 验收: 包含 REQUEST_TIMEOUT、MQTT_KEEPALIVE、SDK_CONFIG_ENDPOINT 等常量
  - 依赖: T1
- [x] T5: 实现 endpoints.py — REST API 端点定义
  - 文件: `src/yarbo_robot_sdk/endpoints.py`
  - 验收: 定义 AUTH_LOGIN、AUTH_REFRESH、DEVICES_LIST、DEVICE_DETAIL、SDK_CONFIG
  - 依赖: T1

### 阶段三: 核心模块
- [x] T6: 实现 config_provider.py — 配置获取器
  - 文件: `src/yarbo_robot_sdk/config_provider.py`, `tests/test_config_provider.py`
  - 验收: 构造参数优先；未传入时调用云端接口；内存缓存（只拉取一次）；TC-018/019/020 通过
  - 依赖: T4, T5
- [x] T7: 实现 auth.py — 认证管理
  - 文件: `src/yarbo_robot_sdk/auth.py`, `tests/test_auth.py`
  - 验收: RSA 加密密码、登录获取 token、刷新 token、restore_session、token/refresh_token 属性导出；TC-001~004, TC-021/022 通过
  - 依赖: T2, T4, T5
- [x] T8: 实现 rest_client.py — REST API 公共层
  - 文件: `src/yarbo_robot_sdk/rest_client.py`, `tests/test_rest_client.py`
  - 验收: 自动注入 token、401 自动刷新重试、统一错误处理；TC-005~008 通过
  - 依赖: T2, T7
- [x] T9: 实现 mqtt_client.py — MQTT 连接管理
  - 文件: `src/yarbo_robot_sdk/mqtt_client.py`, `tests/test_mqtt_client.py`
  - 验收: token 作为 username 鉴权、subscribe/unsubscribe、回调分发、断线重连重新订阅；TC-010~015 通过
  - 依赖: T2, T4, T7

### 阶段四: 设备能力注册表
- [x] T10: 实现 device_registry.py — 设备能力注册表
  - 文件: `src/yarbo_robot_sdk/device_registry.py`, `tests/test_device_registry.py`
  - 验收: DeviceType/TopicDefinition/ApiDefinition 模型、DEVICE_REGISTRY 字典、get_device_type/list_device_types 方法；TC-016/017 通过
  - 依赖: T1

### 阶段五: 主入口集成
- [x] T11: 实现 client.py + __init__.py — YarboClient 主入口与包导出
  - 文件: `src/yarbo_robot_sdk/client.py`, `src/yarbo_robot_sdk/__init__.py`, `tests/test_client.py`
  - 验收: login/restore_session/get_devices/mqtt_connect/mqtt_subscribe/mqtt_disconnect/close 全部可用；token/refresh_token 属性可读；TC-009/024 通过
  - 依赖: T6, T7, T8, T9, T10

### 阶段六: 集成验证
- [x] T12: 全量单元测试通过
  - 文件: `tests/`
  - 验收: `pytest` 全部通过，覆盖 TC-001~TC-024 + 边界条件 + 异常场景
  - 依赖: T11
- [x] T13: pip install 可用性验证
  - 文件: 无新增
  - 验收: 干净虚拟环境中 `pip install .` 成功，`python -c "from yarbo_robot_sdk import YarboClient"` 无报错；TC-023 通过
  - 依赖: T12

## 检查点
- [x] CP1: T5 完成后 — 基础模块就绪，可 import 无报错
- [x] CP2: T9 完成后 — 核心模块全部就绪，各模块可独立测试通过
- [x] CP3: T11 完成后 — YarboClient 集成完毕，完整流程可跑通
- [x] CP4: T13 完成后 — 包可安装，全部测试通过

## 需求覆盖矩阵

> 反查 PRD-Bay-01，确保所有功能需求和验收标准均被任务覆盖。

### 功能需求覆盖

| PRD 需求条目 | 覆盖任务 | 覆盖状态 |
|--------------|----------|----------|
| 4.1 认证与登录 | T7 | ✅ 已覆盖 |
| 4.2 Token 自动刷新 | T7, T8 | ✅ 已覆盖 |
| 4.3 设备发现 | T11 | ✅ 已覆盖 |
| 4.4 MQTT 实时状态订阅 | T9, T11 | ✅ 已覆盖 |
| 4.5 REST API 公共层 | T8 | ✅ 已覆盖 |
| 4.6 设备能力注册表 | T10 | ✅ 已覆盖 |
| 4.7 SDK 配置管理 | T6, T11 | ✅ 已覆盖 |

### 验收标准覆盖

| PRD 验收标准 | 覆盖任务 | 覆盖状态 |
|--------------|----------|----------|
| AC1: pip install 安装 | T1, T13 | ✅ 已覆盖 |
| AC2: 用户名密码登录 + RSA 加密 | T7 | ✅ 已覆盖 |
| AC3: Token 自动刷新 | T7, T8 | ✅ 已覆盖 |
| AC4: 获取设备列表 | T11 | ✅ 已覆盖 |
| AC5: MQTT 订阅 + 回调 | T9, T11 | ✅ 已覆盖 |
| AC6: MQTT JWT 鉴权 | T9 | ✅ 已覆盖 |
| AC7: MQTT 断线重连 | T9 | ✅ 已覆盖 |
| AC8: 构造参数 / 云端配置 | T6 | ✅ 已覆盖 |
| AC9: 设备能力注册表 | T10 | ✅ 已覆盖 |
| AC10: 集中管理可扩展 | T5, T10 | ✅ 已覆盖 |
| AC11: 错误处理 | T2, T7, T8, T9 | ✅ 已覆盖 |
| AC12: token 属性 + restore_session | T7, T11 | ✅ 已覆盖 |

### 覆盖率统计
- 功能需求: 7/7 (100%)
- 验收标准: 12/12 (100%)
- **总覆盖率 100%，可进入开发阶段**
