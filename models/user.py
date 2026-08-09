"""用户模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

NO_TRIPCODE = "无"


@dataclass(slots=True)
class User:
    """房间内的用户。

    Attributes:
        id: 服务器下发的唯一用户 ID。
        name: 用户名。
        icon: 头像名称。
        tc: Tripcode（未设置时为空字符串，展示为"无"）。
        device: 设备标识（web/mobile 等）。
        is_admin: 是否为 drrr 全局管理员（与房间管理权限无关）。
    """

    id: str
    name: str
    icon: str = ""
    tc: str = NO_TRIPCODE
    device: str = ""
    is_admin: bool = False

    def __str__(self) -> str:
        return f"@{self.name}[{self.tc}]"


@dataclass(slots=True)
class BannedUser:
    """被拉黑（ban）的用户。

    服务器下发的 ban 目标可能是完整用户对象，也可能只有 id；
    因此 ``name/tc/icon`` 允许为空。
    """

    id: str
    name: str = ""
    tc: str = ""
    icon: str = ""

    @classmethod
    def from_user(cls, user: User) -> "BannedUser":
        return cls(id=user.id, name=user.name, tc=user.tc, icon=user.icon)


@dataclass(slots=True)
class UserRegistry(dict):
    """房间用户表：``id -> User``，提供便捷查询。"""

    def find_by_name(self, name: str) -> User | None:
        for user in self.values():
            if user.name == name:
                return user
        return None

    def find_by_tc(self, tc: str) -> User | None:
        for user in self.values():
            if user.tc == tc:
                return user
        return None
