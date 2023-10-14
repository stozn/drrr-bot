import asyncio
import sys
import traceback
import networking
import importlib
import concurrent.futures
from modules import module
import logging

# =============配置======================
                                        #
name = 'Bot'                            # 机器人名字
icon = 'kanra'                          # 机器人头像
roomID = 'UgaX0cBVAT'                   # 房间ID
modsToLoad = ['Test', 'BingTa']         # 要加载的模块
                                        # 
# ======================================
modules = {}
mods_dir = 'modules'
logger = logging.getLogger(__name__)


def load_module(name, bot):
    importlib.invalidate_caches()
    if name in modules.keys():
        logger.error(f'模块【{name}】已存在')
        return False
    try:
        mod = importlib.import_module(mods_dir + '.' + name)
    except ModuleNotFoundError:
        logger.error(f'未找到模块【{name}】')
        return False

    try:
        cls = getattr(mod, name)
    except AttributeError:
        logger.error('模块必须有一个与自身同名的顶级类')
        return False

    if not issubclass(cls, module.Module):
        logger.error('模块的顶级类必须继承自 module.Module')
        return False
    logger.info(f'加载模块【{name}】')
    modules[name] = cls(bot)

def unload_module(name):
    try:
        modules[name].unload()
        modules[name].cancel_all_event_loops()

        del modules[name]
        del sys.modules[mods_dir + '.' + name]
        del sys.modules[mods_dir + '.' + name + '.' + name]
        for mod in list(sys.modules.keys()):
            if mod.startswith(mods_dir + '.' + name ):
                del sys.modules[mod]

    except KeyError:
        logger.error(f'模块【{name}】未加载')
    except Exception:
        logger.error(traceback.format_exc())

executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
async def handler(msg):
    for k, v in modules.items():
        # logger.debug(f'模块【{k}】处理消息')
        loop.run_in_executor(executor, v.handler, msg)


if __name__ == '__main__':
    logger.info('程序启动')
    loop = asyncio.get_event_loop()
    bot = networking.Connection(name, icon, roomID, handler, loop)
    for mod in modsToLoad:
        load_module(mod, bot)

    bot.start()