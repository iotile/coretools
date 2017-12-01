"""Output formats that we can save a sensor graph in."""

from .snippet import format_snippet
from .ascii import format_ascii


known_formats = {
    'snippet': format_snippet,
    'ascii': format_ascii
}


__all__ = [u'known_formats']
