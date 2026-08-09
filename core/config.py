"""类型化配置：解析 config.txt 为 dataclass。

支持字段（与 config.txt 键名一致）：

- ``name``: 用户名
- ``tc``: Tripcode
- ``avatar``: 头像名称
- ``roomID``: 房间 ID
- ``agent``: User-Agent
- ``mods``: 加载的模块名列表（逗号分隔）
- ``throttle``: 发送消息间隔（秒）
- ``qps``: 全局限速（请求最小间隔秒）
- ``poll_interval``: 预留的轮询间隔（Socket.IO 下仅作兼容保留）
- ``admin_tc``: 管理员 Tripcode 列表（逗号分隔）
"""

from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from core.logger import get_logger

CONFIG_FILE = "config.txt"
# 本项目位于 core/ 的上层目录（config.txt 在项目根）
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG: dict[str, object] = {
    "name": "test",
    "tc": "",
    "avatar": "setton",
    "agent": "Bot",
    "roomID": "6JjYq34S35",
    "throttle": 1.5,
    "qps": 0.5,
    "poll_interval": 3.0,
    "admin_tc": "",
    "mods": ["test", "guess_number"],
}

# 需要类型转换的字段：{字段名: (转换函数, 是否列表)}
_TYPE_RULES: dict[str, tuple[object, bool]] = {
    "throttle": (float, False),
    "qps": (float, False),
    "poll_interval": (float, False),
    "mods": (lambda s: [x.strip() for x in s.split(",")], True),
    "admin_tc": (lambda s: [x.strip() for x in s.split(",")], True),
}


@dataclass(slots=True)
class Config:
    """类型化配置对象。"""

    name: str = "test"
    tc: str = ""
    avatar: str = "setton"
    agent: str = "Bot"
    room_id: str = ""
    mods: list[str] = field(default_factory=list)
    throttle: float = 1.5
    qps: float = 0.5
    poll_interval: float = 3.0
    admin_tc: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Config":
        return cls(
            name=str(data.get("name", "test")),
            tc=str(data.get("tc", "")),
            avatar=str(data.get("avatar", "setton")),
            agent=str(data.get("agent", "Bot")),
            room_id=str(data.get("roomID", "")),
            mods=list(data.get("mods", []) or []),
            throttle=float(data.get("throttle", 1.5)),
            qps=float(data.get("qps", 0.5)),
            poll_interval=float(data.get("poll_interval", 3.0)),
            admin_tc=list(data.get("admin_tc", []) or []),
        )


def _write_default_config(path: Path, config: dict[str, object]) -> None:
    """将默认配置写入文件。"""
    with open(path, "w", encoding="utf-8") as f:
        for key, value in config.items():
            if isinstance(value, list):
                f.write(f"{key} = {', '.join(value)}\n")
            else:
                f.write(f"{key} = {value}\n")


def _convert_value(key: str, value: str, rules: dict[str, tuple[object, bool]], defaults: dict[str, object]) -> object:
    """按规则对配置值做类型转换。"""
    if key not in rules:
        return value
    converter, is_list = rules[key]
    try:
        return converter(value)  # type: ignore[operator]
    except (ValueError, TypeError):
        logger = get_logger("config")
        logger.error("配置项 %s 的值无效: %r，使用默认值", key, value)
        return defaults[key]


def load_config(
    path: str | os.PathLike[str] = CONFIG_FILE,
    *,
    logger: logging.Logger | None = None,
) -> Config:
    """加载配置文件，缺失字段使用默认值。

    Args:
        path: 配置文件路径（相对项目根目录或绝对路径）。
        logger: 日志器。

    Returns:
        类型化 Config 对象。
    """
    logger = logger or get_logger("config")
    config = copy.deepcopy(DEFAULT_CONFIG)

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = BASE_DIR / path

    if not file_path.exists():
        logger.warning("配置文件 %s 不存在，已生成默认配置", file_path)
        _write_default_config(file_path, config)

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                logger.warning("配置行格式无效，已忽略: %r", line)
                continue
            key, value = [x.strip() for x in line.split("=", 1)]
            if key not in config:
                logger.warning("未知配置项，已忽略: %r", key)
                continue
            config[key] = _convert_value(key, value, _TYPE_RULES, config)

    return Config.from_dict(config)


def save_admin_tc(admin_tc: list[str], path: str | os.PathLike[str] = CONFIG_FILE) -> bool:
    """将管理员 Tripcode 列表写回 config.txt（保留其他配置项）。

    Args:
        admin_tc: 新的管理员列表。
        path: 配置文件路径。

    Returns:
        是否成功。
    """
    logger = get_logger("config")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = BASE_DIR / path
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.strip().startswith("admin_tc"):
                new_lines.append(f"admin_tc = {', '.join(admin_tc)}\n")
            else:
                new_lines.append(line)
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except OSError:
        logger.exception("写回 admin_tc 失败")
        return False
