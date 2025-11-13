# Alfred 配置说明

## 配置文件

Alfred 使用 YAML 配置文件管理环境配置。

### config.yaml (生产环境)
```yaml
database:
  path: "tasks.db"  # 数据库文件路径
logging:
  level: "INFO"
```

### config.test.yaml (测试环境)
```yaml
database:
  path: "test.db"  # 测试数据库文件路径
logging:
  level: "DEBUG"
```

## 自动配置选择

**pytest 运行时自动使用测试配置:**
```bash
pytest  # 自动使用 config.test.yaml
```

**生产环境运行自动使用生产配置:**
```bash
pip install -e .
alfred  # 自动使用 config.yaml
```

## 手动指定配置

通过环境变量 `ALFRED_CONFIG` 指定配置文件：

```bash
# Linux/macOS
export ALFRED_CONFIG=config.custom.yaml
alfred

# Windows PowerShell
$env:ALFRED_CONFIG="config.custom.yaml"
alfred
```

## 在代码中使用

```python
from alfred.utils.config import get_db_path, load_config

# 获取数据库路径（自动根据环境选择配置）
db_path = get_db_path()

# 或手动指定配置文件
db_path = get_db_path('config.test.yaml')

# 加载完整配置
config = load_config()
```

## 配置项说明

### vault.path
- **类型**: string
- **说明**: 数据库文件路径
- **值**:
  - 相对路径（如 `"tasks.db"`）：相对于运行目录
  - 绝对路径（如 `"C:/data/tasks.db"`）
  - 不建议使用`:memory:`，大部分的测试都是临时创建connection。

### vault.init_sql
- **类型**: string
- **说明**: 初始化数据库的 SQL 脚本路径
- **默认**: 代码内置默认脚本
- **值**:
  - 相对路径（如 `"init.sql"`）：相对于运行目录
  - 绝对路径（如 `"/path/to/init.sql"`）

### logging.level
- **类型**: string
- **选项**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **默认**: INFO

### slack.channel
- **类型**: string
- **说明**: Slack 通知频道名称
- **值**: 频道ID

### slack.admin
- **类型**: list of strings
- **说明**: Slack 管理员用户ID列表
- **值**: 用户ID列表

## 环境变量

- **ALFRED_CONFIG**: 指定配置文件路径（可选）
- **PYTEST_CURRENT_TEST**: pytest 自动设置，用于检测测试环境
