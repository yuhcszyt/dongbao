"""注销账号背后的一次性擦除：把「一户家庭」的痕迹从库里抹掉，再清理磁盘文件。

放在顶层而不是 auth / record 任一模块里：它同时跨越两边（`users` / `families` 与
`babies` / `baby_records` / `record_drafts` / `media_assets` / `record_media`），
是唯一知道「一户家庭的数据都由谁持有」的地方。
"""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth.models import Family, User
from .record.models import Baby, BabyRecord, MediaAsset, RecordDraft, RecordMedia
from .ai.models import AiConversation, AiMessage
from .record.storage import remove_media_files


def erase_family(db: Session, family_id: UUID) -> None:
    """擦除一户家庭：成员用户、家庭行、宝宝 / 记录 / 草稿 / 媒体行，以及磁盘上的文件。

    「注销」在 MVP 里就等于擦掉整个家庭——当前一户一用户，两者等价。等 Phase 5 引入多家长，
    这里要改成「只删当前用户，家庭留到最后一个成员注销」，调用点也得变（CONTEXT.md 上线决策 7）。
    """
    object_keys = _purge_family_rows(db, family_id)
    db.commit()  # 行删除全在一个事务里：中途失败即整体回滚，不留「删了一半」的库
    remove_media_files(object_keys)  # 文件清理在提交之后：删不掉不回滚，也不让接口报错


def _purge_family_rows(db: Session, family_id: UUID) -> list[str]:
    """删除该家庭的全部行，返回需要在提交后清理的媒体文件 key。

    顺序被外键钉住：`record_drafts.media_id` 与 `record_media.media_id` 是 RESTRICT，
    必须先删引用方再删 `media_assets`；`users` 先于 `families`。
    文件 key 得在删行之前取——行没了就查不到了。
    """
    object_keys = list(db.scalars(select(MediaAsset.object_key).where(MediaAsset.family_id == family_id)))
    conversation_ids = select(AiConversation.id).where(AiConversation.family_id == family_id)
    db.execute(delete(AiMessage).where(AiMessage.conversation_id.in_(conversation_ids)))
    db.execute(delete(AiConversation).where(AiConversation.family_id == family_id))
    record_ids = select(BabyRecord.id).where(BabyRecord.family_id == family_id)
    db.execute(delete(RecordMedia).where(RecordMedia.record_id.in_(record_ids)))
    db.execute(delete(BabyRecord).where(BabyRecord.family_id == family_id))
    db.execute(delete(RecordDraft).where(RecordDraft.family_id == family_id))
    db.execute(delete(MediaAsset).where(MediaAsset.family_id == family_id))
    db.execute(delete(Baby).where(Baby.family_id == family_id))
    db.execute(delete(User).where(User.family_id == family_id))
    db.execute(delete(Family).where(Family.id == family_id))
    return object_keys
