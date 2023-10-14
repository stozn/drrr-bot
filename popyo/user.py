class User:
    def __init__(self, id, name, icon, tripcode, device, drrr_admin=False):
        self.id = id
        self.name = name
        self.icon = icon
        self.tripcode = tripcode if type(tripcode) is str else "无"
        self.device = device
        self.drrr_admin = drrr_admin

    def __str__(self):
        return "@" + self.name + "["+ self.tripcode + "]" 

class BannedUserInfo(User):
    def __init__(self, id, name, tripcode, icon):
        super().__init__(id, name, icon, tripcode, None, False)

