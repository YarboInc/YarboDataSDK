# TEST-CASE-Bay-01: Yarbo Robot SDK 测试用例

| 字段 | 值 |
|------|----|
| 编号 | TEST-CASE-Bay-01 |
| 创建日期 | 2026-03-25 |
| 关联 PRD | PRD-Bay-01 |
| 关联 ADR | ADR-Bay-01 |

## 1. 测试范围

本次测试覆盖 PRD-Bay-01 中本阶段功能需求：
- 4.1 认证与登录
- 4.2 Token 自动刷新
- 4.3 设备发现
- 4.4 MQTT 实时状态订阅
- 4.5 REST API 公共层
- 4.6 设备能力注册表
- 4.7 SDK 配置管理

因云端 API 尚未开发，所有 HTTP 请求和 MQTT 连接使用 mock 测试。

## 2. 测试用例

### TC-001: RSA 公钥加密密码
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | config.py 中配置了有效的 RSA 公钥 |

**步骤**:
1. 调用 AuthManager._encrypt_password("test_password")
2. 验证返回值

**预期结果**:
- 返回 base64 编码的非空字符串
- 每次加密结果不同（OAEP 填充含随机因子）
- 可使用对应私钥解密还原原始密码

### TC-002: 登录成功
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 登录接口返回 200 + token + refresh_token |

**步骤**:
1. 创建 AuthManager
2. 调用 login("user@test.com", "password123")

**预期结果**:
- auth.token 不为空
- auth.refresh_token 不为空
- auth.is_authenticated 为 True
- HTTP 请求中 password 字段为 RSA 加密后的密文（非明文）

### TC-003: 登录失败 — 凭证错误
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 登录接口返回 401 |

**步骤**:
1. 调用 login("wrong@test.com", "wrongpass")

**预期结果**:
- 抛出 AuthenticationError 异常
- 异常信息包含有意义的错误描述
- auth.is_authenticated 为 False

### TC-004: 登录失败 — 网络异常
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 登录接口抛出 ConnectionError |

**步骤**:
1. 调用 login("user@test.com", "password123")

**预期结果**:
- 抛出 YarboSDKError 或其子类异常
- 不会抛出原始的 requests.ConnectionError

### TC-005: Token 自动刷新 — REST API 401 触发
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock: 首次请求返回 401，刷新接口返回新 token，重试请求返回 200 |

**步骤**:
1. 已登录状态下调用 rest_client.get("/devices")

**预期结果**:
- 自动调用刷新接口获取新 token
- 用新 token 重试原请求
- 最终返回正常数据
- 整个过程用户无感知（无异常抛出）

### TC-006: Token 刷新失败 — refresh_token 过期
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock: 请求返回 401，刷新接口也返回 401 |

**步骤**:
1. 调用 rest_client.get("/devices")

**预期结果**:
- 抛出 TokenExpiredError 异常
- 提示用户需要重新登录

### TC-007: REST API 公共层 — 自动注入 token
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | 已登录，token 有效 |

**步骤**:
1. 调用 rest_client.get("/devices")
2. 检查发出的 HTTP 请求

**预期结果**:
- 请求 header 包含 `Authorization: Bearer {token}`
- 请求 URL 为 `{api_base_url}/devices`

### TC-008: REST API 公共层 — HTTP 错误处理
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 返回 500 |

**步骤**:
1. 调用 rest_client.get("/some-endpoint")

**预期结果**:
- 抛出 APIError 异常
- 异常中包含 status_code = 500

### TC-009: 设备发现 — 获取设备列表
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 设备列表接口返回 2 个设备 |

**步骤**:
1. 调用 client.get_devices()

**预期结果**:
- 返回 list[Device]，长度为 2
- 每个 Device 包含 sn、type_id、name、model、online 字段
- 数据与 mock 返回一致

### TC-010: MQTT 连接 — JWT 鉴权
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | 已登录，Mock paho-mqtt Client |

**步骤**:
1. 调用 mqtt_client.connect()
2. 检查 paho-mqtt Client 的配置

**预期结果**:
- username_pw_set 被调用，username = token，password = ""
- connect 被调用，参数为配置的 host、port
- loop_start 被调用

### TC-011: MQTT 连接 — TLS 配置
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | use_tls=True |

**步骤**:
1. 调用 mqtt_client.connect()

**预期结果**:
- tls_set() 被调用

### TC-012: MQTT 订阅 — 注册回调
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | MQTT 已连接 |

**步骤**:
1. 定义回调函数 my_callback
2. 调用 mqtt_client.subscribe("snowbot/SN123/status", my_callback)

**预期结果**:
- paho client.subscribe("snowbot/SN123/status") 被调用
- 回调已注册到内部 _callbacks 字典

### TC-013: MQTT 消息分发 — 回调触发
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | 已订阅 topic 并注册回调 |

**步骤**:
1. 模拟 _on_message 收到 topic="snowbot/SN123/status", payload=b'{"battery": 80}'

**预期结果**:
- 注册的回调被调用
- 回调参数: topic="snowbot/SN123/status", payload=b'{"battery": 80}'

### TC-014: MQTT 断线重连 — 重新订阅
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | 已订阅 2 个 topic |

**步骤**:
1. 模拟触发 _on_connect（断线后重连成功）

**预期结果**:
- 所有已订阅的 topic 被重新 subscribe

### TC-015: MQTT 取消订阅
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | 已订阅 topic |

**步骤**:
1. 调用 mqtt_client.unsubscribe("snowbot/SN123/status")

**预期结果**:
- paho client.unsubscribe 被调用
- 内部 _callbacks 中移除该 topic

### TC-016: 设备能力注册表 — 查询设备类型
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | 注册表包含 mower 和 snowbot 类型 |

**步骤**:
1. 调用 get_device_type("mower")
2. 调用 get_device_type("nonexistent")

**预期结果**:
- "mower" 返回 DeviceType 对象，type_id="mower"，name="割草机器人"
- "nonexistent" 返回 None

### TC-017: 设备能力注册表 — 列出所有类型
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | 注册表包含至少 2 种设备类型 |

**步骤**:
1. 调用 list_device_types()

**预期结果**:
- 返回列表长度 >= 2
- 每个元素为 DeviceType 实例

### TC-018: SDK 配置 — 构造参数优先
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 云端配置接口 |

**步骤**:
1. 创建 YarboClient(api_base_url="https://api.yarbo.com", mqtt_host="custom.mqtt.com")
2. 检查 config_provider.get("mqtt_host")

**预期结果**:
- mqtt_host = "custom.mqtt.com"（使用构造参数）
- 云端配置接口未被调用（构造参数已提供）

### TC-019: SDK 配置 — 从云端获取
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 云端配置接口返回 {"mqtt_host": "cloud.mqtt.com", "rsa_public_key": "..."} |

**步骤**:
1. 创建 YarboClient(api_base_url="https://api.yarbo.com")（只传 api_base_url）
2. 检查 config_provider.get("mqtt_host")

**预期结果**:
- mqtt_host = "cloud.mqtt.com"（从云端获取）
- 云端配置接口被调用 1 次

### TC-020: SDK 配置 — 云端配置内存缓存
| 字段 | 内容 |
|------|------|
| 优先级 | P1 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 云端配置接口 |

**步骤**:
1. 创建 ConfigProvider(api_base_url="https://api.yarbo.com")
2. 连续调用 get("mqtt_host") 两次

**预期结果**:
- 云端配置接口只被调用 1 次（第二次使用缓存）

### TC-021: 会话恢复 — restore_session
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | 有之前保存的有效 token 和 refresh_token |

**步骤**:
1. 创建 YarboClient(api_base_url="https://api.yarbo.com")
2. 调用 client.restore_session(token="saved_token", refresh_token="saved_refresh")
3. 调用 client.get_devices()（Mock 返回 200）

**预期结果**:
- client.token == "saved_token"
- client.is_authenticated 为 True
- get_devices 请求携带正确的 token
- 无需调用 login

### TC-022: Token 属性导出
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 登录接口 |

**步骤**:
1. 调用 client.login("user@test.com", "pass")
2. 读取 client.token 和 client.refresh_token

**预期结果**:
- client.token 等于登录接口返回的 token
- client.refresh_token 等于登录接口返回的 refresh_token
- 宿主应用可用这些值做持久化

### TC-023: pip install 可用性
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 集成测试 |
| 前置条件 | pyproject.toml 配置正确 |

**步骤**:
1. 在干净的虚拟环境中执行 `pip install .`
2. 执行 `python -c "from yarbo_robot_sdk import YarboClient"`

**预期结果**:
- 安装成功，无报错
- import 成功，YarboClient 可用

### TC-024: YarboClient 完整流程
| 字段 | 内容 |
|------|------|
| 优先级 | P0 |
| 测试类型 | 单元测试 |
| 前置条件 | Mock 所有外部调用 |

**步骤**:
1. client = YarboClient()
2. client.login("user@test.com", "pass")
3. devices = client.get_devices()
4. client.mqtt_connect()
5. client.mqtt_subscribe("snowbot/SN123/status", callback)
6. client.close()

**预期结果**:
- 全流程无异常
- 各步骤按预期调用对应模块

## 3. 边界条件测试

| 场景 | 输入 | 预期结果 |
|------|------|----------|
| 空用户名登录 | username="" | 抛出 ValueError 或 AuthenticationError |
| 空密码登录 | password="" | 抛出 ValueError 或 AuthenticationError |
| 未登录就调用 get_devices | 未调用 login | 抛出 AuthenticationError |
| 未登录就连接 MQTT | 未调用 login | 抛出 AuthenticationError |
| 重复登录 | 连续调用 login 两次 | 第二次覆盖第一次的 token |
| 重复订阅同一 topic | 同一 topic subscribe 两次 | 不重复订阅底层 topic，回调列表追加 |
| MQTT 未连接就订阅 | 未调用 connect | 抛出 MqttConnectionError |

## 4. 异常场景测试

| 场景 | 触发条件 | 预期行为 |
|------|----------|----------|
| 登录接口超时 | Mock 请求超时 | 抛出 YarboSDKError，包含超时信息 |
| REST API 返回非 JSON | Mock 返回 HTML | 抛出 APIError |
| MQTT Broker 不可达 | Mock 连接失败 | 抛出 MqttConnectionError |
| RSA 公钥格式错误 | 传入无效公钥字符串 | 抛出 YarboSDKError，提示公钥格式无效 |
