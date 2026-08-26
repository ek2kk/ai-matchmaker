from ai_dating.ai.client import embedding_model_version
from ai_dating.ai.embed import run_embedding
from ai_dating.ai.schema import EMBED_DIM
from ai_dating.config import Settings


def test_fake_embedding_matches_dim_and_is_normalized():
    settings = Settings(_env_file=None)
    first = run_embedding(settings, "search_mode: dating\nfact interest: music")
    second = run_embedding(settings, "search_mode: dating\nfact interest: music")
    other = run_embedding(settings, "search_mode: friendship")
    assert isinstance(first.payload, list)
    assert len(first.payload) == EMBED_DIM
    assert first.payload == second.payload
    assert first.payload != other.payload
    norm = sum(item * item for item in first.payload) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_dslab_key_selects_gte_base_without_separate_embedding_key():
    settings = Settings(_env_file=None, dslab_api_key="sk-dslab-test")
    assert embedding_model_version(settings) == "gte-base"


def test_explicit_embedding_credentials_win_over_dslab():
    settings = Settings(
        _env_file=None,
        dslab_api_key="sk-dslab-test",
        embedding_api_key="sk-embed",
        embedding_base_url="https://example.invalid/v1",
        embedding_model="EmbeddingsGigaR",
    )
    assert embedding_model_version(settings) == "EmbeddingsGigaR"
