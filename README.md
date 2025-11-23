# Alfred

Alfred管家，她会负责时间管理：
- 定时创建提醒message，发送到slack频道，可以slack中选择完成任务/撤销完成。
- 再过一个ddl，还不完成就再发一次提醒到slack频道。（目前未实现escalate DM到指定用户。）
- 每日总结待办事项的完成情况，方便leader检查，避免遗忘。（不要通过这个方式批评下属，工作多了是容易忘记的，此项目旨在帮助大家更好地检查任务完成情况。）

苦免费版todo management卡脖子久矣。要不不能集成到slack，要不不能自动生成任务，要不付费过于离谱，索性自己写一个。

## Architecture

Alfred 分两个大模块：
- Task：负责任务的创建、存储、状态更新等核心逻辑，也负责更新db中的任务状态。
- Slack：负责从db中主动读取任务，发送提醒。也负责与Slack交互，接收用户命令，更新任务状态。

### Task

基于 APScheduler 定时任务调度器，定时检查任务状态，创建提醒任务。

DB设计和使用方法请参考 [DATABASE](docs/DATABASE.md)。如果不特别准备，建议使用SQLite3最快开始。

### Slack

Websocket模式，不需要公网IP来接收Slack的Event。

创建App，开启Socket Mode，获取Bot Token和App Token，设置权限TODO

## 安装与配置

### 1. 安装依
```bash
pip install -e ".[test]"
```

### 2. 配置文件

Alfred 使用 YAML 配置文件：
- **`config.yaml`** - 生产环境配置
- **`config.test.yaml`** - 测试环境配置

测试时会自动使用 `config.test.yaml`，无需手动切换。

如需使用自定义配置：
```bash
export ALFRED_CONFIG=config.custom.yaml
```

### 3. 运行

配置Slack Token环境变量并运行Alfred：
```bash
# Linux/Mac
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

然后在Slack中邀请bot加入频道。

Slack中可以通过命令行测试，检查权限，交互是否正确等：

```
/alfred test
```

### 4. 测试

Alfred 使用 pytest 进行测试，自动使用 `config.test.yaml`。

#### 运行单元测试（默认）

```bash
# 默认跳过集成测试
pytest
```

所有单元测试会自动 mock Slack API，不需要真实的 Slack token，不要在未配置Slack token时运行集成测试。

#### 运行集成测试

集成测试需要真实的 Slack API 连接：

```bash
# 设置真实的 Slack tokens
export SLACK_BOT_TOKEN="xoxb-your-real-token"
export SLACK_APP_TOKEN="xapp-your-real-token"

# 运行集成测试
pytest -m integration
```

#### 运行所有测试

```bash
# 包括单元测试和集成测试
pytest -m ""
```

## Slack 进阶

如果对TODO界面有更高要求，可以参考[Slack Block Kit](https://api.slack.com/block-kit)自定义消息界面。并在`alfred/slack/block_builder.py`中替换相关函数。

需要预览和调试Block，可以使用官方的Block Kit Builder工具：https://app.slack.com/block-kit-builder 。运行测试[test_block_builder.py](tests/test_block_builder.py)可以获得Block样例，复制到Block Kit Builder中进行预览和调试。

## 贡献

请先创建issue讨论需求，再提交PR。

## TODO

- 时区支持
- 文档完善
- 实现任务升级（escalate）功能，未完成任务自动DM给指定用户。
