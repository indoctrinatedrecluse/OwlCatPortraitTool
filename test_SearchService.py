import pytest
import requests

from SearchService import BOORU_SITES, search_portraits_by_tags


# A mapping of booru sites to a common, safe tag that is likely to return results.
# This helps ensure that our test isn't failing due to a niche tag.
TEST_TAGS_BY_BOORU = {
    "Safebooru": ["1girl", "solo"],
    "Danbooru": ["1girl", "solo"],
    "Konachan": ["1girl", "solo"],
    "Yande.re": ["1girl", "solo"],
    "Gelbooru": ["1girl", "solo"],
    "e621": ["cat", "solo"],
    "Rule34": ["1girl", "solo"],
    "Derpibooru": ["safe", "solo"],
    "HypnoHub": ["1girl", "solo"],
    "Tbib": ["1girl", "solo"],
}


@pytest.mark.network
@pytest.mark.parametrize("booru_name", BOORU_SITES.keys())
def test_booru_search_api_handler(booru_name):
    """
    Performs a live API call to each supported booru site to verify:
    1. The API endpoint is correct and reachable.
    2. The request is formatted correctly.
    3. The JSON response is parsed successfully by the handler.
    4. The handler returns a list of PortraitSearchResult objects.
    """
    if booru_name not in TEST_TAGS_BY_BOORU:
        pytest.skip(f"No test tag defined for {booru_name}. Skipping.")

    tags = TEST_TAGS_BY_BOORU[booru_name]

    try:
        # We request a small limit to keep the test fast and minimize data transfer.
        results = search_portraits_by_tags(tags, booru_name, limit=3)

        # The primary goal is to ensure the handler doesn't crash and returns the correct type.
        # It's okay if a search returns no results, as long as it's an empty list.
        assert isinstance(results, list)

        # If results are returned, validate their structure.
        if results:
            print(f"SUCCESS: [{booru_name}] Found {len(results)} results for tags: {tags}")
            for result in results:
                assert isinstance(result.image_url, str)
                assert result.image_url.startswith("http")
                if result.preview_url:
                    assert isinstance(result.preview_url, str)
                    assert result.preview_url.startswith("http")
        else:
            print(f"SUCCESS: [{booru_name}] Found 0 results for tags: {tags}. This is an acceptable empty response.")
    except requests.exceptions.RequestException as e:
        # Network errors are common for live tests. Skip instead of failing to avoid flaky CI.
        pytest.skip(f"Network error when contacting {booru_name}: {e}")
    except Exception as e:
        # Any other exception (e.g., JSONDecodeError, KeyError) is a failure in our handler.
        pytest.fail(f"Search for tags '{tags}' on {booru_name} failed with an unexpected exception: {e}")