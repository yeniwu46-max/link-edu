# OpenAI Next 模拟授课额度接入

2026-09-09：按用户控制台截图保留三把密钥现有额度，无后台调额、禁用或新建操作。

| 用途 | 平台已分配上限 | 本地提醒 / 停止 | 模型与调用 |
| --- | --- | --- | --- |
| 模拟授课 | $30 | $24 / $27 | deepseek-v4-flash，三名模拟学生共用，包含评课与报告重评 |
| 视觉 | $40 | $32 / $36 | deepseek-v4-flash-vision-exp，用户明确开启的云端截图 |
| 测试 | $30 | $24 / $27 | 上述两模型，文字/视觉接口探针、教学探针及隔离合成课堂 |

每个用途固定使用自己的密钥。单个用途失败或耗尽时不轮换到其他用途。语音识别与合成继续走讯飞；活动美元额度不能用于支付讯飞直连接口。

## 本机配置

密钥仅在 Git 忽略的 `backend/.env`。示例变量见 `backend/.env.classroom.example`。开关为 `CLASSROOM_LLM_PROVIDER=openai_next`，端点固定校验为 `https://api.openai-next.com/v1`。使用 OpenAI 兼容 Chat Completions、JSON 对象返回和 DeepSeek 非思考模式。当前适配器仅核验这两个 Flash 模型，不把已有费率自动套到 GPT/Claude。

三把密钥均通过 `/v1/models` 只读验证，该列表包含上述两模型。随后真实合成探针验证了授课密钥 JSON 返回、视觉密钥蓝/粉双色图识别，以及测试密钥的文字和视觉两种调用；重启后的网页 API 探针也通过。

新增 `classroom_credit_usage` 表按用途记录美元预留、估算结算、模型、tokens 和当时费率。启动时 `db.create_all()` 仅新增表。历史人民币账本保留，讯飞新调用继续进入原账本；美元不换算或写入人民币字段。

按上游公开峰时、输入未命中缓存价格做保守估算：两模型输入 $0.44 / 百万 tokens、输出 $1.32 / 百万 tokens。实际平台扣费、缓存/时段优惠、活动有效期及外部工具用量以控制台为准，本地账本不是平台余额。更换模型或平台调价须重新核验费率。

额度预留使用本机跨进程锁和独立数据库事务；未知失败保留预留。隔离课堂测试也将美元用量写回主库，避免新建测试库重置美元预算。原人民币隔离探针流程继续用于讯飞和旧供应商调用。仍仅支持一个工作目录、一台机器、一个课堂后端。

## 验证与运行

```powershell
C:\Python314\python.exe -m pytest backend/tests -q
npm test --prefix frontend
npm run build --prefix frontend
# 服务器启动后；仅合成内容，会消耗少量测试美元额度。
C:\Python314\python.exe scripts/probe_classroom.py dialogue vision
```

修改本机环境配置后重启 5001 后端。刷新课堂页可查看三份美元估算和独立人民币用量。网页“验证接口”的文字/视觉调用使用测试密钥，成功提示明确区分正式用途密钥；讯飞探针仍扣讯飞额度。

本轮验证：后端 89 项、前端 14 项测试通过；生产构建通过，保留已有大包提示。共 6 次云端合成验证，本地美元估算约 $0.000313；不是平台最终扣费。人民币历史估算与预留仍为 ¥1.7414。本次没有进行麦克风课堂验收。5001 后端已重启，5188 前端代理读取到 OpenAI Next 配置和三份美元额度。

来源（核对于 2026-09-09）：[平台接入地址及协议](https://credits.openai-next.com/guide/quickstart)、[平台计费说明](https://credits.openai-next.com/guide/faq)、[DeepSeek 美元价格](https://api-docs.deepseek.com/quick_start/pricing/)。
