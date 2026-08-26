from __future__ import annotations

JOB_TYPE_PROCESS_PHOTO = "process_photo"
JOB_TYPE_CLEANUP_MEDIA = "cleanup_media"
ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_PHOTOS = 6
DERIVATIVE_FORMAT = "JPEG"
DERIVATIVE_QUALITY = 85
