# Alfred

Alfred管家，她会负责时间管理：
- 定时创建提醒message，发送到slack，可以slack中选择完成任务/撤销完成。
- 再过一个ddl，还不完成就escalate到指定用户。
- 每日总结待办事项的完成情况，方便leader检查，避免遗忘。（不要通过这个方式批评下属，工作多了是容易忘记的，此项目旨在帮助大家更好地检查任务完成情况）

苦免费版todo management卡脖子久矣。要不不能集成到slack，要不不能自动生成任务，要不付费过于离谱，索性自己写一个。

## Architecture

Alfred 分两个大模块：
- Task：负责任务的创建、存储、状态更新等核心逻辑。也负责更新db中的任务状态。
- Slack：负责从db中主动读取任务，发送提醒。也负责与Slack交互，接收用户命令，更新任务状态。

### Task

基于 APScheduler 定时任务调度器，定时检查任务状态，创建提醒任务。

元数据保存在sqlite数据库中，方便持久化存储和查询。后续可以考虑换成更复杂的数据库。

### Slack

Websocket模式，不需要公网IP来接收Slack的Event。

创建App，开启Socket Mode，获取Bot Token和App Token，设置权限TODO

## 安装与配置

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置文件

Alfred 使用 YAML 配置文件：
- **`config.yaml`** - 生产环境配置（数据库：`tasks.db`）
- **`config.test.yaml`** - 测试环境配置（数据库：`:memory:`）

测试时会自动使用 `config.test.yaml`，无需手动切换。

如需使用自定义配置：
```bash
export ALFRED_CONFIG=config.custom.yaml
```

### 3. 运行

先editable安装：
```bash
pip install -e .
```

配置Slack Token环境变量并运行Alfred：
```bash
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
export SLACK_APP_TOKEN="xapp-your-slack-app-token"
alfred
```

```powershell
# Windows
$env:SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
$env:SLACK_APP_TOKEN="xapp-your-slack-app-token"
alfred
```

### 4. 测试

```bash
pytest  # 自动使用 config.test.yaml（内存数据库）
```

然后在Slack中邀请bot加入频道。


测试
mock request，不用和slack通信。


slack中可以通过命令行测试，检查权限，交互是否正确等：
```
/alfred test
```
