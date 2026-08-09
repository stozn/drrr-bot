"""统一日志模块。

提供格式化日志初始化，供入口程序使用。
日志格式：`2026-08-09 12:00:00 | INFO | message`
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Final

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)s | %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
ROOT_LOGGER_NAME: Final[str] = "drrr"
LOG_DIR: Final[str] = "logs"


class _SafeFormatter(logging.Formatter):
    """对日志消息做安全替换，避免 GBK/GB2312 终端无法编码的字符
    （如零宽空格 \\u200b）导致日志崩溃。"""

    _REPLACE = {
        "\u200b": "<ZWSP>",
    }

    def formatMessage(self, record: logging.LogRecord) -> str:
        # 用原始 args 完成一次格式化，再做字符替换；
        # 不得清空 record.args 后调用父类 format，否则 msg 中的
        # %s 占位符会因 args 为空触发 "not all arguments converted" 异常。
        msg = super().formatMessage(record)
        for ch, rep in self._REPLACE.items():
            msg = msg.replace(ch, rep)
        return msg


def setup_logger(
    level: int = logging.INFO,
    *,
    name: str = ROOT_LOGGER_NAME,
    stream=None,
) -> logging.Logger:
    """初始化根 logger（幂等）。

    Args:
        level: 日志级别。
        name: logger 名称，默认 ``drrr``。
        stream: 输出流，默认 ``sys.stdout``。

    Returns:
        配置好的 logger。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler（幂等）
    if any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return logger

    # Windows 控制台多为 GBK 编码，无法编码的字符（emoji 等）
    # 用 ? 替换而非抛异常，避免日志崩溃
    out = stream or sys.stdout
    try:
        out.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    handler = logging.StreamHandler(out)
    handler.setFormatter(_SafeFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
    # 禁止向上传播到根 logger，避免重复输出
    logger.propagate = False
    return logger


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """获取子 logger。

    子 logger 自动继承 ``drrr`` 根 logger 的 handler 与格式，
    可通过 ``__name__`` 区分模块来源。

    Args:
        name: logger 名称（如 ``drrr.sio``）。

    Returns:
        子 logger。
    """
    if name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


class MessageLogger:
    """聊天消息 CSV 落盘。

    与旧版行为一致：按日期写入 ``logs/YYYY年MM月DD日.csv``，
    每行格式：``HH:MM:SS,用户名,tripcode,消息``。
    消息中的换行转义为 ``\\\\n``，逗号替换为中文逗号，保证单行合法。
    """

    def __init__(self, log_dir: str = LOG_DIR) -> None:
        self.log_dir = log_dir
        self._file = None
        self._current_date = ""

    def _ensure_file(self) -> None:
        """按日期打开（或切换）当前日志文件。"""
        today = datetime.now().strftime("%Y年%m月%d日")
        if self._file is not None and today == self._current_date:
            return
        # 切换日期，关闭旧文件
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
        os.makedirs(self.log_dir, exist_ok=True)
        path = os.path.join(self.log_dir, f"{today}.csv")
        # utf-8-sig 带 BOM，Excel 可直接打开
        self._file = open(path, "a", encoding="utf-8-sig")
        self._current_date = today

    def log(self, username: str, tripcode: str, message: str) -> None:
        """写入一条消息日志。

        Args:
            username: 用户名（系统消息传「系统消息」）。
            tripcode: 用户 tripcode（无则空串）。
            message: 消息内容。
        """
        try:
            self._ensure_file()
        except OSError:
            return
        now = datetime.now().strftime("%H:%M:%S ")
        content = message.replace("\n", "\\n").replace(",", "，")
        try:
            self._file.write(f"{now},{username},{tripcode},{content}\n")
            self._file.flush()
        except OSError:
            pass

    def close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
