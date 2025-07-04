from unittest.mock import MagicMock, patch

import pytest

from src.enhanced_media_utils import (
    MediaError,
    enhanced_download_media,
    get_accept_header,
    get_file_extension,
    get_file_type,
    get_supported_extensions,
    is_supported_extension,
    parse_html_for_media,
    validate_url,
)


def test_validate_url():
    assert validate_url("https://example.com/image.jpg")
    assert validate_url("http://example.com/path/to/image")
    assert not validate_url("")
    assert not validate_url("   ")
    assert not validate_url("not_a_url")
    with pytest.raises(TypeError):
        validate_url(None)


def test_get_file_extension():
    assert get_file_extension("https://example.com/image.jpeg") == "jpg"
    assert get_file_extension("https://example.com/image.png") == "png"
    assert get_file_extension("https://example.com/video.mp4") == "mp4"
    assert get_file_extension("https://example.com/image") == "jpg"
    assert get_file_extension("") == "jpg"
    with pytest.raises(TypeError):
        get_file_extension(None)


def test_get_file_extension_empty_path():
    assert get_file_extension("https://example.com") == "jpg"
    assert get_file_extension("https://example.com/") == "jpg"


def test_get_file_extension_parsing_error():
    with patch("src.enhanced_media_utils.urlparse") as mock_urlparse:
        mock_urlparse.side_effect = ValueError("Invalid URL")
        assert get_file_extension("https://example.com/image.jpg") == "jpg"

        mock_urlparse.side_effect = AttributeError("Missing attribute")
        assert get_file_extension("https://example.com/image.jpg") == "jpg"


def test_is_supported_extension():
    assert is_supported_extension("jpg")
    assert is_supported_extension(".jpg")
    assert is_supported_extension("jpeg")
    assert is_supported_extension("png")
    assert not is_supported_extension("doc")
    with pytest.raises(TypeError):
        is_supported_extension(None)


def test_get_file_type():
    assert get_file_type("jpg") == "image"
    assert get_file_type("png") == "image"
    assert get_file_type("mp4") == "video"
    assert get_file_type("webm") == "video"
    assert get_file_type("doc") is None
    assert get_file_type(None) is None


def test_media_error():
    error = MediaError("Test error", "http://example.com")
    assert str(error) == "Test error"
    assert error.url == "http://example.com"


@patch("src.enhanced_media_utils.requests.get")
def test_parse_html_for_media_success(mock_get):
    mock_response = MagicMock()
    mock_response.content = """
        <meta property="og:video" content="https://example.com/video.mp4">
        <meta property="og:image" content="https://example.com/image.jpg">
    """.encode()
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    url, ext = parse_html_for_media("https://example.com", {})
    assert url == "https://example.com/video.mp4"  # Video takes precedence
    assert ext == "mp4"


@patch("src.enhanced_media_utils.requests.get")
def test_parse_html_for_media_error(mock_get):
    mock_get.side_effect = Exception("Network error")
    url, ext = parse_html_for_media("https://example.com", {})
    assert url is None
    assert ext is None


def test_get_accept_header():
    assert "video/*" in get_accept_header("mp4", "https://example.com/video.mp4")
    assert "image/gif" in get_accept_header("gif", "https://example.com/image.gif")
    assert "image/*" in get_accept_header("jpg", "https://example.com/image.jpg")


@patch("src.enhanced_media_utils.requests.get")
def test_enhanced_download_media_success(mock_get):
    mock_response = MagicMock()
    mock_response.headers = {"content-length": "1000", "Content-Type": "image/jpeg"}
    mock_response.iter_content.return_value = [b"test_content"]
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    content, content_type = enhanced_download_media("https://example.com/image.jpg")
    assert content == b"test_content"
    assert content_type == "image/jpeg"


@patch("src.enhanced_media_utils.requests.get")
def test_enhanced_download_media_file_too_large(mock_get):
    mock_response = MagicMock()
    mock_response.headers = {"content-length": str(100 * 1024 * 1024)}  # 100MB
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    content, content_type = enhanced_download_media(
        "https://example.com/large.jpg", max_size=50 * 1024 * 1024
    )
    assert content is None
    assert content_type is None


@patch("src.enhanced_media_utils.requests.get")
def test_enhanced_download_media_network_error(mock_get):
    mock_get.side_effect = Exception("Network error")
    content, content_type = enhanced_download_media("https://example.com/image.jpg")
    assert content is None
    assert content_type is None


def test_get_supported_extensions():
    extensions = get_supported_extensions()
    assert "image" in extensions
    assert "video" in extensions
    assert "all" in extensions
    assert "jpg" in extensions["image"]
    assert "mp4" in extensions["video"]
    assert set(extensions["all"]) == set(extensions["image"] + extensions["video"])
