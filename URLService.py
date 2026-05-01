from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image

from RequestHeaders import IMAGE_REQUEST_HEADERS


REQUEST_TIMEOUT_SECONDS = 15
SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def is_valid_url(url):
    """Return True when the text looks like an absolute HTTP URL."""
    parsed_url = urlparse(url.strip())
    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def get_image_from_url(url):
    """Download an image and return it as a PIL Image."""
    if not is_valid_url(url):
        raise ValueError("Enter a valid HTTP or HTTPS image URL.")

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=IMAGE_REQUEST_HEADERS,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if content_type and content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        raise ValueError(f"URL does not point to a supported image: {content_type}")

    image = Image.open(BytesIO(response.content))
    image.verify()

    return Image.open(BytesIO(response.content))
