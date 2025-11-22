"""Test configuration loading"""
import pytest
from alfred.utils.config import _is_pytest_running, get_vault_path, load_config

def test_default_config_loading():
    """Test loading default config file"""
    assert _is_pytest_running(), "Should detect pytest is running"
    config = load_config()
    assert isinstance(config, dict)
    # Assuming default config.yaml has a 'vault' section
    assert 'vault' in config
    assert 'path' in config['vault']


def test_custom_config_via_env(monkeypatch, tmp_path):
    """Test specifying config file via environment variable"""
    # Create custom config file
    custom_config = tmp_path / "custom.yaml"
    custom_config.write_text("""
database:
  path: "custom.db"
""")
    
    monkeypatch.setenv('ALFRED_CONFIG', str(custom_config))
    config = load_config()
    
    assert config['database']['path'] == 'custom.db'

def test_get_vault_path(monkeypatch, tmp_path):
    """Test getting vault path from config"""
    # Create custom config file
    custom_config = tmp_path / "custom.yaml"
    custom_config.write_text("""
vault:
  path: "custom.vault"
""")

    monkeypatch.setenv('ALFRED_CONFIG', str(custom_config))
    with pytest.raises(ValueError):
        get_vault_path()  # Should raise because path is invalid

    custom_config.write_text("""
vault:
  path: "sqlite:///custom.vault"
""")
    path = get_vault_path()
    assert path == "sqlite:///custom.vault"
