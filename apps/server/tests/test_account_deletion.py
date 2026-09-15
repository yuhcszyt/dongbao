"""注销账号（`DELETE /me`）的外部可观察行为。

断言只落在 HTTP 状态 / 错误信封 / 数据库里的行 / 磁盘上的文件上，不碰被测模块的内部逻辑；
失败路径靠在模块边界上换掉实现来构造（`Session.commit` 抛错、清理时文件删不掉）。

覆盖：
- 带有效 token 注销 → 204，且该家庭在库里一行不剩（含软删记录与草稿确认后的关联行）
- 注销不越过家庭边界（另一个家庭原样保留）
- 旧 token 立刻作废，文案是「账号已注销」（ADR-0002 的吊销即查询副产品）
- 磁盘上的媒体文件被清掉；清不掉也不影响接口成功
- 同一 openid 重新登录 = 全新用户 + 全新家庭，看不到任何旧数据
- 中途失败不留删了一半的库
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import Family, User
from app.main import app
from app.record.database import SessionLocal
from app.record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia
from app.record.providers import ProviderUnavailable
from app.record.storage import media_path

client = TestClient(app)
# 事务中途失败时要把 500 当普通响应读，而不是让它从客户端抛出来
raw_client = TestClient(app, raise_server_exceptions=False)

# 与 conftest 默认 openid 同值（各测试文件都自带字面量，互不引用）
OPENID = "openid-of-parent-a"
OTHER_OPENID = "openid-of-parent-b"
PNG = b"\x89PNG\r\n\x1a\n" + b"stand-in-for-a-real-png"


@pytest.fixture(autouse=True)
def isolated_media_root(tmp_path, monkeypatch) -> Path:
    """把媒体落点指到临时目录：用例之间不互相看见文件，也不弄脏仓库里的 data/media。"""
    root = tmp_path / "media"
    monkeypatch.setenv("MEDIA_ROOT", str(root))
    return root


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _count(model, column, value) -> int:
    """按某一列数行；`value` 给一个列表就是「这批 id 还剩几行」。"""
    ids = value if isinstance(value, list) else [value]
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(column.in_(ids)))


def _ids(model, column, value) -> list:
    with SessionLocal() as db:
        return list(db.scalars(select(model.id).where(column == value)))


def _object_keys(family_id) -> list[str]:
    with SessionLocal() as db:
        return list(db.scalars(select(MediaAsset.object_key).where(MediaAsset.family_id == family_id)))


def _family_id_of(user_id) -> UUID:
    with SessionLocal() as db:
        return db.scalar(select(User.family_id).where(User.id == user_id))


@pytest.fixture
def family(login, monkeypatch) -> dict:
    """一个「什么都有」的家庭：宝宝、手动记录、已软删记录、照片草稿、确认后的记录 + 媒体关联。"""
    account = login(OPENID)
    headers = _headers(account["token"])

    baby = client.post("/api/v1/babies", json={"nickname": "安安", "birth_date": "2026-01-01", "gender": "female"}, headers=headers)
    assert baby.status_code == 201, baby.text
    baby_id = baby.json()["id"]

    def add_record(kind: str, payload: dict) -> str:
        response = client.post(
            f"/api/v1/babies/{baby_id}/records",
            json={"record_type": kind, "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": payload, "note": None},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    add_record("feeding", {"kind": "feeding", "feeding_type": "formula", "amount_ml": 180})
    # 软删的也要一起消失：注销不该把 deleted_at 的记录留在库里
    soft_deleted = add_record("diaper", {"kind": "diaper", "content": "更换尿布"})
    assert client.delete(f"/api/v1/babies/{baby_id}/records/{soft_deleted}", headers=headers).status_code == 204

    image = client.post("/api/v1/media", data={"baby_id": baby_id}, files={"file": ("photo.png", PNG, "image/png")}, headers=headers)
    assert image.status_code == 201, image.text
    media_id = image.json()["id"]

    async def recognizer_unavailable(**kwargs):
        raise ProviderUnavailable("识别未配置")

    monkeypatch.setattr("app.record.routes.extract_draft", recognizer_unavailable)
    draft = client.post("/api/v1/record-drafts/from-photo", json={"baby_id": baby_id, "media_id": media_id}, headers=headers)
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    confirmed = client.post(
        f"/api/v1/record-drafts/{draft_id}/confirm",
        json={"record_type": "custom", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": {"kind": "custom", "title": "手动补充"}, "note": None},
        headers=headers,
    )
    assert confirmed.status_code == 201, confirmed.text  # 产生一行 record_media 关联

    family_id = _family_id_of(account["user_id"])
    return {
        "headers": headers,
        "user_id": account["user_id"],
        "family_id": family_id,
        "baby_id": baby_id,
        "record_ids": _ids(BabyRecord, BabyRecord.family_id, family_id),
        "draft_ids": _ids(RecordDraft, RecordDraft.family_id, family_id),
        "media_ids": _ids(MediaAsset, MediaAsset.family_id, family_id),
    }


def test_deleting_the_account_erases_every_row_of_that_family_and_nothing_else(family, auth):
    other_headers = auth(OTHER_OPENID)
    other_baby = client.post("/api/v1/babies", json={"nickname": "乐乐", "birth_date": "2025-06-01", "gender": "male"}, headers=other_headers)
    assert other_baby.status_code == 201, other_baby.text
    with SessionLocal() as db:
        other_family_id = db.scalar(select(User.family_id).where(User.openid == OTHER_OPENID))

    response = client.delete("/api/v1/me", headers=family["headers"])

    assert response.status_code == 204, response.text
    assert response.content == b""
    family_id = family["family_id"]
    assert _count(Baby, Baby.family_id, family_id) == 0
    assert _count(BabyRecord, BabyRecord.id, family["record_ids"]) == 0
    assert _count(RecordDraft, RecordDraft.id, family["draft_ids"]) == 0
    assert _count(MediaAsset, MediaAsset.id, family["media_ids"]) == 0
    assert _count(RecordMedia, RecordMedia.record_id, family["record_ids"]) == 0
    assert _count(RecordMedia, RecordMedia.media_id, family["media_ids"]) == 0
    assert _count(User, User.family_id, family_id) == 0
    assert _count(Family, Family.id, family_id) == 0

    # 别家原样保留
    assert _count(Baby, Baby.family_id, other_family_id) == 1
    assert _count(User, User.family_id, other_family_id) == 1
    assert _count(Family, Family.id, other_family_id) == 1


def test_the_old_token_stops_working_with_an_account_deleted_message(family):
    baby_id = family["baby_id"]
    assert client.delete("/api/v1/me", headers=family["headers"]).status_code == 204

    calls = [
        ("get", "/api/v1/babies", None),
        ("get", f"/api/v1/babies/{baby_id}/records", None),
        ("post", "/api/v1/babies", {"nickname": "二胎", "birth_date": "2027-01-01", "gender": "male"}),
        ("delete", "/api/v1/me", None),
    ]
    for method, path, body in calls:
        response = client.request(method.upper(), path, json=body, headers=family["headers"])
        assert response.status_code == 401, f"{method} {path}: {response.text}"
        assert response.json()["error"] == {"code": "invalid_token", "message": "账号已注销"}


def test_media_files_are_removed_from_disk(family, isolated_media_root):
    stored = [media_path(key) for key in _object_keys(family["family_id"])]
    assert stored, "用例前提：这个家庭至少有一个媒体文件"
    assert all(isolated_media_root in path.parents for path in stored)
    assert all(path.is_file() for path in stored)

    assert client.delete("/api/v1/me", headers=family["headers"]).status_code == 204

    assert not any(path.exists() for path in stored)


def test_signing_in_again_with_the_same_openid_starts_a_blank_account(family, login):
    old_baby_id = family["baby_id"]
    assert client.delete("/api/v1/me", headers=family["headers"]).status_code == 204

    fresh = login(OPENID)
    fresh_headers = _headers(fresh["token"])

    assert fresh["user_id"] != family["user_id"]
    assert client.get("/api/v1/babies", headers=fresh_headers).json() == []
    stale = client.get(f"/api/v1/babies/{old_baby_id}", headers=fresh_headers)
    assert stale.status_code == 404
    assert stale.json()["error"]["code"] == "baby_not_found"

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.openid == OPENID)) == 1
        assert db.scalar(select(func.count()).select_from(Family)) == 1
        assert db.scalar(select(func.count()).select_from(Baby)) == 0


def test_a_failure_before_commit_does_not_leave_a_half_deleted_family(family, monkeypatch):
    """行删除必须是一个事务：中途炸掉就该整体回滚，而不是「用户没了、宝宝还在」。"""
    original_commit = Session.commit
    state = {"armed": True}

    def flaky_commit(self):
        if state["armed"]:
            state["armed"] = False
            raise RuntimeError("数据库连接断了")
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    response = raw_client.delete("/api/v1/me", headers=family["headers"])
    state["armed"] = False

    assert response.status_code == 500, response.text
    family_id = family["family_id"]
    assert _count(User, User.family_id, family_id) == 1
    assert _count(Family, Family.id, family_id) == 1
    assert _count(Baby, Baby.family_id, family_id) == 1
    assert _count(BabyRecord, BabyRecord.family_id, family_id) == len(family["record_ids"])
    # 账号没被删掉，旧 token 依然能用
    assert client.get("/api/v1/babies", headers=family["headers"]).status_code == 200


@pytest.mark.parametrize("failure", ["os_error", "unexpected"])
def test_a_media_file_that_cannot_be_cleaned_does_not_fail_the_request(family, monkeypatch, failure):
    """磁盘清理是尽力而为：删不掉只留垃圾，不该让注销接口报错（数据一致性优先）。

    两种删不掉：意料之中的 OSError（路径变成了目录），和意料之外的异常（清理实现自己炸了）。
    后者同样不能把已经生效的注销变成 500 —— 那就成了「数据删了、请求却报错」。
    """
    victim = media_path(_object_keys(family["family_id"])[0])
    if failure == "os_error":
        victim.unlink()
        victim.mkdir()
        (victim / "动不了").write_text("x", encoding="utf-8")  # 目录：unlink 抛 IsADirectoryError（OSError）
    else:

        def explode(key):
            raise RuntimeError("清理实现炸了")

        monkeypatch.setattr("app.record.storage.media_path", explode)

    response = client.delete("/api/v1/me", headers=family["headers"])

    assert response.status_code == 204, response.text
    assert _count(User, User.family_id, family["family_id"]) == 0
    assert victim.exists()  # 文件清理失败留下的垃圾，不影响接口成功
