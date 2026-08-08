"""drrr-py-bot 入口程序。

负责：
1. 加载并解析 config.txt 配置
2. 动态加载 modules 目录下的模块
3. 建立网络连接并启动消息处理循环
"""

import asyncio
import copy
import importlib
import logging
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

import networking
from modules import module

# 默认配置（当 config.txt 不存在或缺少字段时使用）
DEFAULT_CONFIG = {
    'name': 'test',
    'tc': '',
    'avatar': 'setton',
    'agent': 'Bot',
    'roomID': '6JjYq34S35',
    'throttle': 1.5,
    'mods': ['Test', 'GuessNumber'],
}

# 需要做类型转换的字段：{字段名: (类型转换函数, 是否列表)}
_TYPE_RULES = {
    'throttle': (float, False),
    'mods': (lambda s: [x.strip() for x in s.split(',')], True),
}

CONFIG_FILE = 'config.txt'
MODS_DIR = 'modules'

logger = logging.getLogger(__name__)
_modules = {}
_executor = ThreadPoolExecutor(max_workers=8)


def load_config():
    """加载配置文件，缺失的字段使用默认值。"""
    config = copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG_FILE):
        _write_default_config(config)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                logger.warning(f'配置行格式无效，已忽略: {line!r}')
                continue
            key, value = [x.strip() for x in line.split('=', 1)]
            if key not in config:
                logger.warning(f'未知配置项，已忽略: {key!r}')
                continue
            config[key] = _convert_value(key, value)
    return config


def _write_default_config(config):
    """将默认配置写入 config.txt。"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        for key, value in config.items():
            if key == 'mods':
                f.write(f"{key} = {', '.join(value)}\n")
            else:
                f.write(f"{key} = {value}\n")


def _convert_value(key, value):
    """按规则对配置值做类型转换。"""
    if key in _TYPE_RULES:
        converter, _ = _TYPE_RULES[key]
        try:
            return converter(value)
        except ValueError:
            logger.error(f'配置项 {key} 的值无效: {value!r}，使用默认值')
            return DEFAULT_CONFIG[key]
    return value


def _filename_to_classname(filename):
    """把模块文件名转换为对应的类名：qing_shu -> QingShu，music -> Music。"""
    parts = filename.split('_')
    return ''.join(p[:1].upper() + p[1:] for p in parts if p)


def load_module(name, bot):
    """动态加载并实例化一个模块。

    name 是模块文件名（如 qing_shu），类名由文件名推导（如 QingShu）。
    """
    if name in _modules:
        logger.error(f'模块【{name}】已存在')
        return False
    try:
        mod = importlib.import_module(f'{MODS_DIR}.{name}')
    except ModuleNotFoundError:
        logger.error(f'未找到模块【{name}】（请确认依赖已安装、文件名正确）')
        return False

    classname = _filename_to_classname(name)
    try:
        cls = getattr(mod, classname)
    except AttributeError:
        logger.error(f'模块 {name} 必须有一个顶级类 {classname}')
        return False

    if not issubclass(cls, module.Module):
        logger.error('模块的顶级类必须继承自 module.Module')
        return False

    logger.info('\033[1;36m' + f'加载模块【{name}】' + '\033[0m')
    _modules[name] = cls(bot)
    return True


def unload_module(name):
    """卸载指定模块。"""
    try:
        _modules[name].unload()
        _modules[name].cancel_all_event_loops()
        del _modules[name]
        for mod in list(sys.modules.keys()):
            if mod.startswith(f'{MODS_DIR}.{name}'):
                del sys.modules[mod]
    except KeyError:
        logger.error(f'模块【{name}】未加载')
    except Exception:
        logger.error(traceback.format_exc())


async def handler(msg, loop):
    """把消息分发给所有已加载的模块处理。"""
    for name, mod in _modules.items():
        loop.run_in_executor(_executor, mod.handler, msg)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    logger.info('程序启动')

    config = load_config()
    print('配置：')
    for k, v in config.items():
        print(f'   {k}: {v}')
    print()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = networking.Connection(
        config['name'], config['tc'], config['avatar'], config['roomID'],
        config['agent'], config['throttle'],
        lambda msg: handler(msg, loop), loop,
    )
    for mod in config['mods']:
        load_module(mod, bot)

    bot.start()


if __name__ == '__main__':
    main()
