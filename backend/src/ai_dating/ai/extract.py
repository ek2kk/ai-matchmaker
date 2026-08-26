from __future__ import annotations

from ai_dating.ai.client import ProviderError, ProviderResult, extract_chat_completion
from ai_dating.ai.fake import extract_with_fake
from ai_dating.ai.guardrails import scan_sensitive
from ai_dating.ai.schema import ExtractionRejected, parse_extraction_output
from ai_dating.config import Settings


def run_extraction(
    settings: Settings, prompt_code: str, answer_text: str
) -> tuple[list[dict], ProviderResult]:
    if (
        settings.dslab_api_key
        or settings.openrouter_api_key
        or (settings.yandex_ai_base_url and settings.yandex_ai_api_key)
    ):
        result = extract_chat_completion(settings, prompt_code, answer_text)
    else:
        result = extract_with_fake(prompt_code, answer_text)
    scan_sensitive(result.payload)
    facts = parse_extraction_output(result.payload)
    return facts, result


__all__ = ["ProviderError", "run_extraction", "ExtractionRejected"]
