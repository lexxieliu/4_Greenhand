"""Upload validation and clean-up shared by diagnosis photos and post images (PRD 6.4 B, 6.6, 2.2 Privacy)."""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DIMENSION = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 50_000_000       # refuse decompression bombs


def process_upload(upload):
    """Validate an uploaded image and return a resized JPEG ContentFile with all metadata (EXIF GPS) removed.
    Raises ValidationError with a user-facing message."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Photos must be 10 MB or smaller.")
    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise ValidationError("Please upload a JPEG, PNG or WebP photo.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValidationError("That file is not a readable image.") from exc
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    # A fresh save without exif= writes no metadata.
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name="photo.jpg")
