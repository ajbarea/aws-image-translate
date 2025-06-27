from unittest.mock import MagicMock
from src import reddit_scraper
import datetime


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


def test_init_reddit_client_success_and_failure(monkeypatch):
    # Patch praw.Reddit to simulate success
    class DummyReddit:
        def __init__(self, *a, **kw):
            self.read_only = False

    monkeypatch.setattr(reddit_scraper.praw, "Reddit", lambda *a, **kw: DummyReddit())
    client = reddit_scraper.init_reddit_client()
    assert client is not None

    # Patch praw.Reddit to raise exception
    def raise_exc(*a, **kw):
        raise RuntimeError("fail")

    monkeypatch.setattr(reddit_scraper.praw, "Reddit", raise_exc)
    client = reddit_scraper.init_reddit_client()
    assert client is None
