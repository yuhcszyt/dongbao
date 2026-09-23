from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from array import array
import math
import subprocess
from typing import Any

MODEL_ID = "Wiam/distilhubert-finetuned-babycry-v7"
MODEL_REVISION = "b409a7fc4eec84b80965760ef4cd6691e4e7138c"

LABELS = {
    "hungry": "饥饿",
    "discomfort": "身体不舒服",
    "tired": "困倦",
    "belly_pain": "腹部不适",
    "burping": "需要拍嗝",
}


class CryModelUnavailable(RuntimeError):
    pass


class InvalidCryAudio(ValueError):
    pass


def model_path() -> Path:
    return Path(os.environ.get("CRY_MODEL_PATH", "/app/data/models/babycry-v7"))


@lru_cache(maxsize=1)
def _pipeline():
    path = model_path()
    if not (path / "model.safetensors").is_file():
        raise CryModelUnavailable("哭声模型尚未安装，请先执行 make setup-cry-model")
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise CryModelUnavailable("哭声模型运行依赖尚未安装，请先执行 make setup") from exc
    try:
        return pipeline("audio-classification", model=str(path), device=-1)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CryModelUnavailable("哭声模型暂时无法加载") from exc


def possibility(score: float, rank: int) -> str:
    if rank == 0 and score >= 0.55:
        return "较可能"
    if rank <= 1 and score >= 0.2:
        return "有可能"
    return "可能性较低"


def normalize_predictions(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = {str(item.get("label", "")).lower(): float(item.get("score", 0)) for item in raw}
    ordered = sorted(LABELS, key=lambda label: scores.get(label, 0), reverse=True)
    return [
        {
            "category": label,
            "label": LABELS[label],
            "score": round(max(0.0, min(1.0, scores.get(label, 0))), 6),
            "possibility": possibility(scores.get(label, 0), rank),
        }
        for rank, label in enumerate(ordered)
    ]


def ensure_audible(path: Path) -> None:
    """拒绝过短或近似静音的输入，避免五分类模型被迫给静音贴原因标签。"""
    try:
        converted = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
            check=True,
            capture_output=True,
            timeout=15,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvalidCryAudio("无法读取这段录音，请重新录制") from exc
    samples = array("h")
    samples.frombytes(converted)
    if len(samples) < 8_000:
        raise InvalidCryAudio("录音太短，请至少录制 1 秒清晰哭声")
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
    if rms < 0.002:
        raise InvalidCryAudio("没有听到清晰声音，请靠近宝宝重新录制")


def classify_audio(path: Path) -> list[dict[str, Any]]:
    ensure_audible(path)
    try:
        raw = _pipeline()(str(path), top_k=len(LABELS))
    except CryModelUnavailable:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise CryModelUnavailable("这段录音暂时无法分析，请重新录制") from exc
    if not isinstance(raw, list):
        raise CryModelUnavailable("哭声模型返回了无法识别的结果")
    return normalize_predictions(raw)


def is_uncertain(candidates: list[dict[str, Any]]) -> bool:
    if len(candidates) < 2:
        return True
    first, second = candidates[0]["score"], candidates[1]["score"]
    return first < 0.35 or first - second < 0.08
