# -*- coding: utf-8 -*-
"""房间管理模块。

只有管理员（Tripcode 匹配 config.txt 的 admin_tc）才能执行管理命令。

命令列表（需管理员）：
  /踢人 <用户名>    踢出用户
  /封禁 <用户名>    封禁用户
  /解封 <用户名>    解封用户
  /切歌            跳过当前歌曲
  /房间人数 <N>     修改房间人数上限
  /DJ模式 <开|关>   切换 DJ 模式
  /全音量 <开|关>   切换全音量模式
  /改房名 <名称>    修改房间名
  /改描述 <描述>    修改房间描述
  /转让房主 <用户名> 转让房主
  /房主            转让房主给自己
  /离开房间         离开当前房间
  /管理员          查看管理员列表
  /加管理员 <tc>    添加管理员（仅已认证管理员）
  /删管理员 <tc>    移除管理员（仅已认证管理员）
"""

from __future__ import annotations

from core.config import save_admin_tc
from modules.base import Module, command
from models import Message
from models.user import User


class RoomAdmin(Module):
    def __init__(self, bot):
        super().__init__(bot)
        self.admins = list(bot.admins)

    @command(r"^/踢人\s+\S+", admin=True)
    def cmd_kick(self, msg: Message):
        if not self.require_admin(msg):
            return
        user = self._resolve_user(msg)
        if not user:
            self.bot.me("未找到用户")
            return
        if not self._check_target_ok(msg, user):
            return
        self.bot.kick(user.id)
        self.bot.me(f"已将 @{user.name} 踢出房间")

    @command(r"^/封禁\s+\S+", admin=True)
    def cmd_ban(self, msg: Message):
        if not self.require_admin(msg):
            return
        user = self._resolve_user(msg)
        if not user:
            self.bot.me("未找到用户")
            return
        if not self._check_target_ok(msg, user):
            return
        self.bot.ban(user.id)
        self.bot.me(f"已封禁 @{user.name}")

    @command(r"^/解封\s+\S+", admin=True)
    def cmd_unban(self, msg: Message):
        if not self.require_admin(msg):
            return
        user = self._resolve_user(msg)
        if not user:
            self.bot.me("未找到用户")
            return
        self.bot.unban(user.id)
        self.bot.me(f"已解封 @{user.name}")

    @command(r"^/切歌\s*$", admin=True)
    def cmd_skip(self, msg: Message):
        if not self.require_admin(msg):
            return
        self.bot.music_skip()
        self.bot.me("已切歌")

    @command(r"^/房间人数\s+\d+\s*$", admin=True)
    def cmd_room_limit(self, msg: Message):
        if not self.require_admin(msg):
            return
        try:
            limit = int(msg.content.split()[1])
        except (IndexError, ValueError):
            self.bot.me("人数上限格式错误")
            return
        self.bot.room_limit(limit)
        self.bot.me(f"已将房间人数上限设为 {limit}")

    @command(r"^/DJ模式\s+(开|关|on|off)\s*$", admin=True)
    def cmd_dj(self, msg: Message):
        if not self.require_admin(msg):
            return
        enabled = self._bool_value(msg.content)
        self.bot.toggle_dj_mode(enabled)
        self.bot.me(f'DJ模式已{"开启" if enabled else "关闭"}')

    @command(r"^/全音量\s+(开|关|on|off)\s*$", admin=True)
    def cmd_full(self, msg: Message):
        if not self.require_admin(msg):
            return
        enabled = self._bool_value(msg.content)
        self.bot.toggle_music_full_mode(enabled)
        self.bot.me(f'全音量模式已{"开启" if enabled else "关闭"}')

    @command(r"^/改房名\s+\S+", admin=True)
    def cmd_title(self, msg: Message):
        if not self.require_admin(msg):
            return
        title = msg.content.split(" ", 1)[1].strip()
        self.bot.title(title)
        self.bot.me(f"房间名已改为：{title}")

    @command(r"^/改描述\s+\S+", admin=True)
    def cmd_desc(self, msg: Message):
        if not self.require_admin(msg):
            return
        desc = msg.content.split(" ", 1)[1].strip()
        self.bot.desc(desc)
        self.bot.me(f"房间描述已改为：{desc}")

    @command(r"^/转让房主\s+\S+", admin=True)
    def cmd_chown(self, msg: Message):
        if not self.require_admin(msg):
            return
        user = self._resolve_user(msg)
        if not user:
            self.bot.me("未找到用户")
            return
        if not self._check_target_ok(msg, user, forbid_self=False):
            return
        self.bot.chown(user.id)
        self.bot.me(f"已将房主转让给 @{user.name}")

    @command(r"^/房主\s*$", admin=True)
    def cmd_self_chown(self, msg: Message):
        """把房主转让给发送命令的用户自己（需管理员）。"""
        if not self.require_admin(msg):
            return
        self.bot.chown(msg.user.id)
        self.bot.me(f"已将房主转让给 @{msg.user.name}")

    @command(r"^/离开房间\s*$", admin=True)
    def cmd_leave(self, msg: Message):
        if not self.require_admin(msg):
            return
        self.bot.leave_room()
        self.bot.me("已离开房间")

    @command(r"^/管理员\s*$", admin=True)
    def cmd_admins(self, msg: Message):
        if not self.require_admin(msg):
            return
        if not self.admins:
            self.bot.me("当前没有配置管理员")
        else:
            self.bot.me("管理员列表：" + "、".join(self.admins))

    @command(r"^/加管理员\s+\S+", admin=True)
    def cmd_add_admin(self, msg: Message):
        if not self.require_admin(msg):
            return
        tc = msg.content.split(" ", 1)[1].strip()
        if tc in self.admins:
            self.bot.me(f"{tc} 已是管理员")
            return
        self.admins.append(tc)
        self._save_admins()
        self.bot.me(f"已添加管理员：{tc}")

    @command(r"^/删管理员\s+\S+", admin=True)
    def cmd_del_admin(self, msg: Message):
        if not self.require_admin(msg):
            return
        tc = msg.content.split(" ", 1)[1].strip()
        if tc not in self.admins:
            self.bot.me(f"{tc} 不是管理员")
            return
        self.admins.remove(tc)
        self._save_admins()
        self.bot.me(f"已移除管理员：{tc}")

    # ---------- 工具方法 ----------
    def _check_target_ok(
        self, msg: Message, user: User, *, forbid_self: bool = True
    ) -> bool:
        """检查操作目标是否允许。

        两个防线：
        - ``forbid_self=True`` 时：不能对自己（发送者）操作
        - 一律不能对 bot 自己（机器人）操作（防止把自己踢出房间/封禁）

        Args:
            msg: 触发命令的消息。
            user: 解析出的目标用户。
            forbid_self: 是否禁止操作发送者自己（踢人/封禁需禁止；转让房主允许）。

        Returns:
            是否允许执行。
        """
        if forbid_self and msg.user is not None and user.id == msg.user.id:
            self.bot.me("不能对自己操作")
            return False
        if self.bot.own_user is not None and user.id == self.bot.own_user.id:
            self.bot.me("不能对机器人自己操作")
            return False
        return True

    @staticmethod
    def _bool_value(message: str) -> bool:
        """解析 开/关/on/off 为布尔值。"""
        val = message.split()[1].lower()
        return val in ("开", "on", "1", "true")

    def _resolve_user(self, msg: Message) -> User | None:
        """根据命令参数解析目标用户对象。"""
        name = msg.content.split(" ", 1)[1].strip().lstrip("@")
        # 先按用户名精确查找
        user = self.bot.room.users.find_by_name(name)
        if user:
            return user
        # 再尝试按 Tripcode 查找（形如 #tripcode）
        if name.startswith("#"):
            return self.bot.room.users.find_by_tc(name[1:])
        return None

    def _save_admins(self) -> None:
        """将管理员列表写回 config.txt 的 admin_tc 字段。"""
        if save_admin_tc(self.admins):
            self.bot.admins = list(self.admins)
        else:
            self.bot.me("管理员列表保存失败")
