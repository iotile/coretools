"""Output formats that we can save a sensor graph in."""

from .snippet import format_snippet
from .ascii import format_ascii
from .config import format_config

known_formats = {
    'snippet': format_snippet,
    'ascii': format_ascii,
    'config': format_config
}


__all__ = [u'known_formats']
