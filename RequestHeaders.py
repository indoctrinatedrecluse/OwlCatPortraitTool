APP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 "
    "OwlcatPortraitTool/1.0"
)

IMAGE_REQUEST_HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

JSON_REQUEST_HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept": "application/json,text/plain,*/*",
}
