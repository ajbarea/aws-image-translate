"""Enhanced media utilities for Reddit image processing.

This module provides advanced media handling capabilities inspired by the subreddit-scraper,
including better file type detection, HTML parsing for media URLs, and robust download handling.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from config import MEDIA_PROCESSING_CONFIG

# Type aliases for better readability
PathLike = Union[str, os.PathLike[str]]
URLString = str

# Constants for supported file extensions
SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif"}
)

SUPPORTED_VIDEO_EXTENSIONS = frozenset(
    {"mp4", "webm", "avi", "mov", "mkv", "flv", "wmv", "m4v"}
)

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

# Extension normalization mapping
EXTENSION_MAPPING = {
    "jpeg": "jpg",
    "tiff": "tif",
}

DEFAULT_EXTENSION = "jpg"

# URL validation pattern
URL_PATTERN = re.compile(r"^https?://[^\s]+$")


class MediaError(Exception):
    """Custom exception for media processing errors."""

    def __init__(self, message: str, url: Optional[str] = None) -> None:
        self.url = url
        super().__init__(message)


def validate_url(url: Optional[str]) -> bool:
    """Validate if a string is a properly formatted URL.

    Args:
        url: URL string to validate

    Returns:
        True if URL is valid

    Raises:
        TypeError: If url is not a string
    """
    if not isinstance(url, str):
        raise TypeError("URL must be a string")

    if not url.strip():
        return False

    return bool(URL_PATTERN.match(url.strip()))


def get_file_extension(url: Optional[str]) -> str:
    """Determine file extension from URL with comprehensive validation.

    Args:
        url: URL to analyze

    Returns:
        File extension (normalized, e.g., 'jpg', 'png', 'mp4') or default 'jpg'

    Raises:
        TypeError: If url is not a string

    Example:
        >>> get_file_extension("https://example.com/image.jpeg")
        'jpg'
        >>> get_file_extension("https://example.com/video.mp4")
        'mp4'
        >>> get_file_extension("https://example.com/unknown")
        'jpg'
    """
    if not isinstance(url, str):
        raise TypeError("URL must be a string")

    if not url.strip():
        return DEFAULT_EXTENSION

    try:
        parsed_url = urlparse(url.strip())
        path = parsed_url.path

        if not path:
            return DEFAULT_EXTENSION

        # Extract extension from path
        _, ext = os.path.splitext(path)
        if ext:
            clean_ext = ext.lstrip(".").lower().strip()
            # Normalize extension
            normalized_ext = EXTENSION_MAPPING.get(clean_ext, clean_ext)
            if normalized_ext in SUPPORTED_EXTENSIONS:
                return normalized_ext

        # Fallback to query parameters
        return _fallback_extension_extraction(url)  # pragma: no cover

    except (ValueError, AttributeError):
        return DEFAULT_EXTENSION


def _fallback_extension_extraction(url: str) -> str:
    """Fallback method for extension extraction using simple string operations.

    Args:
        url: URL string

    Returns:
        File extension or default
    """
    try:
        # Look for common patterns in URL
        url_lower = url.lower()
        for ext in SUPPORTED_EXTENSIONS:
            if f".{ext}" in url_lower:
                normalized = EXTENSION_MAPPING.get(ext, ext)
                return normalized

        return DEFAULT_EXTENSION

    except (IndexError, AttributeError):
        return DEFAULT_EXTENSION


def is_supported_extension(extension: Optional[str]) -> bool:
    """Check if a file extension is supported.

    Args:
        extension: File extension to check (with or without leading dot)

    Returns:
        True if extension is supported

    Raises:
        TypeError: If extension is not a string

    Example:
        >>> is_supported_extension("jpg")
        True
        >>> is_supported_extension(".mp4")
        True
        >>> is_supported_extension("xyz")
        False
    """
    if not isinstance(extension, str):
        raise TypeError("Extension must be a string")

    # Remove leading dot if present
    clean_ext = extension.lstrip(".").lower().strip()

    # Normalize extension
    normalized_ext = EXTENSION_MAPPING.get(clean_ext, clean_ext)

    return normalized_ext in SUPPORTED_EXTENSIONS


def get_file_type(extension: Optional[str]) -> Optional[str]:
    """Get file type category (image/video) for an extension.

    Args:
        extension: File extension

    Returns:
        'image', 'video', or None if unsupported
    """
    if not isinstance(extension, str):
        return None

    clean_ext = extension.lstrip(".").lower().strip()
    normalized_ext = EXTENSION_MAPPING.get(clean_ext, clean_ext)

    if normalized_ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    elif normalized_ext in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    else:
        return None


def parse_html_for_media(
    url: str, headers: Dict[str, str]
) -> Tuple[Optional[str], Optional[str]]:
    """Parse HTML page for og:video or og:image meta tags.

    Args:
        url: URL to parse
        headers: Request headers

    Returns:
        Tuple of (media_url, file_extension) or (None, None) if not found

    Example:
        >>> headers = {"User-Agent": "my-app/1.0"}
        >>> url, ext = parse_html_for_media("https://example.com/post", headers)
        >>> if url:
        ...     print(f"Found media: {url} with extension: {ext}")
    """
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Check for video first (higher priority)
        og_video_tag = soup.find("meta", property="og:video")
        if og_video_tag and isinstance(og_video_tag, Tag):
            try:
                content = og_video_tag.get("content")
                if content:
                    return str(content), "mp4"
            except (AttributeError, TypeError):  # pragma: no cover
                pass  # pragma: no cover

        # Check for image
        og_image_tag = soup.find("meta", property="og:image")
        if og_image_tag and isinstance(og_image_tag, Tag):
            try:
                content = og_image_tag.get("content")
                if content:
                    return str(content), get_file_extension(
                        str(content)
                    )  # pragma: no cover
            except (AttributeError, TypeError):  # pragma: no cover
                pass  # pragma: no cover

        return None, None

    except (requests.exceptions.RequestException, Exception) as e:
        logging.warning(f"Failed to parse HTML for media from {url}: {e}")
        return None, None


def get_accept_header(file_extension: str, media_url: str) -> str:
    """Get appropriate Accept header based on file extension and URL.

    Args:
        file_extension: File extension (e.g., 'mp4', 'jpg', 'gif')
        media_url: Media URL to analyze

    Returns:
        Accept header value for HTTP requests

    Example:
        >>> get_accept_header("mp4", "https://example.com/video.mp4")
        'video/*, */*'
        >>> get_accept_header("jpg", "https://example.com/image.jpg")
        'image/*'
    """
    media_url_lower = media_url.lower()

    if file_extension in [
        "mp4",
        "webm",
        "avi",
        "mov",
        "mkv",
        "flv",
        "wmv",
        "m4v",
    ] or any(f".{ext}" in media_url_lower for ext in ["mp4", "webm", "avi", "mov"]):
        return "video/*, */*"
    elif file_extension == "gif" or ".gif" in media_url_lower:
        return "image/gif, image/*"
    else:
        return "image/*"


def enhanced_download_media(
    url: str,
    user_agent: Optional[str] = None,
    timeout: int = 30,
    max_size: int = 50 * 1024 * 1024,  # 50MB default limit
) -> Tuple[Optional[bytes], Optional[str]]:
    """Enhanced media download with better error handling and validation.

    Args:
        url: Media URL to download
        user_agent: Custom user agent string
        timeout: Request timeout in seconds
        max_size: Maximum file size in bytes

    Returns:
        Tuple of (content_bytes, content_type) or (None, None) on error
    """
    try:
        if not validate_url(url):
            raise MediaError(f"Invalid URL: {url}", url)

        headers: Dict[str, str] = {
            "User-Agent": user_agent
            or cast(str, MEDIA_PROCESSING_CONFIG["USER_AGENT_FALLBACK"])
        }

        # Determine file extension and set appropriate Accept header
        file_extension = get_file_extension(url)
        headers["Accept"] = get_accept_header(file_extension, url)

        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise MediaError(f"File too large: {content_length} bytes", url)

        # Download content
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                raise MediaError(
                    f"File too large during download: {len(content)} bytes", url
                )

        content_type = (
            response.headers.get("Content-Type", "").lower().split(";")[0].strip()
        )

        return content, content_type

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error downloading {url}: {e}")
        return None, None
    except MediaError as e:
        logging.error(f"Media error: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Unexpected error downloading {url}: {e}")
        return None, None


def get_supported_extensions() -> Dict[str, List[str]]:
    """Get all supported file extensions organized by type.

    Returns:
        Dictionary with 'image' and 'video' keys containing lists of extensions

    Example:
        >>> extensions = get_supported_extensions()
        >>> print(extensions['image'])
        ['jpg', 'png', 'gif', ...]
    """
    return {
        "image": sorted(SUPPORTED_IMAGE_EXTENSIONS),
        "video": sorted(SUPPORTED_VIDEO_EXTENSIONS),
        "all": sorted(SUPPORTED_EXTENSIONS),
    }


def get_project_root_path() -> str:
    """Get the absolute path to the project root directory.

    Returns:
        str: Absolute path to the project root directory
    """
    return str(Path(__file__).parent.parent.absolute())
