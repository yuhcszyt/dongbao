from datetime import timedelta
from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.record.database import SessionLocal
from app.record.models import BabyRecord, now
from app.auth.models import User, Family
from app.family.models import FamilyInvite, FamilyMember

client = TestClient(app)


def info(headers):
    response = client.get('/api/v1/family', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def join(owner, member):
    response = client.post('/api/v1/family/invites', headers=owner)
    assert response.status_code == 201, response.text
    invite = response.json()
    response = client.post('/api/v1/family/invites/accept', headers=member, json={'token': invite['token']})
    assert response.status_code == 200, response.text
    return invite


def baby(headers):
    response = client.post('/api/v1/babies', headers=headers, json={'nickname': '豆豆', 'gender': 'unknown'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_invite_is_single_use_and_preserves_old_family(auth):
    owner, member, outsider = auth('owner'), auth('member'), auth('outsider')
    old = info(member)
    old_baby = baby(member)
    shared_baby = baby(owner)
    invite = join(owner, member)
    assert info(member)['role'] == 'member'
    assert len(info(member)['families']) == 2
    assert client.get('/api/v1/babies', headers=member).json()[0]['id'] == shared_baby
    assert client.post('/api/v1/family/invites/accept', headers=outsider, json={'token': invite['token']}).status_code == 410
    assert client.post('/api/v1/family/switch/' + old['id'], headers=member).status_code == 200
    assert client.get('/api/v1/babies', headers=member).json()[0]['id'] == old_baby
    assert client.get('/api/v1/babies/' + shared_baby, headers=member).status_code == 404
    assert client.post('/api/v1/family/switch/' + info(owner)['id'], headers=outsider).status_code == 403


def test_roles_enforced_server_side_and_removal_revokes_access(auth):
    owner, member = auth('owner'), auth('member')
    shared_baby = baby(owner)
    join(owner, member)
    member_id = info(member)['user_id']
    assert client.post('/api/v1/family/invites', headers=member).status_code == 403
    assert client.get('/api/v1/family/audit', headers=member).status_code == 403
    assert client.put('/api/v1/babies/' + shared_baby, headers=member, json={'nickname': '改名', 'gender': 'unknown'}).status_code == 403
    assert client.put('/api/v1/family/members/' + member_id + '/role', headers=member, json={'role': 'admin'}).status_code == 403
    assert client.put('/api/v1/family/members/' + member_id + '/role', headers=owner, json={'role': 'admin'}).status_code == 200
    invite = client.post('/api/v1/family/invites', headers=member).json()
    owner_id = info(owner)['user_id']
    assert client.delete('/api/v1/family/members/' + owner_id, headers=member).status_code == 409
    assert client.delete('/api/v1/family/members/' + member_id, headers=owner).status_code == 204
    assert client.get('/api/v1/babies/' + shared_baby, headers=member).status_code == 404
    assert client.post('/api/v1/family/invites/preview', headers=owner, json={'token': invite['token']}).status_code == 410


def test_revoke_expiry_preview_and_audit_do_not_expose_token(auth):
    owner, member = auth('owner'), auth('member')
    invite = client.post('/api/v1/family/invites', headers=owner).json()
    preview = client.post('/api/v1/family/invites/preview', headers=member, json={'token': invite['token']})
    assert preview.status_code == 200
    assert set(preview.json()) == {'family_name', 'role', 'expires_at'}
    assert client.delete('/api/v1/family/invites/' + invite['id'], headers=owner).status_code == 204
    assert client.post('/api/v1/family/invites/accept', headers=member, json={'token': invite['token']}).status_code == 410
    expired = client.post('/api/v1/family/invites', headers=owner).json()
    with SessionLocal() as db:
        db.get(FamilyInvite, UUID(expired['id'])).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.post('/api/v1/family/invites/accept', headers=member, json={'token': expired['token']}).status_code == 410
    audit = client.get('/api/v1/family/audit', headers=owner).text
    assert invite['token'] not in audit and expired['token'] not in audit


def test_shared_records_survive_owner_account_deletion(auth):
    owner, member = auth('owner'), auth('member')
    family_id = info(owner)['id']
    baby_id = baby(owner)
    join(owner, member)
    client.put('/api/v1/family/profile', headers=member, json={'name': '奶奶'})
    response = client.post(f'/api/v1/babies/{baby_id}/records', headers=member, json={'record_type': 'feeding', 'occurred_at': now().isoformat(), 'payload': {'kind': 'feeding', 'amount_ml': 120}})
    assert response.status_code == 201, response.text
    assert response.json()['created_by_name'] == '奶奶'
    assert client.delete('/api/v1/me', headers=owner).status_code == 204
    assert info(member)['role'] == 'owner'
    assert len(client.get(f'/api/v1/babies/{baby_id}/records', headers=member).json()) == 1
    assert client.get('/api/v1/family', headers=owner).status_code == 401
    assert client.delete('/api/v1/me', headers=member).status_code == 204
    with SessionLocal() as db:
        assert db.get(Family, UUID(family_id)) is None
        assert db.scalar(select(BabyRecord).where(BabyRecord.baby_id == UUID(baby_id))) is None


def test_owner_transfer_then_leave_preserves_family(auth):
    owner, member = auth('owner'), auth('member')
    join(owner, member)
    owner_id, member_id = info(owner)['user_id'], info(member)['user_id']
    assert client.delete('/api/v1/family/members/' + owner_id, headers=owner).status_code == 409
    assert client.post('/api/v1/family/owner/' + member_id, headers=owner).status_code == 200
    assert client.delete('/api/v1/family/members/' + owner_id, headers=owner).status_code == 204
    assert info(member)['role'] == 'owner'
    assert info(owner)['id'] != info(member)['id']
