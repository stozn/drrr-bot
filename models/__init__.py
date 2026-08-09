"""数据模型包：dataclass + enum 完整封装消息与实体。"""

from .enums import MessageType, OutgoingType
from .message import (
    AsyncResponse,
    BanMessage,
    DirectMessage,
    DirectURLMessage,
    ErrorMessage,
    JoinMessage,
    KickMessage,
    LeaveMessage,
    MeMessage,
    Message,
    MusicMessage,
    NewDescMessage,
    NewHostMessage,
    RoomProfileMessage,
    SystemMessage,
    UnbanMessage,
    URLMessage,
)
from .outgoing import (
    OutgoingBan,
    OutgoingChangeDescription,
    OutgoingChangeTitle,
    OutgoingDmUrl,
    OutgoingDirectMessage,
    OutgoingHandoverHost,
    OutgoingKick,
    OutgoingLegacy,
    OutgoingMessage,
    OutgoingMusic,
    OutgoingUrlMessage,
)
from .room import Room
from .user import BannedUser, User

__all__ = [
    # enums
    "MessageType",
    "OutgoingType",
    # message
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
    # outgoing
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
    # room / user
    "Room",
    "BannedUser",
    "User",
]
