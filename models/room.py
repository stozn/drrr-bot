"""房间模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .user import User, UserRegistry

NO_TRIPCODE = "无"


@dataclass(slots=True)
class Room:
    """当前所在的房间。

    Attributes:
        name: 房间名。
        description: 房间描述。
        limit: 人数上限。
        users: 房间用户表（``id -> User``）。
        language: 房间语言。
        room_id: 房间 ID。
        music: 是否允许点歌。
        dj_mode: 是否开启 DJ 模式。
        music_np: 当前播放的歌曲信息（now playing）。
        host_id: 房主用户 ID。
        update: 服务器房间状态版本号（供轮询更新使用）。
        banned_ids: 被拉黑用户 ID 集合。
    """

    name: str = ""
    description: str = ""
    limit: int = 0
    users: UserRegistry = field(default_factory=UserRegistry)
    language: str = ""
    room_id: str = ""
    music: bool = False
    dj_mode: bool = False
    music_np: dict | bool = False
    host_id: str = ""
    update: int = 0
    banned_ids: set[str] = field(default_factory=set)

    def __str__(self) -> str:
        return (
            f"【{self.name}】{self.room_id} | {self.description} | "
            f"{len(self.users)}/{self.limit}"
        )

    def is_host(self, user_id: str) -> bool:
        return user_id == self.host_id

    def update_from_json(self, data: dict[str, Any]) -> bool:
        """从 /json.php?fast=1 的响应体更新房间状态。

        Args:
            data: json.php 返回的字典（含 roomId/users/name 等字段）。

        Returns:
            是否成功（响应中确实包含房间信息）。
        """
        if "roomId" not in data:
            return False

        users: UserRegistry = UserRegistry()
        for raw in data.get("users", []):
            user = User(
                id=str(raw.get("id", "")),
                name=raw.get("name", ""),
                icon=raw.get("icon", ""),
                tc=raw.get("tripcode") or NO_TRIPCODE,
                device=raw.get("device", ""),
                is_admin=bool(raw.get("admin", False)),
            )
            users[user.id] = user

        self.name = data.get("name", self.name)
        self.description = data.get("description", self.description)
        self.limit = data.get("limit", self.limit)
        self.users = users
        self.language = data.get("language", self.language)
        self.room_id = data.get("roomId", self.room_id)
        self.music = data.get("music", data.get("musicRoom", self.music))
        self.dj_mode = data.get("music_dj_mode", data.get("dj_mode", self.dj_mode))
        self.music_np = data.get("np", self.music_np)
        self.host_id = data.get("host", self.host_id)
        self.update = data.get("update", self.update)
        return True
