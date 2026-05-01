from io import BytesIO
from dataclasses import dataclass
from urllib.parse import quote_plus

from PIL import Image
import requests

from GlobalsService import get_full_length_portrait_size, get_required_portrait_dimensions
from RequestHeaders import IMAGE_REQUEST_HEADERS, JSON_REQUEST_HEADERS


MAX_SEARCH_RESULTS = 30
REQUEST_TIMEOUT_SECONDS = 15
SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@dataclass(frozen=True)
class PortraitSearchResult:
    image_url: str
    preview_url: str | None = None
    width: int | None = None
    height: int | None = None

BOORU_SITES = [
    "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags={tags}",
    "https://danbooru.donmai.us/posts.json?tags={tags}",
    "https://konachan.com/post.json?tags={tags}",
    "https://e621.net/posts.json?tags={tags}",
    "https://rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&tags={tags}",
]


def search_portraits_by_tags(tags, max_results=MAX_SEARCH_RESULTS):
    """Return image candidates for the provided booru tags."""
    normalized_tags = normalize_tags(tags)
    if not normalized_tags:
        return []

    tag_query = quote_plus(" ".join(normalized_tags))
    results_by_url = {}

    for site in BOORU_SITES:
        try:
            response = requests.get(
                site.format(tags=tag_query),
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers=JSON_REQUEST_HEADERS,
            )
            response.raise_for_status()
            results = extract_image_results(response.json())
        except (ValueError, requests.RequestException):
            continue

        for result in results:
            if result.image_url in results_by_url:
                continue

            if not is_image_url(result.image_url):
                continue

            results_by_url[result.image_url] = result

            if len(results_by_url) >= max_results:
                break

        if len(results_by_url) >= max_results:
            break

    return list(results_by_url.values())


def get_image_dimensions(image_url):
    response = requests.get(
        image_url,
        headers=IMAGE_REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    with Image.open(BytesIO(response.content)) as image:
        return image.size


def is_supported_portrait_dimensions(width, height):
    required_dimensions = {
        (portrait_size.width, portrait_size.height)
        for portrait_size in get_required_portrait_dimensions()
    }
    full_length_size = get_full_length_portrait_size()

    if (width, height) in required_dimensions:
        return True

    return (
        width >= full_length_size.width
        and height >= full_length_size.height
    )


def is_image_url(image_url):
    return image_url.lower().split("?", 1)[0].endswith(SUPPORTED_IMAGE_EXTENSIONS)


def compress_image_for_portrait(image):
    """Downscale oversized images to the game's full-length portrait size."""
    full_length_size = get_full_length_portrait_size()

    if (
        image.width <= full_length_size.width
        and image.height <= full_length_size.height
    ):
        return image.copy()

    return image.resize(
        (full_length_size.width, full_length_size.height),
        Image.Resampling.LANCZOS,
    )


def normalize_tags(tags):
    """Accept comma-separated text or a list of tags and return clean tags."""
    if isinstance(tags, str):
        tags = tags.split(",")

    if not isinstance(tags, list):
        return []

    return [str(tag).strip() for tag in tags if str(tag).strip()]


def extract_image_results(data):
    """Handle the slightly different response shapes used by booru APIs."""
    if isinstance(data, dict):
        posts = data.get("posts", [])
    elif isinstance(data, list):
        posts = data
    else:
        return []

    image_results = []
    for post in posts:
        if not isinstance(post, dict):
            continue

        result = extract_image_result(post)
        if result:
            image_results.append(result)

    return image_results


def extract_image_result(post):
    image_url = post.get("file_url")
    preview_url = (
        post.get("preview_file_url")
        or post.get("sample_file_url")
        or post.get("large_file_url")
        or post.get("preview_url")
        or post.get("sample_url")
    )
    width = post.get("image_width") or post.get("width")
    height = post.get("image_height") or post.get("height")

    if not image_url and isinstance(post.get("file"), dict):
        image_url = post["file"].get("url")
        width = width or post["file"].get("width")
        height = height or post["file"].get("height")

    if not preview_url and isinstance(post.get("preview"), dict):
        preview_url = post["preview"].get("url")

    if not preview_url and isinstance(post.get("sample"), dict):
        preview_url = post["sample"].get("url")

    if not image_url:
        return None

    return PortraitSearchResult(
        image_url=image_url,
        preview_url=preview_url,
        width=int(width) if width else None,
        height=int(height) if height else None,
    )


# Backward-compatible name for older callers.
def extract_image_urls(data):
    return [result.image_url for result in extract_image_results(data)]
