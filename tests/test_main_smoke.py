import importlib
import sys
import types

import pytest


class _Logger:
    def info(self, *_args, **_kwargs) -> None:
        pass

    def warning(self, *_args, **_kwargs) -> None:
        pass

    def exception(self, *_args, **_kwargs) -> None:
        pass


def _decorator(*_args, **_kwargs):
    def wrap(value):
        return value

    return wrap


@pytest.mark.asyncio
async def test_plugin_entrypoint_imports_and_initializes(monkeypatch, tmp_path) -> None:
    api = types.ModuleType("astrbot.api")
    api.logger = _Logger()
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = object
    event.filter = types.SimpleNamespace(
        command=_decorator,
        permission_type=_decorator,
        PermissionType=types.SimpleNamespace(ADMIN="admin"),
    )
    components = types.ModuleType("astrbot.api.message_components")
    components.Image = type(
        "Image", (), {"fromFileSystem": staticmethod(lambda path: path)}
    )
    components.Plain = type("Plain", (), {})
    star = types.ModuleType("astrbot.api.star")
    star.Context = object
    star.Star = type("Star", (), {"__init__": lambda self, context: None})
    star.register = _decorator

    monkeypatch.setitem(sys.modules, "astrbot", types.ModuleType("astrbot"))
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.api.event", event)
    monkeypatch.setitem(sys.modules, "astrbot.api.message_components", components)
    monkeypatch.setitem(sys.modules, "astrbot.api.star", star)
    monkeypatch.chdir(tmp_path)

    module = importlib.import_module("astrbot_plugin_nai_image.main")
    plugin = module.NovelAIImagePlugin(object(), {"owner_ids": ["123"]})
    try:
        assert plugin._client is None
        assert plugin._store.data_dir.exists()
    finally:
        await plugin.terminate()
