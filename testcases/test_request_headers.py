from RequestHeaders import APP_USER_AGENT, IMAGE_REQUEST_HEADERS, JSON_REQUEST_HEADERS


def test_user_agent_is_browser_compatible_and_identifies_app():
    assert "Mozilla/5.0" in APP_USER_AGENT
    assert "Chrome/" in APP_USER_AGENT
    assert "OwlcatPortraitTool/1.0" in APP_USER_AGENT


def test_request_headers_share_user_agent_with_useful_accept_headers():
    assert IMAGE_REQUEST_HEADERS["User-Agent"] == APP_USER_AGENT
    assert JSON_REQUEST_HEADERS["User-Agent"] == APP_USER_AGENT
    assert "image/" in IMAGE_REQUEST_HEADERS["Accept"]
    assert "application/json" in JSON_REQUEST_HEADERS["Accept"]
