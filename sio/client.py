"""手动实现的轻量 Socket.IO 客户端。

背景
----
drrr.com 使用 Socket.IO（Engine.IO v4 over WebSocket）推送实时消息。
python-socketio 的标准 WebSocket 实现会被 Cloudflare 的 TLS 指纹检测拦截，
而 curl_cffi 的 ``WebSocket``（``impersonate='chrome'``）可以正常握手。

因此这里基于 curl_cffi WebSocket 手动实现 Engine.IO/Socket.IO 协议，
只覆盖本机器人所需的子集：

- Engine.IO v4 帧：``0``(open) / ``1``(close) / ``2``(ping) / ``3``(pong) / ``4``(message)
- Socket.IO 包：``40``(connect) / ``41``(disconnect) / ``42``(event) / ``43``(ack) / ``44``(connect_error)
- 心跳：收到服务端 ping(``2``) 回 pong(``3``)，同时按 open 帧的 pingInterval 兜底保活
- 重连：断线后指数退避重连；首次连接发 ``config``，重连发 ``recover:{last_time}`` 补消息

线程模型
--------
curl_cffi 的 ``recv()`` 是阻塞调用，不能直接放进 asyncio 事件循环。
因此用一个后台线程跑 ``recv`` 循环，把收到的文本帧放入 ``asyncio.Queue``，
事件循环侧通过 ``run()`` 消费队列并分发。发送则直接在主线程调用 ``send()``
（libcurl 支持全双工，recv/send 可并发，但要避免同一函数跨线程同时调用）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from curl_cffi import CurlWsFlag, WebSocket

from core.logger import get_logger

# ---- Engine.IO 帧类型 ----
EIO_OPEN = "0"
EIO_CLOSE = "1"
EIO_PING = "2"
EIO_PONG = "3"
EIO_MESSAGE = "4"
EIO_UPGRADE = "5"
EIO_NOOP = "6"

# ---- Socket.IO 包类型（位于 Engine.IO message 内） ----
SIO_CONNECT = "0"
SIO_DISCONNECT = "1"
SIO_EVENT = "2"
SIO_ACK = "3"
SIO_ERROR = "4"

# drrr 前端连接参数（见 assets/drrr_app.js: io({path:"/conn/", query:{version:"4.1"}})
WS_PATH = "/conn/"
WS_QUERY_VERSION = "4.1"

EventHandler = Callable[[str, Any], Awaitable[None] | None]
DisconnectHandler = Callable[[], Awaitable[None] | None]


class SIoClient:
    """手动 Socket.IO 客户端。"""

    def __init__(
        self,
        *,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: str | None = None,
        impersonate: str = "chrome",
        logger: logging.Logger | None = None,
    ) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.cookies = cookies
        self.impersonate = impersonate
        self.logger = logger or get_logger("sio")

        self._ws: WebSocket | None = None
        self._recv_thread: threading.Thread | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = threading.Event()
        self._send_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

        # open 帧携带的服务器配置
        self.sid: str | None = None
        self.ping_interval: float = 25000.0
        self.ping_timeout: float = 20000.0

        # 事件处理器
        self._event_handlers: list[EventHandler] = []
        self._disconnect_handlers: list[DisconnectHandler] = []

        # 心跳兜底任务
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._last_ping_at: float = 0.0

        # 重连状态
        self._reconnect_delay: float = 3.0
        self._manual_close = False
        self.last_time: float = 0.0

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """建立 WebSocket 连接（阻塞，同步握手）。

        完成 Engine.IO 握手，并在后台启动 recv 线程。
        """
        if self._ws is not None:
            return
        self.logger.info("正在连接 %s ...", self.url)
        ws = WebSocket()
        params = {"EIO": "4", "transport": "websocket", "version": WS_QUERY_VERSION}
        ws.connect(
            self.url,
            params=params,
            headers=self.headers or None,
            cookies=self.cookies,
            impersonate=self.impersonate,
            # 不自动跟随重定向，连接握手是 101 升级
            allow_redirects=False,
        )
        self._ws = ws
        self._manual_close = False
        self._running.set()
        self._recv_thread = threading.Thread(
            target=self._recv_loop, name="sio-recv", daemon=True
        )
        self._recv_thread.start()
        self.logger.info("WebSocket 已连接")

    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    # ------------------------------------------------------------------
    # 事件注册
    # ------------------------------------------------------------------
    def on_event(self, handler: EventHandler) -> None:
        """注册事件处理器，接收 ``(event_name, data)``。"""
        self._event_handlers.append(handler)

    def on_disconnect(self, handler: DisconnectHandler) -> None:
        """注册断线回调。"""
        self._disconnect_handlers.append(handler)

    # ------------------------------------------------------------------
    # 发送
    # ------------------------------------------------------------------
    def send(self, payload: str) -> None:
        """发送一条 Engine.IO 文本帧（线程安全）。"""
        ws = self._ws
        if ws is None or ws.closed:
            self.logger.warning("WebSocket 未连接，丢弃发送: %r", payload[:80])
            return
        with self._send_lock:
            try:
                ws.send_str(payload)
            except Exception as e:
                self.logger.error("发送失败: %s", e)

    def send_event(self, event: str, data: Any = None) -> None:
        """发送 Socket.IO 事件包 ``42["event", data]``。"""
        payload = json.dumps([event, data], ensure_ascii=False)
        self.send(EIO_MESSAGE + SIO_EVENT + payload)

    def send_ack(self, ack_id: int) -> None:
        """回应带 ack 的事件。

        Socket.IO v5 的 ACK 编码：``43<ack_id><args_json>``，
        ack id 直接跟在类型号后（无 ``[``），args 为 JSON 数组。
        无回传参数时为 ``43<ack_id>[]``。
        """
        payload = f"{ack_id}[]"
        self.send(EIO_MESSAGE + SIO_ACK + payload)

    def send_ping(self) -> None:
        """主动发送 ping（Engine.IO v4 客户端也可发 ping 探测）。"""
        self.send(EIO_PING)

    def send_pong(self) -> None:
        """回复 pong。"""
        self.send(EIO_PONG)

    def send_config(self, config: dict[str, Any]) -> None:
        """首次连接后发送 config 事件。"""
        self.send_event("config", config)

    def send_recover(self, last_time: float) -> None:
        """重连后发送 recover 事件请求补消息。"""
        self.send_event("recover", {"last_time": last_time})

    # ------------------------------------------------------------------
    # 后台接收线程
    # ------------------------------------------------------------------
    def _recv_loop(self) -> None:
        """后台线程：阻塞读取 WebSocket 帧并投递到 asyncio 队列。"""
        ws = self._ws
        if ws is None:
            return
        while self._running.is_set():
            try:
                data, flags = ws.recv()
            except Exception as e:
                if self._running.is_set():
                    self.logger.warning("接收线程退出: %s", e, exc_info=True)
                break
            if not data:
                continue
            # 只处理文本帧（Engine.IO 全部为文本）
            if flags & CurlWsFlag.TEXT:
                text = data.decode("utf-8", errors="replace")
                self.logger.debug("recv frame flags=%s len=%d head=%r",
                                  flags, len(text), text[:60])
                if self._loop is None:
                    self.logger.warning("事件循环未绑定，丢弃收到的帧")
                    continue
                self._loop.call_soon_threadsafe(self._queue.put_nowait, text)
            # 对端关闭
            if flags & CurlWsFlag.CLOSE:
                self.logger.info("收到 WebSocket 关闭帧")
                break
        self._running.clear()
        if self._loop is not None and not self._manual_close:
            self._loop.call_soon_threadsafe(self._notify_disconnect)

    def _notify_disconnect(self) -> None:
        for handler in self._disconnect_handlers:
            try:
                coro = handler()
                if coro is not None and self._loop is not None:
                    self._loop.create_task(coro)
            except Exception:
                self.logger.exception("断线回调执行失败")

    # ------------------------------------------------------------------
    # 主事件循环
    # ------------------------------------------------------------------
    async def run(self) -> None:
        """消费接收队列，解析帧并分发。异常时抛出以便上层重连。"""
        self._loop = asyncio.get_running_loop()
        while self._running.is_set():
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            self._handle_frame(frame)

    async def run_forever(self, config: dict[str, Any]) -> None:
        """连接 + 心跳 + 消费循环 + 自动重连。

        该协程**永不返回**（除非手动调用 :meth:`close`），断线后内部
        以指数退避自动重连，保证上层 ``await`` 不会因断线而退出。
        """
        # 先绑定事件循环，供 recv 后台线程回调投递
        self._loop = asyncio.get_running_loop()

        while not self._manual_close:
            try:
                await self._connect_once(config)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error("连接失败: %s", e)

            # 手动关闭则退出循环
            if self._manual_close:
                return
            # 清理本次连接资源后等待重连
            self.close(notify=False)
            delay = self._reconnect_delay
            self.logger.info("将在 %.1f 秒后重连...", delay)
            await asyncio.sleep(delay)
            self._reconnect_delay = min(delay * 2 + random.uniform(0, 1), 60)

    async def _connect_once(self, config: dict[str, Any]) -> None:
        """单次连接：握手 -> 40 -> config -> 消费循环。

        连接断开（对端关闭/异常）时正常返回，由 :meth:`run_forever` 决定重连。
        """
        self.connect()
        # 读取 open 帧
        frame = await asyncio.wait_for(self._queue.get(), timeout=15.0)
        self._handle_frame(frame)
        if not self.sid:
            raise RuntimeError("Socket.IO 握手未完成（未收到 open 帧）")

        # 连接默认命名空间（40）
        self.send(EIO_MESSAGE + SIO_CONNECT)
        # 等待服务器确认命名空间连接（40{...}）后再发送业务事件。
        # 实测 drrr 服务器对「40 后立即 config」的包会直接断开连接，
        # 必须先等 connect ack 到达（见 _dbg_sio4/_dbg_sio5 对照实验）。
        try:
            frame = await asyncio.wait_for(self._queue.get(), timeout=10.0)
            self._handle_frame(frame)
        except asyncio.TimeoutError:
            self.logger.warning("等待命名空间连接确认超时，继续尝试发送 config")

        # 首次连接发送 config，重连发送 recover
        if self.last_time:
            self.send_recover(self.last_time)
        else:
            self.send_config(config)

        # 启动心跳兜底
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        try:
            await self.run()
        finally:
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            # 本次连接结束，若尚未手动关闭则触发断线回调（供上层清理状态）
            if not self._manual_close:
                self._notify_disconnect()

    # ------------------------------------------------------------------
    # 帧解析
    # ------------------------------------------------------------------
    def _handle_frame(self, frame: str) -> None:
        if not frame:
            return
        eio_type = frame[0]
        body = frame[1:]

        if eio_type == EIO_OPEN:
            self._handle_open(body)
        elif eio_type == EIO_PING:
            self._last_ping_at = time.monotonic()
            self.send_pong()
        elif eio_type == EIO_PONG:
            self._last_ping_at = time.monotonic()
        elif eio_type == EIO_MESSAGE:
            self._handle_sio_packet(body)
        elif eio_type == EIO_CLOSE:
            self.logger.info("服务器关闭连接")
        else:
            self.logger.debug("忽略 Engine.IO 帧: %r", frame)

    def _handle_open(self, body: str) -> None:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.logger.error("open 帧解析失败: %r", body[:200])
            return
        self.sid = data.get("sid")
        self.ping_interval = data.get("pingInterval", 25000) / 1000.0
        self.ping_timeout = data.get("pingTimeout", 20000) / 1000.0
        self._last_ping_at = time.monotonic()
        self.logger.info(
            "Socket.IO 握手成功 sid=%s ping=%.1fs timeout=%.1fs",
            self.sid, self.ping_interval, self.ping_timeout,
        )

    def _handle_sio_packet(self, packet: str) -> None:
        if not packet:
            return
        ptype = packet[0]
        body = packet[1:]

        if ptype == SIO_EVENT:
            self._dispatch_event(body)
        elif ptype == SIO_ACK:
            self.logger.debug("收到 ack: %r", body[:200])
        elif ptype == SIO_CONNECT:
            self.logger.info("Socket.IO 命名空间连接成功")
        elif ptype == SIO_DISCONNECT:
            self.logger.info("Socket.IO 断开")
        elif ptype == SIO_ERROR:
            self.logger.warning("Socket.IO 错误: %r", body[:200])
        else:
            self.logger.debug("忽略 Socket.IO 包: %r", packet[:200])

    def _dispatch_event(self, body: str) -> None:
        """解析 ``42[...]`` 事件包的 data 部分。

        drrr 使用的是 Socket.IO v5 协议，事件编码为：
        - 无 ack：``42["event", data]``
        - 带 ack：``42<ackId>["event", data]``（ack id 直接跟在类型号后）

        实测收到的 ``new-talk`` 事件为 ``42 7286786 ["new-talk", {...}]``，
        ack id 与 JSON 之间没有 ``[``（见线上帧: ``'427286786["new-talk",...]'``）。
        收到带 ack 的事件需回复 ``43[ackId]``。
        """
        # 提取可选的 ack id 前缀（Socket.IO v5 编码：类型号 + ackId + JSON）
        ack_id: int | None = None
        i = 0
        while i < len(body) and body[i].isdigit():
            i += 1
        if i:
            try:
                ack_id = int(body[:i])
            except ValueError:
                ack_id = None
            body = body[i:]

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.logger.error("事件包解析失败: %r", body[:200])
            return
        if not isinstance(payload, list) or not payload:
            self.logger.warning("非法事件包: %r", body[:200])
            return

        event = payload[0]
        data = payload[1] if len(payload) > 1 else None

        self.logger.debug("收到事件 %s%s", event, f"(ack={ack_id})" if ack_id else "")
        for handler in self._event_handlers:
            try:
                result = handler(event, data)
                if asyncio.iscoroutine(result):
                    if self._loop is not None:
                        self._loop.create_task(result)
            except Exception:
                self.logger.exception("事件处理器执行失败: %s", event)

        if ack_id is not None:
            self.send_ack(ack_id)

    # ------------------------------------------------------------------
    # 心跳兜底
    # ------------------------------------------------------------------
    async def _heartbeat_loop(self) -> None:
        """兜底保活：服务端正常发 ping 时会被上面及时 pong 回复。

        此处仅处理"长时间未收到任何 ping/pong"的极端情况：
        超过 pingInterval + pingTimeout 时主动发 ping 探测。
        """
        interval = max(self.ping_interval, 5.0)
        while self._running.is_set():
            await asyncio.sleep(interval)
            if not self._running.is_set():
                break
            idle = time.monotonic() - self._last_ping_at
            if idle > self.ping_interval + self.ping_timeout:
                self.logger.warning("心跳超时(%.1fs)，主动 ping", idle)
                self.send_ping()

    # ------------------------------------------------------------------
    # 重连 / 关闭
    # ------------------------------------------------------------------
    def close(self, notify: bool = True) -> None:
        """关闭连接并停止后台线程。"""
        self._manual_close = True
        self._running.clear()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if notify and self._loop is not None:
            self._loop.call_soon_threadsafe(self._notify_disconnect)

    def update_last_time(self, t: float) -> None:
        """记录最近一次消息时间，供重连 recover 使用。"""
        if t:
            self.last_time = max(self.last_time, t)
