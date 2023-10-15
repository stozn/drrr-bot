from modules.module import Module

class Test(Module):
    def __init__(self, bot):
        super().__init__(bot)

    @property
    def cmds(self):
        # 指令字典，格式为：{函数名: 指令正则表达式}
        cmd_dict = {
                    'sayHello': r'hi',
                    'calculate': r'^\/calc\s+\d+\s+[\+\-\*\/]\s+\d+\s*$'
                    }
        return cmd_dict
    
    def sayHello(self, msg):
        self.bot.send(f'@{msg.user.name} 你好')
    
    def calculate(self, msg):
        cont = msg.message.split(' ', 1)[1]
        result = eval(cont)
        self.bot.send(cont + ' = ' + str(result))

    '''
        msg.message: 消息的文本内容
        msg.user: 发送消息的用户
            msg.user.name: 用户名
            msg.user.id: 用户ID (用于发送私信)
            msg.user.tc: 用户Tripcode
        msg.type: 消息类型 (message, me, dm, ...)

        self.bot: Bot对象
            self.bot.send(text): 发送消息
            self.bot.dm(userId, text): 发送私信
    '''