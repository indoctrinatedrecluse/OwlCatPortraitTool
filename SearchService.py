from io import BytesIO
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlparse, urlunparse

from PIL import Image
import requests

from RequestHeaders import IMAGE_REQUEST_HEADERS, JSON_REQUEST_HEADERS


MAX_SEARCH_RESULTS_PER_PAGE = 50
REQUEST_TIMEOUT_SECONDS = 15
SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@dataclass(frozen=True)
class PortraitSearchResult:
    image_url: str
    preview_url: str | None = None
    width: int | None = None
    height: int | None = None

BOORU_SITES = {
    "Safebooru": {
        "api": "gelbooru",
        "url": "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags={tags}&limit={limit}&pid={page}",
    },
    "Danbooru": {
        "api": "danbooru",
        "url": "https://danbooru.donmai.us/posts.json?tags={tags}&limit={limit}&page={page}",
        "max_tags": 2,  # Anonymous users are limited to 2 tags
    },
    "Konachan": {
        "api": "danbooru",
        "url": "https://konachan.com/post.json?tags={tags}&limit={limit}&page={page}",
    },
    "Yande.re": {
        "api": "danbooru",
        "url": "https://yande.re/post.json?tags={tags}&limit={limit}&page={page}",
    },
    "Gelbooru": {
        "api": "gelbooru",
        "url": "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags={tags}&limit={limit}&pid={page}",
    },
    "e621": {
        "api": "e621",
        "url": "https://e621.net/posts.json?tags={tags}&limit={limit}&page={page}",
    },
    "Rule34": {
        "api": "gelbooru",
        "url": "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&tags={tags}&limit={limit}&pid={page}",
    },
    "Derpibooru": {
        "api": "derpibooru",
        "url": "https://derpibooru.org/api/v1/json/search/images?q={tags}&per_page={limit}&page={page}",
    },
    "HypnoHub": {
        "api": "danbooru",
        "url": "https://hypnohub.net/post.json?tags={tags}&limit={limit}&page={page}",
    },
    "Tbib": {
        "api": "gelbooru",
        "url": "https://tbib.org/index.php?page=dapi&s=post&q=index&json=1&tags={tags}&limit={limit}&pid={page}",
    },
}


def get_booru_sites():
    """Return the configured booru site search APIs."""
    return list(BOORU_SITES.keys())


def _get_url_origin(url):
    """Extracts the scheme and netloc from a URL (e.g., 'https://example.com')."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _join_url(base_url, path):
    """Safely join a base URL and a relative path."""
    if not path or path.startswith(("http://", "https://")):
        return path
    return urljoin(base_url, path)


def _make_api_request(url):
    """Shared function to make a JSON API request."""
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=JSON_REQUEST_HEADERS,
    )
    response.raise_for_status()
    # Some APIs (like Gelbooru) return an empty body for no results,
    # which would cause a JSONDecodeError.
    if not response.content:
        return None
    return response.json()


def _extract_common_post_data(post, config):
    """Extracts result data from a standard Danbooru/Gelbooru post object."""
    origin = _get_url_origin(config["url"])
    image_url = post.get("file_url")
    preview_url_path = (
        post.get("preview_url")
        or post.get("preview_file_url")
        or post.get("sample_url")
        or post.get("sample_file_url")
        or post.get("large_file_url")
    )
    width = post.get("image_width") or post.get("width")
    height = post.get("image_height") or post.get("height")

    image_url = _join_url(origin, image_url)
    preview_url = _join_url(origin, preview_url_path)
    if not image_url:
        return None

    return PortraitSearchResult(
        image_url=image_url,
        preview_url=preview_url,
        width=int(width) if width else None,
        height=int(height) if height else None,
    )


def _search_gelbooru(config, tags, page, limit):
    """Handler for Gelbooru-style APIs."""
    tag_query = quote(" ".join(tags))
    api_page = page - 1  # 0-indexed
    search_url = config["url"].format(tags=tag_query, limit=limit, page=api_page)
    json_data = _make_api_request(search_url)

    if not json_data:
        return []

    posts_data = []
    if isinstance(json_data, dict):
        # Handle cases where 'post' is a list of posts or a single post object
        posts = json_data.get("post")
        if isinstance(posts, list):
            posts_data = posts
        elif isinstance(posts, dict):
            posts_data = [posts]
    elif isinstance(json_data, list):
        posts_data = json_data

    results = []
    for p in posts_data:
        if isinstance(p, dict):
            result = _extract_common_post_data(p, config)
            if result:
                results.append(result)
    return results


def _search_danbooru(config, tags, page, limit):
    """Handler for Danbooru-style APIs."""
    max_tags = config.get("max_tags")
    if max_tags and len(tags) > max_tags:
        tags = tags[:max_tags]
    tag_query = quote(" ".join(tags))
    api_page = page  # 1-indexed
    search_url = config["url"].format(tags=tag_query, limit=limit, page=api_page)
    json_data = _make_api_request(search_url)

    if not json_data:
        return []

    posts_data = []
    if isinstance(json_data, dict):
        posts = json_data.get("posts")
        if isinstance(posts, list):
            posts_data = posts
        elif isinstance(posts, dict):
            posts_data = [posts]
    elif isinstance(json_data, list):
        posts_data = json_data

    results = []
    for p in posts_data:
        if isinstance(p, dict):
            result = _extract_common_post_data(p, config)
            if result:
                results.append(result)
    return results


def _search_derpibooru(config, tags, page, limit):
    """Handler for the Derpibooru API."""
    tag_query = quote(" ".join(tags))
    search_url = config["url"].format(tags=tag_query, limit=limit, page=page)
    json_data = _make_api_request(search_url)

    if not json_data:
        return []

    results = []
    for post in json_data.get("images", []):
        if not isinstance(post, dict):
            continue

        representations = post.get("representations", {})
        image_url = representations.get("full")
        if image_url:
            # Prefer smaller thumbnails for faster preview loading
            preview_url = (
                representations.get("thumb")
                or representations.get("small")
                or representations.get("medium")
                or representations.get("large")
            )
            results.append(PortraitSearchResult(
                image_url=image_url,
                preview_url=preview_url,
                width=post.get("width"),
                height=post.get("height"),
            ))
    return results


def _search_e621(config, tags, page, limit):
    """Handler for the e621 API."""
    tag_query = quote(" ".join(tags))
    search_url = config["url"].format(tags=tag_query, limit=limit, page=page)
    json_data = _make_api_request(search_url)

    if not json_data:
        return []

    results = []
    for post in json_data.get("posts", []):
        if not isinstance(post, dict):
            continue

        file_info = post.get("file")
        if not isinstance(file_info, dict):
            continue

        image_url = file_info.get("url")
        if not image_url:
            continue

        preview_url = None
        sample_info = post.get("sample")
        # Prefer sample URL if it exists and has a URL
        if sample_info and sample_info.get("has") and sample_info.get("url"):
            preview_url = sample_info.get("url")

        # Fall back to preview URL
        if not preview_url:
            preview_info = post.get("preview")
            if preview_info and preview_info.get("url"):
                preview_url = preview_info.get("url")

        results.append(PortraitSearchResult(
            image_url=image_url,
            preview_url=preview_url,
            width=file_info.get("width"),
            height=file_info.get("height"),
        ))
    return results


API_HANDLERS = {
    "gelbooru": _search_gelbooru,
    "danbooru": _search_danbooru,
    "derpibooru": _search_derpibooru,
    "e621": _search_e621,
}


def search_portraits_by_tags(
    tags, booru_name, page=1, limit=MAX_SEARCH_RESULTS_PER_PAGE
):
    """
    Search for portraits by tags on a specified booru site, acting as a
    dispatcher to the correct API handler.
    """
    normalized_tags = normalize_tags(tags)
    if not normalized_tags:
        return []

    booru_config = BOORU_SITES.get(booru_name)
    if not booru_config:
        raise ValueError(f"Unknown booru site: {booru_name}")

    handler = API_HANDLERS.get(booru_config["api"])
    if not handler:
        raise ValueError(f"No handler for API type: {booru_config['api']}")

    # Let exceptions propagate to the UI layer, which has its own error handling.
    # This prevents silently failing on network errors or JSON decoding issues.
    results = handler(booru_config, normalized_tags, page, limit)
    # Common logic for filtering and de-duplicating results
    results_by_url = {}
    for result in results:
        if result.image_url in results_by_url:
            continue

        if not is_image_url(result.image_url):
            continue

        results_by_url[result.image_url] = result
        if len(results_by_url) >= limit:
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
    from GlobalsService import get_full_length_portrait_size, get_required_portrait_dimensions

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
    from GlobalsService import get_full_length_portrait_size
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
