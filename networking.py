import asyncio
import os
import sys
import traceback
import datetime
import aiofiles
import aiohttp
import logging
import time
import json
import popyo
from curl_cffi import AsyncSession

path = os.path.dirname(__file__)
sys.path.append(path)

headers = {
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.160 Safari/537.36",
    "x-requested-with": "XMLHttpRequest"
}

proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

class Connection:
    def __init__(self, username, tc, avater, roomID, agent, throttle, msg_cb, loop):
        self.username = username
        self.tc = tc
        self.name_tc = username if tc == 'None' else username + '#' + tc
        self.avatar = avater
        self.room_connected = False
        self.room = None
        self.roomID = roomID
        self.own_user = None
        self.session = None
        self.endpoint = 'https://drrr.com'
        self.cookie_path = path + '/cookies'
        # self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.ua = agent
        self.cookies = {
            "drrr-session-1": input("【请输入cookies】\ndrrr-session-1: "),
            "cf_clearance": input("cf_clearance: ")
        }
        self.retries = 100
        self.sendQ = asyncio.Queue()
        self.throttle = throttle
        self.char_limit = 140
        self.msg_cb = msg_cb
        self.loop = loop
        self.logger = logging.getLogger()
        self.set_loglevel(logging.DEBUG)

        if not os.path.isdir(self.cookie_path):
            os.makedirs(self.cookie_path)
    
    def start(self):
        self.loop.run_until_complete(self.login())

    # 设置日志级别
    def set_loglevel(self, level):
        time_format = '%Y-%m-%d %H:%M:%S'
        debug_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', time_format)
        formatter = logging.Formatter('%(asctime)s | %(message)s', time_format)
        self.logger.setLevel(level)

        handler = logging.StreamHandler()
        handler.setLevel(level)
        if(level == logging.DEBUG):
            handler.setFormatter(debug_formatter)
        else:
            handler.setFormatter(formatter)

        self.logger.addHandler(handler)
    
    def debug(self, msg):
        self.logger.debug('\033[1;32m' + msg + '\033[0m')
    
    def info(self, msg):
        self.logger.info('\033[1;36m' + msg + '\033[0m')
    
    def warning(self, msg):
        self.logger.warning('\033[1;33m' + msg + '\033[0m')
    
    def error(self, msg):
        self.logger.error('\033[1;31m' + msg + '\033[0m')

    # 保存日志
    async def write(self, dir, content, ext='txt'):
        current_date = datetime.datetime.now().strftime('%Y年%m月%d日')
        current_time = datetime.datetime.now().strftime('%H:%M:%S ')
        dir = f'{path}/{dir}'
        file_name = f'{dir}/{current_date}.{ext}'
        if not os.path.isdir(dir):
            os.makedirs(dir)
        
        async with aiofiles.open(file_name, 'a', encoding='utf-8-sig') as file:
            await file.write(current_time +',' + content+'\n')

    # 新建会话
    async def get_session(self):
        if self.session is None:
            self.session = AsyncSession(headers=headers, cookies=self.cookies, proxies=proxies)
        return self.session
    
    # 重新连接
    async def reconnect(self):
        await self.session.close()
        self.session = None
        self.info('重新连接中...')
        await self.login()
        await self.join_room(self.room.id)
    
    # 新建登录
    async def get_login_token(self):
        session = await self.get_session()
        resp = await session.get(self.endpoint + '/?api=json')
        stat, resp = resp.status_code, resp.text
        if stat == 200:
            resp_parsed = json.loads(resp)
            token = resp_parsed['token']
            self.debug('token值：' + token)
            return token
        else:
            self.error('获取token失败')
            return None

    async def post_login(self, token):
        data = {'name': self.name_tc,
                'login': 'ENTER',
                'token': token,
                'language': 'zh-CN',
                'icon': self.avatar}
        session = await self.get_session()
        resp = await session.post(self.endpoint + '/?api=json', data=data)
        self.debug('登录返回值：' + str(resp.status))
        return (resp.status, resp.text, self.session.cookie_jar)
    
    async def login(self):
        await self.connect()
        cookies_file = f'{self.cookie_path}/{self.username}.cookie'
        if os.path.isfile(cookies_file):
            await self.resume(cookies_file)
            return

        self.info('新建登录中')
        token = await self.get_login_token()
        if token is not None:
            stat, resp, cookie_jar = await self.post_login(token)
            self.debug(f'status: {stat}, resp: {resp}')
            resp_parsed = json.loads(resp)
            if stat == 200:
                if resp_parsed['message'] == 'ok':
                    cookie_jar.save(cookies_file)
                    self.info('登录成功，已保存cookie')
                    await self.join_room(self.roomID)
                        
                else:
                    self.warning(f'message: {resp_parsed["message"]}, try again...')
                    await self.login()
            else:
                self.error(f"登录失败: {resp_parsed['error']}")

    # 恢复登录
    async def resume(self, cookies_file):
        self.cookie_jar.load(cookies_file)
        stat, resp = await self.get_lounge()
        if stat == 200:
            self.info('保存的cookie有效，成功登录')
            await self.update_room_state()
            if self.room is not None:
                self.room_connected = True
                self.info('成功连接到房间【' + self.room.name + '】')
                await self.start_loop()
                
            else:
                self.warning('已不在房间中')
                await self.join_room(self.roomID)
                
        elif stat == 401:
            self.warning('保存的cookie无效， 已删除该文件')
            os.remove(cookies_file)
            await self.login()
        else:
            self.error('恢复连接时发生错误')   

    # 使用已有cookie连接
    async def connect(self):
        stat, resp = await self.get_lounge()
        if stat == 200:
            self.info('连接成功')
            await self.update_room_state()
            if self.room is not None:
                self.room_connected = True
                self.info('成功连接到房间【' + self.room.name + '】')
                await self.start_loop()
                
            else:
                self.warning('已不在房间中')
                await self.join_room(self.roomID)
                
        else:
            self.error('恢复连接时发生错误')

    # 获取大厅信息
    async def get_lounge(self):
        session = await self.get_session()
        resp = await session.get(self.endpoint + '/lounge?api=json')
        stat = resp.status_code
        text = resp.text
        return stat, text
        
    # 更新房间信息
    async def update_room_state(self, preserve_banned=False):
        try:
            session = await self.get_session()
            resp = await session.get(self.endpoint + '/json.php?fast=1')
            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', '').lower()
                resp_parsed = None
                if 'application/json' in content_type:
                    resp_parsed = resp.json()
                else:
                    resp = resp.text
                    resp_json = json.loads(resp)
                    self.error(f"更新房间信息失败1: {resp_json['error']}")
                    return

                users = {}

                if 'roomId' in resp_parsed:
                    for user in resp_parsed['users']:
                        users[user['id']] = popyo.User(user['id'], user['name'], user['icon'],
                                                        user['tripcode'] if 'tripcode' in user.keys() else '无', user['device'],
                                                        True if 'admin' in user.keys() and user['admin'] else False)

                    banned_ids = self.room.banned_ids if preserve_banned else set()
                    self.room = popyo.Room(resp_parsed['name'], resp_parsed['description'], resp_parsed['limit'], users, resp_parsed['language'],
                                            resp_parsed['roomId'], None, False, False, resp_parsed['host'], resp_parsed['update'])
                    if 'np' in resp_parsed:
                        self.room.music_np = resp_parsed['np']
                    self.room.banned_ids = banned_ids
            return
        except Exception:
            self.error(f"更新房间信息失败2")
            self.error(traceback.format_exc())
    
    def findUser(self, name=None, tc=None):
        for user in self.room.users.values():
            if tc and user.tc == tc:
                return user.id
            if name and user.name == name:
                return user.id
        return None

    # 进入房间
    async def join_room(self, room_id):
        for _ in range(self.retries):
            try:
                session = await self.get_session()
                resp = await session.get(self.endpoint + '/room/?id=' + room_id + '&api=json')
                stat = resp.status_code
                content_type = resp.headers.get('Content-Type', '').lower()
                resp_json = None
                if 'application/json' in content_type:
                    resp_json = resp.json()
                    if('error' in resp_json.keys()):
                        self.error(f"进入房间失败: {resp_json['error']}")
                        return
                else:
                    resp = resp.text
                    resp_json = json.loads(resp)
                    self.error(f"进入房间失败1: {resp_json['error']}")
                    return
                
                if stat == 200 and 'message' in resp_json and resp_json['message'] == 'ok' and resp_json['redirect'] == 'room':
                    await self.update_room_state()
                    if self.room is not None:
                        self.room_connected = True
                        self.info('成功加入房间【' + self.room.name + '】')
                        await self.start_loop()
                        
                    else:
                        print(resp_json)
                        self.warning('进入房间失败：无法更新房间信息')
                        await self.join_room(self.roomID)
                else:
                    self.warning('未登录') 
                    await self.login()
                return
            except aiohttp.client_exceptions.ContentTypeError:
                self.error(f"进入房间失败2: {resp_json['error']}")
                self.error(resp.text)
                raise()
            except Exception as e:
                if self.room_connected:
                    self.error('循环错误')
                else:
                    self.error('进入房间时发生错误')
                self.error(traceback.format_exc())
                await asyncio.sleep(1)

    # 开始循环
    async def start_loop(self):
        task1 = asyncio.create_task(self.room_loop())
        task2 = asyncio.create_task(self.send_loop())
        await asyncio.gather(task1, task2)

    # 房间循环接受消息
    async def room_loop(self):
        self.last_error = False
        self.exit_loop = False

        if self.room_connected:
            self.debug('开始监听房间【' + self.room.name + '】')
        else:
            self.warning('已不在房间中')
            await self.join_room(self.roomID)
            return
        
        session = await self.get_session()
        resp = await session.get(self.endpoint + '/room/?api=json')
        try:
            resp_parsed = resp.json()
            if resp.status_code == 200 and 'error' not in resp_parsed:
                self.own_user = self.room.users[resp_parsed['profile']['uid']]
        except Exception:
            self.debug(traceback.format_exc())

        last = 0
        while self.room_connected:
            try:
                resp = await session.get(self.endpoint + '/json.php?update=' + str(self.room.update), timeout=10)
                content_type = resp.headers.get('Content-Type', '').lower()
                resp_parsed = None
                if 'application/json' in content_type:
                    resp_parsed = resp.json()
                else:
                    resp = resp.text
                    resp_json = json.loads(resp)
                    self.debug(f"更新房间信息失败: {resp_json['error']}")
                    self.room_connected = False
                    break
                
                stat = resp.status_code   
                if stat == 200:
                    # now = datetime.datetime.now()
                    # if (now - last).seconds > 60:
                    #     self.dm(self.own_user.id, 'keep')
                    #     last = now
                    #     print('keep')
                    if 'talks' in resp_parsed:
                        try:
                            self.room.update = resp_parsed['update']
                            if self.room.update > last:
                                last = self.room.update
                                msgs = popyo.talks_to_msgs(resp_parsed['talks'], self.room)
                                for msg in [x for x in msgs if x is not None]:
                                    if msg.time < self.room.update:
                                        continue
                                    
                                    if msg.message == '/stop':
                                        self.send('已停止运行')
                                        await asyncio.sleep(2)
                                        sys.exit(0)

                                    if msg.message and msg.message != 'keep':
                                        user = getattr(msg, 'user', getattr(msg, 'to', '系统消息'))
                                        info = f"{user} | {msg.message}"
                                        self.info(info)
                                        userInfo = user if type(user) is str else user.name + ',' + user.tc
                                        await self.write('logs', userInfo + ',' + msg.message.replace('\n', '\\n').replace(',', '，'), 'csv')

                                    if msg.type in [popyo.Message_Type.message, popyo.Message_Type.me, popyo.Message_Type.dm]:
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.join:
                                        await self.update_room_state()
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.leave:
                                        if msg.user.id == self.own_user.id:
                                            self.room_connected = False
                                            self.room = None
                                            self.own_user = None
                                            self.exit_loop = True
                                            break
                                        else:
                                            await self.update_room_state()
                                            await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.new_host:
                                        self.room.host_id = msg.user.id
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.async_response:
                                        if msg.stop_fetching:
                                            self.exit_loop = True
                                            break

                                    elif msg.type == popyo.Message_Type.kick:
                                        if msg.to.id != self.own_user.id:
                                            del self.room.users[msg.to.id]
                                            await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.ban:
                                        if isinstance(msg.to, str):
                                            banned_id = msg.to
                                        elif isinstance(msg.to, popyo.User):
                                            banned_id = msg.to.id

                                        if banned_id != self.own_user.id:
                                            self.room.banned_ids.add(banned_id)
                                            if banned_id in self.room.users:
                                                del self.room.users[banned_id]
                                            await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.unban:
                                        if msg.to.id in self.room.banned_ids:
                                            self.room.banned_ids.remove(msg.to.id)
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.system:
                                        await self.update_room_state(preserve_banned=True)
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.room_profile or \
                                                    msg.type == popyo.Message_Type.new_description:
                                        await self.update_room_state(preserve_banned=True)
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.music:
                                        self.room.music_np = resp_parsed['np']
                                        await self.msg_cb(msg)

                                    self.last_error = False

                        except Exception as e:
                            self.error('消息 ' + str(resp_parsed) + ' 解析失败')
                            self.error(traceback.format_exc())

                    elif 'error' in resp_parsed:
                        if not self.last_error:
                            self.last_error = True
                            continue
                        else:
                            # self.exit_loop = True
                            self.error('房间信息更新失败:1')
                            await self.join_room(self.roomID)
                            break

                    else:
                        self.debug('空闲状态')
                        self.last_error = False

                    self.room.update = resp_parsed['update']
                else:
                    self.error('无效信息')
                    self.error(traceback.format_exc())
                    break
            except asyncio.TimeoutError:
                pass
            except Exception:
                self.error('房间信息更新失败:2')
                self.error(traceback.format_exc())
                await asyncio.sleep(1)
                await self.join_room(self.roomID)
                break
        await self.join_room(self.roomID)
    
    # 发送消息
    async def send_post(self, data):
        for _ in range(self.retries):
            try:
                session = await self.get_session()
                resp = await session.post(self.endpoint + '/room/?ajax=1&api=json', data=data)
                if resp.status_code != 200:
                    self.error('发送【' + data['message'] + '】失败')
                return
            except Exception as e:
                self.error('发送【' + data['message'] + '】时产生错误' + str(e))
                self.error(traceback.format_exc())
                await asyncio.sleep(1)

    # 消息循环
    async def send_loop(self):
        self.debug('开始消息循环')
        t2 = time.time()
        while self.room_connected:
            try:
                out_msg = await self.sendQ.get()
                type = out_msg.type

                if self.room_connected:
                    data = None
                    if type == popyo.Outgoing_Message_Type.message:
                        data = {'message': out_msg.msg}
                    elif type == popyo.Outgoing_Message_Type.dm:
                        data = {'message': out_msg.msg,'to': out_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.url:
                        data = {'message': out_msg.msg, 'url': out_msg.url}
                    elif type == popyo.Outgoing_Message_Type.dm_url:
                        data = {'message': out_msg.msg, 'url': out_msg.url, 'to': out_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.music:
                        data = {'music': 'music', 'name': out_msg.name, 'url': out_msg.url}
                    elif type == popyo.Outgoing_Message_Type.handover_host:
                        data = {'new_host': out_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.kick:
                        data = {'kick': out_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.ban:
                        data = {'report_and_ban_user': out_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.change_title:
                        data = {'room_name': out_msg.title}
                    elif type == popyo.Outgoing_Message_Type.change_description:
                        data = {'room_description': out_msg.description}

                    t1 = time.time()
                    await self.send_post(data)
                    if t1 - t2 < self.throttle or not self.sendQ.empty():
                        await asyncio.sleep(self.throttle - t1 + t2)
                    t2 = time.time()
            except Exception:
                self.error('消息发送失败')
                self.debug(traceback.format_exc())
    
    async def putQ(self, msgs):
        for msg in msgs:
            await self.sendQ.put(msg)

    # 发送消息
    def send(self, msg):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked]
        asyncio.run_coroutine_threadsafe(self.putQ(msgs), self.loop)

     # 发送私信
    def dm(self, receiver, msg):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingDirectMessage(chunk, receiver) for chunk in chunked]
        asyncio.run_coroutine_threadsafe(self.putQ(msgs), self.loop)

     # 发送URL
    def send_url(self, msg, url):
        chunked = [msg[i : i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked[:-1]]
        msgs.append(popyo.OutgoingUrlMessage(chunked[-1], url))
        asyncio.run_coroutine_threadsafe(self.putQ(msgs), self.loop)
    
    # 发送私信URL
    def dm_url(self, receiver, msg, url):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingDirectMessage(chunk, receiver) for chunk in chunked[:-1] ]
        msgs.append(popyo.OutgoingDmUrl(chunked[-1], receiver, url))
        
        asyncio.run_coroutine_threadsafe(self.putQ(msgs), self.loop)
    
    # 播放歌曲
    def music(self, name, url):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingMusic(name, url))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)

    # 更换房主
    def chown(self, receiver):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingHandoverHost(receiver))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)
    
    # 踢出用户
    def kick(self, receiver):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingKick(receiver))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)
    
    # 封禁用户
    def ban(self, receiver):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingBan(receiver))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)
    
    # 更改房间名
    def title(self, name):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingChangeTitle(name))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)
    
    # 更改房间描述
    def desc(self, description):
        async def putQ():
            await self.sendQ.put(popyo.OutgoingChangeDescription(description))
        asyncio.run_coroutine_threadsafe(putQ(), self.loop)