from functools import lru_cache
from pathlib import Path
import os
import tomllib
from typing import Literal

from pydantic import BaseModel, Field, model_validator

class TencentASRConfig(BaseModel):
    enabled: bool = False
    endpoint: str
    region: str
    engine_model_type: str
    voice_format: str
    timeout_seconds: int = Field(gt=0, le=120)
    secret_id_env: str
    secret_key_env: str

class LargeModelConfig(BaseModel):
    provider: Literal["openai_compatible"] = "openai_compatible"
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    supports_vision: bool = True
    timeout_seconds: int = Field(gt=0, le=180)
    api_key_env: str

    @model_validator(mode="after")
    def enabled_values(self):
        if self.enabled and (not self.base_url or not self.model):
            raise ValueError("启用大模型时必须配置 base_url 和 model")
        return self

class ProvidersConfig(BaseModel):
    tencent_asr: TencentASRConfig
    large_model: LargeModelConfig

@lru_cache
def get_config() -> ProvidersConfig:
    path = Path(os.environ.get("APP_CONFIG", "/app/config/providers.toml"))
    with path.open("rb") as stream:
        return ProvidersConfig.model_validate(tomllib.load(stream))
