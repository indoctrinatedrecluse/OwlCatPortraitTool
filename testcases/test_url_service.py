from io import BytesIO

import pytest
from PIL import Image

from RequestHeaders import IMAGE_REQUEST_HEADERS
import URLService


class FakeResponse:
    def __init__(self, content=b"", headers=None, status_error=None):
        self.content = content
        self.headers = headers or {}
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error


def make_png_bytes(size=(12, 16), color=(120, 40, 200, 255)):
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_is_valid_url_accepts_http_and_https():
    assert URLService.is_valid_url("http://example.com/a.png")
    assert URLService.is_valid_url("https://example.com/a.png")


def test_is_valid_url_rejects_missing_or_unsupported_scheme():
    assert not URLService.is_valid_url("example.com/a.png")
    assert not URLService.is_valid_url("file:///tmp/a.png")
    assert not URLService.is_valid_url("")


def test_get_image_from_url_downloads_supported_image(monkeypatch):
    image_bytes = make_png_bytes()

    def fake_get(url, timeout, headers):
        assert url == "https://example.com/image.png"
        assert timeout == URLService.REQUEST_TIMEOUT_SECONDS
        assert headers == IMAGE_REQUEST_HEADERS
        return FakeResponse(
            image_bytes,
            headers={"content-type": "image/png; charset=binary"},
        )

    monkeypatch.setattr(URLService.requests, "get", fake_get)

    image = URLService.get_image_from_url("https://example.com/image.png")

    assert image.size == (12, 16)


def test_get_image_from_url_rejects_non_image_content_type(monkeypatch):
    def fake_get(url, timeout, headers):
        assert headers == IMAGE_REQUEST_HEADERS
        return FakeResponse(b"<html></html>", headers={"content-type": "text/html"})

    monkeypatch.setattr(URLService.requests, "get", fake_get)

    with pytest.raises(ValueError, match="supported image"):
        URLService.get_image_from_url("https://example.com/page")


def test_get_image_from_url_rejects_invalid_url():
    with pytest.raises(ValueError, match="valid HTTP or HTTPS"):
        URLService.get_image_from_url("not-a-url")
