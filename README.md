# AstrBot NovelAI 生图插件

在 AstrBot 中调用 NovelAI Diffusion，支持文生图、图生图、Precise Reference、Vibe Transfer、任务排队、限流和账户用量查询。

> 默认启用主人专用模式。请只使用自己的 NovelAI 账户，不要把 Access Token 发送给他人或粘贴到聊天消息中。

## 功能

- NovelAI Diffusion V5 Curated / Full
- NovelAI Diffusion V4.5、V4、Anime V3
- 文生图与图生图
- Precise Reference（V4.5）
- Vibe Transfer（非 V5 模型）
- 自定义尺寸、Seed、步数、Guidance、采样器和噪声计划
- 单并发安全队列、用户冷却、每日限额和排队取消
- Opus、Anlas 和 V5 用量查询
- PNG、WebP、JPEG 与 ZIP 响应解析
- 输入图片验证和过期输出清理
- 生成请求不自动重试，避免超时后重复消耗额度
- NovelAI 原生 Character Prompt 人设卡，人物 Tags 与环境提示词分离
- 用户级人设卡正面/反面 Tags、自动位置和旧版数据兼容
- 普通对话自然语言生图：自动生成 NovelAI 正面/反面 Tags 并匹配人设卡
- WebUI 可配置多个命名画师串预设，支持默认预设和按次选择

## 安装

在 AstrBot WebUI 的插件管理页面选择“从 GitHub 安装”，填入：

```text
https://github.com/awslYui/astrbot_plugin_nai_image
```

也可以放入 AstrBot 插件目录：

```bash
cd AstrBot/data/plugins
git clone https://github.com/awslYui/astrbot_plugin_nai_image.git
```

要求：

- AstrBot `>=4.16,<5`
- Python 3.10+
- 能访问 `https://image.novelai.net`
- 有效的 NovelAI 订阅和本人账户 Access Token

## 首次配置

1. 打开 AstrBot WebUI → 插件管理 → NovelAI 生图 → 配置。
2. 在 `owner_ids` 中填写自己的 QQ 号。
3. 填写本人 NovelAI Access Token，或者在 AstrBot 进程中设置环境变量：

   ```bash
   NOVELAI_ACCESS_TOKEN=你的Token
   ```

4. 保存并重载插件。
5. 发送 `/nai_test` 测试连接，再发送 `/nai_account` 查看订阅状态。

> 健康模式仍暂时禁用。v1.0.3 只在自然语言生图时调用 AstrBot 全局 LLM，将描述转换为 NovelAI Tags；`/nai` Tags 指令不会调用 LLM。

AstrBot 的 `secret` 配置只会遮罩 WebUI 显示，不会加密磁盘配置。生产环境推荐使用容器 Secret 或受限环境变量，并限制 AstrBot 配置目录的文件权限。

## 命令

### 自然语言生图

启用 AstrBot 当前对话模型的工具调用后，可以直接说：

```text
来张然老师在黑板墙讲课的图
画一幅小画嘉站在夏日海边的横图
```

LLM 会调用 `generate_novelai_image` 工具。插件优先读取事件中的原始用户消息，而不是信任外层 LLM 可能改写过的工具参数，再把当前用户可用的人设卡名称交给全局默认 LLM，生成 NovelAI 正面/反面 Tags、选择构图尺寸，并确定性校验、加载存在的人设卡。即使外层 LLM 把“小然老师”改写成“偶像少女”，插件仍会从原始消息中匹配“然老师”。人设卡 Tags 继续使用 V4+ 独立 Character Prompt，不会混入环境提示词。

也可以用显式命令走完全相同的流程：

```text
/nai_nl 来张然老师在黑板墙讲课的图
```

自然语言功能依赖 AstrBot 已配置可用的全局 LLM；不需要额外填写 LLM API Key。

### 文生图

```text
/nai 1girl, solo, pink hair, classroom
/nai --model v5f --size landscape cinematic landscape, sunset
/nai --seed 123456 --neg "lowres, bad hands" 1girl, portrait
/nai --artist sushi 1girl, classroom
```

### 画师预设

在插件配置的 `artist_presets` 列表中，每行填写 `预设名=画师Tags`：

```text
sushi=sushispin, konya_karasue, 0.9::toosaka_asagi, airfish_(lefko_d), ashima_(roro046)
soft=artist_a, 0.8::artist_b
```

`default_artist_preset` 填预设名后，每次生图默认追加该画师串；留空则不默认追加。单次生成可用 `--artist sushi` 指定，或用 `--artist none` 临时关闭默认画师串。自然语言中明确说“使用 sushi 预设”时，LLM 也可以选择该预设。

### 图生图

把图片和命令放在同一条消息中：

```text
/nai_i2i --strength 0.55 --noise 0 1girl, school uniform
```

### Precise Reference

```text
/nai_ref --type character --strength 0.9 --fidelity 0.4 1girl, outdoors
/nai_ref --type style landscape, castle
```

`--type` 支持：

- `character`：角色参考
- `style`：画风参考
- `both`：角色与画风

Precise Reference 会使用配置中的 V4.5 参考模型，并可能产生额外 Image Anlas 消耗。

### Vibe Transfer

```text
/nai_vibe --strength 0.6 --info 1 1girl, city at night
```

### 人设卡

人设卡按用户隔离保存。名称可以是中文；设置同名卡会覆盖旧内容。指令不需要竖线，第一个参数是人设名，后面是正面 Tags；反面 Tags 使用可选的 `--neg` 参数。

```text
/nai_card_set 小画嘉 1girl, solo, blue eyes, silver hair, long hair
/nai_card_set 小画嘉 1girl, solo, blue eyes, silver hair --neg bad hands, extra fingers
/nai_card_set "小画嘉 夏装" 1girl, summer dress, silver hair
/nai_card_list
/nai_card_show 小画嘉
/nai 小画嘉, school uniform, classroom
/nai_card_delete 小画嘉
```

反面提示词不填写时会保存为空。包含空格的人设名需要加引号。

对于 V4、V4.5 和 V5，最后一条生图命令会生成独立的人物槽：

```text
主提示词：character 1, school uniform, classroom
Character 1 正面：1girl, solo, blue eyes, silver hair, long hair
Character 1 反面：（空或用户填写的 --neg 内容）
```

人物 Tags 不会再直接拼进场景提示词，从而减少对背景、构图和环境的污染。多个人设会建立多个 Character Prompt 并自动横向分配位置；V5 最多 22 个，V4/V4.5 最多 6 个。V3 不支持该功能，因此会自动退回原来的行内展开方式。

旧版 v1.0.1 已保存的人设卡会自动读取为正面 Tags，反面 Tags 留空，无需重新创建。

### 健康模式

健康模式暂时禁用。无论旧配置或旧用户状态如何，本版本都不会执行 LLM 健康审查。自然语言提示词转换不属于健康审查。

### 通用参数

| 参数 | 说明 | 示例 |
|---|---|---|
| `--model` | 模型 | `v5c`、`v5f`、`v45c`、`v45f`、`v4c`、`v4f`、`v3` |
| `--size` | 尺寸 | `square`、`portrait`、`landscape`、`832x1216` |
| `--seed` | 随机种子 | `--seed 123456` |
| `--steps` | 采样步数 | `--steps 28` |
| `--scale` | Prompt Guidance | `--scale 5` |
| `--sampler` | 采样器 | `--sampler k_euler_ancestral` |
| `--schedule` | 噪声计划 | `--schedule karras` |
| `--neg` | 负面提示词 | 多词内容需要加引号 |
| `--artist` | 画师预设 | `--artist sushi`；`--artist none` 关闭默认预设 |
| `--no-quality` | 关闭自动质量标签 | 无参数值 |

其他命令：

| 命令 | 功能 |
|---|---|
| `/nai_again` | 用新 Seed 重复上次成功的文生图 |
| `/nai_nl 描述` | 用自然语言生成正反 Tags 并生图 |
| `/nai_status` | 查看排队状态 |
| `/nai_cancel` | 取消尚未发送到 NovelAI 的任务 |
| `/nai_account` | 查看订阅、Anlas 和 V5 用量 |
| `/nai_help` | 查看帮助 |
| `/nai_health` | 查看健康模式禁用状态 |
| `/nai_card_set 名称 正面Tags [--neg 反面Tags]` | 新增或覆盖个人的人设卡 |
| `/nai_card_list` | 列出个人的人设卡 |
| `/nai_card_show 名称` | 查看人设卡内容 |
| `/nai_card_delete 名称` | 删除人设卡 |
| `/nai_test` | 管理员测试连接 |
| `/nai_stats` | 管理员查看生成统计 |

## 安全与费用

- 插件固定每次生成一张图片。
- 请求开始后发生超时，插件不会自动重试，因为服务端可能已经完成生成。
- 大于约一百万像素的自定义尺寸会显示费用警告。
- V5 对 Opus 免费生成有独立用量限制；V4.5 等旧模型沿用原有免费条件。
- NovelAI 服务条款限制让第三方远程使用你的账户，因此默认 `owner_only=true`。
- QQ、Discord 等平台对生成内容可能有额外规则，部署者应自行配置 Curated-only 模式和禁用词。

## 数据

运行数据保存在：

```text
AstrBot/data/plugin_data/astrbot_plugin_nai_image/
```

生成图片默认保留 24 小时后自动删除。`state.json` 保存统计、人设卡和上一次成功的文生图参数，不保存参考图片或图生图原图。旧健康模式状态可能仍保留在文件中，但 v1.0.3 不会读取或执行。

## 开发与测试

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check .
```

自动测试不会调用 NovelAI，也不会消耗 Anlas。正式发布前应由账户本人在私聊环境执行一次真实生成测试。

## 参考

- [NovelAI Image API](https://image.novelai.net/docs/index.html)
- [NovelAI 图像模型](https://docs.novelai.net/en/image/models/)
- [NovelAI Precise Reference](https://docs.novelai.net/en/image/precisereference/)
- [AstrBot 插件开发指南](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot 消息发送](https://docs.astrbot.app/dev/star/guides/send-message.html)
- [AstrBot 插件配置](https://docs.astrbot.app/dev/star/guides/plugin-config.html)

本项目与 NovelAI、Anlatan 和 AstrBot 官方无隶属关系。

## License

MIT
