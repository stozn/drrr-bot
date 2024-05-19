from modules.module import Module


class Test(Module):
    def __init__(self, bot):
        super().__init__(bot)

    @property
    def cmds(self):
        # 指令字典，格式为：{函数名: 消息指令正则表达式}
        cmd_dict = {
            'sayHello': r'hi',
            'calculate': r'^\/calc\s+\d+\s+[\+\-\*\/]\s+\d+\s*$',
            'chown': r'^\/chown',
            'welcome': r'^进入房间$',  # 进入房间的消息默认是 "进入房间" 这个字符串，它不是一般发言消息
        }
        return cmd_dict

    def sayHello(self, msg):
        self.bot.send(f'@{msg.user.name} 你好')

    def calculate(self, msg):
        cont = msg.message.split(' ', 1)[1]
        result = eval(cont)
        self.bot.send(cont + ' = ' + str(result))

    def chown(self, msg):
        self.bot.chown(msg.user.id)

    def welcome(self, msg):
        self.bot.send(f'欢迎@{msg.user.name}进入房间')

    '''
        msg.message: 消息的文本内容
        msg.user: 发送消息的用户
            msg.user.name: 用户名
            msg.user.id: 用户ID (用于发送私信)
            msg.user.tc: 用户Tripcode
        msg.type: 消息类型 (message, me, dm, join, leave, ...)

        self.bot: Bot对象
            self.bot.send(text): 发送消息
            self.bot.dm(userId, text): 发送私信
            self.bot.send_url(text, url): 发送带链接的消息
            self.bot.dm_url(userId, text, url): 发送带链接的私信
            self.bot.music(name, url): 发送音乐
            self.bot.chown(userId): 移交房主
            self.bot.kick(userId): 将用户踢出房间
            self.bot.ban(userId): 禁止用户进入房间
            self.bot.title(title): 设置房间标题
            self.bot.desc(desc): 设置房间描述
            self.bot.findUser(name): 使用用户名查找用户ID
            self.bot.findUser(tc=tc): 使用用户Tripcode查找用户ID

    '''