# A descriptive User-Agent is often required by image board APIs (e.g., Danbooru).
# It should identify the application and provide a way to find its source.
APP_USER_AGENT = (
    "OwlcatPortraitTool/0.9.0 "
    "(https://github.com/indoctrinatedrecluse/OwlcatPortraitTool)"
)

IMAGE_REQUEST_HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

JSON_REQUEST_HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept": "application/json,text/plain,*/*",
}
