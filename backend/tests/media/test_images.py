from io import BytesIO

from PIL import Image

from ai_dating.media.images import decode_image, render_derivative


def test_decode_strips_exif():
    image = Image.new("RGB", (16, 12), (10, 20, 30))
    extra = image.getexif()
    extra[270] = "hidden"
    buf = BytesIO()
    image.save(buf, format="JPEG", exif=extra)
    decoded = decode_image(buf.getvalue())
    derived, width, height = render_derivative(decoded, 8)
    out = decode_image(derived)
    assert width <= 8 and height <= 8
    assert dict(out.getexif()) == {}
