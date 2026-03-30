# TEST-RESULT-Bay-01: Yarbo Robot SDK 测试报告

| 字段 | 值 |
|------|----|
| 编号 | TEST-RESULT-Bay-01 |
| 执行日期 | 2026-03-26 |
| 关联 PRD | PRD-Bay-01 |
| 关联测试用例 | TEST-CASE-Bay-01 |
| 总体结果 | 通过 |

## 1. 测试概要

| 指标 | 数值 |
|------|------|
| 总用例数 | 47 |
| 通过 | 47 |
| 失败 | 0 |
| 跳过 | 0 |
| 通过率 | 100% |

## 2. 用例执行结果

| 用例编号 | 场景 | 结果 | 备注 |
|----------|------|------|------|
| TC-001 | RSA 公钥加密密码 | ✅ 通过 | 3 个子用例（base64 格式、随机性、可解密） |
| TC-002 | 登录成功 | ✅ 通过 | 验证 token 存储 + 密码已加密 |
| TC-003 | 登录失败 — 凭证错误 | ✅ 通过 | AuthenticationError 正确抛出 |
| TC-004 | 登录失败 — 网络异常 | ✅ 通过 | YarboSDKError 包装原始异常 |
| TC-005 | Token 自动刷新 — 401 触发 | ✅ 通过 | 3 次 HTTP 调用（401 + refresh + retry） |
| TC-006 | Token 刷新失败 — refresh_token 过期 | ✅ 通过 | TokenExpiredError 正确抛出 |
| TC-007 | REST API — 自动注入 token | ✅ 通过 | Authorization header 正确 |
| TC-008 | REST API — HTTP 错误处理 | ✅ 通过 | APIError 包含 status_code |
| TC-009 | 设备发现 — 获取设备列表 | ✅ 通过 | 返回 Device 对象列表 |
| TC-010 | MQTT 连接 — JWT 鉴权 | ✅ 通过 | username=token, password="" |
| TC-011 | MQTT 连接 — TLS 配置 | ✅ 通过 | tls_set() 正确调用 |
| TC-012 | MQTT 订阅 — 注册回调 | ✅ 通过 | paho subscribe + 内部回调注册 |
| TC-013 | MQTT 消息分发 — 回调触发 | ✅ 通过 | 精确匹配 + 通配符匹配 |
| TC-014 | MQTT 断线重连 — 重新订阅 | ✅ 通过 | on_connect 重新订阅所有 topic |
| TC-015 | MQTT 取消订阅 | ✅ 通过 | unsubscribe + 回调清理 |
| TC-016 | 设备能力注册表 — 查询设备类型 | ✅ 通过 | mower/snowbot 可查，nonexistent 返回 None |
| TC-017 | 设备能力注册表 — 列出所有类型 | ✅ 通过 | >= 2 种类型 |
| TC-018 | SDK 配置 — 构造参数优先 | ✅ 通过 | 不触发云端请求 |
| TC-019 | SDK 配置 — 从云端获取 | ✅ 通过 | 正确获取云端值 |
| TC-020 | SDK 配置 — 云端配置内存缓存 | ✅ 通过 | 仅 1 次 HTTP 调用 |
| TC-021 | 会话恢复 — restore_session | ✅ 通过 | token 恢复后可直接调用 API |
| TC-022 | Token 属性导出 | ✅ 通过 | token/refresh_token 可读 |
| TC-023 | pip install 可用性 | ✅ 通过 | 安装 + import 均成功 |
| TC-024 | YarboClient 完整流程 | ✅ 通过 | login→devices→mqtt→close 全链路 |

### 边界条件测试

| 场景 | 结果 | 备注 |
|------|------|------|
| 空用户名登录 | ✅ 通过 | AuthenticationError |
| 空密码登录 | ✅ 通过 | AuthenticationError |
| 未登录调用 REST API | ✅ 通过 | AuthenticationError |
| 未登录连接 MQTT | ✅ 通过 | MqttConnectionError |
| 重复订阅同一 topic | ✅ 通过 | 回调追加，不重复订阅底层 |
| MQTT 未连接就订阅 | ✅ 通过 | MqttConnectionError |
| 无效 RSA 公钥 | ✅ 通过 | YarboSDKError |
| 缺少 api_base_url | ✅ 通过 | YarboSDKError |
| 云端配置接口 500 | ✅ 通过 | YarboSDKError |
| TLS 关闭时不调用 tls_set | ✅ 通过 | |

## 3. 失败用例分析

无失败用例。

## 4. 测试命令与日志

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行全量测试
python -m pytest tests/ -v

# 测试结果
# 47 passed in 4.73s
```

## 5. 结论与建议

全部 47 个测试用例通过，覆盖 TEST-CASE-Bay-01 中定义的 TC-001 ~ TC-024 + 边界条件 + 异常场景。

**满足 PRD-Bay-01 全部 12 条验收标准（AC1-AC12）。**

### 后续建议
1. 云端中转层 API 就绪后，进行真实联调测试
2. 下阶段补充设备控制指令的具体实现和测试
3. 设备能力注册表中的 topics/apis/status_fields 待下阶段填充具体内容
