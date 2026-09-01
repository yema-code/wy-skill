# 四层渐进式披露架构

WY 1.0.0 按四个职责层组织。运行普通任务时只加载当前步骤需要的内容，不一次性读取整个目录。

```text
wy/
|-- SKILL.md                    发现层 + 入口层
|-- skill.json                 平台发现元数据
|-- agents/openai.yaml          界面元数据
|-- references/                 知识层
|-- scripts/                    执行层
`-- assets/templates/           模板层
```

## 第一层：发现层

`SKILL.md` 的 YAML frontmatter 只声明名称、判别性描述和 `metadata.version`。`skill.json` 为需要 JSON 清单的平台镜像名称、版本、标签和触发词，不包含业务规则、凭据或隐藏指令。平台可用这些字段决定是否加载 WY，不需要预先读取业务细节。

## 第二层：入口层

`SKILL.md` 正文提供能力菜单、共同边界和按需路由。它不复制各业务模式的详细步骤，也不把所有参考资料载入上下文。

## 第三层：知识层

`references/` 保存工作流、研究质量、竞品与社媒、数据契约、外联和集成规则。只读取当前任务所需文件。例如，单纯导出 CRM 时无需读取竞品或外联规则。

## 第四层：执行与模板层

`scripts/` 提供可测试的确定性 CRM 操作；`assets/templates/` 提供可复制的脱敏 JSON 输入骨架。脚本可以直接执行，模板作为输出素材使用，不作为 agent 指令自动加载。

## 维护约束

- `SKILL.md` 只负责发现、路由和共同约束，条件性细节放入单一对应 reference。
- 新增 reference 后必须从 `SKILL.md` 或另一份已路由的 reference 链接，并写明读取条件。
- 新增脚本必须有可观察行为测试；新增模板必须使用 `.example` 域名和虚构数据。
- WorkBuddy 和 SkillHub 包必须保留相同的 `SKILL.md`、`references/`、`scripts/` 与 `assets/templates/` 内容。
