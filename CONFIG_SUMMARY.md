# 配置化完成 ✅

## 改动内容

### 新增文件
- ✅ `config.yaml` - 生产环境配置
- ✅ `config.test.yaml` - 测试环境配置（内存数据库）
- ✅ `src/utils/config.py` - 配置加载器
- ✅ `tests/test_config.py` - 配置测试
- ✅ `docs/CONFIG.md` - 配置文档

### 修改文件
- ✅ `src/task/task_engine.py` - 使用 `get_db_path()` 代替硬编码
- ✅ `requirements.txt` - 添加 `pyyaml` 依赖
- ✅ `README.md` - 更新安装和配置说明

## 核心特性

### 1. 自动环境检测
```python
# pytest 运行时 → 自动使用 config.test.yaml (内存数据库)
# 正常运行时 → 自动使用 config.yaml (tasks.db)
```

### 2. 手动指定配置
```bash
export ALFRED_CONFIG=config.custom.yaml
```

### 3. 向后兼容
```python
# 现有代码无需修改
from task.task_engine import task_engine
task_engine.run_scheduler(current_time)
```

## 使用方式

### 生产环境
```bash
# 自动使用 config.yaml
python -m src.alfred
```

### 测试环境
```bash
# 自动使用 config.test.yaml（内存数据库）
pytest
```

### 自定义配置
```bash
export ALFRED_CONFIG=my_config.yaml
python -m src.alfred
```

## 配置文件格式

**config.yaml (生产):**
```yaml
database:
  path: "tasks.db"
logging:
  level: "INFO"
```

**config.test.yaml (测试):**
```yaml
database:
  path: ":memory:"
logging:
  level: "DEBUG"
```

## 下一步

1. **安装依赖**
   ```bash
   pip install pyyaml
   ```

2. **验证配置**
   ```bash
   pytest tests/test_config.py -v
   ```

3. **运行所有测试**
   ```bash
   pytest
   ```

## 技术细节

- 使用 `PYTEST_CURRENT_TEST` 环境变量自动检测 pytest 环境
- 相对路径自动转换为绝对路径
- `:memory:` 使用 SQLite 内存数据库，测试后自动清除
- 配置文件不存在时使用默认值，不会报错

完整文档请查看 `docs/CONFIG.md`。
