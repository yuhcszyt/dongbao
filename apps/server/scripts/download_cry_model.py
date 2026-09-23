from argparse import ArgumentParser
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = "Wiam/distilhubert-finetuned-babycry-v7"
MODEL_REVISION = "b409a7fc4eec84b80965760ef4cd6691e4e7138c"


def main() -> None:
    parser = ArgumentParser(description="下载懂宝固定版本的婴儿哭声分类模型")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=args.output,
        allow_patterns=["config.json", "preprocessor_config.json", "model.safetensors"],
    )
    print(f"cry model ready: {args.output}")


if __name__ == "__main__":
    main()
