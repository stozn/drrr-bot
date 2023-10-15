import asyncio
import copy
import os
import sys
import traceback
import networking
import importlib
import concurrent.futures
from modules import module
import logging

defaultConfig = {
  'name': 'test',
  'tc': 'None',
  'avatar': 'setton',
  'agent': 'Bot',
  'roomID': 'gV8M14bkrv',
  'throttle': 1.5,
  'mods' : ['Test', 'BingTa']
}

config = copy.deepcopy(defaultConfig)
if not os.path.exists('config.txt'):
    with open('config.txt', 'w') as f:
        for key, value in config.items():
            if key != 'mods':
                f.write(f"{key} = {value}\n")
            else:
                f.write(f"{key} = {', '.join(value)}\n")

with open('config.txt', 'r', encoding='utf8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        key, value = [x.strip() for x in line.split('=')]
        if(key=='mods'):
            value = [x.strip() for x in value.split(',')]
        elif(key=='throttle'):
            value = float(value)
        config[key] = value

print('配置：')
for k, v in config.items():
    print(f'   {k}: {v}')
print()

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
    logger.info('\033[1;36m' + f'加载模块【{name}】' + '\033[0m')
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
    bot = networking.Connection(config['name'], config['tc'], config['avatar'], config['roomID'], config['agent'], config['throttle'], handler, loop)
    for mod in config['mods']:
        load_module(mod, bot)

    bot.start()