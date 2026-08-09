"""网络会话层：curl_cffi 封装（登录/进房/发送/PoW/QPS）。"""

from .session import HttpSession

__all__ = ["HttpSession"]
