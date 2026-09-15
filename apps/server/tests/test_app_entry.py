from fastapi.testclient import TestClient

from app.auth.models import Family, User
from app.main import app
from app.record.database import SessionLocal

client = TestClient(app)

def test_single_app_serves_health_record_and_auth_routes():
    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json() == {"status": "ok"}
    assert health.headers["X-Request-ID"]

    # 记录路由已挂载（未带 token 也仍按记录侧现状工作，硬编码家庭下没有宝宝）
    assert client.get("/api/v1/babies").status_code == 200

    # 鉴权路由被真正挂载：未配置微信凭证时是 502，而不是 404
    login = client.post("/api/v1/auth/wechat", json={"code": "any-code"})
    assert login.status_code == 502, login.text
    assert login.json()["error"]["code"] == "wechat_login_failed"

def test_auth_dependency_is_reachable_through_the_app():
    missing = client.delete("/api/v1/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "missing_token"

    tampered = client.delete("/api/v1/me", headers={"Authorization": "Bearer not-a-token"})
    assert tampered.status_code == 401
    assert tampered.json()["error"]["code"] == "invalid_token"

def _seed_user(openid: str = "openid-from-ticket-01") -> None:
    with SessionLocal() as db:
        family = Family()
        db.add(family)
        db.flush()
        db.add(User(openid=openid, family_id=family.id))
        db.commit()

def test_first_case_can_seed_a_user():
    _seed_user()

def test_second_case_can_seed_the_same_openid():
    """清理 fixture 覆盖 users/families：连续两个用例不撞 unique openid。"""
    _seed_user()
