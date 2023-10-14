# DrrrBot

简体中文

一个用于 drrr.com 的Python机器人

该项目是基于 [Transfusion/durararobot](https://github.com/Transfusion/durararobot) 进行修改的。

所做的修改：
* 删除了后台交互终端。
* 添加了房间消息的本地日志（保存在`logs`文件夹中）。
* 添加了自动保持连接的功能（定时向机器人发送私信）。
* 添加了配置文件（`config.txt`）。
* 添加了一些异常处理和自动处理功能。



## 快速开始

```
# 运行演示脚本

node script/demo.mjs
```



## 配置

你可以通过编辑`config.txt`文件来配置机器人。

```
# 个人资料
name = test
tc = mytc123
avatar = setton
roomID = UgaX0cBVAT

lang = en-US
agent = Bot

# 保存的Cookies文件
saves = saves.json

# 发送消息的等待时间
sendInterval = 1800

# 获取消息的等待时间
getInterval = 300
```

* 如果你想将某项配置保持默认，可以删除那一行。
* Tripcode（`tc`）可选。如果想无tc登录，只需删除该行。
* `RoomID`可以在房间的URL中找到，例如：https://drrr.com/room/UgaX0cBVAT。
* 推荐将`SendInterval`设置为至少1000ms，如果发送消息太快，你的IP可能会被封禁。
* Cookies将保存在`saves.json`文件中，如果想重置Cookies，只需删除该文件。




## 示例

```js
// script/demo.mjs

import { start } from '../bot.mjs'


start(main) // 启动此脚本

// 主函数
function main(){
    print("start main") // console.log已绑定到print函数。
    drrr.print("/me hello world")

    drrr.event(['msg', 'me', 'dm'] ,(user, cont, tc, url) => {
        if (cont == "/msg"){
            drrr.print(`@${user} msg ok`)
            drrr.print(`/me@${user} me ok`)
        }
    })

    drrr.event('msg' ,(user, cont) => {
        if (cont == "/dm"){
            drrr.dm(user, `@${user} dm ok`)
        }
    })

    drrr.event('join' ,user => {
        drrr.print(`@${user} welcome`)
    })

    /*
        在此处编写你的脚本。
    */
}
```




## 函数

你可以在回调函数（`cb`）中使用以下函数，然后在脚本中运行`start(cb)`。

* `drrr.print(msg, url)`: 将消息（`msg`）发送到房间中。（`url`可选）

* `drrr.dm(name, msg, url)`: 向`name`指定的用户发送私信（`msg`）。（`url`可选）

* `drrr.play(name, url)`: 在房间播放名字为`name`、链接为`url`的音乐。

* `drrr.chown(name)`: 将房间的主机更改为`name`指定的其他用户。

* `drrr.host(name)`: 与`drrr.chown`相同。

* `drrr.kick(name)`: 将`name`指定的用户踢出房间。

* `drrr.ban(name)`: 屏蔽`name`指定的用户重新加入房间。

* `drrr.unban(name)`: 解除对`name`指定的用户的屏蔽，允许他们重新加入房间（如果先前被封禁）。

* `drrr.report(name)`: 举报并屏蔽`name`指定的用户。

* `drrr.title(name)`: 将房间标题设置为`name`指定的值。

* `drrr.descr(desc)`: 将房间描述设置为`desc`指定的值。

* `drrr.join(roomID)`: 让机器人加入由`roomID`指定的房间。

* `drrr.leave()`: 让机器人离开房间。




## 事件

* `msg`: 当接收到普通消息时触发。

* `me`: 当接收到“/me”消息时触发。

* `dm`: 当接收到私信时触发。

* `join`: 当有用户加入房间时触发。

* `leave`: 当有用户离开房间时触发。

* `music`: 当有用户在房间中播放音乐时触发。




## 用户代理

```
Desktop（桌面）
Mobile（手机）
Bot（机器人）
Tv（电视）
Tablet（平板）
```


## 头像

![Avatar](avatar.jpg)