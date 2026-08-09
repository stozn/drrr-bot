"""BotClient：机器人门面。

组合以下组件：

- ``HttpSession``：HTTP 操作（登录/进房/发送/PoW/QPS）
- ``SIoClient``：Socket.IO 实时接收（new-talk/rewind/leave 等）
- ``Parser``：原始 JSON → 类型化消息模型
- ``ModuleRegistry``：模块加载与消息分发
- ``Room``：房间状态
- ``Deduplicator / HistoryFilter``：去重与历史过滤

对外提供与旧版兼容的同步 API（``send/dm/music/kick/...``），
模块可在同步处理器中直接调用。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.limits import Deduplicator, HistoryFilter, RateLimiter
from core.logger import MessageLogger, get_logger
from core.parser import Parser
from core.registry import ModuleRegistry
from net.session import HttpSession
from models import Message, MessageType, OutgoingType, Room, User
from models.outgoing import (
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
from sio import SIoClient

ENDPOINT = "https://drrr.com"
WS_URL = "wss://drrr.com/conn/"
CHAR_LIMIT = 140


class BotClient:
    """drrr 聊天室机器人门面。"""

    def __init__(
        self,
        *,
        config,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or get_logger("bot")
        self.config = config
        self.name = config.name
        self.tc = config.tc
        self.avatar = config.avatar
        self.room_id = config.room_id
        self.throttle = max(config.throttle, 0.0)
        self.admins = list(config.admin_tc)

        # 组件
        self.http = HttpSession(
            username=self.name, qps=config.qps, logger=self.logger
        )
        self.parser = Parser(self.logger)
        self.registry = ModuleRegistry(self)
        self.room = Room()
        self.own_user: User | None = None
        self.room_connected = False

        # 基础设施
        self.dedup = Deduplicator()
        self.history = HistoryFilter()
        self.sender = RateLimiter(self.throttle)
        self.messages_log = MessageLogger()

        # Socket.IO 客户端（登录后创建）
        self.sio: SIoClient | None = None

        # 发送队列与任务
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """启动机器人：登录 → 进房 → 连接 Socket.IO → 接收循环。"""
        self.logger.info("启动中（用户：%s，房间：%s）", self.name, self.room_id)

        if not await self.http.login(self.tc):
            self.logger.error("登录失败，程序退出")
            return

        try:
            await self._run()
        finally:
            await self.stop()

    async def _run(self) -> None:
        """登录成功后的主流程（进房 → 连接 → 接收）。"""
        self.logger.info("启动中（用户：%s，房间：%s）", self.name, self.room_id)

        # 判断是否已在房间中
        await self.http.update_room_state(self.room)
        if self.room.room_id:
            self.room_connected = True
            self.logger.info("已连接房间【%s】", self.room.name)
        else:
            if not await self.http.join_room(self.room_id, self.room):
                self.logger.error("进入房间失败，程序退出")
                return
            self.room_connected = True

        # 记录加入时刻（过滤历史消息）并设置 own_user
        self.history.mark_joined()
        await self._load_own_user()

        # 启动发送循环
        self._tasks.append(asyncio.create_task(self._send_loop()))

        # 发送启动公告（房间内广播 /me）
        self.me("drrr-bot已启动")

        # 连接 Socket.IO 并开始接收
        await self._connect_sio()

    async def stop(self) -> None:
        """停止机器人并清理资源。"""
        self.logger.info("正在停止...")
        if self.sio:
            self.sio.close()
        for task in self._tasks:
            task.cancel()
        await self.http.close()
        self.messages_log.close()

    # ------------------------------------------------------------------
    # Socket.IO
    # ------------------------------------------------------------------
    async def _connect_sio(self) -> None:
        """创建并启动 Socket.IO 客户端。"""
        self.sio = SIoClient(
            url=WS_URL,
            headers=self._build_ws_headers(),
            impersonate="chrome",
            logger=self.logger,
        )
        self.sio.on_event(self._on_sio_event)
        self.sio.on_disconnect(self._on_sio_disconnect)

        config_payload = {
            "webpush_config": None,
            "push_all_messages": False,
        }
        self.logger.info("连接 Socket.IO ...")
        await self.sio.run_forever(config_payload)
        self.logger.info("Socket.IO 已就绪")

    def _build_ws_headers(self) -> dict[str, str]:
        """构造 WebSocket 握手头（携带登录 cookie）。"""
        headers = {"User-Agent": self.http.ua}
        try:
            cookie_str = "; ".join(
                f"{k}={v}" for k, v in self.http.session.cookies.items()
            )
        except Exception:
            cookie_str = ""
        if cookie_str:
            headers["Cookie"] = cookie_str
        return headers

    async def _on_sio_disconnect(self) -> None:
        """Socket.IO 断线：记录状态。重连由 SIoClient.run_forever 内部自动处理。"""
        self.logger.warning("Socket.IO 连接断开，等待自动重连")

    async def _on_sio_event(self, event: str, data: Any) -> None:
        """处理 Socket.IO 事件。"""
        try:
            if event == "new-talk":
                await self._handle_talk(data)
            elif event == "rewind":
                await self._handle_rewind(data)
            elif event == "leave":
                await self._handle_leave(data)
            elif event == "room-not-exist":
                self.logger.warning("房间不存在，尝试重新进入")
                await self._rejoin()
            elif event == "not-in-any-room":
                self.logger.warning("不在任何房间，尝试重新进入")
                await self._rejoin()
            else:
                self.logger.debug("忽略事件 %s", event)
        except Exception:
            self.logger.exception("处理事件 %s 失败", event)

    async def _handle_talk(self, data: Any) -> None:
        """处理单条新消息（new-talk）。"""
        if not isinstance(data, dict):
            return
        if data.get("time"):
            self.sio.update_last_time(float(data["time"]))
        msg = self.parser.talk_to_message(data, self.room)
        if msg is None:
            return
        await self._process_message(msg)

    async def _handle_rewind(self, data: Any) -> None:
        """处理重连补消息（rewind 事件带 talks 数组）。"""
        if not isinstance(data, dict):
            return
        talks = data.get("talks") or []
        msgs = self.parser.talks_to_messages(talks, self.room)
        for msg in msgs:
            await self._process_message(msg)
        # 补完消息后更新时间戳
        if talks and self.sio:
            last = talks[-1].get("time")
            if last:
                self.sio.update_last_time(float(last))
        self.logger.info("rewind 补消息完成，共 %d 条", len(msgs))

    async def _handle_leave(self, data: Any) -> None:
        """处理 leave 事件（自己被踢/封/主动离开）。"""
        reason = (data or {}).get("reason", "leave") if isinstance(data, dict) else "leave"
        self.logger.warning("收到 leave 事件，reason=%s", reason)
        self.room_connected = False
        # 等待离场后重新加入
        await self._rejoin()

    async def _rejoin(self) -> None:
        """重新进入房间。"""
        for _ in range(5):
            await asyncio.sleep(3)
            self.logger.info("重新进入房间 %s ...", self.room_id)
            self.room = Room()
            if await self.http.join_room(self.room_id, self.room):
                self.room_connected = True
                self.history.mark_joined()
                await self._load_own_user()
                self.logger.info("重新加入房间【%s】", self.room.name)
                return
        self.logger.error("重新进入房间多次失败")

    async def _load_own_user(self) -> None:
        """从房间用户表定位自己的 User 对象。"""
        # 从 /room/?api=json 获取 profile.uid
        try:
            await self.http._throttle()
            resp = await self.http.session.get(f"{ENDPOINT}/room/?api=json")
            data = resp.json()
            uid = data.get("profile", {}).get("uid")
            if uid:
                self.own_user = self.room.users.get(str(uid))
        except Exception:
            self.logger.debug("获取 own_user 失败", exc_info=True)

    # ------------------------------------------------------------------
    # 消息处理
    # ------------------------------------------------------------------
    async def _process_message(self, msg: Message) -> None:
        """消息统一处理：去重 → 历史过滤 → 状态维护 → 分发。"""
        # 去重
        if msg.id is not None:
            if not self.dedup.check_and_mark(msg.id):
                return

        # 历史过滤（加入房间之前的消息忽略）
        if msg.time and msg.time < self.history.join_time:
            return

        # /stop 退出命令：关闭 Socket.IO，使 run_forever 正常返回，
        # 进而 _run 返回、start 的 finally 调用 stop() 完成清理。
        # （不能用 loop.stop()：asyncio.run 下会抛 RuntimeError 且不清理资源）
        if msg.content == "/stop":
            self.send("已停止运行")
            await asyncio.sleep(2)
            if self.sio:
                self.sio.close()
            return

        # 日志（控制台 + CSV 落盘）
        if msg.content and msg.content != "keep":
            user = msg.sender.name if msg.sender else "系统消息"
            self.logger.info("%s | %s", user, msg.content)
            tripcode = msg.sender.tc if msg.sender else ""
            self.messages_log.log(user, tripcode, msg.content)

        # 房间状态维护 + 分发
        if msg.type == MessageType.JOIN:
            await self.http.update_room_state(self.room)
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.LEAVE:
            if msg.sender is not None and msg.sender.id == getattr(self.own_user, "id", None):
                self.room_connected = False
                self.room = Room()
                self.own_user = None
                await self._rejoin()
                return
            await self.http.update_room_state(self.room)
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.NEW_HOST:
            if msg.sender is not None:
                self.room.host_id = msg.sender.id
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.KICK:
            target = msg.target
            if isinstance(target, User):
                self.room.users.pop(target.id, None)
                # 自己被踢出：清空状态并等待重新加入
                if target.id == getattr(self.own_user, "id", None):
                    self.room_connected = False
                    self.room = Room()
                    self.own_user = None
                    await self._rejoin()
                    return
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.BAN:
            banned_id = msg.target.id if isinstance(msg.target, User) else msg.target
            if banned_id and str(banned_id) != getattr(self.own_user, "id", None):
                self.room.banned_ids.add(str(banned_id))
                self.room.users.pop(str(banned_id), None)
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.UNBAN:
            if isinstance(msg.target, User):
                self.room.banned_ids.discard(msg.target.id)
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.SYSTEM:
            await self.http.update_room_state(self.room)
            await self.registry.dispatch(msg)

        elif msg.type in (MessageType.ROOM_PROFILE, MessageType.NEW_DESCRIPTION):
            await self.http.update_room_state(self.room)
            await self.registry.dispatch(msg)

        elif msg.type == MessageType.MUSIC:
            if isinstance(msg, Message):
                self.room.music_np = msg.content
            await self.registry.dispatch(msg)

        else:
            # 普通消息 / 私信 / me / url
            await self.registry.dispatch(msg)

    # ------------------------------------------------------------------
    # 发送队列
    # ------------------------------------------------------------------
    async def _send_loop(self) -> None:
        """发送循环：按 throttle 间隔消费发送队列。"""
        self.logger.debug("发送循环启动")
        while True:
            item = await self._send_queue.get()
            await self.sender.acquire()
            try:
                await self._do_send(item)
            except Exception:
                self.logger.exception("发送失败: %r", item)

    async def _do_send(self, item: Any) -> None:
        """根据出站类型组装并发送 HTTP POST。"""
        if not self.room_connected:
            self.logger.warning("尚未连接房间，丢弃出站消息")
            return

        t = item.type
        if t == OutgoingType.MESSAGE:
            data = {"message": item.msg}
        elif t == OutgoingType.DM:
            data = {"message": item.msg, "to": item.receiver}
        elif t == OutgoingType.URL:
            data = {"message": item.msg, "url": item.url}
        elif t == OutgoingType.DM_URL:
            data = {"message": item.msg, "url": item.url, "to": item.receiver}
        elif t == OutgoingType.MUSIC:
            data = {"music": "music", "name": item.name, "url": item.url}
        elif t == OutgoingType.HANDOVER_HOST:
            data = {"new_host": item.receiver}
        elif t == OutgoingType.KICK:
            data = {"kick": item.receiver}
        elif t == OutgoingType.BAN:
            data = {"ban": item.receiver}
        elif t == OutgoingType.CHANGE_TITLE:
            data = {"room_name": item.title}
        elif t == OutgoingType.CHANGE_DESCRIPTION:
            data = {"room_description": item.description}
        elif t == OutgoingType.UNBAN:
            data = {"unban": item.receiver}
        elif t == OutgoingType.LEAVE:
            data = {"leave": "leave"}
        elif t == OutgoingType.MUSIC_SKIP:
            data = {"message": "/skip"}
        elif t == OutgoingType.ROOM_LIMIT:
            data = {"room_limit": item.receiver}
        elif t == OutgoingType.DJ_MODE:
            data = {"dj_mode": item.receiver}
        elif t == OutgoingType.MUSIC_FULL_MODE:
            data = {"music_full_mode": item.receiver}
        elif t == OutgoingType.LEGACY:
            data = item.data
        else:
            self.logger.error("未知出站类型: %s", t)
            return

        ok = await self.http.send_post(data)
        if not ok:
            self.logger.warning("发送未成功: %r", data)

    def _enqueue(self, item: Any) -> None:
        """把出站消息放入发送队列（线程安全）。"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(self._send_queue.put_nowait, item)
        else:
            self._send_queue.put_nowait(item)

    def _chunk_and_enqueue(self, text: str, builder) -> None:
        """按 140 字符分块后入队。"""
        chunked = [text[i : i + CHAR_LIMIT] for i in range(0, len(text), CHAR_LIMIT)]
        for chunk in chunked:
            self._enqueue(builder(chunk))

    # ------------------------------------------------------------------
    # 对外 API（同步，线程安全）
    # ------------------------------------------------------------------
    def send(self, msg: str) -> None:
        """发送消息（自动按 140 字符分块）。"""
        self._chunk_and_enqueue(msg, lambda c: OutgoingMessage(msg=c))

    def me(self, msg: str) -> None:
        """发送 /me 动作消息。"""
        self.send(f"/me{msg}")

    def dm(self, receiver: str, msg: str) -> None:
        """发送私信。"""
        self._chunk_and_enqueue(
            msg, lambda c: OutgoingDirectMessage(msg=c, receiver=receiver)
        )

    def send_url(self, msg: str, url: str) -> None:
        """发送带链接的消息（链接追加在最后一块）。"""
        chunked = [msg[i : i + CHAR_LIMIT] for i in range(0, len(msg), CHAR_LIMIT)]
        if len(chunked) == 1:
            self._enqueue(OutgoingUrlMessage(msg=chunked[0], url=url))
            return
        for c in chunked[:-1]:
            self._enqueue(OutgoingMessage(msg=c))
        self._enqueue(OutgoingUrlMessage(msg=chunked[-1], url=url))

    def dm_url(self, receiver: str, msg: str, url: str) -> None:
        """发送带链接的私信。"""
        chunked = [msg[i : i + CHAR_LIMIT] for i in range(0, len(msg), CHAR_LIMIT)]
        if len(chunked) == 1:
            self._enqueue(OutgoingDmUrl(msg=chunked[0], receiver=receiver, url=url))
            return
        for c in chunked[:-1]:
            self._enqueue(OutgoingDirectMessage(msg=c, receiver=receiver))
        self._enqueue(OutgoingDmUrl(msg=chunked[-1], receiver=receiver, url=url))

    def music(self, name: str, url: str) -> None:
        """点歌。"""
        self._enqueue(OutgoingMusic(name=name, url=url))

    def chown(self, receiver: str) -> None:
        """转让房主。"""
        self._enqueue(OutgoingHandoverHost(receiver=receiver))

    def kick(self, receiver: str) -> None:
        """踢人。"""
        self._enqueue(OutgoingKick(receiver=receiver))

    def ban(self, receiver: str) -> None:
        """封禁。"""
        self._enqueue(OutgoingBan(receiver=receiver))

    def unban(self, receiver: str) -> None:
        """解封。"""
        self._enqueue(OutgoingLegacy(data={"unban": receiver}))

    def title(self, name: str) -> None:
        """修改房间名。"""
        self._enqueue(OutgoingChangeTitle(title=name))

    def desc(self, description: str) -> None:
        """修改房间描述。"""
        self._enqueue(OutgoingChangeDescription(description=description))

    def leave_room(self) -> None:
        """离开房间。"""
        self._enqueue(OutgoingLegacy(data={"leave": "leave"}))

    def music_skip(self) -> None:
        """切歌。"""
        self._enqueue(OutgoingLegacy(data={"message": "/skip"}))

    def room_limit(self, limit: int) -> None:
        """修改房间人数上限。"""
        self._enqueue(OutgoingLegacy(data={"room_limit": str(limit)}))

    def toggle_dj_mode(self, enabled: bool = True) -> None:
        """切换 DJ 模式。"""
        self._enqueue(OutgoingLegacy(data={"dj_mode": enabled}))

    def toggle_music_full_mode(self, enabled: bool = True) -> None:
        """切换全音量模式。"""
        self._enqueue(OutgoingLegacy(data={"music_full_mode": enabled}))

    def find_user(self, name: str | None = None, tc: str | None = None) -> str | None:
        """按用户名或 tripcode 查找用户 ID。"""
        for user in self.room.users.values():
            if tc and user.tc == tc:
                return user.id
            if name and user.name == name:
                return user.id
        return None

    def findUser(self, name: str | None = None, tc: str | None = None) -> str | None:
        """兼容旧版命名。"""
        return self.find_user(name=name, tc=tc)
