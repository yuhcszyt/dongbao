from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..auth.models import Family, User
from ..auth.dependencies import api_error
from ..record.models import BabyRecord
from .models import FamilyMember, FamilyInvite, FamilyAudit


def member_for(db: Session, user: User, family_id: UUID | None = None) -> FamilyMember:
    member = db.get(FamilyMember, (family_id or user.family_id, user.id), populate_existing=True)
    if not member:
        raise api_error(403, "family_access_denied", "你已不在这个家庭，请刷新后重试")
    return member


def require_manager(db: Session, user: User) -> FamilyMember:
    member = member_for(db, user)
    if member.role not in ("owner", "admin"):
        raise api_error(403, "permission_denied", "请让家庭管理员进行这项操作")
    return member


def lock_family(db: Session, family_id: UUID) -> Family:
    family = db.scalar(select(Family).where(Family.id == family_id).with_for_update())
    if not family:
        raise api_error(404, "not_found", "没有找到这个家庭")
    return family


def audit(db: Session, user: User, action: str, target_id: UUID | None = None, **details):
    db.add(FamilyAudit(family_id=user.family_id, actor_id=user.id, target_id=target_id, action=action, details=details))


def activate_other_family(db: Session, user: User, removed_family_id: UUID):
    remaining = db.scalar(select(FamilyMember).where(FamilyMember.user_id == user.id, FamilyMember.family_id != removed_family_id).order_by(FamilyMember.joined_at))
    if remaining:
        user.family_id = remaining.family_id
    else:
        family = Family()
        db.add(family)
        db.flush()
        user.family_id = family.id
        db.add(FamilyMember(family_id=family.id, user_id=user.id, role="owner"))


def erase_user(db: Session, user: User):
    from ..erasure import _purge_family_rows
    from ..record.storage import remove_media_files
    memberships = list(db.scalars(select(FamilyMember).where(FamilyMember.user_id == user.id).order_by(FamilyMember.family_id)))
    object_keys = []
    for membership in memberships:
        lock_family(db, membership.family_id)
        others = list(db.scalars(select(FamilyMember).where(FamilyMember.family_id == membership.family_id, FamilyMember.user_id != user.id).order_by(FamilyMember.joined_at, FamilyMember.user_id)))
        if others and membership.role == "owner":
            successor = next((item for item in others if item.role == "admin"), others[0])
            successor.role = "owner"
        if others:
            db.add(FamilyAudit(family_id=membership.family_id, actor_id=None, action="account_deleted", details={}))
    db.execute(update(BabyRecord).where(BabyRecord.created_by == user.id).values(created_by=None))
    db.execute(update(FamilyAudit).where(FamilyAudit.actor_id == user.id).values(actor_id=None))
    db.execute(update(FamilyAudit).where(FamilyAudit.target_id == user.id).values(target_id=None))
    family_ids = [item.family_id for item in memberships]
    db.delete(user)
    db.flush()
    for family_id in family_ids:
        remaining = db.scalar(select(FamilyMember).where(FamilyMember.family_id == family_id))
        if not remaining:
            object_keys.extend(_purge_family_rows(db, family_id))
    db.commit()
    remove_media_files(object_keys)
