"""简单的配置加载器"""
import os
import sys
import yaml
from pathlib import Path


def _is_pytest_running():
    """检测是否在 pytest 环境中运行"""
    # 方法1: 检查 PYTEST_CURRENT_TEST 环境变量（pytest 设置）
    if 'PYTEST_CURRENT_TEST' in os.environ:
        return True
    
    # 方法2: 检查 sys.modules 中是否已导入 pytest
    if 'pytest' in sys.modules:
        return True
    
    # 方法3: 检查命令行参数
    if any('pytest' in arg.lower() for arg in sys.argv):
        return True
    
    return False


def load_config(config_file: str = None):
    """
    加载配置文件
    
    优先级:
    1. config_file 参数
    2. ALFRED_CONFIG 环境变量
    3. pytest 环境下自动使用 config.test.yaml
    4. 默认使用 config.yaml
    """
    if config_file is None:
        # 检查环境变量
        config_file = os.getenv('ALFRED_CONFIG')
        
        if config_file is None:
            # pytest 运行时自动使用测试配置
            if _is_pytest_running():
                config_file = 'config.test.yaml'
            else:
                config_file = 'config.yaml'
    
    # 找到项目根目录
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / config_file
    
    if not config_path.exists():
        # 如果配置文件不存在，返回默认配置
        return {
            'database': {'path': 'tasks.db'},
            'logging': {'level': 'INFO'}
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def get_db_path(config_file: str = None) -> str:
    """获取数据库路径"""
    config = load_config(config_file)
    db_path = config.get('database', {}).get('path', 'tasks.db')
    
    # 如果是相对路径且不是内存数据库，转为绝对路径
    if not os.path.isabs(db_path) and db_path != ':memory:':
        project_root = Path(__file__).parent.parent.parent
        db_path = str(project_root / db_path)
    
    return db_path
