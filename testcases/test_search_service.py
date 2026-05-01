from io import BytesIO

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


def test_extract_image_results_handles_flat_booru_shape():
    results = SearchService.extract_image_results(
        [
            {
                "file_url": "https://example.com/full.jpg",
                "preview_url": "https://example.com/preview.jpg",
                "width": "800",
                "height": "1200",
            }
        ]
    )

    assert len(results) == 1
    assert results[0].image_url == "https://example.com/full.jpg"
    assert results[0].preview_url == "https://example.com/preview.jpg"
    assert results[0].width == 800
    assert results[0].height == 1200


def test_extract_image_results_handles_nested_danbooru_style_shape():
    results = SearchService.extract_image_results(
        {
            "posts": [
                {
                    "file": {
                        "url": "https://example.com/full.png",
                        "width": 900,
                        "height": 1300,
                    },
                    "preview": {"url": "https://example.com/preview.png"},
                }
            ]
        }
    )

    assert len(results) == 1
    assert results[0].image_url == "https://example.com/full.png"
    assert results[0].preview_url == "https://example.com/preview.png"
    assert results[0].width == 900
    assert results[0].height == 1300


def test_search_portraits_by_tags_deduplicates_and_skips_non_images(monkeypatch):
    monkeypatch.setattr(SearchService, "BOORU_SITES", ["https://example.com/api?tags={tags}"])

    def fake_get(url, timeout, headers):
        assert "tags=vampire" in url
        assert headers == JSON_REQUEST_HEADERS
        return FakeResponse(
            [
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/b.mp4"},
                {"file_url": "https://example.com/c.png"},
            ]
        )

    monkeypatch.setattr(SearchService.requests, "get", fake_get)

    results = SearchService.search_portraits_by_tags(["vampire"], max_results=10)

    assert [result.image_url for result in results] == [
        "https://example.com/a.jpg",
        "https://example.com/c.png",
    ]


def test_search_portraits_by_tags_obeys_max_results(monkeypatch):
    monkeypatch.setattr(SearchService, "BOORU_SITES", ["https://example.com/api?tags={tags}"])

    def fake_get(url, timeout, headers):
        assert headers == JSON_REQUEST_HEADERS
        return FakeResponse(
            [
                {"file_url": "https://example.com/a.jpg"},
                {"file_url": "https://example.com/b.jpg"},
                {"file_url": "https://example.com/c.jpg"},
            ]
        )

    monkeypatch.setattr(SearchService.requests, "get", fake_get)

    results = SearchService.search_portraits_by_tags("vampire", max_results=2)

    assert [result.image_url for result in results] == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]


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
