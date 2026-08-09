"""类型枚举：消息类型与出站动作类型。"""

from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    """入站消息类型，对应 Socket.IO/JSON 中的 ``type`` 字段。

    使用 ``str`` 值以兼容服务器返回的字符串（如 ``"message"``），
    ``auto()`` 生成的仅作为本地内部类型（如 dm/url/dm_url）。
    """

    # ---- 服务器 type 字段 ----
    JOIN = "join"
    LEAVE = "leave"
    MESSAGE = "message"
    MUSIC = "music"
    ME = "me"
    NEW_HOST = "new-host"
    ASYNC_RESPONSE = "async-response"
    KICK = "kick"
    BAN = "ban"
    UNBAN = "unban"
    SYSTEM = "system"
    ROOM_PROFILE = "room-profile"
    NEW_DESCRIPTION = "new-description"
    USER_PROFILE = "user-profile"

    # ---- 本地派生类型（服务器不会直接下发） ----
    DM = "dm"
    URL = "url"
    DM_URL = "dm_url"

    # ---- 错误 ----
    ERROR = "error"


class OutgoingType(str, Enum):
    """出站动作类型，驱动发送循环组装 HTTP POST 数据。"""

    MESSAGE = "message"
    DM = "dm"
    URL = "url"
    DM_URL = "dm_url"
    MUSIC = "music"
    HANDOVER_HOST = "handover_host"
    KICK = "kick"
    BAN = "ban"
    CHANGE_TITLE = "change_title"
    CHANGE_DESCRIPTION = "change_description"
    UNBAN = "unban"
    LEAVE = "leave"
    MUSIC_SKIP = "music_skip"
    ROOM_LIMIT = "room_limit"
    DJ_MODE = "dj_mode"
    MUSIC_FULL_MODE = "music_full_mode"
    LEGACY = "legacy"
