"""入站消息模型：dataclass + 继承体系完整封装各类聊天消息。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import MessageType
from .user import User


@dataclass(slots=True)
class Message:
    """基础消息：普通发言 / 系统动作的公共字段。

    Attributes:
        id: 消息 ID（去重依据）。Socket.IO 新版为字符串 hash，
            旧 json.php 为整数，故同时支持两种。
        time: 服务器时间戳（秒）。
        type: 消息类型（MessageType 枚举）。
        content: 消息文本内容。
        sender: 发送者（join/leave/new-host 等系统消息也可能携带）。
        is_me: 是否由本 bot 发出。
        to: 私信/踢人等动作的目标用户。
    """

    id: str | int | None = None
    time: float = 0.0
    type: MessageType = MessageType.MESSAGE
    content: str = ""
    sender: User | None = None
    is_me: bool = False
    to: User | None = None

    @property
    def message(self) -> str:
        """兼容旧模块中的 ``msg.message`` 访问方式。"""
        return self.content

    @property
    def user(self) -> User | None:
        """兼容旧模块中的 ``msg.user`` 访问方式。"""
        return self.sender


@dataclass(slots=True)
class JoinMessage(Message):
    """用户加入房间。"""

    type: MessageType = MessageType.JOIN
    content: str = "进入房间"


@dataclass(slots=True)
class LeaveMessage(Message):
    """用户离开房间。"""

    type: MessageType = MessageType.LEAVE
    content: str = "离开房间"


@dataclass(slots=True)
class NewHostMessage(Message):
    """变更房主。"""

    type: MessageType = MessageType.NEW_HOST
    content: str = "成为新房主"


@dataclass(slots=True)
class URLMessage(Message):
    """带链接的普通消息。"""

    url: str = ""


@dataclass(slots=True)
class DirectMessage(Message):
    """私信。"""

    type: MessageType = MessageType.DM
    receiver: User | None = None


@dataclass(slots=True)
class DirectURLMessage(DirectMessage):
    """带链接的私信。"""

    type: MessageType = MessageType.DM_URL
    url: str = ""


@dataclass(slots=True)
class MusicMessage(Message):
    """分享音乐。

    Attributes:
        name: 歌曲名。
        play_url: 播放地址。
        share_url: 分享地址。
        thumbnail_url: 封面图（可选）。
    """

    type: MessageType = MessageType.MUSIC
    name: str = ""
    play_url: str = ""
    share_url: str = ""
    thumbnail_url: str = ""

    @property
    def music_name(self) -> str:
        """兼容旧模块访问方式。"""
        return self.name

    @property
    def music_url(self) -> str:
        """兼容旧模块访问方式。"""
        return self.play_url

    @property
    def url(self) -> str:
        return self.share_url


@dataclass(slots=True)
class MeMessage(Message):
    """动作消息（/me 前缀）。"""

    type: MessageType = MessageType.ME
    content: str = ""


@dataclass(slots=True)
class KickMessage(Message):
    """踢人动作。target 可能为 None（服务器偶发省略）。"""

    type: MessageType = MessageType.KICK
    target: User | str | None = None

    @property
    def to(self) -> User | str | None:  # type: ignore[override]
        return self.target

    @to.setter
    def to(self, value: User | str | None) -> None:
        self.target = value


@dataclass(slots=True)
class BanMessage(Message):
    """封禁动作。"""

    type: MessageType = MessageType.BAN
    target: User | str | None = None

    @property
    def to(self) -> User | str | None:  # type: ignore[override]
        return self.target

    @to.setter
    def to(self, value: User | str | None) -> None:
        self.target = value


@dataclass(slots=True)
class UnbanMessage(Message):
    """解封动作。"""

    type: MessageType = MessageType.UNBAN
    target: User | str | None = None

    @property
    def to(self) -> User | str | None:  # type: ignore[override]
        return self.target

    @to.setter
    def to(self, value: User | str | None) -> None:
        self.target = value


@dataclass(slots=True)
class SystemMessage(Message):
    """系统消息（如被踢出时服务器提示）。"""

    type: MessageType = MessageType.SYSTEM


@dataclass(slots=True)
class RoomProfileMessage(Message):
    """房间信息更新（主题/人数等）。"""

    type: MessageType = MessageType.ROOM_PROFILE


@dataclass(slots=True)
class NewDescMessage(Message):
    """房间描述更新。"""

    type: MessageType = MessageType.NEW_DESCRIPTION
    description: str = ""

    @property
    def message(self) -> str:
        return f"设置房间主题：{self.description}"


@dataclass(slots=True)
class AsyncResponse(Message):
    """异步响应（async-response），主要用于服务器异步任务通知。"""

    type: MessageType = MessageType.ASYNC_RESPONSE
    secret: str = ""
    title: str = ""
    level: str = ""
    stop_fetching: bool = False


@dataclass(slots=True)
class ErrorMessage(Message):
    """错误消息。"""

    type: MessageType = MessageType.ERROR
    text: str = ""
    reload: bool = False


__all__ = [
    "AsyncResponse",
    "BanMessage",
    "DirectMessage",
    "DirectURLMessage",
    "ErrorMessage",
    "JoinMessage",
    "KickMessage",
    "LeaveMessage",
    "MeMessage",
    "Message",
    "MusicMessage",
    "NewDescMessage",
    "NewHostMessage",
    "RoomProfileMessage",
    "SystemMessage",
    "UnbanMessage",
    "URLMessage",
]
