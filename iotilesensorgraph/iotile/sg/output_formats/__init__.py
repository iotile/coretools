"""Output formats that we can save a sensor graph in."""

from .snippet import format_snippet


known_formats = {
    'snippet': format_snippet
}


__all__ = u'known_formats'
