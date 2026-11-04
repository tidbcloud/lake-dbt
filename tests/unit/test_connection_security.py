from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from dbt.adapters.tidbcloudlake import connections


def credentials(**kwargs):
    return connections.TiDBCloudLakeCredentials(
        host="lake.example", username="test-user", password="test-password",
        schema="default", **kwargs,
    )


@pytest.mark.parametrize("secure", [None, True])
def test_direct_dsn_builder_defaults_to_tls(secure):
    dsn = connections.TiDBCloudLakeConnectionManager.build_dsn(credentials(secure=secure))
    assert parse_qs(urlsplit(dsn).query)["sslmode"] == ["require"]


def test_explicit_http_is_preserved_and_visible(monkeypatch):
    logger = Mock()
    monkeypatch.setattr(connections, "logger", logger)
    dsn = connections.TiDBCloudLakeConnectionManager.build_dsn(credentials(secure=False))
    assert parse_qs(urlsplit(dsn).query)["sslmode"] == ["disable"]
    logger.warning.assert_called_once()
    assert "test-password" not in logger.warning.call_args.args[0]


def test_private_ca_path_is_forwarded_and_encoded():
    ca = "/etc/ssl/private CA/湖.pem"
    creds = credentials(secure=True, tls_ca_file=ca, warehouse="test-wh")
    dsn = connections.TiDBCloudLakeConnectionManager.build_dsn(creds)
    query = parse_qs(urlsplit(dsn).query)
    assert query["tls_ca_file"] == [ca]
    assert query["warehouse"] == ["test-wh"]
    assert query["sslmode"] == ["require"]


def test_open_and_direct_builder_agree_on_tls_default(monkeypatch):
    connect = Mock(return_value=object())
    monkeypatch.setattr(connections, "connect", connect)
    conn = SimpleNamespace(credentials=credentials(), state="init", handle=None)
    direct = connections.TiDBCloudLakeConnectionManager.build_dsn(conn.credentials)
    connections.TiDBCloudLakeConnectionManager.open(conn)
    connect.assert_called_once_with(direct)
    assert conn.state == "open"


def test_debug_keys_show_transport_settings_without_secrets():
    keys = credentials()._connection_keys()
    assert "secure" in keys
    assert "tls_ca_file" in keys
    assert "username" in keys
    assert "password" not in keys
