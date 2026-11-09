import json
import uuid
from io import BytesIO
import urllib.error
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
GEOCODING_TIMEOUT = 5


class GeocodingError(Exception):
    """The place lookup service could not be reached or returned something unusable."""


def search_places(query, count=5):
    """Look up cities by name with Open-Meteo geocoding (PRD 6.1, no API key).

    Returns [{"city", "region", "country_code", "latitude", "longitude", "timezone", "label"}].
    Coordinates are rounded to 2 decimals (~1 km): city precision is enough and stays private.
    """
    url = f"{GEOCODING_URL}?{urllib.parse.urlencode({'name': query, 'count': count, 'language': 'en', 'format': 'json'})}"
    try:
        with urllib.request.urlopen(url, timeout=GEOCODING_TIMEOUT) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise GeocodingError(str(exc)) from exc

    places = []
    for item in payload.get("results") or []:
        try:
            place = {
                "city": item["name"],
                "region": item.get("admin1", ""),
                "country_code": item.get("country_code", ""),
                "latitude": round(item["latitude"], 2),
                "longitude": round(item["longitude"], 2),
                "timezone": item.get("timezone", ""),
            }
        except (KeyError, TypeError):
            continue
        place["label"] = ", ".join(part for part in (place["city"], place["region"], item.get("country", "")) if part)
        places.append(place)
    return places


AVATAR_MAX_BYTES = 10 * 1024 * 1024  # PRD 6.6: image uploads max 10 MB
AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_SIZE = 512


def clean_avatar(upload):
    """Validate an uploaded avatar and return a re-encoded JPEG with all metadata removed.

    Re-encoding drops EXIF (including GPS, PRD 2.2 privacy), and the image is shrunk to 512 px.
    Raises ValueError with a user-facing message.
    """
    if upload.size > AVATAR_MAX_BYTES:
        raise ValueError("That image is over 10 MB. Choose a smaller one.")
    try:
        image = Image.open(upload)
        if image.format not in AVATAR_FORMATS:
            raise ValueError("Upload a JPEG, PNG, or WebP image.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("We couldn't read that image. Try a different file.") from exc
    image.thumbnail((AVATAR_SIZE, AVATAR_SIZE))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
