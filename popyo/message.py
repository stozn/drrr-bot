# i've been doing java for too long
# class representing incoming messages
from enum import Enum

# roughly corresponds to the type field in the json, not exactly because we use inheritance here
class Message_Type(Enum):
    join = 0
    leave = 1
    message = 2
    music = 3
    me = 4
    new_host = 5
    async_response = 9
    kick = 10
    ban = 11
    unban = 12
    system = 13
    room_profile = 14
    new_description = 15

#     my own fields
    dm = 6
    url = 7
    dm_url = 8


    error = -1

class ErrorMessage:
    def __init__(self, text, reload=False):
        self.type = Message_Type.error
        self.text = text
        self.reload = reload

class KickMessage:
    def __init__(self, id, time, to, message):
        self.id = id
        self.time = time
        self.to = to
        self.message = message
        self.type = Message_Type.kick

class BanMessage:
    def __init__(self, id, time, to, message):
        self.id = id
        self.time = time
        self.to = to
        self.message = message
        self.type = Message_Type.ban

class UnbanMessage:
    def __init__(self, id, time, to, message):
        self.id = id
        self.time = time
        self.to = to
        self.message = message
        self.type = Message_Type.unban

class SystemMessage:
    def __init__(self, id, time, message):
        self.id = id
        self.time = time
        self.message = message
        self.type = Message_Type.system

class RoomProfileMessage:
    def __init__(self, id, time, user):
        self.id = id
        self.time = time
        self.user = user
        self.message = ''
        self.type = Message_Type.room_profile

class NewDescMessage:
    def __init__(self, id, time, user, description):
        self.id = id
        self.time = time
        self.user = user
        self.type = Message_Type.new_description
        self.description = description
        self.message = f'设置房间主题：{description}'


class AsyncResponse:
    def __init__(self, id, time, secret, to, message, title, level, stop_fetching):
        self.type = Message_Type.async_response
        self.id = id
        self.time = time
        self.secret = secret
        self.to = to
        self.message = message
        self.title = title
        self.level = level
        self.stop_fetching = stop_fetching

class Message:
    def __init__(self, id, time, type, user, message):
        self.id = id
        self.time = time
        self.type = type
        self.user = user
        self.message = message

class NewHostMessage(Message):
    def __init__(self, id, time, user):
        super(NewHostMessage, self).__init__(id, time, Message_Type.new_host, user, f'成为新房主')

class JoinMessage(Message):
    def __init__(self, id, time, user):
        super(JoinMessage, self).__init__(id, time, Message_Type.join, user, f'进入房间')

class LeaveMessage(Message):
    def __init__(self, id, time, user):
        super(LeaveMessage, self).__init__(id, time, Message_Type.leave, user, f'离开房间')

class URLMessage(Message):
    def __init__(self, id, time, type, user, message, url):
        super(URLMessage, self).__init__(id, time, type, user, message)
        self.url = url

class MusicMessage(URLMessage):
    def __init__(self, id, time, user, music_name, music_url, url, play_url, share_url):
        super(MusicMessage, self).__init__(id, time, Message_Type.music, user, f'分享了 {music_name}', url)
        self.music_name = music_name
        self.music_url = music_url
        self.play_url = play_url
        self.share_url = share_url

class MeMessage(Message):
    def __init__(self, id, time, user, content):
        super(MeMessage, self).__init__(id, time, Message_Type.me, user, content)
        self.content = content

class DirectMessage(Message):
    def __init__(self, id, time, type, user, receiver, message):
        super(DirectMessage, self).__init__(id, time, type, user, message)
        self.receiver = receiver

class DirectURLMessage(DirectMessage):
    def __init__(self, id, time, type, user, receiver, message, url):
        super(DirectURLMessage, self).__init__(id, time, type, user, receiver, message)
        self.url = url