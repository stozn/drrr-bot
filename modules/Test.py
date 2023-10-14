import os
from time import time
from modules.module import Module

class Test(Module):
    def __init__(self, bot):
        super().__init__(bot)

    @property
    def cmds(self):
        cmd_dict = {
                    'test': r'^\/test',
                    'showTime': r'^\/time'
                    }
        return cmd_dict
    
    def unload(self):
        pass
    
    def test(self, msg):
        self.bot.send(f'@{msg.user} test')
    
    def showTime(self, msg):
        self.bot.send(f'/me {time.strftime("%H:%M:%S", time.localtime())}')
