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
  path: ":memory:"  # 内存数据库，测试后自动清除
logging:
  level: "DEBUG"
```

## 自动配置选择

**pytest 运行时自动使用测试配置:**
```bash
pytest  # 自动使用 config.test.yaml，数据库为 :memory:
```

**生产环境运行自动使用生产配置:**
```bash
python -m src.alfred  # 自动使用 config.yaml
```

## 手动指定配置

通过环境变量 `ALFRED_CONFIG` 指定配置文件：

```bash
# Linux/macOS
export ALFRED_CONFIG=config.custom.yaml
python -m src.alfred

# Windows PowerShell
$env:ALFRED_CONFIG="config.custom.yaml"
python -m src.alfred
```

## 在代码中使用

```python
from utils.config import get_db_path, load_config

# 获取数据库路径（自动根据环境选择配置）
db_path = get_db_path()

# 或手动指定配置文件
db_path = get_db_path('config.test.yaml')

# 加载完整配置
config = load_config()
```

## 测试中的使用

测试代码会自动使用内存数据库，无需任何配置：

```python
def test_something():
    # 这里的 task_engine 会自动使用 :memory: 数据库
    from task.task_engine import task_engine
    # ... 测试代码
```

如需在测试中使用自定义数据库：

```python
@pytest.fixture
def custom_engine(tmp_path):
    from task.task_engine import TaskEngine
    from task.database.database_manager import DatabaseManager
    
    db = DatabaseManager(str(tmp_path / "test.db"))
    db.create_tables()
    return TaskEngine(db)
```

## 配置项说明

### database.path
- **类型**: string
- **说明**: 数据库文件路径
- **值**:
  - 相对路径（如 `"tasks.db"`）：相对于项目根目录
  - 绝对路径（如 `"C:/data/tasks.db"`）
  - `:memory:`：内存数据库（测试用，数据不持久化）

### logging.level
- **类型**: string
- **选项**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **默认**: INFO

## 环境变量

- **ALFRED_CONFIG**: 指定配置文件路径（可选）
- **PYTEST_CURRENT_TEST**: pytest 自动设置，用于检测测试环境

## 优势

1. ✅ **自动切换** - pytest 运行时自动使用测试配置
2. ✅ **测试隔离** - 测试使用内存数据库，互不干扰
3. ✅ **简单配置** - YAML 格式，易于阅读和修改
4. ✅ **灵活覆盖** - 可通过环境变量手动指定配置
5. ✅ **向后兼容** - 现有代码无需修改
