from __future__ import annotations

from ai_dating.ai.client import (
    ProviderError,
    ProviderResult,
    embed_text,
)
from ai_dating.ai.fake import embed_with_fake
from ai_dating.ai.schema import EMBED_DIM
from ai_dating.config import Settings


def run_embedding(settings: Settings, text: str) -> ProviderResult:
    if settings.dslab_api_key:
        result = embed_text(settings, text)
    else:
        result = embed_with_fake(text, EMBED_DIM)
    vector = result.payload
    if not isinstance(vector, list) or len(vector) != EMBED_DIM:
        raise ProviderError("schema_invalid")
    return result


__all__ = ["ProviderError", "run_embedding"]
