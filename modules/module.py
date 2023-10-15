import re
from abc import ABCMeta, abstractmethod, abstractproperty

class Module(metaclass=ABCMeta):
    def __init__(self, bot):
        self.bot = bot

    @abstractproperty
    def cmds(self):
        pass

    # @abstractmethod
    # def unload(self):
    #     pass

    def handler(self, msg):
        for name, reg in self.cmds.items():
            pattern = re.compile(reg)
            if re.findall(pattern, msg.message):
                getattr(self, name)(msg)

    
