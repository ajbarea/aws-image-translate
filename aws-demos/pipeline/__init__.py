"""
Pipeline package for AWS translation components.
"""

from .detect_text import detect_text
from .detect_language import detect_language
from .translate_text import translate_text

__all__ = ['detect_text', 'detect_language', 'translate_text']