---
name: overseas-opportunity-radar
description: Find overseas software ideas worth adapting for China and return a practical, ranked inspiration list. Use when the user wants hot overseas apps, rising software ideas, or China-localization opportunities; do not use for product implementation.
---

# 海外热门机会雷达

目标是尽可能发现有启发性的海外软件 idea，并直接交付**所有不重复、能说清中国切法的方向**。搜索链接用于说明灵感从哪里来和大致热度，不是投资尽调门槛。

## 执行

1. 先明确用户指定的赛道、目标用户或产品类型；未指定时不传统一查询词，直接让每个来源按用途覆盖"中小商家工作流"、"专业用户效率工具"、"内容/消费应用"和"开发者早期采用"。不要把四个赛道拆成四轮串行检索，也不要把它们硬塞进一句宽查询。
2. 平行建立三类**候选池**，三类条目都可以直接成为候选，不能只把它们当作评分信号：
   - **榜单候选**：Product Hunt 的日/周/月 Top，GitHub Trending 与 7 天 star 增长，应用商店分类榜，AppSumo 热门 deal；榜单中的每个产品/项目直接进入候选池。
   - **雷达候选**：Exploding Topics 的产品、创业公司、关键词趋势，Trending Startups，BetaList 新产品；产品/公司直接进入候选池，趋势关键词则生成下一轮定向搜索词。BetaList 使用首页明确分组的 **Today** 和 **Yesterday** 全量列表，逐条保留产品页链接和定位，不用搜索结果代替。
   - **需求候选**：Reddit、G2、AppSumo 评论里的具体抱怨、手工绕行和“希望有某工具”的场景；每个重复问题直接形成一个问题型候选。
   Hacker News、X、Indie Hackers 用来补充早期扩散、产品定位和创始人叙述。
3. 不要把榜单、雷达或需求源降级成“趋势层判读”。例如 Product Hunt Top 的某款产品应该先作为“产品候选”进入清单，再结合评论、国内替代和本地化切法决定是否保留。
4. 为了发现 idea，不要因页面日期缺失、产品较早发布或只有单一来源就丢弃条目。保留它们，并将“新鲜度/热度”轻量标注为近期讨论、持续需求、旧产品新切法或仅作灵感。
5. 先运行一次宽覆盖采集。按来源注册表中的路由优先级获取条目：**专用 CLI 的结构化输出**（如 OpenCLI 的 Product Hunt、GitHub Trending）→ 官方 API / 原生 CLI → 公开榜单或 RSS → 公开搜索。OpenCLI 的浏览器型命令只用于需要实时榜单或登录态的来源；若 Chrome Bridge 不可用，使用注册表给出的非浏览器回退，不让单一浏览器故障拖慢整轮采集。只有某个赛道明显值得深挖时，再补一轮定向采集。将原始链接写入内部证据：

   ```sh
   ./skills/overseas-opportunity-radar/scripts/run-step.sh discover \
     --days 30 --limit 5 --sources balanced
   ```

   默认 `balanced` 追求广覆盖与低延迟；需要首页实时榜和分类榜时使用 `--sources leaderboards`。命令只写入 `.opportunity-radar/runs/*-evidence.json`，保存可追溯的原始证据；不要把它的内容直接当作面向用户的答复。
6. 读取 JSON，并用可用的 API、CLI 或公开搜索补查最有意思的条目。优先使用来源原页面、Hacker News 和 GitHub 的原生数据；但不要把“补查不全”当作不输出 idea 的理由。
7. 将候选按**同一个用户问题或产品机制**聚类，而不是按网站逐条罗列。一个单一帖子、榜单条目或趋势产品都可以变成候选 idea；明显无产品切口或无法映射到中国场景的条目再淘汰。
8. 在最终回复前，先按下方“报告归档”规则保存本次报告，再从保存的文件整理回复；每次运行都必须产生一份报告，即使结果为空或采集受限。

## 报告归档（每次运行必做）

- 报告目录固定为项目目录下的 `.opportunity-radar/reports/`；原始采集证据仍只放 `.opportunity-radar/runs/`，两者不混用。
- 文件名为 `YYYYMMDD-NN.md`：使用保存当天的本地日期，`NN` 从 `01` 起按当天已有文件递增；序号至少两位，超过 `99` 时自然扩展为三位。任何情况下都不覆盖已有报告。
- 先写一份自包含的报告正文，再调用 `scripts/save-report.py --input <draft.md>` 保存。脚本以独占创建方式分配下一个序号，避免重复命名；可用 `OPPORTUNITY_RADAR_PROJECT_DIR` 指定项目目录，或用 `OPPORTUNITY_RADAR_REPORT_DIR` 覆盖报告目录。
- 文件内容就是面向用户的报告正文：标题、机会表格和“暂不建议碰”部分；不写原始 JSON、采集日志或内部评分。最终回复中的报告正文必须与文件一致，回复只需额外附上文件链接。
- 保存后重新读取文件确认内容和链接完整，再发送最终回复。用户另行指定目录或命名格式时，以用户指定为准。

## 交付格式

用下面的表格直接给出“本次最值得看的机会”，按优先级排序：

| 优先级 | 机会 | 海外热度 / 需求证据 | 国内能怎么做 | 判断 |
|---:|---|---|---|---|

- 表格中的“需求证据”写成自然语言并嵌入 1–3 个直接链接。
- “国内能怎么做”写第一版具体工作流和首个行业，不写泛泛的“本地化”。
- “判断”使用“优先看 / 值得看 / 待验证 / 不建议”，剔除“不建议”的机会。
- 只合并同一问题的重复条目，不因篇幅或证据不足而特意减少 idea。
- 表格后仅补充“暂不建议碰”的方向。
- 除非用户要求，不输出原始采集日志、来源状态表、候选卡、评分表、验证计划或命令教程。

## 约束

- 不把单一 GitHub star、单篇帖子、搜索排名或无日期页面写成“爆火”；它们可以作为灵感来源。
- 区分“近期讨论”“持续需求”“旧产品的新本地切法”和“仅作灵感”，但不要求每一项都有完整增长数据。
- 海外产品只用于发现问题模型和本地化机会，不复制品牌、代码、界面、素材或受保护内容。
- 来源范围与适配器在 [来源注册表](references/source-registry.json) 中维护；不要在采集脚本里硬编码网站。
