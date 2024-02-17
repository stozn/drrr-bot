import re
from abc import ABCMeta, abstractmethod, abstractproperty

class Module(metaclass=ABCMeta):
    def __init__(self, bot):
        self.bot = bot
        self.on = True

    @abstractproperty
    def cmds(self):
        pass

    # @abstractmethod
    def switch(self, msg):
        pass

    def handler(self, msg):
        if re.findall(re.compile(r'^\/切换'), msg.message):
            self.switch(msg)
            return
        
        if self.on:
            for name, reg in self.cmds.items():
                pattern = re.compile(reg)
                if re.findall(pattern, msg.message):
                    getattr(self, name)(msg)
                    break