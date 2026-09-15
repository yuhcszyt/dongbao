import pytest
from sqlalchemy import delete

from app.auth.models import Family, User
from app.record.database import SessionLocal
from app.record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia

@pytest.fixture(autouse=True)
def no_login_configuration(monkeypatch):
    """让「未配置微信凭证、未开开发降级」成为所有用例的前提，而不是环境巧合。

    凭证一旦存在，`code_to_openid` 会真的去请求微信接口（10s 超时）；`DEV_LOGIN` 残留则会让
    缺凭证的用例悄悄登录成功。
    """
    for name in ("WECHAT_APPID", "WECHAT_SECRET", "DEV_LOGIN"):
        monkeypatch.delenv(name, raising=False)

@pytest.fixture(autouse=True)
def clean_database():
    """清空记录侧与鉴权侧全部表，保证用例之间互不残留（否则第二个用例会撞 unique openid）。"""
    with SessionLocal() as db:
        for model in (RecordMedia, RecordDraft, BabyRecord, MediaAsset, Baby, User, Family):
            db.execute(delete(model))
        db.commit()
    yield
