from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from ai_dating.media.constants import DERIVATIVE_FORMAT, DERIVATIVE_QUALITY


def decode_image(body: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(body))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("invalid_image") from exc
    return ImageOps.exif_transpose(image)


def render_derivative(image: Image.Image, max_edge: int) -> tuple[bytes, int, int]:
    rgb = image.convert("RGB")
    rgb.thumbnail((max_edge, max_edge))
    buf = BytesIO()
    rgb.save(buf, format=DERIVATIVE_FORMAT, quality=DERIVATIVE_QUALITY, optimize=True)
    return buf.getvalue(), rgb.width, rgb.height
