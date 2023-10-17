import random
from modules.module import Module

class GuessNumber(Module):
    def __init__(self, bot):
        super().__init__(bot)
        self.answer = None
        self.help_doc='''帮助：
先回复/start 开始游戏，系统会生成四位不重复的数字
然后回复四位数字进行猜测，系统会返回xAxB，A表示数字和位置都正确的个数，B表示数字正确但位置不正确的个数
如答案为 1234
2345：0A3B
1342：1A3B'''

    @property
    def cmds(self):
        # 指令字典，格式为：{函数名: 指令正则表达式}
        cmd_dict = {
                    'start': r'^\/start$',
                    'guess': r'^[\d\s]+$',
                    'help': r'^\/help$',
                    }
        return cmd_dict
    
    def start(self, msg):
        self.bot.send(f'@{msg.user.name} 四位不重复的数字已生成，请直接回复四位数字进行猜测，如需帮助请回复 /help')
        self.answer = self.generateAnswer()
    
    def guess(self, msg):
        if self.answer == None:
            self.bot.send(f'@{msg.user.name} 请先回复 /start 开始游戏')
            return
        
        guess = msg.message.replace(' ', '')

        if len(guess) != 4:
            self.bot.send(f'@{msg.user.name} 请输入四位数字')
        if len(set(guess)) != 4:
            self.bot.send(f'@{msg.user.name} 请输入四位不重复的数字')
        else:
            a, b = self.compare(guess)
            if a == 4:
                self.bot.send(f'@{msg.user.name} 恭喜你猜对了！')
                self.answer = None
            else:
                self.bot.send(f'@{msg.user.name} {a}A{b}B')
    
    def help(self, msg):
        self.bot.send(self.help_doc)
    
    def generateAnswer(self):
        numbers = random.sample(list(range(10)), 4)
        answer = ''.join(map(str, numbers))
        print('答案：【' + answer + '】')
        return answer
    
    def compare(self, guess):
        a = b = 0
        for i in range(4):
            if guess[i] == self.answer[i]:
                a += 1
            elif guess[i] in self.answer:
                b += 1
        return a, b