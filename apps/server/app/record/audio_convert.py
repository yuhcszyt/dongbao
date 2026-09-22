"""ASR 前把浏览器常见容器转成腾讯能认的 wav。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .providers import ProviderUnavailable

# 浏览器 MediaRecorder 常落 webm；腾讯一句话识别 VoiceFormat 没有 webm。
NEEDS_WAV_CONVERT = frozenset({"audio/webm", "audio/ogg", "application/ogg"})


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_to_asr_wav(src: Path) -> Path:
    """转成 16kHz 单声道 PCM wav，写到临时文件；调用方负责删除。"""
    if not ffmpeg_available():
        raise ProviderUnavailable("当前录音格式暂不支持识别，已保留录音并转为手动填写")
    out = Path(tempfile.mkstemp(prefix="dongbao-asr-", suffix=".wav")[1])
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(out),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        out.unlink(missing_ok=True)
        raise ProviderUnavailable("录音转码失败，已保留录音并转为手动填写") from exc
    if not out.is_file() or out.stat().st_size < 44:
        out.unlink(missing_ok=True)
        raise ProviderUnavailable("录音转码失败，已保留录音并转为手动填写")
    return out
