"""媒体文件在本地磁盘上的唯一落点：写入、读取、清理都从这里取根目录与路径。

根目录按需读 `MEDIA_ROOT`（而不是 import 时定死），调用点与测试都能把它指向别处。
"""
import logging
import os
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


def media_root() -> Path:
    return Path(os.environ.get("MEDIA_ROOT", "/app/data/media"))


def media_path(object_key: str) -> Path:
    return media_root() / object_key


def remove_media_files(object_keys: Iterable[str]) -> None:
    """尽力删除磁盘文件：数据一致性优先于文件清理，删不掉只记日志、不打断调用方。

    调用方在事务提交之后才会走到这里——此时注销已经生效，任何异常都不该让接口变成 500
    （那就成了「数据删了、请求却报错」）。所以这里连意料之外的异常也一并吃掉，逐个 key 兜住，
    坏掉一个不影响其余的清理。
    """
    for key in object_keys:
        try:
            media_path(key).unlink(missing_ok=True)
        except Exception:
            logger.warning("媒体文件清理失败，已跳过 %s", key, exc_info=True)
