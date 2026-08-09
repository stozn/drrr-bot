"""HTTP 会话层。

基于 curl_cffi 的 ``AsyncSession``，负责：

- 登录：GET 首页提取 token/nonce/timestamp/difficulty，求解 PoW 后 POST 提交
- 恢复登录：从 cookie 文件加载登录态
- 进入房间：GET 房间页提取 PoW 挑战，带 ``challenged`` 提交
- 发送消息：POST ``/room/?ajax=1&api=json``
- 全局 QPS 限速：保证任意两次请求之间至少间隔 ``qps`` 秒
- Cookie 持久化：保存到 ``cookies/<name>.cookie``，支持断线恢复

所有公开方法均为 async，且自带 QPS 限速。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import RequestException

from core.logger import get_logger

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ENDPOINT = "https://drrr.com"
COOKIE_DIR = "cookies"
MAX_RETRIES = 10


@dataclass(slots=True)
class LoginResult:
    """登录/进房结果。"""

    ok: bool
    location: str = ""
    body: str = ""
    status: int = 0


def solve_challenge(nonce: str, timestamp: str, difficulty: int) -> dict[str, Any]:
    """求解 drrr.com 的 PoW（Proof of Work）挑战。

    与前端 JS 一致：``sha256(nonce + timestamp + counter)`` 的十六进制结果
    以 ``difficulty`` 个 ``0`` 开头，``counter`` 从 1 开始递增。

    Args:
        nonce: 页面下发的随机数。
        timestamp: 页面下发的时间戳。
        difficulty: 难度（前导 0 个数）。

    Returns:
        与前端格式一致的 solved 字典（challenged 参数值）。
    """
    prefix = "0" * int(difficulty)
    counter = 1
    while True:
        h = hashlib.sha256(
            f"{nonce}{timestamp}{counter}".encode("utf-8")
        ).hexdigest()
        if h.startswith(prefix):
            break
        counter += 1
    return {
        "hash": h,
        "nonce": nonce,
        "timestamp": str(timestamp),
        "counter": counter,
        "difficulty": str(difficulty),
    }


class HttpSession:
    """基于 curl_cffi AsyncSession 的 drrr HTTP 会话。"""

    def __init__(
        self,
        *,
        username: str,
        qps: float = 0.0,
        ua: str = DEFAULT_UA,
        cookie_dir: str = COOKIE_DIR,
        logger: logging.Logger | None = None,
    ) -> None:
        self.username = username
        self.qps_interval = max(qps, 0.0)
        self.ua = ua
        self.logger = logger or get_logger("http")

        # cookie 持久化
        self.cookie_dir = cookie_dir
        if not os.path.isdir(self.cookie_dir):
            os.makedirs(self.cookie_dir, exist_ok=True)
        self.cookie_file = os.path.join(self.cookie_dir, f"{username}.cookie")

        # 会话（惰性创建，需在事件循环内）
        self._session: AsyncSession | None = None
        self._qps_last = 0.0
        self._qps_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------
    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                headers={"User-Agent": self.ua},
                impersonate="chrome",
                timeout=30,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # QPS 限速
    # ------------------------------------------------------------------
    async def _throttle(self) -> None:
        """全局 QPS 限速：保证任意两次请求之间至少间隔 qps 秒。"""
        async with self._qps_lock:
            now = time.monotonic()
            wait = self._qps_last + self.qps_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._qps_last = time.monotonic()

    # ------------------------------------------------------------------
    # 基础请求
    # ------------------------------------------------------------------
    async def _get(self, url: str, **kwargs: Any) -> Response:
        await self._throttle()
        return await self.session.get(url, **kwargs)

    async def _post(self, url: str, **kwargs: Any) -> Response:
        await self._throttle()
        return await self.session.post(url, **kwargs)

    # ------------------------------------------------------------------
    # HTML 表单字段提取
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_field(html: str, name: str) -> str | None:
        """从 HTML 表单中提取隐藏字段值（兼容 data-value 与 value）。"""
        m = re.search(name + r'"(?: data-value| value)="([^"]*)"', html)
        if m:
            return m.group(1)
        m = re.search(r'name="' + name + r'"[^>]*(?: data-value| value)="([^"]*)"', html)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------
    async def get_login_page(self) -> dict[str, str] | None:
        """GET 首页，提取登录表单的 token 与 PoW 挑战字段。"""
        try:
            resp = await self._get(f"{ENDPOINT}/")
        except RequestException as e:
            self.logger.error("获取登录页失败: %s", e)
            return None
        if resp.status_code != 200:
            self.logger.error("获取登录页失败，status=%s", resp.status_code)
            return None
        html = resp.text
        return {
            "token": self._extract_field(html, "token"),
            "nonce": self._extract_field(html, "nonce"),
            "timestamp": self._extract_field(html, "timestamp"),
            "difficulty": self._extract_field(html, "difficulty"),
        }

    async def post_login(self, page: dict[str, str]) -> LoginResult:
        """求解 PoW 并提交登录表单。"""
        solved = solve_challenge(
            page["nonce"], page["timestamp"], int(page["difficulty"] or 1)
        )
        data = {
            "name": self.username,
            "tripcode": "",
            "login": "ENTER",
            "token": page["token"],
            "nonce": page["nonce"],
            "timestamp": str(page["timestamp"]),
            "difficulty": str(page["difficulty"]),
            "challenged": json.dumps(solved),
        }
        # tripcode 单独处理：登录页没有 tripcode 字段时后端从表单读
        resp = await self._post(f"{ENDPOINT}/", data=data, allow_redirects=False)
        return LoginResult(
            ok=resp.status_code in (200, 302, 303),
            status=resp.status_code,
            location=resp.headers.get("Location", ""),
            body=resp.text[:300],
        )

    async def login(self, tc: str = "") -> bool:
        """执行登录。

        - 优先从 cookie 文件恢复
        - 否则新建登录并保存 cookie

        Returns:
            是否登录成功（进入大厅）。
        """
        if os.path.isfile(self.cookie_file):
            if await self.resume():
                return True
            self.logger.warning("cookie 无效，删除并重新登录")
            try:
                os.remove(self.cookie_file)
            except OSError:
                pass

        self.logger.info("新建登录中")
        for attempt in range(MAX_RETRIES):
            page = await self.get_login_page()
            if not page or not page.get("token"):
                self.logger.error("获取登录 token 失败")
                return False
            result = await self.post_login(page)
            self.logger.debug("登录响应: status=%s location=%s", result.status, result.location)
            if result.ok and result.location.startswith("/"):
                self.save_cookies()
                self.logger.info("登录成功")
                return True
            self.logger.error("登录失败: %s", result.body)
            await asyncio.sleep(2)
        return False

    async def resume(self) -> bool:
        """使用保存的 cookie 恢复登录。"""
        self.load_cookies()
        resp = await self._get(f"{ENDPOINT}/lounge?api=json")
        if resp.status_code == 200:
            self.logger.info("保存的 cookie 有效")
            return True
        if resp.status_code == 401:
            self.logger.warning("保存的 cookie 已失效")
        else:
            self.logger.error("恢复连接失败，status=%s", resp.status_code)
        return False

    # ------------------------------------------------------------------
    # Cookie 持久化
    # ------------------------------------------------------------------
    def save_cookies(self) -> None:
        """把当前会话 cookie 保存到文件（JSON 序列化）。"""
        try:
            data = {
                "cookies": list(self.session.cookies.items()),
                "saved_at": int(time.time()),
            }
            with open(self.cookie_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error("保存 cookie 失败: %s", e)

    def load_cookies(self) -> bool:
        """从文件加载 cookie 到会话。"""
        try:
            with open(self.cookie_file, encoding="utf-8") as fh:
                data = json.load(fh)
            for name, value in data.get("cookies", []):
                self.session.cookies.set(name, value)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            self.logger.warning("加载 cookie 失败: %s", e)
            return False

    # ------------------------------------------------------------------
    # 房间操作
    # ------------------------------------------------------------------
    async def update_room_state(self, room) -> bool:
        """获取房间当前状态并更新 Room 对象。

        Args:
            room: 待更新的 Room 对象。

        Returns:
            是否成功。
        """
        resp = await self._get(f"{ENDPOINT}/json.php?fast=1")
        if resp.status_code != 200:
            self.logger.error("获取房间状态失败，status=%s", resp.status_code)
            return False
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            self.logger.error("房间状态响应非 JSON")
            return False
        if "roomId" not in data:
            self.logger.warning("不在房间中或房间状态异常")
            return False
        return room.update_from_json(data)

    async def join_room(self, room_id: str, room) -> bool:
        """进入房间（带 PoW challenge）。

        Args:
            room_id: 目标房间 ID。
            room: 用于承载房间状态的 Room 对象。

        Returns:
            是否成功进入房间。
        """
        for _ in range(MAX_RETRIES):
            try:
                # 1. 获取房间页，提取 challenge
                resp = await self._get(f"{ENDPOINT}/room/?id={room_id}")
                html = resp.text
                nonce = self._extract_field(html, "nonce")
                timestamp = self._extract_field(html, "timestamp")
                difficulty = self._extract_field(html, "difficulty")
                if nonce and timestamp and difficulty:
                    solved = solve_challenge(nonce, timestamp, int(difficulty))
                    challenged = json.dumps(solved)
                    # 2. 带 challenged 提交进房间
                    resp = await self._get(
                        f"{ENDPOINT}/room/?id={room_id}&challenged={challenged}",
                        allow_redirects=False,
                    )
                    location = resp.headers.get("Location", "")
                    if resp.status_code in (200, 302) and location == "/room/":
                        if await self.update_room_state(room):
                            self.logger.info("成功加入房间【%s】", room.name)
                            return True
                        self.logger.warning("进入房间成功但无法获取房间信息")
                    else:
                        self.logger.warning(
                            "进入房间未成功: status=%s location=%s", resp.status_code, location
                        )
                else:
                    # Cloudflare 等中间层可能瞬时拦截房间页（返回验证页），
                    # 提取不到挑战表单时不应放弃，稍后重试
                    self.logger.warning(
                        "房间页未返回挑战表单（可能被 Cloudflare 拦截），重试中..."
                    )
            except RequestException as e:
                self.logger.error("进入房间时发生错误: %s", e)
            await asyncio.sleep(1)
        return False

    async def send_post(self, data: dict[str, Any], loudness: int | None = None) -> bool:
        """发送一条房间操作请求（聊天/私信/点歌/管理操作等）。

        Args:
            data: POST 表单字段。
            loudness: 可选，3 表示「轻言细语」（悄悄话保活）。

        Returns:
            是否成功（HTTP 200）。
        """
        payload = dict(data)
        if loudness is not None:
            payload["loudness"] = loudness
        for _ in range(MAX_RETRIES):
            try:
                resp = await self._post(
                    f"{ENDPOINT}/room/?ajax=1&api=json", data=payload
                )
                if resp.status_code == 200:
                    self.logger.debug("发送成功: %r", {k: v for k, v in data.items() if k != "message" or (k == "message" and v.strip(" \u200b"))})
                else:
                    self.logger.error("发送失败: status=%s data=%r", resp.status_code, data)
                return resp.status_code == 200
            except RequestException as e:
                self.logger.error("发送时产生错误: %s", e)
                await asyncio.sleep(1)
        return False
