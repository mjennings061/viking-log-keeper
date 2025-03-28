"""test_auth.py - Test cases for the auth module."""

import pytest
from unittest.mock import MagicMock, patch
from dashboard.auth import AuthConfig


# Mock environment variables
@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_VGS", "TESTVGS")
    monkeypatch.setenv("TEST_PASSWORD", "test_password")
    monkeypatch.setenv("TEST_AUTH_PASSWORD", "test_auth_password")


@pytest.fixture
def mock_auth_config():
    with patch('dashboard.auth.is_streamlit_running', return_value=False):
        with patch('dashboard.auth.kr') as mock_keyring:
            mock_keyring.get_password.side_effect = lambda project, key: {
                ("viking-log-keeper", "vgs"): "TESTVGS",
                ("viking-log-keeper", "password"): "test_password",
                ("viking-log-keeper", "auth_password"): "test_auth_password"
            }.get((project, key))
            config = AuthConfig()
            return config


def test_auth_config_init(mock_auth_config):
    """Test AuthConfig initialization."""
    assert mock_auth_config.db_name == "auth"
    assert mock_auth_config.db_collection_name == "auth"
    assert mock_auth_config.vgs == "TESTVGS"
    assert mock_auth_config.password == "test_password"
    assert not mock_auth_config.authenticated
    assert not mock_auth_config.connected


def test_validate_config_valid(mock_auth_config):
    """Test validate() with valid configuration."""
    assert mock_auth_config.validate() is True


def test_validate_config_invalid():
    """Test validate() with invalid configuration."""
    config = AuthConfig()
    config.vgs = None
    config.password = None
    assert config.validate() is False


def test_validate_config_invalid_auth_url():
    """Test validate() with invalid auth_url."""
    config = AuthConfig()
    config.vgs = "TESTVGS"
    config.password = "test_password"
    config.auth_url = "mongodb+srv://vgs_user:<password>@auth.example.com"
    assert config.validate() is False


def test_connect_success(mock_auth_config):
    """Test successful DB connection."""
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {'ok': 1.0}

    with patch('dashboard.auth.MongoClient', return_value=mock_client):
        assert mock_auth_config._connect() is True
        assert mock_auth_config.connected is True


def test_connect_failure(mock_auth_config):
    """Test failed DB connection."""
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {'ok': 0.0}

    with patch('dashboard.auth.MongoClient', return_value=mock_client):
        assert mock_auth_config._connect() is False
        assert mock_auth_config.connected is False


def test_connect_exception(mock_auth_config):
    """Test DB connection with exception."""
    mock_client = MagicMock()
    mock_client.admin.command.side_effect = Exception("Connection error")

    with patch('dashboard.auth.MongoClient', return_value=mock_client):
        assert mock_auth_config._connect() is False
        assert mock_auth_config.connected is False


def test_login_success(mock_auth_config):
    """Test successful login."""
    with patch.object(mock_auth_config, '_connect', return_value=True):
        mock_auth_config.client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            'vgs': 'TESTVGS',
            'password': 'test_password',
            'allowed_vgs': ['TESTVGS']
        }
        mock_db.__getitem__.return_value = mock_collection
        mock_auth_config.client.__getitem__.return_value = mock_db
        mock_auth_config.connected = True
        assert mock_auth_config._login('TESTVGS', 'test_password') is True
        assert mock_auth_config.authenticated is True
        assert mock_auth_config.allowed_vgs == ['TESTVGS']


def test_login_failure_wrong_password(mock_auth_config):
    """Test login failure with wrong password."""
    with patch.object(mock_auth_config, '_connect', return_value=True):
        mock_auth_config.client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            'vgs': '661VGS',
            'password': 'correct_password',
            'allowed_vgs': ['661VGS']
        }
        mock_db.__getitem__.return_value = mock_collection
        mock_auth_config.client.__getitem__.return_value = mock_db
        mock_auth_config.connected = True
        assert mock_auth_config._login('TESTVGS', 'wrong_password') is False
        assert mock_auth_config.authenticated is False


def test_login_failure_user_not_found(mock_auth_config):
    """Test login failure when user is not found."""
    with patch.object(mock_auth_config, '_connect', return_value=True):
        mock_auth_config.client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db.__getitem__.return_value = mock_collection
        mock_auth_config.client.__getitem__.return_value = mock_db
        mock_auth_config.connected = True
        assert mock_auth_config._login('nonexistent_vgs', 'test_password') is False
        assert mock_auth_config.authenticated is False


def test_fetch_log_sheets_credentials_success(mock_auth_config):
    """Test successful credentials fetch."""
    with patch.object(mock_auth_config, '_login', return_value=True):
        mock_auth_config.client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            '_id': 'some_id',
            'vgs': 'testvgs',
            'url': 'mongodb://test',
            'username': 'test_user'
        }
        mock_db.__getitem__.return_value = mock_collection
        mock_auth_config.client.__getitem__.return_value = mock_db
        mock_auth_config.authenticated = True
        credentials = mock_auth_config.fetch_log_sheets_credentials('TESTVGS', 'test_password')
        assert credentials == {'url': 'mongodb://test', 'username': 'test_user'}


def test_fetch_log_sheets_credentials_failure(mock_auth_config):
    """Test failed credentials fetch."""
    with patch.object(mock_auth_config, '_login', return_value=False):
        credentials = mock_auth_config.fetch_log_sheets_credentials('TESTVGS', 'wrong_password')
        assert credentials == {}


def test_fetch_log_sheets_credentials_with_stored_auth(mock_auth_config):
    """Test credentials fetch using stored auth."""
    with patch.object(mock_auth_config, '_login', return_value=True):
        mock_auth_config.client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            '_id': 'some_id',
            'vgs': 'testvgs',
            'url': 'mongodb://test',
            'username': 'test_user'
        }
        mock_db.__getitem__.return_value = mock_collection
        mock_auth_config.client.__getitem__.return_value = mock_db
        mock_auth_config.authenticated = True
        credentials = mock_auth_config.fetch_log_sheets_credentials()
        assert credentials == {'url': 'mongodb://test', 'username': 'test_user'}


def test_close_connection(mock_auth_config):
    """Test close_connection."""
    mock_auth_config.client = MagicMock()
    mock_auth_config.close_connection()
    mock_auth_config.client.close.assert_called_once()


def test_update_credentials(mock_auth_config):
    """Test update_credentials."""
    mock_answers = {
        'vgs': 'TESTVGS',
        'password': 'new_password',
        'auth_password': 'new_auth_password'
    }

    with patch('dashboard.auth.inquirer.prompt', return_value=mock_answers):
        with patch('dashboard.auth.kr') as mock_keyring:
            mock_auth_config.update_credentials()
            assert mock_auth_config.vgs == 'TESTVGS'
            assert mock_auth_config.password == 'new_password'
            assert 'new_auth_password' in mock_auth_config.auth_url
            mock_keyring.set_password.assert_any_call('viking-log-keeper', 'vgs', 'TESTVGS')
            mock_keyring.set_password.assert_any_call('viking-log-keeper', 'auth_password', 'new_auth_password')
            mock_keyring.set_password.assert_any_call('viking-log-keeper', 'password', 'new_password')


def test_update_credentials_keyring_error(mock_auth_config):
    """Test update_credentials with keyring error."""
    mock_answers = {
        'vgs': 'TESTVGS',
        'password': 'new_password',
        'auth_password': 'new_auth_password'
    }

    with patch('dashboard.auth.inquirer.prompt', return_value=mock_answers):
        with patch('dashboard.auth.kr') as mock_keyring:
            mock_keyring.set_password.side_effect = Exception("Keyring error")
            mock_auth_config.update_credentials()
            assert mock_auth_config.vgs == 'TESTVGS'
            assert mock_auth_config.password == 'new_password'
            assert 'new_auth_password' in mock_auth_config.auth_url
