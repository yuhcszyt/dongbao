"""腾讯一句话识别 Response 到转写文本：空结果是没听清，不是配置故障。"""
import pytest

from app.record.providers import ProviderUnavailable, transcript_from_tencent_response


def test_asr_text_is_stripped():
    assert transcript_from_tencent_response({"Result": "  喝了奶  "}) == "喝了奶"


def test_empty_asr_result_asks_to_speak_again():
    with pytest.raises(ProviderUnavailable, match="没有听清说话"):
        transcript_from_tencent_response({"Result": "", "AudioDuration": 2183, "WordSize": 0})


def test_asr_error_stays_generic():
    with pytest.raises(ProviderUnavailable, match="语音识别暂时失败"):
        transcript_from_tencent_response({"Error": {"Code": "FailedOperation.ErrorRecognize", "Message": "secret"}})
