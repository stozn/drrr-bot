"""drrr-py-bot 入口程序。

流程：
1. 初始化日志
2. 加载 config.txt 配置
3. 创建 BotClient
4. 加载 config.mods 中声明的模块
5. 启动机器人（登录 → 进房 → Socket.IO 接收 → 分发）
"""

from __future__ import annotations

import asyncio
import logging

from bot import BotClient
from core.config import load_config
from core.logger import get_logger, setup_logger

logger = get_logger("main")


def main() -> None:
    setup_logger(level=logging.INFO)
    logger.info("程序启动")

    config = load_config()
    logger.info("配置：%s", config)
    logger.info("加载模块：%s", ", ".join(config.mods))

    bot = BotClient(config=config)

    async def run() -> None:
        bot.registry.load(config.mods)
        await bot.start()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    except Exception:
        logger.exception("程序异常退出")
    finally:
        logger.info("程序结束")


if __name__ == "__main__":
    main()
