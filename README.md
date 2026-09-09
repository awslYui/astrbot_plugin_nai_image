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

AstrBot 的 `secret` 配置只会遮罩 WebUI 显示，不会加密磁盘配置。生产环境推荐使用容器 Secret 或受限环境变量，并限制 AstrBot 配置目录的文件权限。

## 命令

### 文生图

```text
/nai 1girl, solo, pink hair, classroom
/nai --model v5f --size landscape cinematic landscape, sunset
/nai --seed 123456 --neg "lowres, bad hands" 1girl, portrait
```

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
| `--no-quality` | 关闭自动质量标签 | 无参数值 |

其他命令：

| 命令 | 功能 |
|---|---|
| `/nai_again` | 用新 Seed 重复上次成功的文生图 |
| `/nai_status` | 查看排队状态 |
| `/nai_cancel` | 取消尚未发送到 NovelAI 的任务 |
| `/nai_account` | 查看订阅、Anlas 和 V5 用量 |
| `/nai_help` | 查看帮助 |
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

生成图片默认保留 24 小时后自动删除。`state.json` 只保存统计和上一次成功的文生图参数，不保存参考图片或图生图原图。

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

