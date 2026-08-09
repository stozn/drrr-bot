"""模块注册中心：加载模块、注册命令/事件处理器、消息分发。"""

from __future__ import annotations

import importlib
import logging
import re
import sys
import traceback
from typing import TYPE_CHECKING, Any

from core.logger import get_logger
from models import Message, MessageType

if TYPE_CHECKING:
    from modules.base import Module


def filename_to_classname(filename: str) -> str:
    """把模块文件名转换为类名：qing_shu -> QingShu，music -> Music。"""
    parts = filename.split("_")
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


class ModuleRegistry:
    """模块注册中心。

    职责：
    1. 从 ``modules`` 包动态加载模块类并实例化
    2. 收集模块内通过装饰器注册的命令 / 事件处理器
    3. 将收到的消息分发给匹配的处理器
    """

    def __init__(
        self,
        bot: Any,
        *,
        modules_pkg: str = "modules",
        logger: logging.Logger | None = None,
    ) -> None:
        self.bot = bot
        self.modules_pkg = modules_pkg
        self.logger = logger or get_logger("registry")

        self._modules: dict[str, Module] = {}
        # 命令处理器：正则 -> (模块实例, 方法)
        self._commands: list[tuple[re.Pattern[str], Any, Any]] = []
        # 事件处理器：MessageType -> [(模块实例, 方法)]
        self._event_handlers: dict[MessageType, list[tuple[Any, Any]]] = {}

    # ------------------------------------------------------------------
    # 模块加载
    # ------------------------------------------------------------------
    def load(self, names: list[str]) -> None:
        """加载一组模块。"""
        for name in names:
            self.load_one(name)

    def load_one(self, name: str) -> bool:
        """加载单个模块。

        Args:
            name: 模块文件名（如 ``room_admin``）。

        Returns:
            是否加载成功。
        """
        if name in self._modules:
            self.logger.error("模块【%s】已加载", name)
            return False
        try:
            mod = importlib.import_module(f"{self.modules_pkg}.{name}")
        except ModuleNotFoundError:
            self.logger.error("未找到模块【%s】（请确认文件存在、依赖已安装）", name)
            return False
        except Exception:
            self.logger.error("模块【%s】导入失败:\n%s", name, traceback.format_exc())
            return False

        classname = filename_to_classname(name)
        cls = getattr(mod, classname, None)
        if cls is None:
            self.logger.error("模块 %s 必须有一个顶级类 %s", name, classname)
            return False

        from modules.base import Module as BaseModule

        if not isinstance(cls, type) or not issubclass(cls, BaseModule):
            self.logger.error("模块 %s 的顶级类必须继承自 modules.base.Module", name)
            return False

        try:
            instance = cls(self.bot)
        except Exception:
            self.logger.error("模块【%s】实例化失败:\n%s", name, traceback.format_exc())
            return False

        self._modules[name] = instance
        self._register_module(instance, name)
        self.logger.info("加载模块【%s】", name)
        return True

    def unload(self, name: str) -> None:
        """卸载模块。"""
        mod = self._modules.pop(name, None)
        if mod is None:
            self.logger.error("模块【%s】未加载", name)
            return
        try:
            mod.unload()
        except Exception:
            self.logger.debug(traceback.format_exc())
        # 清理命令与事件处理器
        self._commands = [
            (pat, m, fn) for pat, m, fn in self._commands if m is not mod
        ]
        for handlers in self._event_handlers.values():
            handlers[:] = [(m, fn) for m, fn in handlers if m is not mod]
        # 从 sys.modules 移除，允许热重载
        for key in list(sys.modules):
            if key == f"{self.modules_pkg}.{name}" or key.startswith(
                f"{self.modules_pkg}.{name}."
            ):
                del sys.modules[key]
        self.logger.info("卸载模块【%s】", name)

    def _register_module(self, instance: "Module", name: str) -> None:
        """扫描模块实例，注册装饰器标记的处理器。"""
        from modules.base import is_handler

        for attr in dir(instance):
            fn = getattr(instance, attr)
            if not callable(fn) or not is_handler(fn):
                continue

            # 命令处理器
            pattern = getattr(fn, "_drrr_cmd", None)
            if pattern is not None:
                self._commands.append((pattern, instance, fn))
                self.logger.debug("  [%s] 命令: %s", name, pattern.pattern)
                continue

            # 事件处理器
            event = getattr(fn, "_drrr_event", None)
            if event is not None:
                self._event_handlers.setdefault(event, []).append((instance, fn))
                self.logger.debug("  [%s] 事件: %s", name, event.value)

    # ------------------------------------------------------------------
    # 分发
    # ------------------------------------------------------------------
    async def dispatch(self, msg: Message) -> None:
        """将一条消息分发给匹配的命令与事件处理器。

        事件处理器总是执行；命令处理器在消息为
        ``message / me / dm / url / dm_url`` 且内容匹配时才执行。
        """
        # 1. 事件处理器（join/leave/new_host 等）
        for event_type, handlers in self._event_handlers.items():
            if msg.type != event_type:
                continue
            for instance, fn in handlers:
                await self._safe_call(instance, fn, msg)

        # 2. 兼容旧版 /切换 模块开关命令
        content = msg.content or ""
        if content.startswith("/切换"):
            for instance in self._modules.values():
                switch = getattr(instance, "switch", None)
                if callable(switch):
                    await self._safe_call(instance, switch, msg)
            return

        # 3. 命令处理器
        if msg.type not in (
            MessageType.MESSAGE,
            MessageType.ME,
            MessageType.DM,
            MessageType.URL,
            MessageType.DM_URL,
        ):
            return
        for pattern, instance, fn in self._commands:
            try:
                if pattern.search(content):
                    # admin 装饰器兜底拦截：标记为 admin 的命令，
                    # 若模块未自行校验管理员则在此强制校验。
                    if getattr(fn, "_drrr_admin", False):
                        check = getattr(instance, "require_admin", None)
                        if check is not None and not check(msg):
                            return
                    await self._safe_call(instance, fn, msg)
            except re.error:
                self.logger.error("命令正则非法: %r", pattern.pattern)

    async def _safe_call(self, instance: "Module", fn: Any, msg: Message) -> None:
        """调用处理器，捕获异常避免拖垮整个分发链路。"""
        try:
            result = fn(msg)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            self.logger.error(
                "模块【%s】处理器执行失败:\n%s",
                instance.__class__.__name__,
                traceback.format_exc(),
            )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def loaded_modules(self) -> list[str]:
        return list(self._modules.keys())
