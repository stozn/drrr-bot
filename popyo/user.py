class User:
    def __init__(self, id, name, icon, tc, device, drrr_admin=False):
        self.id = id
        self.name = name
        self.icon = icon
        self.tc = tc if type(tc) is str else "无"
        self.device = device
        self.drrr_admin = drrr_admin

    def __str__(self):
        return "@" + self.name + "["+ self.tc + "]" 

class BannedUserInfo(User):
    def __init__(self, id, name, tc, icon):
        super().__init__(id, name, icon, tc, None, False)

