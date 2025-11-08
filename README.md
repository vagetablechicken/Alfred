# Alfred

管家，定时提醒，每日总结待办事项的完成情况。

苦免费版todo management卡脖子久矣。

websocket模式，只需要运行App，不需要公网IP来接收slack的event。

创建App，开启Socket Mode，获取Bot Token和App Token，设置权限TODO

```bash
# linux or macOS
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
export SLACK_APP_TOKEN="xapp-your-slack-app-token"
python app.py
```

```powershell
# Windows
$env:SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
$env:SLACK_APP_TOKEN="xapp-your-slack-app-token"
python app.py
```

然后在Slack中邀请bot加入频道。


测试
```bash
/alfred test
```
