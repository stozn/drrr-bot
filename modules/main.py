from modules.module import Module

user = { "uid": "duid", "name": "user", "tc": "tc", "live": 1, "coin": 0, "check": True, "day": 0, "dayz": 0, "drink": 0, "tree": 0, "trc": True, "bag": [], "pet": [], "checkb": True, "win": 0, "letters": [], "newl": False }

class Main(Module):
    def __init__(self, bot):
        super().__init__(bot)
        
    @property
    def cmds(self):
        cmd_dict = {'checkin': r'^\/签到'}
        return cmd_dict
    
    def unload(self):
        pass
    
    def checkin(self, msg):
        self.bot.send(f'/me{msg.user} test')


