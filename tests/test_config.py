"""测试配置加载"""
import os
from alfred.utils.config import get_vault_path, load_config


def test_load_default_config():
    """测试加载默认配置"""
    config = load_config('config.yaml')
    assert 'vault' in config
    assert 'prod.db' in config['vault']['path']


def test_load_test_config():
    """测试加载测试配置"""
    config = load_config('config.test.yaml')
    assert 'vault' in config
    assert 'test.db' in config['vault']['path']


def test_get_vault_path_production():
    """测试生产环境数据库路径"""
    db_path = get_vault_path('config.yaml')
    assert db_path.endswith('prod.db')


def test_get_vault_path_test():
    """测试环境数据库路径"""
    db_path = get_vault_path('config.test.yaml')
    assert db_path.endswith('test.db')


def test_auto_use_test_config_in_pytest():
    """pytest 运行时应该自动使用测试配置"""
    # 这个测试本身在 pytest 中运行，所以会自动使用测试配置
    db_path = get_vault_path()
    # 在 pytest 环境下应该使用测试数据库
    assert db_path.endswith('test.db')


def test_custom_config_via_env(monkeypatch, tmp_path):
    """测试通过环境变量指定配置文件"""
    # 创建自定义配置文件
    custom_config = tmp_path / "custom.yaml"
    custom_config.write_text("""
database:
  path: "custom.db"
""")
    
    monkeypatch.setenv('ALFRED_CONFIG', str(custom_config))
    config = load_config()
    
    assert config['database']['path'] == 'custom.db'
