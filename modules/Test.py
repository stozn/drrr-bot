"""示例模块：演示装饰器命令写法。"""

from __future__ import annotations

import operator

from modules.base import Module, command, on_event
from models import Message, MessageType


class Test(Module):
    @command(r"hi")
    def say_hello(self, msg: Message):
        """匹配包含 hi 的任意消息。"""
        self.bot.send(f"@{msg.user.name} 你好")

    @command(r"^/calc\s+\d+\s+[\+\-\*/]\s+\d+\s*$")
    def calculate(self, msg: Message):
        cont = msg.content.split(" ", 1)[1]
        # 用白名单运算符求值，禁止 eval()，防止任意代码执行
        try:
            result = self._safe_eval(cont)
        except (ValueError, ZeroDivisionError):
            self.bot.send(f"表达式无效: {cont}")
            return
        self.bot.send(f"{cont} = {result}")

    @command(r"^/chown")
    def chown(self, msg: Message):
        self.bot.chown(msg.user.id)

    @on_event(MessageType.JOIN)
    def welcome(self, msg: Message):
        self.bot.send(f"欢迎@{msg.user.name}进入房间")

    @staticmethod
    def _safe_eval(expr: str):
        """安全地计算形如 '1 + 2' 的四则运算表达式。"""
        left, op, right = expr.split()
        a, b = int(left), int(right)
        ops = {"+": operator.add, "-": operator.sub,
               "*": operator.mul, "/": operator.truediv}
        return ops[op](a, b)
