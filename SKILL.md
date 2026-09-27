---
name: overseas-opportunity-radar
description: Find overseas software ideas worth adapting for China and return a practical, ranked inspiration list. Cloud-native version: use built-in web search for discovery and local scripts only for planning, validation, and report persistence.
---

# 海外热门机会雷达（Cloud Native）

目标是尽可能发现有启发性的海外软件 idea，并直接交付**所有不重复、能说清中国切法的方向**。

本版本专门面向 ChatGPT 云端/定时任务运行：**联网采集必须使用模型可用的内置 Web 搜索/网页读取能力，不依赖 OpenCLI、mcporter、Exa CLI、gh CLI、浏览器桥接、Chrome 登录态或任何第三方 Python 包。** 本地脚本不承担联网职责，只负责生成检索计划、校验结构化证据和保存报告。

## 云端执行原则

1. 不尝试在 Python、Shell 或容器脚本里联网。云端沙盒可能禁止 DNS/外网访问。
2. 不检查或安装 `opencli`、`mcporter`、`gh`、Playwright、Selenium、Node 包或 pip 包。
3. 需要公开互联网数据时，直接使用当前运行环境提供的 Web 搜索/网页读取工具。
4. 如果某个来源无法直接访问，用公开搜索结果、来源原页面、官方 API 页面或可信二级来源补位；单个来源失败不能阻塞整轮。
5. 任何“热度/增长/排名”结论都要有可追溯 URL；搜索摘要只作为线索，重要候选尽量打开原页面核实。

## 执行流程

### 1. 生成检索计划

先运行：

```sh
./scripts/run-step.sh discover --days 30 --limit 8 --sources weekly
```

这个命令**不会联网**，只会根据 `references/source-registry.json` 生成：

```text
.opportunity-radar/runs/YYYY-MM-DD-HHMMSS-plan.json
```

计划里包含来源、类别、域名、建议查询和新鲜度要求。读取该 JSON 后，使用内置 Web 搜索并行执行其中的检索任务。

未指定赛道时，不传统一查询词；默认覆盖：
- 中小商家工作流
- 专业用户效率工具
- 内容/消费应用
- 开发者早期采用

### 2. 建立四层雷达

来源按“发现新品 → 观察增长 → 垂直生态验证 → 真实需求/使用量验证”组织，不按网站机械罗列。

- **新品雷达**：Product Hunt、YC Startup Directory、Peerlist Launchpad、Uneed、Microlaunch、BetaList、Show HN。用于发现刚发布或刚进入早期采用阶段的产品。
- **增长雷达**：GitHub Trending、Chrome Web Store Top Charts、Google Play / Similarweb Trending、Exploding Topics。用于找排名上升、采用加速或机制快速扩散的产品。
- **垂直生态雷达**：Shopify App Store、Atlassian Marketplace、Zapier App Directory、Notion Marketplace。用于发现已经嵌入真实业务工作流、愿意付费的窄需求。
- **需求与验证**：Reddit、G2、AppSumo、App Market Intelligence、a16z Gen AI 榜单。用于确认抱怨、付费意愿、使用量和赛道热度。

前三层条目可以直接成为候选；验证层通常用来补证据，除非其中出现非常明确的新问题或新机制。Chinese Independent Developer 用于最后核对国内是否已有明显同类切法。

### 3. Web 搜索执行方式

读取 plan 后按来源并行搜索。优先级：

1. 来源原站榜单/产品页/帖子；
2. 官方 API 或官方公开页面；
3. Hacker News / GitHub 等可核验讨论页；
4. 搜索结果摘要与可信二级报道。

搜索规则：
- 当前榜单、最近发布、近期讨论默认用近 7–30 天的新鲜度约束；
- Peerlist 优先覆盖最近 1–2 周 Launchpad；Uneed 优先覆盖 Daily / Weekly / Monthly 中重复出现的产品；
- Chrome Web Store 优先看 Trending 与 New and notable；Google Play 优先看 Similarweb 的 Rising / Joined top 100；
- Shopify / Atlassian / Zapier / Notion 不追求全量扫榜，优先看评论量、榜单变化、Recent/Upcoming 与明确业务工作流；
- BetaList 优先覆盖 Today / Yesterday；
- Reddit/G2/AppSumo 重点搜索“pain / alternative / wish / manual / expensive / missing / workaround”等需求表达；
- 对没有明确发布日期但有明确产品机制的条目可以保留，并标为“持续需求 / 旧产品新切法 / 仅作灵感”；
- 不因为某个来源打不开就删除一个已经有其它公开证据支持的候选。


### 3.1 来源权重与去重

`source-registry.json` 中每个来源包含 `radar_layer` 和 `signal_role`：
- `core`：每周核心发现源，优先采集；
- `supporting`：补充覆盖，避免遗漏长尾；
- `validation`：用于验证使用量、市场成熟度或国内竞争，不应单独证明“新品爆火”。

同一个产品若同时出现在多个新品/增长来源，视为更强信号，但报告仍按“用户问题 / 产品机制”聚类，只保留一条机会方向并合并证据。

### 4. 形成证据 JSON

搜索完成后，把有效条目整理为：

```text
.opportunity-radar/runs/YYYY-MM-DD-HHMMSS-evidence.json
```

结构必须符合 `references/evidence-schema.json`。每条记录至少包含：
- `source_id`
- `title`
- `url`
- `summary`
- `evidence_type`

可选：
- `published_at`
- `signal`
- `discussion_url`

然后运行：

```sh
python3 scripts/validate-evidence.py .opportunity-radar/runs/<file>-evidence.json
```

校验通过后再进入聚类与报告阶段。

### 5. 聚类与判断

将候选按**同一个用户问题或产品机制**聚类，而不是按网站逐条罗列。

每个机会至少回答：
- 海外现在出现了什么产品/需求信号？
- 用户问题是什么？
- 为什么中国市场存在可迁移空间？
- 第一版具体工作流是什么？
- 第一个适合切入的用户/行业是谁？

不要因为证据不够“投研级”而过度删 idea；本 skill 目标是产品机会发现，不是投资尽调。

### 6. 报告归档（每次运行必做）

报告目录固定为项目目录下：

```text
.opportunity-radar/reports/
```

文件名：`YYYYMMDD-NN.md`，当天从 `01` 递增，永不覆盖。

先写完整 Markdown 正文到临时文件，然后运行：

```sh
python3 scripts/save-report.py --input <draft.md>
```

保存后重新读取文件确认内容完整，再把该 `.md` 文件作为最终交付附件。

## 交付格式

```markdown
# 海外产品机会雷达 YYYY-MM-DD

| 优先级 | 机会 | 海外热度 / 需求证据 | 国内能怎么做 | 判断 |
|---:|---|---|---|---|
| 1 | ... | ... | ... | 优先看 |

## 暂不建议碰

- ...
```

判断只使用：
- `优先看`
- `值得看`
- `待验证`
- `不建议`

最终表格中剔除 `不建议`；这些方向只放在“暂不建议碰”。

## 约束

- 不把单一 GitHub star、单篇帖子、搜索排名或无日期页面写成“爆火”。
- 区分“近期讨论”“持续需求”“旧产品的新本地切法”和“仅作灵感”。
- 海外产品只用于发现问题模型和本地化机会，不复制品牌、代码、界面、素材或受保护内容。
- 不输出原始采集日志、内部 JSON、评分表或来源状态表，除非用户明确要求。
- 来源和查询策略只在 `references/source-registry.json` 维护，不在执行流程里硬编码。
