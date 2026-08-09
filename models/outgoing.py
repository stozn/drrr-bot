"""出站动作模型：统一描述一次发送请求，由发送循环转换为 HTTP POST 数据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import OutgoingType


@dataclass(slots=True)
class OutgoingMessage:
    """普通发言。"""

    type: OutgoingType = OutgoingType.MESSAGE
    msg: str = ""


@dataclass(slots=True)
class OutgoingDirectMessage:
    """私信。"""

    type: OutgoingType = OutgoingType.DM
    msg: str = ""
    receiver: str = ""


@dataclass(slots=True)
class OutgoingUrlMessage:
    """带链接的发言。"""

    type: OutgoingType = OutgoingType.URL
    msg: str = ""
    url: str = ""


@dataclass(slots=True)
class OutgoingDmUrl:
    """带链接的私信。"""

    type: OutgoingType = OutgoingType.DM_URL
    msg: str = ""
    receiver: str = ""
    url: str = ""


@dataclass(slots=True)
class OutgoingMusic:
    """点歌。"""

    type: OutgoingType = OutgoingType.MUSIC
    name: str = ""
    url: str = ""


@dataclass(slots=True)
class OutgoingHandoverHost:
    """转让房主。"""

    type: OutgoingType = OutgoingType.HANDOVER_HOST
    receiver: str = ""


@dataclass(slots=True)
class OutgoingKick:
    """踢人。"""

    type: OutgoingType = OutgoingType.KICK
    receiver: str = ""


@dataclass(slots=True)
class OutgoingBan:
    """封禁。"""

    type: OutgoingType = OutgoingType.BAN
    receiver: str = ""


@dataclass(slots=True)
class OutgoingChangeTitle:
    """修改房间名。"""

    type: OutgoingType = OutgoingType.CHANGE_TITLE
    title: str = ""


@dataclass(slots=True)
class OutgoingChangeDescription:
    """修改房间描述。"""

    type: OutgoingType = OutgoingType.CHANGE_DESCRIPTION
    description: str = ""


@dataclass(slots=True)
class OutgoingLegacy:
    """通用房间操作（解封/离开/切歌/改人数上限/DJ 模式等）。

    data 为要 POST 到 /room/?ajax=1 的字段字典。
    """

    type: OutgoingType = OutgoingType.LEGACY
    data: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "OutgoingBan",
    "OutgoingChangeDescription",
    "OutgoingChangeTitle",
    "OutgoingDmUrl",
    "OutgoingDirectMessage",
    "OutgoingHandoverHost",
    "OutgoingKick",
    "OutgoingLegacy",
    "OutgoingMessage",
    "OutgoingMusic",
    "OutgoingUrlMessage",
]
