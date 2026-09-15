import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth.models import Family, User
from app.main import app
from app.record.database import SessionLocal
from app.record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia

DEFAULT_OPENID = "openid-of-parent-a"

@pytest.fixture(autouse=True)
def no_login_configuration(monkeypatch):
    """让「未配置微信凭证、未开开发降级」成为所有用例的前提，而不是环境巧合。

    凭证一旦存在，`code_to_openid` 会真的去请求微信接口（10s 超时）；`DEV_LOGIN` 残留则会让
    缺凭证的用例悄悄登录成功。
    """
    for name in ("WECHAT_APPID", "WECHAT_SECRET", "DEV_LOGIN"):
        monkeypatch.delenv(name, raising=False)

@pytest.fixture(autouse=True)
def media_root_in_tmp(monkeypatch, tmp_path):
    """媒体根目录固定到本次用例的临时目录。

    `storage.media_root()` 的默认值 `/app/data/media` 只在容器里存在；这么钉住，用例不必依赖
    Makefile 传的 `MEDIA_ROOT`，裸跑 `pytest tests/xxx.py` 也能过。
    """
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))


@pytest.fixture(autouse=True)
def clean_database():
    """清空记录侧与鉴权侧全部表，保证用例之间互不残留（否则第二个用例会撞 unique openid）。"""
    with SessionLocal() as db:
        for model in (RecordMedia, RecordDraft, BabyRecord, MediaAsset, Baby, User, Family):
            db.execute(delete(model))
        db.commit()
    yield


@pytest.fixture
def login(monkeypatch):
    """走真实登录接口拿凭证（开发降级）：回归网跑的是带 token 的全链路，不是测试期身份。"""
    monkeypatch.setenv("DEV_LOGIN", "1")

    def _login(code: str = DEFAULT_OPENID) -> dict:
        response = TestClient(app).post("/api/v1/auth/wechat", json={"code": code})
        assert response.status_code == 200, response.text
        return response.json()

    return _login


@pytest.fixture
def auth(login):
    """返回 Authorization 头工厂；不同 openid 即不同家庭。"""

    def _headers(code: str = DEFAULT_OPENID) -> dict:
        return {"Authorization": f"Bearer {login(code)['token']}"}

    return _headers
