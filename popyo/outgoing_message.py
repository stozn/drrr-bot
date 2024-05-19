from enum import Enum

class Outgoing_Message_Type(Enum):
    message = 0
    dm = 1
    handover_host = 2
    music = 3
    url = 4
    dm_url = 5
    kick = 6
    ban = 7
    change_title = 8
    change_description = 9

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

class OutgoingHandoverHost:
    def __init__(self, receiver):
        self.type = Outgoing_Message_Type.handover_host
        self.receiver = receiver

class OutgoingKick:
    def __init__(self, receiver):
        self.type = Outgoing_Message_Type.kick
        self.receiver = receiver

class OutgoingBan:
    def __init__(self, receiver):
        self.type = Outgoing_Message_Type.ban
        self.receiver = receiver

class OutgoingChangeTitle:
    def __init__(self, title):
        self.type = Outgoing_Message_Type.change_title
        self.title = title

class OutgoingChangeDescription:
    def __init__(self, description):
        self.type = Outgoing_Message_Type.change_description
        self.description = description