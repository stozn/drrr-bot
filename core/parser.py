"""消息解析器：把 Socket.IO/JSON 原始数据转换为类型化模型。"""

from __future__ import annotations

import logging
from typing import Any

from core.logger import get_logger
from models import (
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
    MessageType,
    MusicMessage,
    NewDescMessage,
    NewHostMessage,
    RoomProfileMessage,
    SystemMessage,
    UnbanMessage,
    URLMessage,
)
from models.room import Room
from models.user import BannedUser, User

NO_TRIPCODE = "无"


class Parser:
    """将 talk JSON 对象转换为类型化消息模型。"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or get_logger("parser")

    # ------------------------------------------------------------------
    # 用户解析
    # ------------------------------------------------------------------
    def _parse_user(self, data: dict[str, Any]) -> User:
        return User(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            icon=data.get("icon", ""),
            tc=data.get("tripcode") or NO_TRIPCODE,
            device=data.get("device", ""),
            is_admin=bool(data.get("admin", False)),
        )

    def _resolve_user(self, room: Room, uid: Any) -> User | None:
        """通过用户 ID 在房间用户表中查找用户。"""
        if uid is None:
            return None
        return room.users.get(str(uid))

    # ------------------------------------------------------------------
    # 消息解析
    # ------------------------------------------------------------------
    def talk_to_message(self, data: dict[str, Any], room: Room) -> Message | None:
        """解析单个 talk 对象。解析失败或未知类型返回 None。"""
        msg_type = data.get("type")
        msg_id = data.get("id")
        msg_time = data.get("time", 0.0)
        from_data = data.get("from")
        sender = self._parse_user(from_data) if isinstance(from_data, dict) else None

        # 兜底：from 不在房间用户表时以独立用户对象重建（join 等消息自带完整用户）
        if msg_type == MessageType.JOIN.value:
            user_data = data.get("user")
            user = self._parse_user(user_data) if isinstance(user_data, dict) else sender
            return JoinMessage(id=msg_id, time=msg_time, sender=user)

        if msg_type == MessageType.LEAVE.value:
            user_data = data.get("user")
            user = self._parse_user(user_data) if isinstance(user_data, dict) else sender
            return LeaveMessage(id=msg_id, time=msg_time, sender=user)

        if msg_type == MessageType.NEW_HOST.value:
            user_data = data.get("user")
            user = self._parse_user(user_data) if isinstance(user_data, dict) else sender
            return NewHostMessage(id=msg_id, time=msg_time, sender=user)

        if msg_type == MessageType.MESSAGE.value:
            content = data.get("message", "")
            url = data.get("url")
            to_data = data.get("to")
            receiver = (
                self._parse_user(to_data) if isinstance(to_data, dict) else None
            )
            if url and receiver:
                return DirectURLMessage(
                    id=msg_id, time=msg_time, sender=sender, content=content,
                    receiver=receiver, url=url,
                )
            if url:
                return URLMessage(
                    id=msg_id, time=msg_time, sender=sender, content=content, url=url
                )
            if receiver:
                return DirectMessage(
                    id=msg_id, time=msg_time, sender=sender, content=content,
                    receiver=receiver,
                )
            return Message(id=msg_id, time=msg_time, sender=sender, content=content)

        if msg_type == MessageType.ME.value:
            return MeMessage(
                id=msg_id, time=msg_time, sender=sender,
                content=data.get("content", ""),
            )

        if msg_type == MessageType.MUSIC.value:
            music = data.get("music") or {}
            return MusicMessage(
                id=msg_id, time=msg_time, sender=sender,
                name=music.get("name", ""),
                play_url=music.get("playURL", ""),
                share_url=music.get("shareURL", ""),
                content=f"分享了 {music.get('name', '')}",
            )

        if msg_type == MessageType.KICK.value:
            to_data = data.get("to")
            return KickMessage(
                id=msg_id, time=msg_time, content=data.get("message", ""),
                target=self._resolve_target(to_data, room),
            )

        if msg_type == MessageType.BAN.value:
            to_data = data.get("to")
            return BanMessage(
                id=msg_id, time=msg_time, content=data.get("message", ""),
                target=self._resolve_target(to_data, room),
            )

        if msg_type == MessageType.UNBAN.value:
            to_data = data.get("to")
            return UnbanMessage(
                id=msg_id, time=msg_time, content=data.get("message", ""),
                target=self._resolve_target(to_data, room),
            )

        if msg_type == MessageType.SYSTEM.value:
            return SystemMessage(
                id=msg_id, time=msg_time, content=data.get("message", "")
            )

        if msg_type == MessageType.ROOM_PROFILE.value:
            return RoomProfileMessage(
                id=msg_id, time=msg_time,
                sender=room.users.get(room.host_id) if room.host_id else None,
            )

        if msg_type == MessageType.NEW_DESCRIPTION.value:
            return NewDescMessage(
                id=msg_id, time=msg_time, sender=sender,
                description=data.get("description", ""),
            )

        if msg_type == MessageType.ASYNC_RESPONSE.value:
            to_data = data.get("to")
            return AsyncResponse(
                id=msg_id, time=msg_time, sender=sender,
                secret=data.get("secret", ""),
                content=data.get("message", ""),
                title=data.get("title", ""),
                level=data.get("level", ""),
                to=self._parse_user(to_data) if isinstance(to_data, dict) else None,
                stop_fetching=False,
            )

        if msg_type == MessageType.USER_PROFILE.value:
            return None

        if msg_type == "error":
            return ErrorMessage(
                content=data.get("error", ""), reload=bool(data.get("reload", False))
            )

        self.logger.warning("未知消息类型: %s", msg_type)
        self.logger.debug("原始消息: %r", data)
        return None

    def _resolve_target(
        self, to_data: Any, room: Room
    ) -> User | str | None:
        """解析踢人/封禁的目标：优先返回房间内用户对象，否则返回 id。"""
        if not isinstance(to_data, dict):
            return to_data
        uid = str(to_data.get("id", ""))
        user = room.users.get(uid)
        if user is not None:
            return user
        # 服务器可能返回不完整的 banned 用户信息
        if "tripcode" in to_data or "name" in to_data:
            return User(
                id=uid,
                name=to_data.get("name", ""),
                icon=to_data.get("icon", ""),
                tc=to_data.get("tripcode") or NO_TRIPCODE,
            )
        return uid

    def talks_to_messages(self, talks: list[dict[str, Any]], room: Room) -> list[Message]:
        """解析 talks 数组。"""
        result: list[Message] = []
        for talk in talks:
            try:
                msg = self.talk_to_message(talk, room)
            except Exception:
                self.logger.exception("消息解析失败: %r", talk)
                msg = None
            if msg is not None:
                result.append(msg)
        return result
