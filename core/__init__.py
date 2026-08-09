"""核心设施：消息解析、限速去重、模块注册、配置、日志。"""

from .limits import Deduplicator, RateLimiter
from .parser import Parser

__all__ = ["Deduplicator", "RateLimiter", "Parser"]
