# LOGOS 运维使用场景

> 语言：[English](./use-cases.md) · [Русский](./use-cases.ru.md) · [Español](./use-cases.es.md) · [Français](./use-cases.fr.md) · **中文**

以下是运维流程，不是营销故事。示例值来自 **2026-08-10 17:24 UTC** 的本地实时
LOGOS API；它们是带时间戳的观测值，不是常量，使用时应重新请求。

## 1. 联邦早班交接

值班工程师先读取 `GET /api/v1/report/daily`，再用 `GET /api/v1/snapshot` 核对来源。
当时报告为 `overall_status=warn`、健康 Hub `1/4`、已索引 capabilities `53`，目录仍列出
Oracle Family（42）、GAIA IoT（11）和 Factory。

**决策：**调查健康探测，而不是宣称三个 Hub 已消失。`latency_ms=null` 不能解释为零延迟。

## 2. FinOps：能否预测下月支出

`GET /api/v1/consumption` 测得已结算 `$0.04`、52 个付费 capability、1 个免费
capability，最高路由单价 `$0.0505`。由于 Hub 没有发布可用的 24 小时结算窗口，
LOGOS 返回 `estimated_monthly_spend_usd=null` 与 `spend_basis=unavailable`。

**决策：**不根据虚构预测充值；先恢复结算遥测，等待代表性窗口后再计算。

## 3. 上线前检查供应商集中度

产品负责人按 `source_hub` 汇总 `GET /api/v1/federation/capabilities`，并比较具体
capability、价格和信任度。53 个外部条目中 42 个来自 Oracle Family（79.25%），
11 个来自 GAIA IoT。

**决策：**为目标 production capability 找到第二条路由，或明确接受单一系列依赖。
集中度是风险信号，不是故障或不当行为的证据。

## 4. 安全到修复的证据链

配置 `LOGOS_MOMUS_URL` 与 `LOGOS_SKOPOS_URL` 后，安全负责人关联 severity、受影响
Hub 和 remediation 状态，敏感 finding 细节不得进入 LLM。观测部署中
`findings.status=no_data`，因为未配置 MOMUS；其含义是“数据源未连接”，不是“零漏洞”。

## 5. 证明目录是否真的收缩

`GET /api/v1/trend?metric=total_capabilities&hours=24` 返回 15:08 至 17:21 UTC 的
24 个存储点，所有值均为 `53.0`。

**决策：**否定该测量窗口内的目录收缩，转而检查 reachability、客户端过滤或其他 Hub。
历史不足时，LOGOS 不会合成 baseline。

## 6. 保留来源的自然语言问答

提问：“capabilities 消失了，还是 peers 只是健康检查失败？”合格回答必须给出观测时间，
区分 53 个已索引 capabilities 与 1/4 健康 Hub，并将 MOMUS/Treasury 标为不可用。
绝不能编造原因或支出预测，也不能把 `null` 变成 `0`。
