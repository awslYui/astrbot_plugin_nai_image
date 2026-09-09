from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import httpx

from .models import (
    AccountInfo,
    CharacterPrompt,
    GeneratedImage,
    GenerationMode,
    GenerationRequest,
)
from .presets import is_v4_plus


class NaiAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        charge_uncertain: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.charge_uncertain = charge_uncertain


class NovelAIClient:
    """Small async client for NovelAI's image-generation service.

    The client deliberately performs no automatic generation retry. A request that
    times out after transmission may still have completed and consumed allowance.
    """

    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://image.novelai.net",
        timeout_seconds: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = access_token.strip()
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 20.0)),
            transport=transport,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/zip, image/png, image/webp, application/json",
                "User-Agent": "astrbot-plugin-nai-image/1.0.2",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def test_connection(self) -> bool:
        if not self._token:
            return False
        try:
            response = await self._client.get(f"{self._base_url}/user/information")
        except httpx.HTTPError as exc:
            raise NaiAPIError(f"无法连接 NovelAI：{type(exc).__name__}") from exc
        if response.status_code == 401:
            return False
        if response.status_code >= 400:
            raise self._http_error(response)
        return True

    async def get_account_info(self) -> AccountInfo:
        try:
            response = await self._client.get(f"{self._base_url}/user/data")
        except httpx.HTTPError as exc:
            raise NaiAPIError(f"账户信息请求失败：{type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise self._http_error(response)
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise NaiAPIError("NovelAI 返回了无法解析的账户信息") from exc

        subscription = payload.get("subscription") or {}
        tier = _optional_int(subscription.get("tier"))
        tier_name = {0: "Paper", 1: "Tablet", 2: "Scroll", 3: "Opus"}.get(
            tier, "未知"
        )
        active_value = subscription.get("active")
        active = active_value if isinstance(active_value, bool) else None
        anlas = _parse_anlas(subscription.get("trainingStepsLeft"))

        usage = subscription.get("usage") or {}
        percent = _optional_int(usage.get("percent"))
        if usage.get("isNegative") is True:
            percent = 0
        return AccountInfo(
            tier=tier,
            tier_name=tier_name,
            active=active,
            anlas=anlas,
            v5_usage_percent=max(percent, 0) if percent is not None else None,
            v5_next_percent_seconds=_nonnegative_optional_int(
                usage.get("timeUntilNextPercent")
            ),
        )

    async def generate(self, request: GenerationRequest) -> GeneratedImage:
        payload = build_generation_payload(request)
        try:
            response = await self._client.post(
                f"{self._base_url}/ai/generate-image", json=payload
            )
        except httpx.TimeoutException as exc:
            raise NaiAPIError(
                "生成请求超时；服务端可能仍已完成生成，为避免重复扣费不会自动重试",
                charge_uncertain=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise NaiAPIError(
                f"生成请求连接失败：{type(exc).__name__}", charge_uncertain=True
            ) from exc

        if response.status_code >= 400:
            raise self._http_error(response)
        image_data, extension = extract_first_image(response.content)
        return GeneratedImage(
            data=image_data,
            extension=extension,
            seed=request.seed,
            content_type=response.headers.get("content-type", ""),
        )

    @staticmethod
    def _http_error(response: httpx.Response) -> NaiAPIError:
        status = response.status_code
        known = {
            400: "生成参数无效或当前模型不支持该功能",
            401: "NovelAI Token 无效或已过期",
            402: "NovelAI 额度不足",
            403: "NovelAI 拒绝了当前账户的访问",
            409: "NovelAI 当前无法接受该生成任务",
            429: "NovelAI 请求过于频繁，请稍后再试",
            500: "NovelAI 服务内部错误",
            502: "NovelAI 网关暂时不可用",
            503: "NovelAI 服务暂时不可用",
        }
        message = known.get(status, f"NovelAI 请求失败（HTTP {status}）")
        request_id = response.headers.get("x-request-id")
        if request_id:
            message += f"，请求编号：{request_id}"
        return NaiAPIError(message, status_code=status)


def build_generation_payload(request: GenerationRequest) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "params_version": 3,
        "width": request.width,
        "height": request.height,
        "scale": request.scale,
        "sampler": request.sampler,
        "steps": request.steps,
        "seed": request.seed,
        "n_samples": 1,
        "ucPreset": 0,
        "uc_preset": 0,
        "qualityToggle": request.quality_tags,
        "sm": False,
        "sm_dyn": False,
        "dynamic_thresholding": False,
        "controlnet_strength": 1,
        "legacy": False,
        "legacy_v3_extend": False,
        "add_original_image": True,
        "cfg_rescale": 0,
        "noise_schedule": request.schedule,
        "skip_cfg_above_sigma": None,
        "negative_prompt": request.negative_prompt,
        "uc": request.negative_prompt,
    }

    if request.sampler == "k_euler_ancestral" and request.schedule != "native":
        parameters["deliberate_euler_ancestral_bug"] = False
        parameters["prefer_brownian"] = True

    if is_v4_plus(request.model):
        use_coords = len(request.character_prompts) > 1
        parameters["use_coords"] = use_coords
        parameters["characterPrompts"] = [
            {
                "prompt": item.positive,
                "uc": item.negative,
                "center": {"x": item.x, "y": item.y},
            }
            for item in request.character_prompts
        ]
        parameters["v4_prompt"] = _structured_prompt(
            request.prompt,
            request.character_prompts,
            use_coords=use_coords,
        )
        parameters["v4_negative_prompt"] = _structured_prompt(
            request.negative_prompt,
            request.character_prompts,
            negative=True,
            use_coords=use_coords,
        )

    action = "generate"
    if request.mode is GenerationMode.IMAGE_TO_IMAGE:
        if not request.source_image_b64:
            raise ValueError("图生图缺少输入图片")
        action = "img2img"
        parameters.update(
            {
                "image": request.source_image_b64,
                "strength": request.strength,
                "noise": request.noise,
                "extra_noise_seed": request.seed,
            }
        )
    elif request.mode is GenerationMode.PRECISE_REFERENCE:
        if not request.reference_image_b64:
            raise ValueError("Precise Reference 缺少参考图片")
        parameters.update(
            {
                "director_reference_images": [request.reference_image_b64],
                "director_reference_strength_values": [request.reference_strength],
                "director_reference_secondary_strength_values": [
                    round(1.0 - request.reference_fidelity, 2)
                ],
                "director_reference_information_extracted": [1.0],
                "director_reference_descriptions": [
                    _structured_prompt(request.reference_type.value)
                ],
            }
        )
    elif request.mode is GenerationMode.VIBE_TRANSFER:
        if not request.reference_image_b64:
            raise ValueError("Vibe Transfer 缺少参考图片")
        parameters.update(
            {
                "reference_image_multiple": [request.reference_image_b64],
                "reference_strength_multiple": [request.vibe_strength],
                "reference_information_extracted_multiple": [
                    request.vibe_information
                ],
            }
        )

    return {
        "input": request.prompt,
        "model": request.model,
        "action": action,
        "parameters": parameters,
    }


def _structured_prompt(
    text: str,
    characters: list[CharacterPrompt] | None = None,
    *,
    negative: bool = False,
    use_coords: bool = False,
) -> dict[str, Any]:
    char_captions = [
        {
            "char_caption": item.negative if negative else item.positive,
            "centers": [{"x": item.x, "y": item.y}],
        }
        for item in characters or []
    ]
    return {
        "caption": {"base_caption": text, "char_captions": char_captions},
        "use_coords": use_coords,
        "use_order": True,
    }


def extract_first_image(data: bytes) -> tuple[bytes, str]:
    if not data:
        raise NaiAPIError("NovelAI 返回了空响应")

    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                candidates = [
                    item
                    for item in archive.infolist()
                    if not item.is_dir()
                    and item.filename.lower().endswith(
                        (".png", ".webp", ".jpg", ".jpeg")
                    )
                ]
                if not candidates:
                    raise NaiAPIError("NovelAI 压缩包中没有图片")
                first = candidates[0]
                if first.file_size > 30 * 1024 * 1024:
                    raise NaiAPIError("NovelAI 返回的图片异常过大")
                image = archive.read(first)
                return image, _detect_extension(image)
        except zipfile.BadZipFile as exc:
            raise NaiAPIError("NovelAI 返回的压缩包已损坏") from exc

    return data, _detect_extension(data)


def _detect_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    raise NaiAPIError("NovelAI 返回的内容不是受支持的图片格式")


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _nonnegative_optional_int(value: Any) -> int | None:
    parsed = _optional_int(value)
    return max(parsed, 0) if parsed is not None else None


def _parse_anlas(value: Any) -> int | None:
    if isinstance(value, dict):
        fixed = _optional_int(value.get("fixedTrainingStepsLeft")) or 0
        purchased = _optional_int(value.get("purchasedTrainingSteps")) or 0
        return fixed + purchased
    return _optional_int(value)
