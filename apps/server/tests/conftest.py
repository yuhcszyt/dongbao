import pytest
from sqlalchemy import delete

from app.auth.models import Family, User
from app.record.database import SessionLocal
from app.record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia

@pytest.fixture(autouse=True)
def clean_database():
    """清空记录侧与鉴权侧全部表，保证用例之间互不残留（否则第二个用例会撞 unique openid）。"""
    with SessionLocal() as db:
        for model in (RecordMedia, RecordDraft, BabyRecord, MediaAsset, Baby, User, Family):
            db.execute(delete(model))
        db.commit()
    yield
