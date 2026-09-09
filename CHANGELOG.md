# Changelog

## 1.0.2 - 2026-09-09

- 人设卡改用 NovelAI V4+ 原生 Character Prompt，人物 Tags 不再并入场景提示词。
- 同步生成 `characterPrompts`、正面 `char_captions` 与反面 `char_captions`。
- 新人设卡指令不再需要竖线，支持可选 `--neg` 反面提示词。
- 旧版字符串人设卡自动兼容为“原 Tags + 空反面提示词”。
- V5 最多使用 22 张人设卡，V4/V4.5 最多 6 张；V3 自动行内展开。
- 按要求暂时禁用健康模式，生成过程不会调用 LLM。

## 1.0.1 - 2026-09-09

- 新增用户级健康模式，可使用 AstrBot 全局 LLM 或自定义 OpenAI 兼容接口。
- 健康审查只返回删除序号，插件确定性删除 Tags，避免审查模型改写提示词。
- 新增用户级人设卡的创建、覆盖、查看、列出、删除和提示词自动展开。
- 修复 Python 3.10 对 UTC 常量的兼容问题。

## 1.0.0 - 2026-09-09

- NovelAI V5、V4.5、V4 与 Anime V3 文生图。
- 图生图、Precise Reference 与 Vibe Transfer。
- 单用户任务保护、全局生成队列、冷却和每日限额。
- NovelAI 账户、Anlas 与 V5 用量查询。
- Token 脱敏、输入图片校验、输出自动清理。
- 对超时请求禁用自动重试，降低重复扣费风险。
