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
- 全局共享人设卡、LLM 自动可见区域分层、人工调整和旧版数据兼容
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

> 健康模式仍暂时禁用。v1.0.5 会在自然语言生图和人设卡自动分层时调用 AstrBot 全局 LLM；NovelAI 生成本身不经过 LLM。

AstrBot 的 `secret` 配置只会遮罩 WebUI 显示，不会加密磁盘配置。生产环境推荐使用容器 Secret 或受限环境变量，并限制 AstrBot 配置目录的文件权限。

## 命令

### 自然语言生图

启用 AstrBot 当前对话模型的工具调用后，可以直接说：

```text
来张然老师在黑板墙讲课的图
画一幅小画嘉站在夏日海边的横图
```

LLM 会调用 `generate_novelai_image` 工具。插件优先读取事件中的原始用户消息，而不是信任外层 LLM 可能改写过的工具参数，再把全局共享的人设卡名称交给全局默认 LLM，生成 NovelAI 正面/反面 Tags、选择构图尺寸、判断 `shot` 镜头并加载存在的人设卡。即使外层 LLM 把“小然老师”改写成“偶像少女”，插件仍会从原始消息中匹配“然老师”；原文明确写了“近景、上半身、腿部、全身”等镜头时，也会覆盖 LLM 的不同判断。

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
/nai --shot closeup 然老师, sleeping at desk, side profile
```

### 画师预设

在插件配置的 `artist_presets` 列表中，每行填写 `预设名=画师Tags`：

```text
sushi=sushispin, konya_karasue, 0.9::toosaka_asagi, airfish_(lefko_d), ashima_(roro046)
soft=artist_a, 0.8::artist_b
```

`default_artist_preset` 默认是 `sushi`。留空时也会自动使用 `artist_presets` 列表中的第一项，以兼容已经保存空配置的 v1.0.3；填写 `none`、`off` 或 `关闭` 才会全局禁用默认画师串。单次生成可用 `--artist sushi` 指定，或用 `--artist none` 临时关闭。自然语言中明确说“使用 sushi 预设”时，LLM 也可以选择该预设。

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

人设卡为全局共享：任何可使用插件的用户设置后，其他用户也可以直接调用；设置同名卡会覆盖旧内容。新建卡默认交给 AstrBot 全局 LLM 自动分层。LLM 只能返回每个原始 Tag 的序号归属，插件会检查无遗漏、无重复后用原文回填，因此不会改写 `{{权重}}`、角色名或词条。

```text
/nai_card_set 小画嘉 1girl, solo, blue eyes, silver hair, long hair
/nai_card_set 小画嘉 1girl, solo, blue eyes, silver hair --neg bad hands, extra fingers
/nai_card_set "小画嘉 夏装" 1girl, summer dress, silver hair
/nai_card_set 临时卡 1girl, red hair --no-auto-layer
/nai_card_list
/nai_card_show 小画嘉
/nai_card_relayer 小画嘉
/nai_card_part_set 小画嘉 lower pleated skirt, white socks, brown shoes --neg wrong shoes
/nai 小画嘉, school uniform, classroom
/nai_card_delete 小画嘉
```

反面提示词不填写时会保存为空。包含空格的人设名需要加引号。如果全局 LLM 不可用，自动分层会明确报错；可修复 LLM 配置，或追加 `--no-auto-layer` 保存传统未分层卡。

自动分层包括：

| 分层 | 内容 | 加载镜头 |
|---|---|---|
| `core` | 角色身份及极少量通用辨识信息 | 所有镜头 |
| `face` | 头发、眼睛、眼镜、脸型和头饰 | `closeup`、`upper`、`full` |
| `upper` | 上衣、胸肩、手臂和上半身饰品 | `upper`、`full` |
| `lower` | 裙摆、腿部、袜鞋和下半身饰品 | `lower`、`full` |
| `full` | 身高、腿长、整体比例和完整服装轮廓 | 仅 `full` |

`/nai_card_part_set 人设名 分层 正面Tags [--neg 反面Tags]` 会完整覆盖该分层，其他层保持不变。`/nai_card_relayer 人设名` 可重新自动整理全部原始 Tags。

对于 V4、V4.5 和 V5，最后一条生图命令会生成独立的人物槽：

```text
主提示词：character 1, school uniform, classroom
Character 1 正面：根据 `--shot` 选择后的人物 Tags
Character 1 反面：（空或用户填写的 --neg 内容）
```

人物 Tags 不会再直接拼进场景提示词，从而减少对背景、构图和环境的污染。`--shot auto` 会从提示词识别镜头，无法判断时为兼容旧行为使用 `full`；自然语言流程会直接提供镜头类型。多个人设会建立多个 Character Prompt 并自动横向分配位置；V5 最多 22 个，V4/V4.5 最多 6 个。V3 不支持 Character Prompt，但仍会按镜头选层后行内展开。

旧版人设卡无需重新创建，仍会完整加载。建议执行 `/nai_card_relayer 人设名` 升级为镜头分层卡。

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
| `--shot` | 人设卡镜头分层 | `auto`、`closeup`、`upper`、`lower`、`full` |
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
| `/nai_card_set 名称 正面Tags [--neg 反面Tags]` | 新增人设卡并默认使用 LLM 自动分层 |
| `/nai_card_relayer 名称` | 使用 LLM 重新分层现有人设卡 |
| `/nai_card_part_set 名称 分层 正面Tags [--neg 反面Tags]` | 人工覆盖一个分层 |
| `/nai_card_list` | 列出全局共享人设卡 |
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

生成图片默认保留 24 小时后自动删除。`state.json` 保存统计、人设卡和上一次成功的文生图参数，不保存参考图片或图生图原图。旧健康模式状态可能仍保留在文件中，但 v1.0.5 不会读取或执行。

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
