"""Validate and clean uploaded garden photos (PRD 6.4 B, 6.6, 8.2).

clean_photo() checks the upload really is a JPEG/PNG/WebP image under the size limit (by decoding
it, not trusting the extension or browser MIME type), fixes the orientation, drops all metadata
(EXIF, including GPS location) by re-encoding the pixels, and shrinks it to at most 1600 px.
"""
import io
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE_PX = 1600
JPEG_QUALITY = 85


def clean_photo(upload):
    """Return a metadata-free JPEG ContentFile, or raise ValidationError with a user-facing message."""
    if upload.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"Photos must be {settings.MAX_UPLOAD_MB} MB or smaller.")
    try:
        with Image.open(upload) as probe:
            image_format = probe.format
            probe.verify()                      # detects truncated or corrupt files
        upload.seek(0)
        with Image.open(upload) as image:
            image.load()
            if image_format not in ALLOWED_FORMATS:
                raise ValidationError("Please upload a JPEG, PNG or WebP photo.")
            image = ImageOps.exif_transpose(image)          # apply the camera rotation before EXIF is dropped
            image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
            clean = image.convert("RGB")                    # new pixel buffer: no EXIF, GPS or other metadata
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError("That file is not a valid image.") from exc
    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
