import hashlib
import secrets
from datetime import timedelta
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth.dependencies import current_user, api_error
from ..auth.models import Family, User
from ..record.database import get_db
from ..record.models import now
from .models import FamilyMember, FamilyInvite, FamilyAudit
from .service import member_for, require_manager, lock_family, audit, activate_other_family

router = APIRouter(prefix="/api/v1/family", tags=["family"])


class NameInput(BaseModel):
    name: str = Field(min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("请填写名称")
        return value.strip()


class TokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class RoleInput(BaseModel):
    role: Literal["admin", "member"]


def invite_for(db: Session, token: str, lock=False):
    stmt = select(FamilyInvite).where(FamilyInvite.token_hash == hashlib.sha256(token.encode()).hexdigest())
    invite = db.scalar(stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt)
    if not invite or invite.revoked_at or invite.used_at or invite.expires_at <= now():
        raise api_error(410, "invite_unavailable", "邀请已失效，请向家人索取新的邀请码")
    creator = db.get(FamilyMember, (invite.family_id, invite.created_by)) if invite.created_by else None
    if not creator or creator.role not in ("owner", "admin"):
        raise api_error(410, "invite_unavailable", "邀请已失效，请向家人索取新的邀请码")
    return invite


@router.get("")
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership = member_for(db, user)
    family = db.get(Family, user.family_id)
    members = db.execute(select(FamilyMember, User).join(User, User.id == FamilyMember.user_id).where(FamilyMember.family_id == family.id).order_by(FamilyMember.joined_at)).all()
    families = db.execute(select(Family, FamilyMember).join(FamilyMember, FamilyMember.family_id == Family.id).where(FamilyMember.user_id == user.id)).all()
    invites = db.scalars(select(FamilyInvite).where(FamilyInvite.family_id == family.id, FamilyInvite.used_at.is_(None), FamilyInvite.revoked_at.is_(None), FamilyInvite.expires_at > now())).all() if membership.role in ("owner", "admin") else []
    return {"id": family.id, "name": family.name, "role": membership.role, "user_id": user.id, "display_name": user.display_name,
            "members": [{"user_id": m.user_id, "name": u.display_name, "role": m.role} for m, u in members],
            "families": [{"id": f.id, "name": f.name, "role": m.role} for f, m in families],
            "invites": [{"id": i.id, "expires_at": i.expires_at} for i in invites]}


@router.put("/name")
def rename(body: NameInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    family = lock_family(db, user.family_id)
    require_manager(db, user)
    family.name = body.name
    audit(db, user, "rename")
    db.commit()
    return {"name": family.name}


@router.put("/profile")
def profile(body: NameInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.display_name = body.name
    db.commit()
    return {"name": user.display_name}


@router.post("/invites", status_code=201)
def invite(user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_family(db, user.family_id)
    require_manager(db, user)
    active = list(db.scalars(select(FamilyInvite).where(FamilyInvite.family_id == user.family_id, FamilyInvite.used_at.is_(None), FamilyInvite.revoked_at.is_(None), FamilyInvite.expires_at > now())))
    if len(active) >= 10:
        raise api_error(409, "too_many_invites", "未使用的邀请较多，请先撤销旧邀请")
    token = secrets.token_urlsafe(32)
    row = FamilyInvite(family_id=user.family_id, token_hash=hashlib.sha256(token.encode()).hexdigest(), created_by=user.id, expires_at=now() + timedelta(hours=48))
    db.add(row)
    audit(db, user, "invite_created")
    db.commit()
    return {"id": row.id, "token": token, "expires_at": row.expires_at}


@router.delete("/invites/{invite_id}", status_code=204)
def revoke(invite_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_family(db, user.family_id)
    require_manager(db, user)
    row = db.scalar(select(FamilyInvite).where(FamilyInvite.id == invite_id, FamilyInvite.family_id == user.family_id))
    if not row:
        raise api_error(404, "not_found", "没有找到邀请")
    row.revoked_at = now()
    audit(db, user, "invite_revoked", invite_id)
    db.commit()


@router.post("/invites/preview")
def preview(body: TokenInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = invite_for(db, body.token)
    return {"family_name": db.get(Family, row.family_id).name, "role": "member", "expires_at": row.expires_at}


@router.post("/invites/accept")
def accept(body: TokenInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # 统一锁顺序：家庭 -> 邀请 -> 用户，串行化接受和撤销。
    row = invite_for(db, body.token)
    lock_family(db, row.family_id)
    row = invite_for(db, body.token, lock=True)
    db.refresh(user, with_for_update=True)
    if db.get(FamilyMember, (row.family_id, user.id)):
        raise api_error(409, "already_member", "你已经是这个家庭的成员")
    db.add(FamilyMember(family_id=row.family_id, user_id=user.id, role="member"))
    user.family_id = row.family_id
    row.used_at = now()
    audit(db, user, "member_joined", user.id)
    db.commit()
    return {"family_id": user.family_id}


@router.post("/switch/{family_id}")
def switch(family_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_family(db, family_id)
    member_for(db, user, family_id)
    user.family_id = family_id
    db.commit()
    return {"family_id": family_id}


@router.put("/members/{user_id}/role")
def change_role(user_id: UUID, body: RoleInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_family(db, user.family_id)
    if member_for(db, user).role != "owner":
        raise api_error(403, "permission_denied", "只有家庭创建者可以修改角色")
    target = db.get(FamilyMember, (user.family_id, user_id))
    if not target or target.role == "owner":
        raise api_error(409, "invalid_member", "请选择其他家庭成员")
    target.role = body.role
    audit(db, user, "role_changed", user_id, role=body.role)
    db.commit()
    return {"role": target.role}


@router.post("/owner/{user_id}")
def transfer(user_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_family(db, user.family_id)
    current = member_for(db, user)
    target = db.get(FamilyMember, (user.family_id, user_id))
    if current.role != "owner":
        raise api_error(403, "permission_denied", "只有家庭创建者可以转交管理")
    if not target or user_id == user.id:
        raise api_error(409, "invalid_member", "请选择其他家庭成员")
    current.role, target.role = "admin", "owner"
    audit(db, user, "owner_transferred", user_id)
    db.commit()
    return {"ok": True}


@router.delete("/members/{user_id}", status_code=204)
def remove(user_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    family_id = user.family_id
    lock_family(db, family_id)
    current = member_for(db, user)
    target = db.get(FamilyMember, (family_id, user_id))
    if not target:
        raise api_error(404, "not_found", "没有找到成员")
    if target.role == "owner":
        raise api_error(409, "owner_required", "请先将家庭管理转交给另一位成员")
    if user_id != user.id and (current.role == "member" or (current.role == "admin" and target.role != "member")):
        raise api_error(403, "permission_denied", "你没有权限移除这位成员")
    audit(db, user, "member_left" if user_id == user.id else "member_removed", user_id)
    target_user = db.get(User, user_id)
    if target_user.family_id == family_id:
        activate_other_family(db, target_user, family_id)
    db.delete(target)
    db.commit()


@router.get("/audit")
def audit_history(offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_manager(db, user)
    rows = db.scalars(select(FamilyAudit).where(FamilyAudit.family_id == user.family_id).order_by(FamilyAudit.created_at.desc(), FamilyAudit.id.desc()).offset(offset).limit(50))
    return [{"id": r.id, "action": r.action, "actor_id": r.actor_id, "target_id": r.target_id, "details": r.details, "created_at": r.created_at} for r in rows]
