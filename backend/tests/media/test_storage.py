from pathlib import Path

from ai_dating.config import Settings
from ai_dating.media.storage import LocalStore, local_key_from_upload_token


def test_local_store_roundtrip(tmp_path: Path):
    settings = Settings(_env_file=None, object_storage_path=str(tmp_path))
    store = LocalStore(tmp_path, settings.media_signing_secret)
    store.put("photos/a/b", b"hello", "image/jpeg")
    got = store.get("photos/a/b")
    assert got.exists
    assert got.body == b"hello"
    url = store.upload_url("photos/a/b", "image/jpeg", 2_000_000_000)
    token = url.rsplit("/", 1)[-1]
    assert local_key_from_upload_token(settings, token) == "photos/a/b"
    store.delete("photos/a/b")
    assert store.head("photos/a/b").exists is False
