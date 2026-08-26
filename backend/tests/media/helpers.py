from __future__ import annotations

import hashlib
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from tests.onboarding.helpers import key


def jpeg_bytes(
    color: tuple[int, int, int] = (200, 30, 30), *, exif: bool = False
) -> bytes:
    image = Image.new("RGB", (32, 24), color)
    buf = BytesIO()
    if exif:
        extra = image.getexif()
        extra[270] = "secret GPS note"
        image.save(buf, format="JPEG", exif=extra)
    else:
        image.save(buf, format="JPEG")
    return buf.getvalue()


def upload_photo(
    client: TestClient,
    auth: dict,
    body: bytes | None = None,
    content_type: str = "image/jpeg",
) -> dict:
    payload = body if body is not None else jpeg_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    intent = client.post(
        "/v1/profile/photos/upload-intents",
        json={
            "content_type": content_type,
            "byte_size": len(payload),
            "content_sha256": digest,
        },
        headers={**auth, **key()},
    )
    assert intent.status_code == 200, intent.text
    put = client.put(
        intent.json()["upload_url"],
        content=payload,
        headers={"Content-Type": content_type},
    )
    assert put.status_code == 204, put.text
    done = client.post(
        f"/v1/profile/photos/{intent.json()['upload_intent_id']}/complete",
        json={},
        headers={**auth, **key()},
    )
    assert done.status_code == 200, done.text
    return done.json()
