import asyncio
import copy
from modules.module import Module
from popyo import *
from datetime import datetime
import random
import re


def chk(s, p):
    return re.match(p, s)


def ckn(username):
    username = username.replace('@', '')
    username = username.strip()
    return username


def pop(my_list):
    return my_list.pop(random.randrange(len(my_list)))


class Card:
    def __init__(self, mp, name, order):
        self.mp = mp
        self.name = name
        self.order = order


class WXR(Card):
    def __init__(self):
        super().__init__(-1, "外星人", 1)
        self.desc = "可装作犯人"


class GRZ(Card):
    def __init__(self):
        super().__init__(0, "感染者", 2)
        self.desc = "抽走1张调和牌"


class FR(Card):
    def __init__(self):
        super().__init__(0, "犯人", 3)
        self.desc = "不能直接使用"


class GF(Card):
    def __init__(self):
        super().__init__(0, "共犯", 3)
        self.desc = "移动自己的1张质疑牌给他人"


class XSHZ(Card):
    def __init__(self):
        super().__init__(3, "学生会长", 4)
        self.desc = "起始玩家"


class BZ(Card):
    def __init__(self):
        super().__init__(2, "班长", 4)
        self.desc = "和某人交换1张手牌"


class YDS(Card):
    def __init__(self):
        super().__init__(2, "优等生", 4)
        self.desc = "查出犯人"


class FJWY(Card):
    def __init__(self):
        super().__init__(1, "风纪委员", 4)
        self.desc = "查看某人的全部手牌"


class BJWY(Card):
    def __init__(self):
        super().__init__(1, "保健委员", 4)
        self.desc = "取走1张他人的已用牌"


class TSWY(Card):
    def __init__(self):
        super().__init__(1, "图书委员", 4)
        self.desc = "查看调和牌"


class DXJ(Card):
    def __init__(self):
        super().__init__(1, "大小姐", 4)
        self.desc = "抽走某人1张手牌并返还1张"


class XWB(Card):
    def __init__(self):
        super().__init__(1, "新闻部", 4)
        self.desc = "全体将1张手牌给下家"


class GZB(Card):
    def __init__(self):
        super().__init__(0, "归宅部", 5)
        self.desc = "用1张手牌交换1张调和牌"


class Cont:
    def __init__(self, type, cont, id):
        self.type = type
        self.cont = cont
        self.id = id


class Stage:
    def __init__(self):
        self.cur = 0
        self.player = None
        self.skill = None
        self.to_p = None

    def reset(self):
        self.cur = 0
        self.player = None
        self.skill = None
        self.to_p = None

class Player:
    def __init__(self, name, id):
        self.name = name
        self.id = id
        self.cards = None
        self.fixed = False
        self.used = []
        self.suspect = []

    def showCards(self):
        reply = f"@{self.name} 的手牌：\n" + "\n".join(f"{i + 1}.【{c.name}】" + \
                                                   f"(🧪{c.mp}⭐{c.order}){c.desc}" for i, c in enumerate(self.cards))
        return reply

    def showUsed(self):
        reply = f"@{self.name} 已用：" + "".join(f"【{c.name}】" \
                                              for c in self.used)
        return reply

    def showSuspect(self):
        reply = f"@{self.name} 被质疑：" + "".join(f"【{c.name}】(🧪{c.mp})" \
                                               for c in self.suspect)
        return reply

    def has(self, card):
        return any(c.name == card for c in self.cards)

    def lose(self, card):
        if not self.has(card):
            return False
        rcard = None
        for c in self.cards:
            if c.name == card:
                rcard = copy.copy(c)
                self.cards.remove(c)
                break
        return rcard

    def get(self, card):
        if not any(c.name == card for c in self.used):
            return False
        rcard = None
        for c in self.used:
            if c.name == card:
                rcard = copy.copy(c)
                self.used.remove(c)
                break
        return rcard

    def use(self, card):
        if card == "犯人":
            return False
        else:
            return self.lose(card)


class Game:
    def __init__(self, stage, bot):
        self.bot = bot
        self.stage = stage
        self.players = []
        self.n = 0
        self.deck = None
        self.target = None
        self.body = []
        self.result = None

    def say(self, cont):
        self.bot.send(cont)

    def me(self, cont):
        self.say("/me" + cont)

    def dm(self, uid, cont):
        self.bot.dm(uid, cont)

    def reset(self):
        self.players = []
        self.n = 0
        self.deck = None
        self.target = None
        self.result = None
        self.stage.reset()
        self.me("【冰冷的她醒来之前】游戏开始, [+1] 加入, [-1] 退出, [/p] 玩家," + \
                "[/go] 开始, [/游戏] 重新报名, [/指令] 指令列表")

    def next_player(self):
        cur_player = self.stage.player
        self.stage.cur = 1
        self.stage.skill = None
        if len(cur_player.cards) == 1:
            cur_player.fixed = True
            self.me(f"@{cur_player.name} 身份已固定，无法行动")
        idx = [i for i, p in enumerate(self.players) if p.name == cur_player.name][0]

        while True:
            idx += 1
            if idx == len(self.players):
                idx = 0
            if self.players[idx].name == cur_player.name:
                self.end()
                break
            elif not self.players[idx].fixed:
                self.stage.player = self.players[idx]
                self.me(f"@{self.stage.player.name} 请开始行动")
                break

    def has(self, card):
        return any(p.cards[0].name == card for p in self.players)

    def find(self, name):
        if any(p.name == name for p in self.players):
            return [p for p in self.players if p.name == name][0]
        return False

    def use(self, player, card):
        ret = player.use(card)
        if not ret:
            self.me(f"@{player.name} 无此卡 或 使用【犯人】卡")
        else:
            player.used.append(ret)
            if card in ["外星人", "感染者", "学生会长", "图书委员"]:
                if card in ["外星人", "学生会长"]:
                    self.me(f"@{player.name} 使用了一张【{card}】，但无效果")
                elif card == "感染者":
                    if not len(self.body):
                        self.me(f"@{player.name} 使用了一张【{card}】，但调和区是空的")
                    else:
                        rcard = pop(self.body)
                        player.cards.append(rcard)
                        self.me(f"@{player.name} 使用了一张【{card}】,抽走了随机一张调和牌")
                        self.dm(player.id, f"你得到了【{rcard.name}】")
                elif card == "图书委员":
                    self.dm(player.id, self.bodyCards())
                    self.me(f"@{player.name} 使用了一张【{card}】,查看了调和区")
                self.next_player()
            else:
                self.stage.cur = 2
                self.stage.skill = card
                if card == "优等生":
                    self.me(f"@{player.name} 使用了一张【{card}】,请外星人选择是否伪装犯人【/伪装】or【/不伪装】")
                    if not any(p.has("外星人") for p in self.players):
                        suspect = ["@" + p.name for p in self.players if p.has("犯人")][0]
                        self.dm(player.id, "犯人是" + suspect)
                        self.me(f"@{player.name} 已获得犯人信息")
                        self.next_player()
                    else:
                        to_p = [p.id for p in self.players if p.has("外星人")]
                        self.dm(to_p, "请选择是否伪装犯人【/伪装】or【/不伪装】")
                elif card == "风纪委员":
                    self.me(f"@{player.name} 使用了一张【{card}】,请选择要查看的目标玩家【/查看 玩家名】")
                elif card == "保健委员":
                    if not any(len(p.used) > 0 for p in self.players if p.name != player.name):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是其他人的已用区是空的")
                        self.next_player()
                    elif not any(
                            c.name != "保健委员" for p in self.players if p.name != player.name and len(p.used) > 0 for c in
                            p.used):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是不能取走【保健委员】")
                        self.next_player()
                    else:
                        self.me(f"@{player.name} 使用了一张【{card}】,请选择要取走卡牌的目标玩家【/取走 玩家名 卡牌名】")
                        self.showUsed()
                elif card == "归宅部":
                    if not len(self.body):
                        self.me(f"@{player.name} 使用了一张【{card}】，但调和区是空的")
                        self.next_player()
                    else:
                        self.me(f"@{player.name} 使用了一张【{card}】,请选择要交换调和牌的手牌【/交换 卡牌名】")
                elif card == "共犯":
                    if not len(player.suspect):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是你的质疑区是空的")
                        self.next_player()
                    else:
                        self.me(f"@{player.name} 使用了一张【{card}】,请选择要移动质疑牌的目标玩家【/移动 玩家名】")
                elif card == "大小姐":
                    if not any(not p.fixed for p in self.players if p.name != player.name):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是其他人都已固定身份")
                        self.next_player()
                    else:
                        self.me(f"@{player.name} 使用了一张【{card}】,请选择要抽走卡牌的目标玩家【/抽走 用户名】")
                elif card == "班长":
                    if not any(not p.fixed for p in self.players if p.name != player.name):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是其他人都已固定身份")
                        self.next_player()
                    else:
                        self.me(f"@{player.name} 使用了一张【{card}】,请选择要交换卡牌的目标玩家【/交换 用户名】")
                elif card == "新闻部":
                    if not any(not p.fixed for p in self.players if p.name != player.name):
                        self.me(f"@{player.name} 使用了一张【{card}】,但是其他人都已固定身份")
                        self.next_player()
                    else:
                        self.stage.to_p = []
                        self.me(f"@{player.name} 使用了一张【{card}】,请全体玩家选择要交换给下家的手牌【/交换 卡牌名】")

    def brew(self, player, card):
        ret = player.use(card)
        if not ret:
            self.me(f"@{player.name} 无此卡 或 使用【犯人】卡")
        else:
            self.body.append(ret)
            self.me(f"@{player.name} 添加了一张调和牌。目前调和区有\
                {len(self.body)}张卡牌，调和目标是{self.target}点")
            self.next_player()

    def suspect(self, player, to_name, card):
        to_p = self.find(to_name)
        if not to_p:
            return self.me(f"@{player.name} 玩家@{to_name}不存在")

        ret = player.use(card)
        if not ret:
            self.me(f"@{player.name} 无此卡 或 使用【犯人】卡")
        else:
            to_p.suspect.append(ret)
            self.me(f"@{player.name} 质疑了 @{to_p.name} | \
                     目前@{to_p.name} 有{len(to_p.suspect)}张质疑牌")
            self.next_player()

    def join(self, name, id):
        if any(p.name == name for p in self.players):
            self.me(f"@{name} 已经加入了游戏")
        else:
            self.players.append(Player(name, id))
            self.me(f"@{name} 加入游戏")

    def quit(self, name):
        if any(p.name == name for p in self.players):
            self.players = list(filter(lambda p: p.name != name, self.players))
            self.me(f"@{name} 退出游戏")
        else:
            self.me(f"@{name} 未加入游戏")

    def showPlayers(self):
        self.say("玩家:\n" + "\n".join(f"{i + 1}.@{p.name}【{len(p.cards)}】 {'已固定身份' if p.fixed else '未固定身份'}" \
                                     for i, p in enumerate(self.players)))

    def showRoles(self):
        self.say("玩家身份:\n" + "\n".join(f"{i + 1}.@{p.name} 【{p.cards[0].name}】" \
                                       for i, p in enumerate(self.players)))

    def showBody(self):
        self.me(f"目前调和区有{len(self.body)}张卡牌\n调和目标是{self.target}点")

    def bodyCards(self):
        return "调和区:\n" + "\n".join(f"{i + 1}.【{c.name}】(🧪{c.mp})" \
                                    for i, c in enumerate(self.body))

    def showUsed(self):
        self.say("已用区:\n" + "\n".join(f"{i + 1}." + p.showUsed() \
                                      for i, p in enumerate(self.players)))

    def showSuspect(self):
        self.say("目前质疑情况；:\n" + "\n".join(f"{i + 1}.@{p.name} {len(p.suspect)}张" \
                                          for i, p in enumerate(self.players)))

    def showSuspectCards(self):
        self.say("质疑区:\n" + "\n".join(f"{i + 1}." + p.showSuspect() \
                                      for i, p in enumerate(self.players)))

    def prepare(self):
        self.me("开始发牌...")
        self.n = len(self.players)
        n = self.n
        self.target = 12 - n
        self.deck = [WXR()] * 1 + [GRZ()] * 1 + [FR()] * 1 + [GF()] * 0 + [XSHZ()] * 1 \
                    + [BZ()] * 2 + [YDS()] * 1 + [FJWY()] * 1 + [BJWY()] * 2 + [TSWY()] * 2 \
                    + [DXJ()] * 2 + [XWB()] * 2 + [GZB()] * 2
        if n>3:
            self.deck.append([GF(), YDS(), FJWY(), DXJ(), XWB(), GZB()])
        if n==5:
            self.deck.append([TSWY()])
        random.shuffle(self.deck)
        m = len(self.deck)
        for i, j in zip(range(0, m, m // n), range(0, n)):
            self.players[j].cards = self.deck[i:i + m // n]
            self.dm(self.players[j].id, self.players[j].showCards())
        self.start()

    def start(self):
        self.stage.cur = 1
        self.stage.player = [p for p in self.players if p.has("学生会长")][0]
        self.me("出牌：【/使用 卡牌名】┃调和：【/调和 卡牌名】┃质疑：【/质疑 玩家名 卡牌名】")
        self.me(f"游戏开始，共{len(self.players)}人参加游戏，调和目标是{self.target}点。" + \
                f"请拥有【学生会长】的@{self.stage.player.name} 开始行动")

    def end(self):
        self.stage.cur = 3
        self.me("全体玩家身份固定，开始判定游戏结果")
        self.showRoles()
        self.showSuspectCards()
        self.say(self.bodyCards())

        result = "结果："
        sc = [0] * self.n
        for i in range(self.n):
            for c in self.players[i].suspect:
                sc[i] += c.mp
        prison = [i for i, s in enumerate(sc) if s == max(sc)]
        arr = " ".join("@" + self.players[i].name for i in prison)
        if len(prison) == self.n:
            prison = []
            arr = "无人"
        result += "\n监禁结果：" + arr + " 被监禁"

        body = 0
        brew = False
        for c in self.body:
            body += c.mp
        if body > self.target:
            brew = True
            result += f"\n调和结果：【{body}/{self.target}】调和成功"
        else:
            result += f"\n调和结果：【{body}/{self.target}】调和失败"

        result += "\n最终结果："

        def arrest(card):
            return any(self.players[i].cards[0].name == card for i in prison)

        def all(card):
            return ["@" + p.name for p in self.players if p.cards[0].name == card]

        if arrest("外星人"):
            winner = all("外星人")[0]
            result += f"【外星人】{winner} 取得胜利"
        elif self.has("感染者") and not brew:
            winner = all("感染者")[0]
            result += f"【感染者】{winner} 取得胜利"
        elif self.has("犯人") and not arrest("犯人"):
            winner = "【犯人】" + all("犯人")[0]
            if self.has("共犯"):
                winner += "  【共犯】" + all("共犯")[0]
            result += f"{winner} 取得胜利"
        elif brew and (self.has("学生会长") or self.has("班长") or self.has("优等生") or self.has("风纪委员")
                       or self.has("保健委员") or self.has("图书委员") or self.has("大小姐") or self.has("新闻部")):
            result += f"【好人集团】取得胜利"
        elif self.has("归宅部"):
            winner = " ".join(all("归宅部"))
            result += f"【归宅部】{winner} 取得胜利"
        else:
            result += f"无人获胜"

        self.result = result
        self.say(result)
        self.me("如需再次查看结果请回复【/s】查看其他信息请回复【/身份】【/已用区】【/质疑区】【/调和区】※重新开局【/game】")


class BingTa(Module):

    def unload(self):
        pass

    @property
    def cmds(self):
        cmd_dict = {'play': r'.*'}
        return cmd_dict

    # ===========================================游戏代码区==============================================================

    def play(self, message):
        type = message.type
        tmsg = Message_Type.message
        tme = Message_Type.me
        tdm = Message_Type.dm

        if type == tmsg or type == tme or type == tdm:
            msg = message.message
            uid = message.user.id
            user = message.user.name
            game = self.game
            stage = game.stage

            def say(cont):
                self.bot.send(cont)

            def me(cont):
                say("/me" + cont)

            def dm(uid, cont):
                self.bot.dm(uid, cont)

            # ------------------------游戏事件---------------------

            # 指令说明
            if chk(msg, r"^/指令") or chk(msg, r"^/cmd"):
                cmd = '''游戏指令
/游戏 回到报名阶段┃/go 开始游戏
/s 查看状态┃/p 查看玩家
+1 加入游戏┃-1 退出游戏
/手牌 查看手牌┃/调和 查看调和牌数量
/质疑 查看所有玩家质疑牌数量
/已用区 查看所有玩家的已用牌
/取消 放弃使用卡牌技能（防卡死）
'''
                say(cmd)

            elif chk(msg, r"^/游戏") or chk(msg, r"^/game"):
                game.reset()
            elif chk(msg, r"^/p"):
                game.showPlayers()
            elif chk(msg, r"^/keep"):
                dm(uid, "ok")
            elif chk(msg, r"^/s"):
                if stage.cur == 0:
                    me("报名阶段")
                elif stage.cur == 1:
                    me(f"@{stage.player.name} 行动中")
                elif stage.cur == 2:
                    me(f"@{stage.player.name} 发动【{stage.skill}】的技能中")
                elif stage.cur == 3:
                    say(game.result)

            # stage 0 预备阶段
            if stage.cur == 0:
                if chk(msg, r"^\+1"):
                    game.join(user, uid)
                elif chk(msg, r"^-1"):
                    game.quit(user)
                elif chk(msg, r"^/go"):
                    if len(game.players) not in range(3,7):
                        me(f"游戏人数为3~6人，目前报名玩家{len(game.players)}人")
                    else:
                        game.prepare()

            # stage 1 出牌阶段
            elif stage.cur == 1 and any(p.name == user for p in game.players):
                player = [p for p in game.players if p.name == user][0]
                if chk(msg, r"^/手牌"):
                    dm(player.id, player.showCards())
                elif chk(msg, r"^/调和$"):
                    game.showBody()
                elif chk(msg, r"^/质疑$"):
                    game.showSuspect()
                elif chk(msg, r"^/已用区"):
                    game.showUsed()
                elif stage.player.name == user:
                    if chk(msg, r"^/调和\s+\S+"):
                        card = msg.split()[1]
                        game.brew(player, card)
                    if chk(msg, r"^/使用\s+\S+"):
                        card = msg.split()[1]
                        game.use(player, card)
                    elif chk(msg, r"^/质疑\s+\S+\s+\S+"):
                        msg_split = msg.split()
                        to_p = ckn(msg_split[1])
                        card = msg_split[2]
                        game.suspect(player, to_p, card)

            # stage 2 技能阶段
            elif stage.cur == 2 and any(p.name == user for p in game.players):
                player = [p for p in game.players if p.name == user][0]
                if chk(msg, r"^/手牌"):
                    dm(player.id, player.showCards())
                elif chk(msg, r"^/调和$"):
                    game.showBody()
                elif chk(msg, r"^/质疑$"):
                    game.showSuspect()
                elif chk(msg, r"^/已用区"):
                    game.showUsed()
                elif stage.skill == "优等生" and player.has("外星人"):
                    suspect = ["@" + p.name for p in game.players if p.has("犯人")][0]
                    if chk(msg, r"^/伪装"):
                        suspect += " @" + user
                        dm(stage.player.id, "犯人是" + suspect)
                        me(f"@{stage.player.name} 获得了犯人信息")
                        game.next_player()
                    elif chk(msg, r"^/不伪装"):
                        dm(stage.player.id, "犯人是" + suspect)
                        me(f"@{stage.player.name} 已获得犯人信息")
                        game.next_player()
                elif stage.skill == "风纪委员" and user == stage.player.name:
                    if chk(msg, r"^/查看\s+\S+"):
                        to_p = game.find(ckn(msg.split()[1]))
                        if not to_p:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 不存在")
                        else:
                            dm(player.id, to_p.showCards())
                            me(f"@{player.name} 查看了@{to_p.name} 的卡牌")
                            game.next_player()
                elif stage.skill == "保健委员" and user == stage.player.name:
                    if chk(msg, r"^/取走\s+\S+\s+\S+"):
                        to_p = game.find(ckn(msg.split()[1]))
                        if not to_p:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 不存在")
                        elif to_p.name == user:
                            me(f"@{player.name} 不能取走自己的牌")
                        else:
                            card = msg.split()[2]
                            rcard = to_p.get(card)
                            if not rcard:
                                me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 的已用牌中没有【{msg.split()[2]}】")
                            else:
                                player.cards.append(rcard)
                                me(f"@{player.name} 取走了@{to_p.name} 已用的【{rcard.name}】")
                                game.next_player()
                elif stage.skill == "归宅部" and user == stage.player.name:
                    if chk(msg, r"^/交换\s+\S+"):
                        card = msg.split()[1]
                        rcard = player.lose(card)
                        if not rcard:
                            me(f"@{player.name} 你没有这张牌")
                        else:
                            lcard = pop(game.body)
                            game.body.append(rcard)
                            player.cards.append(lcard)
                            dm(player.id, f"你得到了【{lcard.name}】")
                            me(f"@{player.name} 交换了一张调和牌")
                            game.next_player()
                elif stage.skill == "共犯" and user == stage.player.name:
                    if chk(msg, r"^/移动\s+\S+"):
                        to_p = game.find(ckn(msg.split()[1]))
                        if not to_p:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 不存在")
                        else:
                            to_p.suspect.append(pop(player.suspect))
                            me(f"@{player.name} 移动了自己的一张质疑牌给 @{to_p.name}")
                            game.next_player()
                elif stage.skill == "大小姐" and user == stage.player.name:
                    if chk(msg, r"^/抽走\s+\S+"):
                        to_p = game.find(ckn(msg.split()[1]))
                        if not to_p:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 不存在")
                        elif to_p.fixed:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 只有一张身份牌了")
                        else:
                            card = pop(to_p.cards)
                            player.cards.append(card)
                            stage.to_p = to_p
                            dm(to_p.id, f"你失去了【{card.name}】")
                            dm(player.id, f"你得到了【{card.name}】")
                            me(f"@{player.name} 抽走了@{to_p.name} 的一张卡牌，请选择要返还的卡牌【/返还 卡牌名】")
                            stage.skill = "大小姐（返还卡牌）"
                elif stage.skill == "大小姐（返还卡牌）" and user == stage.player.name:
                    if chk(msg, r"^/返还\s+\S+"):
                        card = msg.split()[1]
                        rcard = player.lose(card)
                        if not rcard:
                            me(f"@{player.name} 你没有这张牌")
                        else:
                            stage.to_p.cards.append(rcard)
                            dm(stage.to_p.id, f"你得到了【{card}】")
                            me(f"@{player.name} 返还了@{stage.to_p.name}一张牌")
                            game.next_player()
                elif stage.skill == "班长" and user == stage.player.name:
                    if chk(msg, r"^/交换\s+\S+"):
                        to_p = game.find(ckn(msg.split()[1]))
                        if not to_p:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 不存在")
                        elif to_p.fixed:
                            me(f"@{player.name} 玩家@{ckn(msg.split()[1])} 只有一张身份牌了")
                        else:
                            stage.to_p = {"p": to_p, "s":[]}
                            me(f"@{player.name} @{to_p.name} 请各自选择要交换的卡牌【/交换 卡牌名】")
                            stage.skill = "班长（交换卡牌）"
                elif stage.skill == "班长（交换卡牌）" and user in [player.name, stage.to_p["p"].name]\
                                                    and user not in stage.to_p["s"]:
                    if chk(msg, r"^/交换\s+\S+"):
                        card = msg.split()[1]
                        rcard = player.lose(card)
                        if not rcard:
                            me(f"@{player.name} 你没有这张牌")
                        elif player.fixed:
                            me(f"@{player.name} 你只有一张身份牌了")
                        else:
                            p = stage.player
                            t = stage.to_p["p"]
                            if user == stage.to_p["p"].name:
                                p = stage.to_p["p"]
                                t = stage.player
                            t.cards.append(rcard)
                            stage.to_p["s"].append(user)
                            dm(t.id, f"你得到了【{card}】")
                            me(f"@{p.name} 交给了@{t.name} 一张牌")
                            if len(stage.to_p["s"])==2:
                                game.next_player()
                elif stage.skill == "新闻部" and user not in stage.to_p:
                    if chk(msg, r"^/交换\s+\S+"):
                        card = msg.split()[1]
                        rcard = player.lose(card)
                        if not rcard:
                            me(f"@{player.name} 你没有这张牌")
                        else:
                            idx = [i for i, p in enumerate(game.players) if p.name == player.name][0]
                            while True:
                                idx += 1
                                if idx == len(game.players): idx = 0
                                if not game.players[idx].fixed:  break
                                if game.players[idx].name == player.name:
                                    say("ERROR!")
                                    game.next_player()
                                    break
                            to = game.players[idx]
                            to.cards.append(rcard)
                            stage.to_p.append(user)
                            dm(to.id, f"你得到了【{card}】")
                            me(f"@{player.name} 交给了@{to.name} 一张牌")
                            if not any(p.name not in stage.to_p for p in game.players if not p.fixed):
                                game.next_player()
                elif chk(msg, r"^/取消") and user == stage.player.name:
                    me(f"@{player.name} 放弃使用【{stage.skill}】的技能")
                    game.next_player()

            # stage 3 结束阶段
            elif stage.cur == 3:
                if chk(msg, r"^/身份"):
                    game.showRoles()
                elif chk(msg, r"^/已用区"):
                    game.showUsed()
                elif chk(msg, r"^/调和区"):
                    say(game.bodyCards())
                elif chk(msg, r"^/质疑区"):
                    game.showSuspectCards()

    # =========================================================================================================

    def __init__(self, bot):
        super().__init__(bot)
        self.game = Game(Stage(), bot)
    