"""记录侧的鉴权与家庭隔离：401 语义、跨家庭 404、媒体能力凭证、created_by 归属。

断言只落在外部可观察行为上：HTTP 状态、错误信封里的 code 与文案、数据库里的归属字段。
数据隔离的验收语言是「两个家庭互相看不见」，这是产品承诺，不是实现细节。
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.models import User
from app.main import app
from app.record.database import SessionLocal
from app.record.models import BabyRecord

client = TestClient(app)

BABY = {"nickname": "安安", "birth_date": "2026-01-01", "gender": "female"}
FEEDING = {"kind": "feeding", "feeding_type": "formula", "amount_ml": 180}
IMAGE = b"\x89PNG\r\n\x1a\n" + b"placeholder"
MEDIA_PATH = "/api/v1/media"


def _create_baby(headers: dict) -> str:
    response = client.post("/api/v1/babies", json=BABY, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_record(baby_id: str, headers: dict) -> str:
    response = client.post(
        f"/api/v1/babies/{baby_id}/records",
        json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": FEEDING, "note": None},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_image(baby_id: str, headers: dict):
    return client.post(MEDIA_PATH, data={"baby_id": baby_id}, files={"file": ("photo.png", IMAGE, "image/png")}, headers=headers)


def _draft_from_photo(baby_id: str, media_id: str, headers: dict, monkeypatch) -> str:
    async def fake_extract(**kwargs):
        return {"record_type": "custom", "payload": {"kind": "custom", "title": "待确认"}, "missing_fields": [], "recognition_warnings": []}

    monkeypatch.setattr("app.record.routes.extract_draft", fake_extract)
    response = client.post("/api/v1/record-drafts/from-photo", json={"baby_id": baby_id, "media_id": media_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assert_401(response, code: str, message: str) -> None:
    assert response.status_code == 401, response.text
    assert response.json()["error"] == {"code": code, "message": message}
    assert response.json()["request_id"]


def _assert_not_found(response, code: str) -> None:
    """跨家庭访问一律 404 + not_found 系列：不引入 403，不泄露别人数据的存在性。"""
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == code


def test_every_record_side_endpoint_rejects_a_missing_token(auth):
    headers = auth()
    baby_id = _create_baby(headers)
    record_id = _create_record(baby_id, headers)
    media_id = _upload_image(baby_id, headers).json()["id"]
    draft_id = str(uuid4())
    record_body = {"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": FEEDING, "note": None}
    update_body = {"occurred_at": datetime.now(timezone.utc).isoformat(), "payload": FEEDING, "note": None}
    draft_body = {"baby_id": baby_id, "media_id": media_id}
    confirm_body = {"record_type": "custom", "payload": {"kind": "custom", "title": "手动补充"}, "note": None}

    calls = [
        ("post", "/api/v1/babies", {"json": BABY}),
        ("get", "/api/v1/babies", {}),
        ("get", f"/api/v1/babies/{baby_id}", {}),
        ("patch", f"/api/v1/babies/{baby_id}", {"json": BABY}),
        ("put", f"/api/v1/babies/{baby_id}", {"json": BABY}),
        ("post", MEDIA_PATH, {}),  # 上传（uni.uploadFile 可带 header，所以必须鉴权）
        ("post", "/api/v1/record-drafts/from-voice", {"json": draft_body}),
        ("post", "/api/v1/record-drafts/from-photo", {"json": draft_body}),
        ("post", f"/api/v1/record-drafts/{draft_id}/confirm", {"json": confirm_body}),
        ("post", f"/api/v1/babies/{baby_id}/records", {"json": record_body}),
        ("get", f"/api/v1/babies/{baby_id}/records", {}),
        ("get", f"/api/v1/babies/{baby_id}/records/{record_id}", {}),
        ("patch", f"/api/v1/babies/{baby_id}/records/{record_id}", {"json": update_body}),
        ("put", f"/api/v1/babies/{baby_id}/records/{record_id}", {"json": update_body}),
        ("delete", f"/api/v1/babies/{baby_id}/records/{record_id}", {}),
        ("post", f"/api/v1/babies/{baby_id}/records/{record_id}/restore", {}),
        ("get", f"/api/v1/babies/{baby_id}/daily-summary", {}),
    ]

    for method, url, kwargs in calls:
        response = getattr(client, method)(url, **kwargs)
        _assert_401(response, "missing_token", "请先登录")

    # 这些接口在没有 token 时都没被执行：数据一行未动
    assert client.get(f"/api/v1/babies/{baby_id}/records", headers=headers).json()[0]["id"] == record_id


def test_tampered_and_expired_tokens_are_rejected(auth, login, monkeypatch):
    header, payload, signature = auth()["Authorization"].split()[1].split(".")
    tampered = f"{header}.{payload}.{'x' * len(signature)}"
    _assert_401(
        client.get("/api/v1/babies", headers={"Authorization": f"Bearer {tampered}"}),
        "invalid_token",
        "登录已过期，请重新进入",
    )

    monkeypatch.setattr("app.auth.security.TOKEN_TTL_SECONDS", -60)  # 走真实登录接口签发一张已过期的凭证
    expired = login()["token"]
    _assert_401(
        client.get("/api/v1/babies", headers={"Authorization": f"Bearer {expired}"}),
        "invalid_token",
        "登录已过期，请重新进入",
    )


def test_token_of_a_deleted_user_is_rejected(login):
    body = login()
    with SessionLocal() as db:
        db.delete(db.scalar(select(User).where(User.id == UUID(body["user_id"]))))
        db.commit()

    _assert_401(
        client.get("/api/v1/babies", headers={"Authorization": f"Bearer {body['token']}"}),
        "invalid_token",
        "账号已注销",
    )


def test_a_second_family_cannot_reach_the_first_family_data(auth, monkeypatch):
    first = auth("openid-of-parent-a")
    second = auth("openid-of-parent-b")

    first_baby = _create_baby(first)
    first_record = _create_record(first_baby, first)
    first_media = _upload_image(first_baby, first).json()
    first_draft = _draft_from_photo(first_baby, first_media["id"], first, monkeypatch)

    second_baby = _create_baby(second)

    # 列表层：别人的宝宝不出现
    assert [baby["id"] for baby in client.get("/api/v1/babies", headers=second).json()] == [second_baby]
    assert client.get(f"/api/v1/babies/{second_baby}/records", headers=second).json() == []

    # 直接请求别人的宝宝：baby_not_found（不是 403）
    _assert_not_found(client.get(f"/api/v1/babies/{first_baby}", headers=second), "baby_not_found")
    _assert_not_found(client.patch(f"/api/v1/babies/{first_baby}", json=BABY, headers=second), "baby_not_found")
    _assert_not_found(client.put(f"/api/v1/babies/{first_baby}", json=BABY, headers=second), "baby_not_found")
    _assert_not_found(client.get(f"/api/v1/babies/{first_baby}/records", headers=second), "baby_not_found")
    _assert_not_found(
        client.post(
            f"/api/v1/babies/{first_baby}/records",
            json={"record_type": "feeding", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": FEEDING, "note": None},
            headers=second,
        ),
        "baby_not_found",
    )
    _assert_not_found(client.get(f"/api/v1/babies/{first_baby}/daily-summary", headers=second), "baby_not_found")
    _assert_not_found(_upload_image(first_baby, second), "baby_not_found")
    _assert_not_found(
        client.post("/api/v1/record-drafts/from-photo", json={"baby_id": first_baby, "media_id": first_media["id"]}, headers=second),
        "baby_not_found",
    )

    # 借自己的宝宝去摸别人的记录 / 草稿：record_not_found / draft_not_found
    _assert_not_found(client.get(f"/api/v1/babies/{second_baby}/records/{first_record}", headers=second), "record_not_found")
    _assert_not_found(
        client.patch(
            f"/api/v1/babies/{second_baby}/records/{first_record}",
            json={"occurred_at": datetime.now(timezone.utc).isoformat(), "payload": FEEDING, "note": None},
            headers=second,
        ),
        "record_not_found",
    )
    _assert_not_found(client.delete(f"/api/v1/babies/{second_baby}/records/{first_record}", headers=second), "record_not_found")
    _assert_not_found(client.post(f"/api/v1/babies/{second_baby}/records/{first_record}/restore", headers=second), "record_not_found")
    _assert_not_found(
        client.post(
            f"/api/v1/record-drafts/{first_draft}/confirm",
            json={"record_type": "custom", "payload": {"kind": "custom", "title": "偷来的草稿"}, "note": None},
            headers=second,
        ),
        "draft_not_found",
    )

    # 用别人的媒体 id 建草稿：media_not_found
    _assert_not_found(
        client.post("/api/v1/record-drafts/from-photo", json={"baby_id": second_baby, "media_id": first_media["id"]}, headers=second),
        "media_not_found",
    )

    # 媒体 URL 只在带 token 的列表 / 详情响应里下发，所以第二个家庭拿不到第一个家庭的 URL
    first_url = f"{MEDIA_PATH}/{first_media['id']}"
    assert first_url not in client.get(f"/api/v1/babies/{second_baby}/records", headers=second).text
    assert first_url not in client.get("/api/v1/babies", headers=second).text

    # 而文件本身（`{MEDIA_PATH}/{uuid}`）刻意不做家庭校验：previewImage / createInnerAudioContext
    # 无法带请求头，UUID 就是能力凭证（spec《媒体文件的取用方式》：URL 泄露即文件泄露，MVP 接受）。
    # 拿不到 id 就无从访问——不存在「猜一个 id 就摸到别人文件」的路径。
    assert client.get(f"{MEDIA_PATH}/{uuid4()}").status_code == 404

    # 今日汇总不串家庭：第一个家庭那条 180ml 不出现在第二个家庭
    local_date = datetime.now(timezone.utc).astimezone().date().isoformat()
    summary = client.get(
        f"/api/v1/babies/{second_baby}/daily-summary",
        params={"date": local_date, "timezone": "Asia/Shanghai"},
        headers=second,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["feeding_ml"] == 0


def test_media_get_is_a_capability_url_while_upload_needs_a_token(auth):
    headers = auth()
    baby_id = _create_baby(headers)

    _assert_401(client.post(MEDIA_PATH, data={"baby_id": baby_id}), "missing_token", "请先登录")

    media = _upload_image(baby_id, headers).json()
    assert media["url"] == f"{MEDIA_PATH}/{media['id']}"  # UUID 即能力凭证，只在带 token 的响应体里下发

    # uni.previewImage / uni.createInnerAudioContext 无法带请求头，所以取文件本身免 token
    fetched = client.get(media["url"])
    assert fetched.status_code == 200, fetched.text
    assert fetched.content == IMAGE
    assert fetched.headers["content-type"] == "image/png"

    # 但媒体列表 / 详情只能靠已鉴权的记录接口拿到 → 没有 token 就无从得知 URL
    assert client.get(f"/api/v1/babies/{baby_id}/records").status_code == 401
    # 不可猜：随便一个 UUID 取不到别人（或自己）没下发的文件
    _assert_not_found(client.get(f"{MEDIA_PATH}/{uuid4()}"), "media_not_found")


def test_created_by_records_the_real_user_for_manual_and_confirmed_records(login, monkeypatch):
    body = login()
    headers = {"Authorization": f"Bearer {body['token']}"}
    baby_id = _create_baby(headers)

    manual_id = _create_record(baby_id, headers)
    media = _upload_image(baby_id, headers).json()
    draft_id = _draft_from_photo(baby_id, media["id"], headers, monkeypatch)
    confirmed = client.post(
        f"/api/v1/record-drafts/{draft_id}/confirm",
        json={"record_type": "custom", "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": {"kind": "custom", "title": "手动补充"}, "note": None},
        headers=headers,
    )
    assert confirmed.status_code == 201, confirmed.text

    with SessionLocal() as db:
        created_by = {str(record.id): str(record.created_by) for record in db.scalars(select(BabyRecord)).all()}
        assert created_by[manual_id] == body["user_id"]
        assert created_by[confirmed.json()["id"]] == body["user_id"]
