from enum import Enum

class Outgoing_Message_Type(Enum):
    message = 0
    dm = 1
    handover_host = 2
    music = 3
    url = 4
    dm_url = 5
    kick = 6
    action = 7
    direct_action = 8

class OutgoingMessage:
    def __init__(self, msg):
        self.type = Outgoing_Message_Type.message
        self.msg = msg

class OutgoingDirectMessage:
    def __init__(self, msg, receiver):
        self.type = Outgoing_Message_Type.dm
        self.msg = msg
        self.receiver = receiver

class OutgoingUrlMessage:
    def __init__(self, msg, url):
        self.type = Outgoing_Message_Type.url
        self.msg = msg
        self.url = url

class OutgoingDmUrl:
    def __init__(self, msg, receiver, url):
        self.type = Outgoing_Message_Type.dm_url
        self.msg = msg
        self.receiver = receiver
        self.url = url

class OutgoingMusic:
    def __init__(self, name, url):
        self.type = Outgoing_Message_Type.music
        self.name = name
        self.url = url
