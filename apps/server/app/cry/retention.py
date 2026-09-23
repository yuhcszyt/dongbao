import logging

from sqlalchemy import select

from ..record.database import SessionLocal
from ..record.models import MediaAsset, now
from ..record.storage import remove_media_files

logger = logging.getLogger(__name__)


def purge_expired_cry_audio() -> int:
    """删除超过七天的私有哭声音频；数据库先提交，磁盘清理按已有容错策略执行。"""
    with SessionLocal() as db:
        expired = list(db.scalars(select(MediaAsset).where(
            MediaAsset.is_private.is_(True),
            MediaAsset.expires_at.is_not(None),
            MediaAsset.expires_at <= now(),
        )))
        keys = [item.object_key for item in expired]
        for item in expired:
            db.delete(item)
        db.commit()
    remove_media_files(keys)
    if keys:
        logger.info("已清理 %d 条过期哭声音频", len(keys))
    return len(keys)
