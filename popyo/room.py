class Room:
    def __init__(self, name, desc, limit, users, lang, room_id, music, dj_mode, music_np, host_id, update):
        self.name = name
        self.desc = desc
        self.limit = limit
        self.users = users
        self.banned_ids = set()
        self.host_id = host_id
        self.update = update
        self.lang = lang
        self.room_id = room_id
        self.music = music
        self.dj_mode = music and dj_mode
        self.music_np = music_np
        
    def __str__(self):
        return "【" + self.name + " 】" + self.room_id + " | " + self.desc + " | "  + str(len(self.users)) + "/" + str(self.limit)
