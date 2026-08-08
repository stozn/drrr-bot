# -*- coding: utf-8 -*-
"""房间管理模块。

只有管理员（Tripcode 匹配）才能执行管理命令。
管理员 Tripcode 在 config.txt 的 admin_tc 字段中维护（加密后的值，逗号分隔）。

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
  /离开房间         离开当前房间
  /管理员          查看管理员列表
  /加管理员 <tc>    添加管理员（仅已认证管理员）
  /删管理员 <tc>    移除管理员（仅已认证管理员）
"""

import os

from modules.module import Module

# 管理员 Tripcode 从主项目的 config.txt 中的 admin_tc 字段读取（加密后的值，逗号分隔）
CONFIG_FILE = 'config.txt'
DEFAULT_ADMINS = []


class RoomAdmin(Module):
    def __init__(self, bot):
        super().__init__(bot)
        self.admins = self._load_admins()

    @property
    def cmds(self):
        return {
            'cmd_kick': r'^\/踢人\s+\S+',
            'cmd_ban': r'^\/封禁\s+\S+',
            'cmd_unban': r'^\/解封\s+\S+',
            'cmd_skip': r'^\/切歌\s*$',
            'cmd_room_limit': r'^\/房间人数\s+\d+\s*$',
            'cmd_dj': r'^\/DJ模式\s+(开|关|on|off)\s*$',
            'cmd_full': r'^\/全音量\s+(开|关|on|off)\s*$',
            'cmd_title': r'^\/改房名\s+\S+',
            'cmd_desc': r'^\/改描述\s+\S+',
            'cmd_chown': r'^\/转让房主\s+\S+',
            'cmd_self_chown': r'^\/房主\s*$',
            'cmd_leave': r'^\/离开房间\s*$',
            'cmd_admins': r'^\/管理员\s*$',
            'cmd_add_admin': r'^\/加管理员\s+\S+',
            'cmd_del_admin': r'^\/删管理员\s+\S+',
        }

    # ---------- 配置读写 ----------
    def _config_path(self):
        # 优先使用主项目目录，避免依赖运行时 cwd
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, CONFIG_FILE)

    def _load_admins(self):
        """从 config.txt 的 admin_tc 字段读取管理员 Tripcode 列表。"""
        path = self._config_path()
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('admin_tc'):
                            value = line.split('=', 1)[1].strip()
                            admins = [x.strip() for x in value.split(',') if x.strip()]
                            return admins
            except OSError:
                pass
        return list(DEFAULT_ADMINS)

    def _save_admins(self):
        """将管理员列表写回 config.txt 的 admin_tc 字段（保留其他配置项）。"""
        path = self._config_path()
        try:
            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.strip().startswith('admin_tc'):
                    new_lines.append(f'admin_tc = {", ".join(self.admins)}\n')
                else:
                    new_lines.append(line)
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except OSError:
            pass

    # ---------- 权限校验 ----------
    def is_admin(self, msg):
        """判断发言用户是否为管理员（Tripcode 匹配）。"""
        return msg.user.tc in self.admins

    # ---------- 命令 ----------
    def cmd_kick(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        user = self._resolve_user(msg.message, msg)
        if not user:
            self.bot.me('未找到用户')
            return
        self.bot.kick(user.id)
        self.bot.me(f'已将 @{user.name} 踢出房间')

    def cmd_ban(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        user = self._resolve_user(msg.message, msg)
        if not user:
            self.bot.me('未找到用户')
            return
        self.bot.ban(user.id)
        self.bot.me(f'已封禁 @{user.name}')

    def cmd_unban(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        user = self._resolve_user(msg.message, msg)
        if not user:
            self.bot.me('未找到用户')
            return
        self.bot.unban(user.id)
        self.bot.me(f'已解封 @{user.name}')

    def cmd_skip(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        self.bot.music_skip()
        self.bot.me('已切歌')

    def cmd_room_limit(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        try:
            limit = int(msg.message.split()[1])
        except (IndexError, ValueError):
            self.bot.me('人数上限格式错误')
            return
        self.bot.room_limit(limit)
        self.bot.me(f'已将房间人数上限设为 {limit}')

    def cmd_dj(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        enabled = self._bool_value(msg.message)
        self.bot.toggle_dj_mode(enabled)
        self.bot.me(f'DJ模式已{"开启" if enabled else "关闭"}')

    def cmd_full(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        enabled = self._bool_value(msg.message)
        self.bot.toggle_music_full_mode(enabled)
        self.bot.me(f'全音量模式已{"开启" if enabled else "关闭"}')

    def cmd_title(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        title = msg.message.split(' ', 1)[1].strip()
        self.bot.title(title)
        self.bot.me(f'房间名已改为：{title}')

    def cmd_desc(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        desc = msg.message.split(' ', 1)[1].strip()
        self.bot.desc(desc)
        self.bot.me(f'房间描述已改为：{desc}')

    def cmd_chown(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        user = self._resolve_user(msg.message, msg)
        if not user:
            self.bot.me('未找到用户')
            return
        self.bot.chown(user.id)
        self.bot.me(f'已将房主转让给 @{user.name}')

    def cmd_self_chown(self, msg):
        """把房主转让给发送命令的用户自己（需管理员）。"""
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        self.bot.chown(msg.user.id)
        self.bot.me(f'已将房主转让给 @{msg.user.name}')

    def cmd_leave(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        self.bot.leave_room()
        self.bot.me('已离开房间')

    def cmd_admins(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        if not self.admins:
            self.bot.me('当前没有配置管理员')
        else:
            self.bot.me('管理员列表：' + '、'.join(self.admins))

    def cmd_add_admin(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        tc = msg.message.split(' ', 1)[1].strip()
        if tc in self.admins:
            self.bot.me(f'{tc} 已是管理员')
            return
        self.admins.append(tc)
        self._save_admins()
        self.bot.me(f'已添加管理员：{tc}')

    def cmd_del_admin(self, msg):
        if not self.is_admin(msg):
            self.bot.me(f'@{msg.user.name} 没有权限')
            return
        tc = msg.message.split(' ', 1)[1].strip()
        if tc not in self.admins:
            self.bot.me(f'{tc} 不是管理员')
            return
        self.admins.remove(tc)
        self._save_admins()
        self.bot.me(f'已移除管理员：{tc}')

    # ---------- 工具方法 ----------
    @staticmethod
    def _bool_value(message):
        """解析 开/关/on/off 为布尔值。"""
        val = message.split()[1].lower()
        return val in ('开', 'on', '1', 'true')

    def _resolve_user(self, message, msg):
        """根据命令参数解析目标用户对象。"""
        name = message.split(' ', 1)[1].strip().lstrip('@')
        # 先按用户名精确查找
        for u in self.bot.room.users.values():
            if u.name == name:
                return u
        # 再尝试按 Tripcode 查找（形如 #tripcode）
        if name.startswith('#'):
            tc = name[1:]
            for u in self.bot.room.users.values():
                if u.tc == tc:
                    return u
        return None
