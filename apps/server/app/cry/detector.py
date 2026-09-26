"""AudioSet 声音事件门槛。阈值是保守产品规则，未经真实场景校准。"""
from functools import lru_cache
import os
from pathlib import Path

import numpy as np

MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"
MODEL_REVISION = "f826b80d28226b62986cc218e5cec390b1096902"
CRY_LABEL = "Baby cry, infant cry"


@lru_cache(maxsize=1)
def detector_pipeline():
    from .classifier import CryModelUnavailable
    path = Path(os.environ.get("CRY_DETECTOR_PATH", "/app/data/models/cry-detector"))
    if not (path / "model.safetensors").is_file():
        raise CryModelUnavailable("哭声检测模型尚未就绪，请稍后再试")
    try:
        from transformers import pipeline
        return pipeline("audio-classification", model=str(path), device=-1)
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        raise CryModelUnavailable("哭声检测模型暂时无法加载") from exc


def has_cry(predictions: list[dict]) -> bool:
    # AudioSet 为多标签；使用 sigmoid 分数，不把它呈现为原因概率。
    score = next((float(item["score"]) for item in predictions if item["label"] == CRY_LABEL), 0.0)
    ordered = sorted(predictions, key=lambda item: float(item["score"]), reverse=True)
    return score >= 0.2 and any(item["label"] == CRY_LABEL for item in ordered[:3])


def ensure_cry(samples: np.ndarray) -> None:
    from .classifier import CryModelUnavailable, InvalidCryAudio
    # 检查全部录音；模型每次处理最多 10 秒，避免只看开头。
    detector = detector_pipeline()
    try:
        for offset in range(0, len(samples), 160_000):
            chunk = samples[offset:offset + 160_000]
            if len(chunk) < 16_000:
                continue
            predictions = detector({"raw": chunk, "sampling_rate": 16_000}, top_k=None, function_to_apply="sigmoid")
            if has_cry(predictions):
                return
    except (OSError, RuntimeError, ValueError) as exc:
        raise CryModelUnavailable("哭声检测暂时失败，请稍后重试") from exc
    raise InvalidCryAudio("没有识别到足够清晰的婴儿哭声，请重新录制")
