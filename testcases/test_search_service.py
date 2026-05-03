from io import BytesIO

import pytest
from PIL import Image

from RequestHeaders import IMAGE_REQUEST_HEADERS, JSON_REQUEST_HEADERS
import SearchService


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self.data = data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def make_png_bytes(size=(25, 35)):
    buffer = BytesIO()
    Image.new("RGBA", size, (10, 20, 30, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_normalize_tags_accepts_comma_separated_text():
    assert SearchService.normalize_tags(" vampire, portrait ,, elf ") == [
        "vampire",
        "portrait",
        "elf",
    ]


def test_normalize_tags_rejects_non_list_non_string():
    assert SearchService.normalize_tags({"vampire"}) == []


def test_is_image_url_accepts_supported_image_extensions_and_query_strings():
    assert SearchService.is_image_url("https://example.com/a.JPG")
    assert SearchService.is_image_url("https://example.com/a.webp?download=1")
    assert not SearchService.is_image_url("https://example.com/a.mp4")


def test_search_portraits_by_tags_deduplicates_and_skips_non_images(monkeypatch):
    def fake_api_request(url):
        assert "tags=vampire" in url
        return FakeResponse(
            [
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/b.mp4"},
                {"file_url": "https://example.com/c.png"},
            ]
        )

    monkeypatch.setattr(SearchService, "_make_api_request", fake_api_request)

    results = SearchService.search_portraits_by_tags(
        ["vampire"], "Safebooru", limit=10
    )

    assert [result.image_url for result in results] == [
        "https://example.com/a.jpg",
        "https://example.com/c.png",
    ]


def test_search_portraits_by_tags_obeys_max_results(monkeypatch):
    def fake_api_request(url):
        return FakeResponse(
            [
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/b.jpg"},
                {"file_url": "https://example.com/c.jpg"},
            ]
        )

    monkeypatch.setattr(SearchService, "_make_api_request", fake_api_request)

    results = SearchService.search_portraits_by_tags("vampire", "Safebooru", limit=2)

    assert [result.image_url for result in results] == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]


def test_search_portraits_by_tags_handles_pagination_schemes(monkeypatch):
    calls = []

    def fake_api_request(url):
        calls.append(url)
        return FakeResponse([])

    monkeypatch.setattr(SearchService, "_make_api_request", fake_api_request)

    # Gelbooru (0-indexed pid)
    SearchService.search_portraits_by_tags("test", "Safebooru", page=3)
    assert "pid=2" in calls[-1]

    # Danbooru (1-indexed page)
    SearchService.search_portraits_by_tags("test", "Danbooru", page=3)
    assert "page=3" in calls[-1]


def test_search_portraits_by_tags_limits_tags_for_danbooru(monkeypatch):
    calls = []

    def fake_api_request(url):
        calls.append(url)
        return FakeResponse([])

    monkeypatch.setattr(SearchService, "_make_api_request", fake_api_request)

    SearchService.search_portraits_by_tags(["a", "b", "c"], "Danbooru")
    assert "tags=a%20b" in calls[-1]
    assert "c" not in calls[-1]


def test_search_portraits_by_tags_handles_derpibooru(monkeypatch):
    def fake_api_request(url):
        assert "derpibooru.org" in url
        return {
            "images": [
                {
                    "width": 100,
                    "height": 200,
                    "representations": {
                        "full": "https://example.com/derpi.png",
                        "thumb": "https://example.com/derpi_thumb.png",
                    },
                }
            ]
        }

    monkeypatch.setattr(SearchService, "_make_api_request", fake_api_request)

    results = SearchService.search_portraits_by_tags("test", "Derpibooru")

    assert len(results) == 1
    assert results[0].image_url == "https://example.com/derpi.png"
    assert results[0].preview_url == "https://example.com/derpi_thumb.png"


@pytest.mark.parametrize(
    "booru_name, expected_handler_name",
    [
        ("Safebooru", "_search_gelbooru"),
        ("Danbooru", "_search_danbooru"),
        ("Derpibooru", "_search_derpibooru"),
        ("HypnoHub", "_search_danbooru"),
        ("Tbib", "_search_gelbooru"),
    ],
)
def test_search_portraits_by_tags_dispatches_to_correct_handler(
    monkeypatch, booru_name, expected_handler_name
):
    handler_calls = []

    def mock_handler(config, tags, page, limit):
        handler_calls.append(True)
        return []

    monkeypatch.setattr(SearchService, expected_handler_name, mock_handler)

    SearchService.search_portraits_by_tags("test", booru_name)

    assert len(handler_calls) == 1

def test_get_image_dimensions_reads_downloaded_image_size(monkeypatch):
    def fake_get(url, headers, timeout):
        assert headers == IMAGE_REQUEST_HEADERS
        return FakeResponse(content=make_png_bytes((44, 55)))

    monkeypatch.setattr(SearchService.requests, "get", fake_get)

    assert SearchService.get_image_dimensions("https://example.com/a.png") == (44, 55)


def test_supported_portrait_dimensions_accepts_exact_or_large_enough():
    assert SearchService.is_supported_portrait_dimensions(185, 242)
    assert SearchService.is_supported_portrait_dimensions(692, 1024)
    assert SearchService.is_supported_portrait_dimensions(900, 1200)
    assert not SearchService.is_supported_portrait_dimensions(400, 600)


def test_compress_image_for_portrait_downscales_large_image():
    image = Image.new("RGBA", (1200, 1600))

    compressed = SearchService.compress_image_for_portrait(image)

    assert compressed.size == (692, 1024)
