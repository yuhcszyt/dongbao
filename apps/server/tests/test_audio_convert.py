"""H5 MediaRecorder 常见 webm → 腾讯 ASR 可认的 wav。"""
from pathlib import Path

import pytest

from app.record.audio_convert import NEEDS_WAV_CONVERT, convert_to_asr_wav, ffmpeg_available

FIXTURE = Path(__file__).resolve().parents[3] / "data" / "media" / "5c" / "5cf3901c80a44dd8a077d7ae7801f521.webm"


@pytest.mark.skipif(not FIXTURE.is_file(), reason="缺少本地 webm 样例")
@pytest.mark.skipif(not ffmpeg_available(), reason="本机未装 ffmpeg")
def test_webm_converts_to_pcm_wav():
    assert "audio/webm" in NEEDS_WAV_CONVERT
    out = convert_to_asr_wav(FIXTURE)
    try:
        assert out.suffix == ".wav"
        assert out.stat().st_size > 44
        assert out.read_bytes()[:4] == b"RIFF"
    finally:
        out.unlink(missing_ok=True)
