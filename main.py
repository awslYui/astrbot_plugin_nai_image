from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star, register

from .character_cards import expand_character_cards, validate_card
from .health_review import HealthPromptReviewer, HealthReviewError
from .image_utils import normalize_image_base64
from .models import GenerationMode, GenerationRequest
from .nai_client import NaiAPIError, NovelAIClient
from .presets import model_alias, random_seed
from .queue_manager import GenerationQueue
from .request_parser import parse_generation_command
from .storage import StateStore

PLUGIN_NAME = "astrbot_plugin_nai_image"
VERSION = "1.0.1"


@register(
    "astrbot_plugin_nai_image",
    "awslYui",
    "NovelAI V5/V4.5 文生图、图生图与参考图生成",
    VERSION,
)
class NovelAIImagePlugin(Star):
    def __init__(self, context: Context, config: Any = None) -> None:
        super().__init__(context)
        self.config: dict[str, Any] = dict(config or {})
        self._token = (
            os.environ.get("NOVELAI_ACCESS_TOKEN")
            or str(self.config.get("access_token", ""))
        ).strip()
        self._client: NovelAIClient | None = None
        if self._token:
            self._client = NovelAIClient(
                self._token,
                base_url=str(
                    self.config.get("api_base_url", "https://image.novelai.net")
                ),
                timeout_seconds=float(self.config.get("request_timeout", 180)),
            )

        self._queue = GenerationQueue(
            concurrency=int(self.config.get("concurrency", 1)),
            max_size=int(self.config.get("max_queue_size", 20)),
        )
        data_dir = Path("data") / "plugin_data" / PLUGIN_NAME
        self._store = StateStore(data_dir)
        self._health_reviewer = HealthPromptReviewer(context, self.config)
        self._last_started: dict[str, float] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        try:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._cleanup_loop())
        except RuntimeError:
            pass
        logger.info("[NAI生图] v%s 已加载", VERSION)

    async def terminate(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.close()
        await self._health_reviewer.close()
        logger.info("[NAI生图] 插件已停止")

    @filter.command("nai")
    async def nai(self, event: AstrMessageEvent):
        """NovelAI 文生图。用法：/nai <提示词>"""
        async for result in self._parse_and_run(
            event, "nai", GenerationMode.TEXT_TO_IMAGE
        ):
            yield result

    @filter.command("nai_i2i")
    async def nai_i2i(self, event: AstrMessageEvent):
        """NovelAI 图生图。发送图片并输入：/nai_i2i <提示词>"""
        async for result in self._parse_and_run(
            event, "nai_i2i", GenerationMode.IMAGE_TO_IMAGE, needs_image=True
        ):
            yield result

    @filter.command("nai_ref")
    async def nai_ref(self, event: AstrMessageEvent):
        """使用 Precise Reference 生成图片。"""
        async for result in self._parse_and_run(
            event,
            "nai_ref",
            GenerationMode.PRECISE_REFERENCE,
            needs_image=True,
        ):
            yield result

    @filter.command("nai_vibe")
    async def nai_vibe(self, event: AstrMessageEvent):
        """使用 Vibe Transfer 生成图片。"""
        async for result in self._parse_and_run(
            event,
            "nai_vibe",
            GenerationMode.VIBE_TRANSFER,
            needs_image=True,
        ):
            yield result

    @filter.command("nai_again")
    async def nai_again(self, event: AstrMessageEvent):
        """使用上一次成功的文生图参数和新 Seed 再生成一次。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        user_id = str(event.get_sender_id())
        request = await self._store.get_last_request(user_id)
        if not request:
            yield event.plain_result("❌ 没有可以重复的文生图记录")
            return
        request.seed = random_seed()
        async for result in self._run_generation(event, request, []):
            yield result

    @filter.command("nai_status")
    async def nai_status(self, event: AstrMessageEvent):
        """查看自己的生成任务状态。"""
        user_id = str(event.get_sender_id())
        state, position = await self._queue.status(user_id)
        if state == "running":
            text = "🎨 你的图片正在生成"
        elif state == "queued":
            text = f"⏳ 你的任务正在排队，当前位置：{position}"
        else:
            text = "ℹ️ 你当前没有生成任务"
        yield event.plain_result(text)

    @filter.command("nai_cancel")
    async def nai_cancel(self, event: AstrMessageEvent):
        """取消尚未开始的生成任务。"""
        user_id = str(event.get_sender_id())
        result = await self._queue.cancel(user_id)
        if result == "cancelled":
            text = "✅ 已取消排队任务"
        elif result == "running":
            text = "⚠️ 请求已经发送到 NovelAI，不能安全取消"
        else:
            text = "ℹ️ 没有可以取消的排队任务"
        yield event.plain_result(text)

    @filter.command("nai_account")
    async def nai_account(self, event: AstrMessageEvent):
        """查看 NovelAI 订阅、Anlas 和 V5 用量。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        if not self._client:
            yield event.plain_result(self._missing_token_message())
            return
        try:
            info = await self._client.get_account_info()
        except NaiAPIError as exc:
            yield event.plain_result(f"❌ {exc}")
            return
        lines = [f"NovelAI 订阅：{info.tier_name}"]
        if info.active is not None:
            lines.append(f"订阅状态：{'有效' if info.active else '无效'}")
        if info.anlas is not None:
            lines.append(f"Anlas：{info.anlas}")
        if info.v5_usage_percent is not None:
            lines.append(f"V5 免费用量：{info.v5_usage_percent}%")
        if info.v5_next_percent_seconds is not None:
            lines.append(
                "下一档恢复约："
                + self._format_duration(info.v5_next_percent_seconds)
            )
        yield event.plain_result("\n".join(lines))

    @filter.command("nai_help")
    async def nai_help(self, event: AstrMessageEvent):
        """显示 NAI 生图插件帮助。"""
        yield event.plain_result(self._help_text())

    @filter.command("nai_health")
    async def nai_health(self, event: AstrMessageEvent):
        """开启、关闭或查看个人健康模式。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        user_id = str(event.get_sender_id())
        action = self._command_body(event.message_str or "", "nai_health").lower()
        default = bool(self.config.get("health_mode_default", False))
        if action in {"on", "开启", "开"}:
            await self._store.set_health_mode(user_id, True)
            yield event.plain_result("✅ 健康模式已开启，生成前会使用 LLM 删除不健康 Tags")
        elif action in {"off", "关闭", "关"}:
            await self._store.set_health_mode(user_id, False)
            yield event.plain_result("✅ 健康模式已关闭")
        elif action in {"", "status", "状态"}:
            enabled = await self._store.get_health_mode(user_id, default=default)
            source = (
                "自定义 LLM"
                if str(self.config.get("health_llm_api_key", "")).strip()
                else "AstrBot 全局 LLM"
            )
            yield event.plain_result(
                f"健康模式：{'开启' if enabled else '关闭'}\n审查模型来源：{source}"
            )
        else:
            yield event.plain_result("❌ 用法：/nai_health on|off|status")

    @filter.command("nai_card_set")
    async def nai_card_set(self, event: AstrMessageEvent):
        """新增或覆盖个人的人设卡。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        body = self._command_body(event.message_str or "", "nai_card_set")
        name, separator, tags = body.partition("|")
        if not separator:
            yield event.plain_result("❌ 用法：/nai_card_set 人设名 | tag1, tag2, tag3")
            return
        try:
            name, tags = validate_card(
                name,
                tags,
                max_tags_length=int(self.config.get("character_card_max_tags_length", 2000)),
            )
            created = await self._store.set_character_card(
                str(event.get_sender_id()),
                name,
                tags,
                max_cards=int(self.config.get("character_card_limit", 50)),
            )
        except ValueError as exc:
            yield event.plain_result(f"❌ {exc}")
            return
        yield event.plain_result(
            f"✅ 已{'新增' if created else '更新'}人设卡：{name}\n"
            "以后在生图提示词中写入该名称即可自动展开。"
        )

    @filter.command("nai_card_list")
    async def nai_card_list(self, event: AstrMessageEvent):
        """列出个人的人设卡。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        cards = await self._store.get_character_cards(str(event.get_sender_id()))
        if not cards:
            yield event.plain_result("ℹ️ 你还没有人设卡")
            return
        names = "\n".join(f"- {name}" for name in sorted(cards))
        yield event.plain_result(f"你的人设卡（{len(cards)}）：\n{names}")

    @filter.command("nai_card_show")
    async def nai_card_show(self, event: AstrMessageEvent):
        """查看个人的人设卡内容。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        name = self._command_body(event.message_str or "", "nai_card_show")
        cards = await self._store.get_character_cards(str(event.get_sender_id()))
        if not name or name not in cards:
            yield event.plain_result("❌ 未找到该人设卡，用 /nai_card_list 查看名称")
            return
        yield event.plain_result(f"人设卡：{name}\n{cards[name]}")

    @filter.command("nai_card_delete")
    async def nai_card_delete(self, event: AstrMessageEvent):
        """删除个人的人设卡。"""
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        name = self._command_body(event.message_str or "", "nai_card_delete")
        deleted = await self._store.delete_character_card(
            str(event.get_sender_id()), name
        )
        yield event.plain_result(
            f"✅ 已删除人设卡：{name}"
            if deleted
            else "❌ 未找到该人设卡，用 /nai_card_list 查看名称"
        )

    @filter.command("nai_test")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def nai_test(self, event: AstrMessageEvent):
        """测试 NovelAI Token 和网络连接（管理员）。"""
        if not self._client:
            yield event.plain_result(self._missing_token_message())
            return
        try:
            valid = await self._client.test_connection()
        except NaiAPIError as exc:
            yield event.plain_result(f"❌ {exc}")
            return
        yield event.plain_result(
            "✅ NovelAI 连接正常" if valid else "❌ NovelAI Token 无效或已过期"
        )

    @filter.command("nai_stats")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def nai_stats(self, event: AstrMessageEvent):
        """查看插件生成统计（管理员）。"""
        stats = await self._store.statistics()
        yield event.plain_result(
            "NAI 生图统计\n"
            f"已提交：{stats.get('attempted', 0)}\n"
            f"成功：{stats.get('succeeded', 0)}\n"
            f"失败：{stats.get('failed', 0)}"
        )

    async def _parse_and_run(
        self,
        event: AstrMessageEvent,
        command_name: str,
        mode: GenerationMode,
        *,
        needs_image: bool = False,
    ) -> AsyncIterator[Any]:
        denied = self._permission_error(event)
        if denied:
            yield event.plain_result(denied)
            return
        try:
            parsed = parse_generation_command(
                event.message_str or "",
                command_name=command_name,
                config=self.config,
                mode=mode,
            )
            await self._prepare_prompt(event, parsed.request, parsed.warnings)
            self._apply_content_rules(parsed.request)
            if needs_image:
                image_b64 = await self._get_message_image_b64(event)
                if not image_b64:
                    raise ValueError("请在同一条消息中附带一张图片")
                normalized = await asyncio.to_thread(normalize_image_base64, image_b64)
                if mode is GenerationMode.IMAGE_TO_IMAGE:
                    parsed.request.source_image_b64 = normalized
                else:
                    parsed.request.reference_image_b64 = normalized
        except ValueError as exc:
            yield event.plain_result(f"❌ {exc}\n输入 /nai_help 查看用法")
            return

        async for result in self._run_generation(
            event, parsed.request, parsed.warnings
        ):
            yield result

    async def _run_generation(
        self,
        event: AstrMessageEvent,
        request: GenerationRequest,
        warnings: list[str],
    ) -> AsyncIterator[Any]:
        if not self._client:
            yield event.plain_result(self._missing_token_message())
            return

        user_id = str(event.get_sender_id())
        limit_error = await self._limit_error(user_id)
        if limit_error:
            yield event.plain_result(limit_error)
            return
        try:
            job, position = await self._queue.register(user_id)
        except ValueError as exc:
            yield event.plain_result(f"❌ {exc}")
            return

        if position > 1:
            yield event.plain_result(f"⏳ 已加入队列，当前位置：{position}")
        else:
            yield event.plain_result("🎨 正在生成，请稍候……")
        if warnings:
            yield event.plain_result("⚠️ " + "；".join(warnings))

        started = await self._queue.wait_turn(job)
        if not started:
            yield event.plain_result("ℹ️ 任务已取消")
            return

        await self._store.mark_attempt(user_id)
        self._last_started[user_id] = time.monotonic()
        success = False
        try:
            generated = await self._client.generate(request)
            output_path = await self._store.write_image(
                user_id, generated.data, generated.extension
            )
            success = True
            await self._store.mark_result(user_id, request, success=True)
            summary = (
                f"✅ {model_alias(request.model)} | "
                f"{request.width}×{request.height} | Seed {request.seed}"
            )
            yield event.chain_result(
                [Plain(summary), Image.fromFileSystem(str(output_path))]
            )
        except (NaiAPIError, ValueError) as exc:
            await self._store.mark_result(user_id, request, success=False)
            suffix = "\n请求结果状态未知，请先检查账户记录再决定是否重试。" if (
                isinstance(exc, NaiAPIError) and exc.charge_uncertain
            ) else ""
            yield event.plain_result(f"❌ {exc}{suffix}")
        except Exception as exc:
            await self._store.mark_result(user_id, request, success=False)
            logger.exception("[NAI生图] 未处理异常：%s", type(exc).__name__)
            yield event.plain_result("❌ 生成失败，请管理员查看 AstrBot 日志")
        finally:
            await self._queue.finish(job)
            if not success:
                logger.warning(
                    "[NAI生图] 生成未成功，用户=%s，模型=%s，Seed=%s",
                    user_id,
                    request.model,
                    request.seed,
                )

    def _permission_error(self, event: AstrMessageEvent) -> str | None:
        user_id = str(event.get_sender_id())
        owners = self._string_set(self.config.get("owner_ids", []))
        if bool(self.config.get("owner_only", True)):
            if not owners:
                return "❌ 插件尚未配置 owner_ids，请先在 WebUI 填写主人 QQ 号"
            if user_id not in owners:
                return "❌ 当前插件仅限主人使用"
            return None

        if user_id in owners or user_id in self._string_set(
            self.config.get("allowed_user_ids", [])
        ):
            return None
        group_id = self._group_id(event)
        if group_id and group_id in self._string_set(
            self.config.get("allowed_group_ids", [])
        ):
            return None
        return "❌ 你不在 NAI 生图白名单中"

    async def _limit_error(self, user_id: str) -> str | None:
        owners = self._string_set(self.config.get("owner_ids", []))
        bypass = bool(self.config.get("owner_bypass_limits", False))
        if not (bypass and user_id in owners):
            daily_limit = max(1, int(self.config.get("daily_user_limit", 50)))
            attempts = await self._store.daily_attempts(user_id)
            if attempts >= daily_limit:
                return f"❌ 今日生成次数已达到上限（{daily_limit} 次）"
            cooldown = max(0, int(self.config.get("user_cooldown", 20)))
            elapsed = time.monotonic() - self._last_started.get(user_id, 0.0)
            if elapsed < cooldown:
                return f"⏳ 请等待 {int(cooldown - elapsed) + 1} 秒后再试"
        return None

    def _apply_content_rules(self, request: GenerationRequest) -> None:
        if bool(self.config.get("curated_only", False)) and "curated" not in request.model:
            raise ValueError("管理员已启用 Curated-only 模式")
        blocked_terms = [
            str(term).strip().lower()
            for term in self.config.get("blocked_terms", [])
            if str(term).strip()
        ]
        combined = f"{request.prompt}\n{request.negative_prompt}".lower()
        hit = next((term for term in blocked_terms if term in combined), None)
        if hit:
            raise ValueError("提示词包含管理员禁用的内容")

    async def _prepare_prompt(
        self,
        event: AstrMessageEvent,
        request: GenerationRequest,
        warnings: list[str],
    ) -> None:
        user_id = str(event.get_sender_id())
        cards = await self._store.get_character_cards(user_id)
        expansion = expand_character_cards(request.prompt, cards)
        request.prompt = expansion.prompt
        if expansion.matched_names:
            warnings.append("已展开人设卡：" + "、".join(expansion.matched_names))

        max_length = int(self.config.get("max_prompt_length", 6000))
        if len(request.prompt) > max_length:
            raise ValueError(f"人设卡展开后的提示词不能超过 {max_length} 个字符")

        enabled = await self._store.get_health_mode(
            user_id, default=bool(self.config.get("health_mode_default", False))
        )
        if not enabled:
            return
        try:
            review = await self._health_reviewer.review(request.prompt, event)
        except HealthReviewError as exc:
            if bool(self.config.get("health_fail_closed", True)):
                raise ValueError(f"健康审查失败：{exc}") from exc
            warnings.append(f"健康审查不可用，已按原提示词继续：{exc}")
            return
        request.prompt = review.prompt
        if review.removed_segments:
            warnings.append(
                f"健康模式已删除 {len(review.removed_segments)} 个不健康提示词片段"
            )

    @staticmethod
    async def _get_message_image_b64(event: AstrMessageEvent) -> str | None:
        message = getattr(event.message_obj, "message", None) or []
        for component in message:
            if isinstance(component, Image):
                return await component.convert_to_base64()
        return None

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                retention = int(self.config.get("output_retention_hours", 24))
                removed = await self._store.cleanup_outputs(retention)
                if removed:
                    logger.info("[NAI生图] 已清理 %s 个过期图片文件", removed)
            except Exception:
                logger.exception("[NAI生图] 清理输出文件失败")
            await asyncio.sleep(3600)

    @staticmethod
    def _string_set(value: Any) -> set[str]:
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",")]
        if not isinstance(value, (list, tuple, set)):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}

    @staticmethod
    def _group_id(event: AstrMessageEvent) -> str | None:
        group_id = getattr(event.message_obj, "group_id", None)
        return str(group_id) if group_id else None

    @staticmethod
    def _command_body(text: str, command_name: str) -> str:
        stripped = text.strip()
        for prefix in (f"/{command_name}", command_name):
            if stripped.lower().startswith(prefix.lower()):
                return stripped[len(prefix) :].strip()
        return stripped

    @staticmethod
    def _format_duration(seconds: int) -> str:
        minutes, second = divmod(max(0, seconds), 60)
        hours, minute = divmod(minutes, 60)
        if hours:
            return f"{hours}小时{minute}分钟"
        if minute:
            return f"{minute}分钟{second}秒"
        return f"{second}秒"

    @staticmethod
    def _missing_token_message() -> str:
        return (
            "❌ 尚未配置 NovelAI Token。请在 AstrBot WebUI 中填写，"
            "或设置 NOVELAI_ACCESS_TOKEN 环境变量；不要把 Token 发到聊天中。"
        )

    @staticmethod
    def _help_text() -> str:
        return (
            "NAI 生图插件 v1.0.1\n\n"
            "文生图：/nai <提示词>\n"
            "图生图：图片 + /nai_i2i <提示词>\n"
            "精准参考：图片 + /nai_ref <提示词>\n"
            "画风迁移：图片 + /nai_vibe <提示词>\n\n"
            "常用参数：\n"
            "--model v5c|v5f|v45c|v45f|v4c|v4f|v3\n"
            "--size square|portrait|landscape|832x1216\n"
            "--seed 123  --steps 28  --scale 5\n"
            "--neg \"负面提示词\"  --no-quality\n"
            "图生图：--strength 0.6 --noise 0\n"
            "精准参考：--type character|style|both --strength 1 --fidelity 0\n"
            "画风迁移：--strength 0.6 --info 1\n\n"
            "人设卡：/nai_card_set 名称 | tags\n"
            "/nai_card_list /nai_card_show /nai_card_delete\n"
            "健康模式：/nai_health on|off|status\n\n"
            "其他：/nai_again /nai_status /nai_cancel /nai_account\n"
            "管理：/nai_test /nai_stats"
        )
