"""手动实现的轻量 Socket.IO 客户端（基于 curl_cffi WebSocket）。"""

from .client import (
    SIO_ERROR,
    SIO_EVENT,
    SIO_CONNECT,
    SIO_DISCONNECT,
    SIO_ACK,
    SIoClient,
)

__all__ = [
    "SIO_ERROR",
    "SIO_EVENT",
    "SIO_CONNECT",
    "SIO_DISCONNECT",
    "SIO_ACK",
    "SIoClient",
]
