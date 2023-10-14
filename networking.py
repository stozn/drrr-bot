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

path = os.path.dirname(__file__)
sys.path.append(path)

class Connection:
    def __init__(self, username, avater, roomID, msg_cb, loop):
        self.username = username
        self.avatar = avater
        self.room_connected = False
        self.room = None
        self.roomID = roomID
        self.own_user = None
        self.session = None
        self.endpoint = 'https://drrr.com'
        self.cookie_path = path + '/cookies'
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.ua = 'Bot'
        self.retries = 100
        self.sendQ = asyncio.Queue()
        self.throttle = 2.5
        self.char_limit = 140
        self.msg_cb = msg_cb
        self.loop = loop
        self.handler = logging.StreamHandler()
        self.logger = logging.getLogger()
        self.logger.addHandler(self.handler)
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
        self.handler.setLevel(level)
        if(level == logging.DEBUG):
            self.handler.setFormatter(debug_formatter)
        else:
            self.handler.setFormatter(formatter)

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
            self.session = aiohttp.ClientSession(
                cookie_jar=self.cookie_jar,
                headers={'User-Agent': self.ua})
        return self.session
    
    # 重新连接
    async def reconnect(self):
        await self.session.close()
        self.session = None
        self.logger.info('重新连接中...')
        await self.login()
        await self.join_room(self.room.id)
    
    # 新建登录
    async def get_login_token(self):
        session = await self.get_session()
        async with session.get(self.endpoint + '/?api=json') as resp:
            stat, resp = resp.status, await resp.text()
            if stat == 200:
                resp_parsed = json.loads(resp)
                token = resp_parsed['token']
                self.logger.debug('token值：' + token)
                return token
            else:
                self.logger.error('获取token失败')
                return None

    async def post_login(self, token):
        data = {'name': self.username,
                'login': 'ENTER',
                'token': token,
                'language': 'zh-CN',
                'icon': self.avatar}
        session = await self.get_session()
        async with session.post(self.endpoint + '/?api=json', data=data) as resp:
            self.logger.debug('登录返回值：' + str(resp.status))
            return (resp.status, await resp.text(), self.session.cookie_jar)
    
    async def login(self):
        cookies_file = f'{self.cookie_path}/{self.username}.cookie'
        if os.path.isfile(cookies_file):
            await self.resume(cookies_file)
        else:
            self.logger.info('没有已保存的cookie，新建登录中')
            token = await self.get_login_token()
            if token is not None:
                stat, resp, cookie_jar = await self.post_login(token)
                self.logger.debug(f'status: {stat}, resp: {resp}')
                if stat == 200:
                    resp_parsed = json.loads(resp)
                    if resp_parsed['message'] == 'ok':
                        cookie_jar.save(cookies_file)
                        self.logger.info('登录成功，已保存cookie')
                        await self.join_room(self.roomID)
                            
                    else:
                        self.logger.warning('not ok???')
                else:
                    self.logger.error('登录失败')

    # 恢复登录
    async def resume(self, cookies_file):
        self.cookie_jar.load(cookies_file)
        stat, resp = await self.get_lounge()
        if stat == 200:
            self.logger.info('保存的cookie有效，成功登录')
            await self.update_room_state()
            if self.room is not None:
                self.room_connected = True
                self.logger.info('成功连接到房间【' + self.room.name + '】')
                await self.start_loop()
                
            else:
                self.logger.warning('已不在房间，请重新进入房间')
                await self.join_room(self.roomID)
                
        elif stat == 401:
            self.logger.warning('保存的cookie无效， 请重新登录')
        else:
            self.logger.error('恢复连接时发生错误')   


    # 获取大厅信息
    async def get_lounge(self):
        session = await self.get_session()
        async with session.get(self.endpoint + '/lounge?api=json') as resp:
            stat = resp.status
            text = await resp.text()
            return stat, text
        
    # 更新房间信息
    async def update_room_state(self, preserve_banned=False):
        for _ in range(self.retries):
            try:
                session = await self.get_session()
                async with session.get(self.endpoint + '/json.php?fast=1') as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('Content-Type', '').lower()
                        resp_parsed = None
                        if 'application/json' in content_type:
                            resp_parsed = await resp.json()
                        else:
                            resp = await resp.text()
                            resp_json = json.loads(resp)
                            self.logger.error('更新房间信息失败1', resp_json['error'])
                            return

                        users = {}

                        if 'roomId' in resp_parsed:
                            for user in resp_parsed['users']:
                                users[user['id']] = popyo.User(user['id'], user['name'], user['icon'],
                                                               user['tripcode'] if 'tripcode' in user.keys() else '无', user['device'],
                                                               True if 'admin' in user.keys() and user['admin'] else False)

                            banned_ids = self.room.banned_ids if preserve_banned else set()
                            self.room = popyo.Room(resp_parsed['name'], resp_parsed['description'], resp_parsed['limit'], users, resp_parsed['language'],
                                                   resp_parsed['roomId'], resp_parsed['music'], False, False, resp_parsed['host'], resp_parsed['update'])
                            if 'np' in resp_parsed:
                                self.room.music_np = resp_parsed['np']
                            self.room.banned_ids = banned_ids
                    return
            except Exception:
                self.logger.error('更新房间信息失败2', resp_json['error'])
                self.logger.error(traceback.format_exc())

    # 进入房间
    async def join_room(self, room_id):
        for _ in range(self.retries):
            try:
                session = await self.get_session()
                async with session.get(self.endpoint + '/room/?id=' + room_id + '&api=json') as resp:
                    stat = resp.status
                    content_type = resp.headers.get('Content-Type', '').lower()
                    resp_json = None
                    if 'application/json' in content_type:
                        resp_json = await resp.json()
                    else:
                        resp = await resp.text()
                        resp_json = json.loads(resp)
                        self.logger.error('进入房间失败1', resp_json['error'])
                        return
                  
                    if stat == 200 and resp_json['message'] == 'ok' and resp_json['redirect'] == 'room':
                        await self.update_room_state()
                        if self.room is not None:
                            self.room_connected = True
                            self.logger.info('成功加入房间【' + self.room.name + '】')
                            await self.start_loop()
                            
                        else:
                            self.logger.warning('已不在房间中')
                    else:
                        self.logger.warning('房间不存在或未登录') 
                    return
            except aiohttp.client_exceptions.ContentTypeError:
                self.logger.error('进入房间失败2', resp_json['error'])
                self.logger.error(await resp.text())
                raise()
            except Exception as e:
                if self.room_connected:
                    self.logger.error('循环错误')
                else:
                    self.logger.error('进入房间时发生错误')
                self.logger.error(traceback.format_exc())
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
            self.logger.debug('开始监听房间【' + self.room.name + '】')
        else:
            self.logger.warning('已不在房间中')
            await self.join_room(self.roomID)
            return
        
        session = await self.get_session()
        async with session.get(self.endpoint + '/room/?api=json') as resp:
            try:
                resp_parsed = await resp.json()
                if resp.status == 200 and 'error' not in resp_parsed:
                    self.own_user = self.room.users[resp_parsed['profile']['uid']]
            except Exception:
                self.logger.debug(traceback.format_exc())

        while self.room_connected:
            try:
                async with session.get(self.endpoint + '/json.php?update=' + str(self.room.update), timeout=10) as resp:
                    content_type = resp.headers.get('Content-Type', '').lower()
                    resp_parsed = None
                    if 'application/json' in content_type:
                        resp_parsed = await resp.json()
                    else:
                        resp = await resp.text()
                        resp_json = json.loads(resp)
                        self.logger.debug('更新房间信息失败：', resp_json['error'])
                        self.room_connected = False
                        return
                    
                    stat = resp.status   
                    if stat == 200:
                        if  datetime.datetime.now().minute%10 == 0 and datetime.datetime.now().second<5:
                                            self.dm(self.own_user.id, 'keep')
                        if 'talks' in resp_parsed:
                            try:
                                msgs = popyo.talks_to_msgs(resp_parsed['talks'], self.room)
                                for msg in [x for x in msgs if x is not None]:

                                    if msg.message:
                                        info = f'{msg.user} | {msg.message}'
                                        self.logger.info(info)
                                        await self.write('log', msg.user.name + ',' + msg.user.tripcode + ',' + msg.message.replace('\n', '\\n').replace(',', '，'), 'csv')

                                    if msg.type == popyo.Message_Type.message:
                                        await self.msg_cb(msg)

                                    elif msg.type == popyo.Message_Type.join:
                                        await self.update_room_state()

                                    elif msg.type == popyo.Message_Type.leave:
                                        if msg.user.id == self.own_user.id:
                                            self.room_connected = False
                                            self.room = None
                                            self.own_user = None
                                            self.exit_loop = True
                                            break
                                        else:
                                            await self.update_room_state()

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
                                self.logger.error('消息 ' + str(resp_parsed) + ' 解析失败')
                                self.logger.error(traceback.format_exc())

                        elif 'error' in resp_parsed:
                            if not self.last_error:
                                self.last_error = True
                                pass
                            else:
                                # self.exit_loop = True
                                self.logger.error('房间信息更新失败:1')
                                break

                        else:
                            self.logger.debug('空闲状态')
                            self.last_error = False

                        self.room.update = resp_parsed['update']
                    else:
                        self.logger.error('无效信息')
                        self.logger.error(traceback.format_exc())
                        break
            except asyncio.TimeoutError:
                pass
            except Exception:
                self.logger.error('房间信息更新失败:2')
                self.logger.error(traceback.format_exc())
                await asyncio.sleep(1)
        await self.join_room(self.roomID)

    # 消息循环
    async def send_loop(self):
        self.logger.debug('开始消息循环')
        t = time.time()
        while self.room_connected:
            try:
                outgoing_msg = await self.sendQ.get()
                type = outgoing_msg.type
                msg = outgoing_msg.msg
                t1 = time.time()
                if (t1 - t) < self.throttle:
                    await asyncio.sleep(self.throttle - t1 + t)

                if self.room_connected:
                    data = None
                    if type == popyo.Outgoing_Message_Type.message:
                        data = {'message': msg}
                    elif type == popyo.Outgoing_Message_Type.dm:
                        data = {'message': msg,'to': outgoing_msg.receiver}
                    elif type == popyo.Outgoing_Message_Type.url:
                        data = {'message': msg, 'url': outgoing_msg.url}
                    elif type == popyo.Outgoing_Message_Type.dm_url:
                        data = {'message': msg, 'url': outgoing_msg.url, 'to': outgoing_msg.receiver}

                    await self.send_post(data)
                    t = time.time()
            except Exception:
                self.logger.error('消息发送失败')
                self.logger.debug(traceback.format_exc())

    # 添加待发送消息
    def send(self, msg):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked]
        async def run_sendQ():
            for msg in msgs:
                await self.sendQ.put(msg)
        asyncio.run_coroutine_threadsafe(run_sendQ(), self.loop)

     # 添加待发送私信
    def dm(self, receiver, msg):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingDirectMessage(chunk, receiver) for chunk in chunked]
        async def run_sendQ():
            for msg in msgs:
                await self.sendQ.put(msg)
        asyncio.run_coroutine_threadsafe(run_sendQ(), self.loop)

     # 添加待发送URL
    def send_url(self, msg, url):
        chunked = [msg[i : i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked[:-1]]
        msgs.append(popyo.OutgoingUrlMessage(chunked[-1], url))
        async def run_sendQ():
            for msg in msgs:
                await self.sendQ.put(msg)
        asyncio.run_coroutine_threadsafe(run_sendQ(), self.loop)
    
    # 添加待发送私信URL
    def dm_url(self, receiver, msg, url):
        chunked = [msg[i:i + self.char_limit] for i in range(0, len(msg), self.char_limit)]
        msgs = [popyo.OutgoingDirectMessage(chunk, receiver) for chunk in chunked[:-1] ]
        msgs.append(popyo.OutgoingDmUrl(chunked[-1], receiver, url))
        async def run_sendQ():
            for msg in msgs:
                await self.sendQ.put(msg)
        asyncio.run_coroutine_threadsafe(run_sendQ(), self.loop)

    # 发送消息
    async def send_post(self, data):
        for _ in range(self.retries):
            try:
                session = await self.get_session()
                async with session.post(self.endpoint + '/room/?ajax=1&api=json', data=data) as resp:
                    if resp.status != 200:
                        self.logger.error('发送【' + data['message'] + '】失败')
                    return
            except Exception as e:
                self.logger.error('发送【' + data['message'] + '】时产生错误' + str(e))
                self.logger.error(traceback.format_exc())
                await asyncio.sleep(1)

        