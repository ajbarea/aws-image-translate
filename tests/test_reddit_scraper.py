import datetime
import os
from unittest.mock import MagicMock, patch

import pytest

from src import reddit_scraper


class DummySubmission:
    def __init__(self, url, selftext=None, fullname="t3_dummy", created_utc=None):
        self.url = url
        self.selftext = selftext
        self.fullname = fullname
        if created_utc is None:
            # Use timezone-aware UTC timestamp
            self.created_utc = datetime.datetime.now(datetime.timezone.utc).timestamp()
        else:
            self.created_utc = created_utc


def test_extract_urls_from_text():
    text = "Check this image https://i.redd.it/abc123.jpg and this gallery https://imgur.com/gallery/xyz456"
    urls = reddit_scraper._extract_urls_from_text(text)
    assert "https://i.redd.it/abc123.jpg" in urls
    assert "https://imgur.com/gallery/xyz456" in urls
    assert len(urls) == 2


def test_extract_image_urls_from_submission_url_and_selftext():
    # Direct image URL
    sub = DummySubmission(url="https://i.imgur.com/def456.png")
    urls = reddit_scraper.extract_image_urls_from_submission(sub)
    assert "https://i.imgur.com/def456.png" in urls
    # Gallery URL in selftext
    sub2 = DummySubmission(
        url="https://notimage.com/", selftext="https://imgur.com/gallery/xyz456"
    )
    urls2 = reddit_scraper.extract_image_urls_from_submission(sub2)
    assert "https://imgur.com/gallery/xyz456" in urls2
    # Reddit gallery
    sub3 = DummySubmission(url="https://reddit.com/gallery/abc123")
    urls3 = reddit_scraper.extract_image_urls_from_submission(sub3)
    assert "https://reddit.com/gallery/abc123" in urls3


def test_is_supported_media_url():
    assert reddit_scraper.is_supported_media_url("https://example.com/image.jpg")
    assert reddit_scraper.is_supported_media_url("https://example.com/photo.jpeg")
    assert reddit_scraper.is_supported_media_url("https://example.com/pic.png")
    assert reddit_scraper.is_supported_media_url("https://example.com/animation.gif")
    assert reddit_scraper.is_supported_media_url("https://example.com/photo.webp")
    assert not reddit_scraper.is_supported_media_url("https://example.com/doc.pdf")
    assert not reddit_scraper.is_supported_media_url("https://example.com/video.mp4")


def test_is_direct_media_url():
    assert reddit_scraper.is_direct_media_url("https://i.redd.it/abc123.jpg")
    assert reddit_scraper.is_direct_media_url("https://i.imgur.com/def456.png")
    assert reddit_scraper.is_direct_media_url("https://preview.redd.it/xyz789.gif")
    assert not reddit_scraper.is_direct_media_url("https://example.com/abc123.jpg")
    assert not reddit_scraper.is_direct_media_url("https://i.redd.it/abc123.mp4")


def test_get_image_urls_from_translator_handles_no_reddit():
    assert reddit_scraper.get_image_urls_from_translator(None) == []


def test_get_image_urls_from_translator_success():
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    submissions = [
        DummySubmission(url="https://i.redd.it/abc123.jpg"),
        DummySubmission(url="https://imgur.com/gallery/xyz456"),
    ]
    mock_subreddit.new.return_value = submissions
    mock_reddit.subreddit.return_value = mock_subreddit
    urls = reddit_scraper.get_image_urls_from_translator(mock_reddit)
    assert "https://i.redd.it/abc123.jpg" in urls
    assert "https://imgur.com/gallery/xyz456" in urls


def test_get_new_image_posts_since_handles_no_reddit():
    assert reddit_scraper.get_new_image_posts_since(None) == []


def test_get_new_image_posts_since_success():
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    submissions = [
        DummySubmission(
            url="https://i.redd.it/abc123.jpg", fullname="t3_1", created_utc=1
        ),
        DummySubmission(
            url="https://imgur.com/gallery/xyz456", fullname="t3_2", created_utc=2
        ),
    ]
    mock_subreddit.new.return_value = submissions
    mock_reddit.subreddit.return_value = mock_subreddit
    posts = reddit_scraper.get_new_image_posts_since(mock_reddit)
    assert ("t3_1", "https://i.redd.it/abc123.jpg") in posts
    assert ("t3_2", "https://imgur.com/gallery/xyz456") in posts


@patch.dict(os.environ, {"REDDIT_TEST_MODE": "1"})
def test_create_reddit_credentials_success():
    creds = reddit_scraper.create_reddit_credentials()
    assert creds["client_id"] == "test_id"
    assert creds["client_secret"] == "test_secret"
    assert creds["user_agent"] == "test_agent"


@patch.dict(os.environ, {}, clear=True)  # Clear all environment variables
@patch("src.reddit_scraper.REDDIT_CLIENT_ID", None)
@patch("src.reddit_scraper.REDDIT_CLIENT_SECRET", None)
@patch("src.reddit_scraper.REDDIT_USER_AGENT", None)
def test_create_reddit_credentials_missing_creds():
    with pytest.raises(ValueError) as exc_info:
        reddit_scraper.create_reddit_credentials()
    assert "Missing Reddit credentials" in str(exc_info.value)


@patch.dict(os.environ, {}, clear=True)  # Clear all environment variables
@patch("src.reddit_scraper.REDDIT_CLIENT_ID", "real_id")
@patch("src.reddit_scraper.REDDIT_CLIENT_SECRET", "real_secret")
@patch("src.reddit_scraper.REDDIT_USER_AGENT", "real_agent")
def test_create_reddit_credentials_no_env_local_file():
    """Test create_reddit_credentials when .env.local doesn't exist (line 66->69)."""
    with patch("src.reddit_scraper.Path") as mock_path:
        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = False  # .env.local doesn't exist
        mock_path.return_value.parent.parent.__truediv__.return_value = mock_env_path

        creds = reddit_scraper.create_reddit_credentials()
        assert creds["client_id"] == "real_id"
        assert creds["client_secret"] == "real_secret"
        assert creds["user_agent"] == "real_agent"


def test_init_reddit_client_success_and_failure(monkeypatch):
    # Success case with mocked create_reddit_credentials
    mock_create_creds = MagicMock(
        return_value={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "user_agent": "test_agent",
        }
    )
    monkeypatch.setattr(reddit_scraper, "create_reddit_credentials", mock_create_creds)

    # Mock Reddit client
    class DummyReddit:
        def __init__(self, *args, **kwargs):
            self.read_only = False

        def subreddit(self, name):
            class DummySubreddit:
                display_name = name

            return DummySubreddit()

    monkeypatch.setattr(reddit_scraper.praw, "Reddit", lambda *a, **kw: DummyReddit())
    client = reddit_scraper.init_reddit_client()
    assert client is not None

    # Failure case
    def raise_exc(*a, **kw):
        raise RuntimeError("fail")

    monkeypatch.setattr(reddit_scraper.praw, "Reddit", raise_exc)
    client = reddit_scraper.init_reddit_client()
    assert client is None


def test_get_image_urls_from_subreddits_handles_no_reddit():
    assert reddit_scraper.get_image_urls_from_subreddits(None) == {}


def test_get_image_urls_from_subreddits_success():
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    # Different submissions for different subreddits
    translator_submissions = [
        DummySubmission(url="https://i.redd.it/translator1.jpg"),
        DummySubmission(url="https://imgur.com/gallery/translator2"),
    ]
    food_submissions = [
        DummySubmission(url="https://i.redd.it/food1.jpg"),
    ]

    # Mock subreddit.new() to return different submissions based on subreddit
    def mock_new(limit):
        if mock_reddit.subreddit.call_args[0][0] == "translator":
            return translator_submissions
        else:
            return food_submissions

    mock_subreddit.new.side_effect = mock_new

    # Test with specific subreddits
    urls = reddit_scraper.get_image_urls_from_subreddits(
        mock_reddit, subreddits=["translator", "food"]
    )

    assert "translator" in urls
    assert "food" in urls
    assert "https://i.redd.it/translator1.jpg" in urls["translator"]
    assert "https://imgur.com/gallery/translator2" in urls["translator"]
    assert "https://i.redd.it/food1.jpg" in urls["food"]

    # Test error handling for non-existent subreddit
    mock_reddit.subreddit.side_effect = Exception("Subreddit not found")
    urls = reddit_scraper.get_image_urls_from_subreddits(
        mock_reddit, subreddits=["nonexistent"]
    )
    assert urls["nonexistent"] == []


def test_create_reddit_credentials_with_real_values():
    """Test create_reddit_credentials when credentials are actually found (line 86)."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.reddit_scraper.REDDIT_CLIENT_ID", "real_id"):
            with patch("src.reddit_scraper.REDDIT_CLIENT_SECRET", "real_secret"):
                with patch("src.reddit_scraper.REDDIT_USER_AGENT", "real_agent"):
                    creds = reddit_scraper.create_reddit_credentials()
                    assert creds["client_id"] == "real_id"
                    assert creds["client_secret"] == "real_secret"
                    assert creds["user_agent"] == "real_agent"


def test_init_reddit_client_credential_error():
    """Test init_reddit_client when create_reddit_credentials raises ValueError (lines 115-116)."""
    with patch("src.reddit_scraper.create_reddit_credentials") as mock_create_creds:
        mock_create_creds.side_effect = ValueError("Missing credentials")
        client = reddit_scraper.init_reddit_client()
        assert client is None


def test_get_image_urls_from_subreddits_uses_config_subreddits():
    """Test get_image_urls_from_subreddits when subreddits is None and config has SUBREDDITS (lines 235-237)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    submissions = [DummySubmission(url="https://i.redd.it/test.jpg")]
    mock_subreddit.new.return_value = submissions

    # Mock config to have SUBREDDITS set
    with patch.dict(
        reddit_scraper.REDDIT_SCRAPING_CONFIG, {"SUBREDDITS": ["test1", "test2"]}
    ):
        urls = reddit_scraper.get_image_urls_from_subreddits(
            mock_reddit, subreddits=None
        )
        assert "test1" in urls
        assert "test2" in urls


def test_get_image_urls_from_subreddits_uses_default_subreddit():
    """Test get_image_urls_from_subreddits when subreddits is None and config has no SUBREDDITS (lines 235-237)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    submissions = [DummySubmission(url="https://i.redd.it/test.jpg")]
    mock_subreddit.new.return_value = submissions

    # Mock config to have no SUBREDDITS (None)
    with patch.dict(
        reddit_scraper.REDDIT_SCRAPING_CONFIG,
        {"SUBREDDITS": None, "DEFAULT_SUBREDDIT": "translator"},
    ):
        urls = reddit_scraper.get_image_urls_from_subreddits(
            mock_reddit, subreddits=None
        )
        assert "translator" in urls


def test_get_new_image_posts_since_with_after_fullname():
    """Test get_new_image_posts_since when after_fullname is provided (line 307)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    submissions = [
        DummySubmission(url="https://i.redd.it/test.jpg", fullname="t3_test")
    ]
    mock_subreddit.new.return_value = submissions

    posts = reddit_scraper.get_new_image_posts_since(
        mock_reddit, after_fullname="t3_previous"
    )

    # Verify that subreddit.new was called with the after parameter
    mock_subreddit.new.assert_called_with(limit=25, params={"after": "t3_previous"})
    assert len(posts) == 1


def test_get_new_image_posts_since_without_after_fullname():
    """Test get_new_image_posts_since when after_fullname is None (line 316->315)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    submissions = [
        DummySubmission(url="https://i.redd.it/test.jpg", fullname="t3_test")
    ]
    mock_subreddit.new.return_value = submissions

    posts = reddit_scraper.get_new_image_posts_since(mock_reddit, after_fullname=None)

    # Verify that subreddit.new was called without the after parameter
    mock_subreddit.new.assert_called_with(limit=25)
    assert len(posts) == 1


def test_get_new_image_posts_since_no_posts_found():
    """Test get_new_image_posts_since when no posts are found (line 325->334)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    # No submissions found
    mock_subreddit.new.return_value = []

    posts = reddit_scraper.get_new_image_posts_since(mock_reddit)

    # Should return empty list when no posts are found
    assert posts == []


def test_get_new_image_posts_since_duplicate_posts():
    """Test get_new_image_posts_since when duplicate posts are filtered out (line 329->328)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    # Create submissions with duplicate URL
    submissions = [
        DummySubmission(
            url="https://i.redd.it/same.jpg", fullname="t3_1", created_utc=1
        ),
        DummySubmission(
            url="https://i.redd.it/same.jpg", fullname="t3_1", created_utc=1
        ),  # Duplicate
    ]
    mock_subreddit.new.return_value = submissions

    posts = reddit_scraper.get_new_image_posts_since(mock_reddit)

    # Should only return one post, not the duplicate
    assert len(posts) == 1
    assert posts[0] == ("t3_1", "https://i.redd.it/same.jpg")


def test_get_new_image_posts_since_unsupported_media_url():
    """Test get_new_image_posts_since when URLs are found but not supported media format (line 316->315)."""
    mock_reddit = MagicMock()
    mock_subreddit = MagicMock()
    mock_reddit.subreddit.return_value = mock_subreddit

    # Create a submission with a URL that contains an image domain but isn't supported by the regex
    # This will pass the IMAGE_DOMAINS check but not match the regex pattern
    submissions = [
        DummySubmission(
            url="https://i.redd.it/some_video.mp4", fullname="t3_1", created_utc=1
        ),
    ]
    mock_subreddit.new.return_value = submissions

    # Mock extract_image_urls_from_submission to return a URL that would fail is_supported_media_url
    def mock_extract_urls(submission):
        return {"https://i.redd.it/some_video.mp4"}

    with patch(
        "src.reddit_scraper.extract_image_urls_from_submission",
        side_effect=mock_extract_urls,
    ):
        posts = reddit_scraper.get_new_image_posts_since(mock_reddit)

    # Should return empty list since the URL is not supported (mp4 is not in SUPPORTED_MEDIA_FORMATS)
    assert posts == []


def test_get_new_image_posts_since_exception_handling():
    """Test get_new_image_posts_since when an exception occurs (lines 332-333)."""
    mock_reddit = MagicMock()
    mock_reddit.subreddit.side_effect = Exception("Reddit API error")

    posts = reddit_scraper.get_new_image_posts_since(mock_reddit)
    assert posts == []
