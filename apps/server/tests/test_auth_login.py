"""登录接口的外部可观察行为：契约、家庭归属、失败信封、开发降级、启动日志。

断言只落在 HTTP 状态 / 错误信封 / 数据库里的家庭归属 / 日志文本上，
不碰私有函数，也不断言 SQL 写法。
"""
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.auth.models import Family, User
from app.main import app
from app.record.database import SessionLocal, engine

client = TestClient(app)

SERVER_DIR = Path(__file__).resolve().parents[1]

TOKEN_TTL_SECONDS = 30 * 86400


@pytest.fixture
def wechat_credentials(monkeypatch):
    monkeypatch.setenv("WECHAT_APPID", "wx-appid")
    monkeypatch.setenv("WECHAT_SECRET", "wx-secret")


@pytest.fixture
def dev_login(monkeypatch):
    monkeypatch.setenv("DEV_LOGIN", "1")


def _login(code: str):
    return client.post("/api/v1/auth/wechat", json={"code": code})


def _token_payload(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def _stored_families_and_users() -> tuple[list[Family], list[User]]:
    with SessionLocal() as db:
        return list(db.scalars(select(Family))), list(db.scalars(select(User)))


def _fake_wechat(json_body: dict | None = None, error: Exception | None = None):
    """把 httpx.AsyncClient 换成不联网的替身，用来模拟微信侧的回应。"""
    class _Response:
        def json(self):
            return json_body

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, *args, **kwargs):
            if error is not None:
                raise error
            return _Response()

    return _Client


def test_same_code_logs_into_the_same_user_and_family(dev_login):
    first = _login("openid-of-parent-a")
    second = _login("openid-of-parent-a")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["user_id"] == second.json()["user_id"]

    families, users = _stored_families_and_users()
    assert len(families) == 1
    assert len(users) == 1
    assert str(users[0].family_id) == str(families[0].id)
    assert _token_payload(first.json()["token"])["fid"] == _token_payload(second.json()["token"])["fid"]


def test_different_codes_get_different_users_and_families(dev_login):
    first = _login("openid-of-parent-a").json()
    second = _login("openid-of-parent-b").json()

    assert first["user_id"] != second["user_id"]

    families, users = _stored_families_and_users()
    assert len(families) == 2
    assert {str(user.id) for user in users} == {first["user_id"], second["user_id"]}
    assert _token_payload(first["token"])["fid"] != _token_payload(second["token"])["fid"]


def test_token_carries_no_plaintext_privacy_and_login_keeps_no_session(dev_login):
    openid = "openid-should-never-appear-in-the-token"
    body = _login(openid).json()

    token = body["token"]
    assert openid not in token
    payload = _token_payload(token)
    assert set(payload) == {"uid", "fid", "exp"}
    assert payload["uid"] == body["user_id"]
    assert TOKEN_TTL_SECONDS - 60 < payload["exp"] - int(time.time()) <= TOKEN_TTL_SECONDS

    # 服务端零存储：没有会话表 / Redis，登录只落一个家庭 + 一个用户
    tables = set(inspect(engine).get_table_names())
    assert not [table for table in tables if "session" in table or "token" in table]
    families, users = _stored_families_and_users()
    assert (len(families), len(users)) == (1, 1)


def test_missing_wechat_credentials_returns_generic_502(monkeypatch):
    monkeypatch.delenv("DEV_LOGIN", raising=False)

    response = _login("any-code")

    assert response.status_code == 502, response.text
    body = response.json()
    assert body["error"]["code"] == "wechat_login_failed"
    assert body["request_id"] == response.headers["X-Request-ID"]
    message = body["error"]["message"]
    assert message
    # 不吐内部配置名，也不带上游原始错误
    assert "APPID" not in message and "SECRET" not in message


def test_upstream_error_detail_never_reaches_the_client(monkeypatch, wechat_credentials):
    monkeypatch.delenv("DEV_LOGIN", raising=False)
    sentinel = "errmsg: invalid code, rid=UPSTREAM-SECRET-98765"
    monkeypatch.setattr(httpx, "AsyncClient", _fake_wechat({"errcode": 40029, "errmsg": sentinel}))

    response = _login("stale-code")

    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "wechat_login_failed"
    assert response.json()["request_id"]
    # 只看错误信封：request_id 是随机 UUID，拿整串 body 做子串判断会假阳性
    error = json.dumps(response.json()["error"], ensure_ascii=False)
    assert "UPSTREAM-SECRET-98765" not in error
    assert "40029" not in error


def test_wechat_unreachable_is_reported_as_wechat_login_failed(monkeypatch, wechat_credentials):
    monkeypatch.delenv("DEV_LOGIN", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _fake_wechat(error=httpx.ConnectError("connection refused")))

    response = _login("any-code")

    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "wechat_login_failed"
    assert "connection refused" not in response.text


def test_configured_credentials_still_use_jscode2session(monkeypatch, wechat_credentials):
    monkeypatch.delenv("DEV_LOGIN", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _fake_wechat({"openid": "real-openid", "session_key": "secret-session-key"}))

    response = _login("fresh-code")

    assert response.status_code == 200, response.text
    _, users = _stored_families_and_users()
    assert [user.openid for user in users] == ["real-openid"]


def test_dev_login_accepts_any_code_without_touching_wechat(monkeypatch, dev_login):
    def explode(*args, **kwargs):
        raise AssertionError("开发降级不得请求微信")

    monkeypatch.setattr(httpx, "AsyncClient", explode)

    for code in ("任意字符串", "code-with spaces", "a" * 64, "a" * 128):
        response = _login(code)
        assert response.status_code == 200, response.text
        assert response.json()["token"] and response.json()["user_id"]


def test_dev_login_still_works_when_the_code_is_longer_than_the_openid_column(dev_login):
    """users.openid 只有 64 字符，超长 code 也不能变成 500。"""
    long_code = "x" * 128

    first = _login(long_code)
    second = _login(long_code)

    assert first.status_code == 200, first.text
    assert first.json()["user_id"] == second.json()["user_id"]

    _, users = _stored_families_and_users()
    assert len(users) == 1


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "2", "1.0"])
def test_only_explicit_dev_login_one_enables_dev_mode(monkeypatch, value):
    monkeypatch.setenv("DEV_LOGIN", value)

    response = _login("any-code")

    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "wechat_login_failed"


@pytest.mark.parametrize(
    ("dev_login_value", "announced", "absent"),
    [("1", "开发降级", "真实微信"), ("", "真实微信", "开发降级")],
)
def test_startup_log_prints_the_mode_even_when_the_host_configures_its_own_loggers(dev_login_value, announced, absent):
    """uvicorn 只给自己的 logger 配 handler，root 停在 WARNING：启动日志必须照样打到 stderr。

    这一条在干净进程里跑：pytest 自己会往 root 挂 handler、把级别问题掩盖掉。
    """
    script = (
        "import logging\n"
        "logging.getLogger('uvicorn').addHandler(logging.StreamHandler())\n"  # 宿主只给自己的 logger 配 handler
        "from fastapi.testclient import TestClient\n"
        "import app.main\n"
        "with TestClient(app.main.app) as started:\n"
        "    assert started.get('/health').status_code == 200\n"
    )
    env = {**os.environ, "DEV_LOGIN": dev_login_value}

    result = subprocess.run([sys.executable, "-c", script], cwd=SERVER_DIR, capture_output=True, text=True, env=env)

    assert result.returncode == 0, result.stderr
    assert f"登录模式：{announced}" in result.stderr
    assert absent not in result.stderr
