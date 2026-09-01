# 本地 CRM 数据契约

本地 SQLite 数据库是多步骤项目的默认稳定源。它不依赖 Notion 或网络，可用于去重、恢复、校验和 CSV 导出。

## 常用命令

从 skill 目录执行时使用相对脚本路径；从其他目录执行时解析 skill 的绝对路径。

```bash
python3 scripts/wy_crm.py init --db .wy/wy.db --project-name "Solar NG" --product "solar street lights" --countries "Nigeria"
python3 scripts/wy_crm.py set-project --db .wy/wy.db --json-file project.json
python3 scripts/wy_crm.py upsert-company --db .wy/wy.db --json-file company.json
python3 scripts/wy_crm.py upsert-contact --db .wy/wy.db --json-file contact.json
python3 scripts/wy_crm.py upsert-competitor --db .wy/wy.db --json-file competitor.json
python3 scripts/wy_crm.py upsert-social --db .wy/wy.db --json-file social.json
python3 scripts/wy_crm.py upsert-outreach --db .wy/wy.db --json-file outreach.json
python3 scripts/wy_crm.py upsert-activation --db .wy/wy.db --json-file activation.json
python3 scripts/wy_crm.py activation-report --db .wy/wy.db --as-of 2026-09-10
python3 scripts/wy_crm.py upsert-campaign --db .wy/wy.db --json-file campaign.json
python3 scripts/wy_crm.py add-evidence --db .wy/wy.db --json-file evidence.json
python3 scripts/wy_crm.py status --db .wy/wy.db
python3 scripts/wy_crm.py validate --db .wy/wy.db
python3 scripts/wy_crm.py export --db .wy/wy.db --out-dir .wy/export
```

命令输出 JSON，便于继续处理。`upsert-*` 和 `add-evidence` 的 JSON 文件必须是单个对象；批量数据逐条调用，便于在每条后检查错误。

可从 `assets/templates/` 复制对应 JSON 骨架到项目目录再填写。模板只含虚构数据；不得直接覆盖 skill 目录中的原始模板。脚本会在连接数据库前检查命令行输入，并在读取 JSON 后、业务校验前递归检查对象；安全拒绝固定返回通用错误，不回显原始内容。

## 项目对象

```json
{
  "project_name": "Solar NG",
  "product": "solar street lights",
  "countries": ["Nigeria"],
  "customer_types": ["distributor", "EPC contractor"],
  "exclusions": ["consumer", "marketplace-only seller"],
  "stage": "search",
  "qualify_threshold": 80,
  "notes": "Optional"
}
```

`stage` 取值：`prepare`、`search`、`contacts`、`contact_details`、`research`、`outreach`、`export`。

## 公司对象

```json
{
  "name": "Example Energy Ltd",
  "website": "https://www.example.com/about",
  "country": "Nigeria",
  "customer_type": "EPC contractor",
  "fit_score": 86,
  "fit_status": "qualified",
  "score_breakdown": {
    "product_relevance": 27,
    "customer_role": 18,
    "geography": 10,
    "commercial_readiness": 12,
    "recent_activity": 10,
    "evidence_strength": 9
  },
  "status": "researched",
  "summary": "Evidence-based summary",
  "risks": ["No recent project list"],
  "unknowns": ["Annual purchasing volume"],
  "last_researched_at": "2026-08-31"
}
```

`fit_status` 取值：`qualified`、`review`、`rejected`。`status` 取值：`new`、`researched`、`draft_ready`、`contacted`、`replied`、`disqualified`。脚本按官网规范化域名 upsert。

## 联系人对象

```json
{
  "company_domain": "example.com",
  "name": "Ada Example",
  "title": "Head of Procurement",
  "role_rank": 1,
  "profile_url": "https://example.com/team/ada",
  "work_email": "ada@example.com",
  "email_status": "confirmed_on_source",
  "work_phone": "+234...",
  "phone_status": "confirmed_on_source",
  "notes": "Role confirmed on company team page"
}
```

联系人按公司、姓名和职位 upsert。没有姓名时不要用空值创建“联系人”；通用公司邮箱应作为公司证据或备注，而不是虚构联系人。

## 竞品对象

```json
{
  "name": "Benchmark Home",
  "website": "https://benchmark.example/products",
  "country": "United Kingdom",
  "market_position": "mass market",
  "product_scope": "duvet-cover sets",
  "price_position": "£20-£55 retail observed",
  "materials": ["cotton", "organic cotton", "cotton/lyocell"],
  "specifications": ["150x200 cm + 1 pillowcase", "200x200 cm + 2 pillowcases"],
  "demand_signals": ["checks, stripes and neutral solids", "local size packs"],
  "differentiation": ["certified material line", "good-better-best price ladder"],
  "last_researched_at": "2026-08-31"
}
```

竞品按规范化官网域名 upsert。潜客兼竞品可以分别存在于 `companies` 和 `competitors`，但摘要必须说明双重角色与供应冲突。

## 社媒对象

```json
{
  "entity_type": "company",
  "entity_key": "example.com",
  "platform": "instagram",
  "profile_url": "https://www.instagram.com/example",
  "verification_status": "official_linked",
  "activity_status": "not_checked",
  "audience_notes": "用于观察新品、颜色和场景图；不作为采购意向证据。",
  "content_signals": [],
  "last_checked_at": "2026-08-31"
}
```

`entity_type` 取值 `company` 或 `competitor`。`platform` 取值 `linkedin`、`facebook`、`instagram`、`tiktok`、`pinterest`、`youtube`、`x`、`whatsapp` 或 `other`。`verification_status` 取值 `official_linked`、`claimed_unverified` 或 `not_found`；`activity_status` 取值 `not_checked`、`recently_active`、`inactive` 或 `not_found`。

## 证据对象

```json
{
  "entity_type": "company",
  "entity_key": "example.com",
  "field": "products",
  "claim": "The company lists solar street lighting projects.",
  "source_url": "https://example.com/projects/solar-lighting",
  "source_title": "Solar Lighting Projects",
  "source_type": "official",
  "confidence": "high",
  "observed_at": "2026-08-31"
}
```

公司和竞品的 `entity_key` 是规范化域名；联系人键是脚本返回的联系人数字 ID。不要把搜索查询页保存为原始证据。

## 外联计划对象

```json
{
  "company_domain": "buyer.example",
  "contact_id": 1,
  "contact_label": "Alex Example | Head of Procurement",
  "mode": "first_touch",
  "channel": "email",
  "company_size": "medium",
  "route_confidence": "high",
  "status": "draft",
  "subject": "Local-size bedding set options",
  "message": "Replace with an evidence-based draft.",
  "evidence_refs": ["evidence:12", "https://buyer.example/products"],
  "cta": "Confirm whether Alex owns this category.",
  "next_action": "Human review of specifications and recipient details.",
  "due_date": "2026-09-08",
  "notes": "No message has been sent."
}
```

`mode` 取值 `first_touch`、`reengagement`、`quote` 或 `post_sale`。`channel` 取值 `email`、`linkedin`、`whatsapp`、`official_form`、`phone` 或 `other`；`company_size` 取值 `micro`、`small`、`medium`、`large` 或 `unknown`；`route_confidence` 取值 `high`、`medium`、`low` 或 `blocked`；`status` 取值 `draft`、`review_ready`、`approved`、`sent`、`replied`、`paused` 或 `closed`。

已知联系人使用脚本返回的 `contact_id`；没有个人联系人时省略它，并用 `contact_label` 说明官网采购入口、通用商务邮箱或官方表单。相同公司、模式、渠道和联系入口会 upsert。`evidence_refs` 至少包含一个证据 ID、原始 URL 或用户提供资料的清晰引用。`approved` 只是人工审核状态，不会触发发送；`sent` 和 `replied` 只用于事后记录。

`blocked` 路由只能保持 `draft` 或 `paused`。已知联系人的推测/未核验邮箱，以及未确认用于 WhatsApp 的号码，不能标为 `high` 或 `medium` 路由置信度。

## 客户激活对象

```json
{
  "company_domain": "buyer.example",
  "contact_id": 1,
  "contact_label": "Alex Example | Head of Procurement",
  "lifecycle_stage": "quoted",
  "status": "waiting",
  "priority": 1,
  "channel": "email",
  "last_outbound_at": "2026-09-01",
  "last_reply_at": "2026-08-28",
  "followup_count": 1,
  "max_followups": 3,
  "activation_after_days": 5,
  "next_due_date": "2026-09-06",
  "next_action": "Add one new specification clarification for review.",
  "notes": "No automatic message sending."
}
```

`lifecycle_stage` 取值 `new_lead`、`engaged`、`quoted`、`sampling`、`negotiation`、`customer` 或 `dormant`；`status` 取值 `active`、`waiting`、`dormant`、`paused`、`closed` 或 `opted_out`；`priority` 为 1-5，数值越小优先级越高；`channel` 与外联计划相同。

激活案例按公司和联系人/联系入口 upsert。`waiting`、`dormant` 状态必须低于最大跟进次数；已有晚于最后发出日期的回复时必须先转为 `active`、`paused` 或 `closed`；`closed` 和 `opted_out` 不得保留下一到期日。`activation-report` 只报告达到沉默阈值和到期日的待人工审核项，不发送消息。

## Campaign 规划对象

```json
{
  "name": "EU Bedding Importers - September",
  "campaign_type": "prospecting",
  "objective": "Validate category ownership and exchange target specifications.",
  "audience_segments": ["Germany | importer | procurement | qualified"],
  "target_languages": ["English", "German"],
  "status": "draft",
  "subject_variants": ["Local-size bedding set options for {company}"],
  "content_brief": "One verified observation, one supplier value and one CTA.",
  "suppression_rules": ["opted_out", "hard_bounce", "complaint", "pattern_inferred", "duplicate"],
  "success_metrics": ["delivered", "positive_reply", "meeting", "unsubscribe"],
  "planned_start": "2026-09-15",
  "notes": "Planning record only; approved does not send."
}
```

`campaign_type` 取值 `prospecting`、`reengagement`、`quote_followup` 或 `post_sale`；`status` 取值 `draft`、`review_ready`、`approved` 或 `archived`。Campaign 按规范化名称 upsert，受众、语言、主题、抑制规则和指标必须是非空字符串数组。`approved` 只记录内部审核状态，不触发发送。

## 校验与导出

`validate` 检查枚举、分项总分、合格阈值、合格记录的必要证据、联系方式状态和悬空记录。错误返回非零退出码；警告需要在交付中披露，但不一定阻止继续研究。

`export` 生成 `project.csv`、`companies.csv`、`contacts.csv`、`competitors.csv`、`social_profiles.csv`、`outreach_plans.csv`、`activation_cases.csv`、`campaign_plans.csv` 和 `evidence.csv`。需要格式化 XLSX 时，读取并使用环境中的 spreadsheet skill；需要 PDF 时使用 PDF skill，并把 CSV/数据库作为数据源。不要手工伪造 `.xlsx` 或把 CSV 改扩展名。

数据库和导出文件可能含职业联系数据。保持在用户指定工作区，不提交到公开仓库，不把凭据写入数据库。
