import os
from modules.module import Module

# import re
# cmd = r'^\+1'
# msg = '+1 '
# print(re.findall( re.compile(cmd), msg))
# print(os.path.dirname(__file__))

class Test(Module):
    def __init__(self, bot):
        super().__init__(bot)

    @property
    def cmds(self):
        cmd_dict = {'test': r'^\/test'}
        return cmd_dict
    
    def unload(self):
        pass
    
    def test(self, msg):
        self.bot.send(f'/me{msg.user} test')


