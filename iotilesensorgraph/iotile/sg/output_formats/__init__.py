"""Output formats that we can save a sensor graph in."""

from collections import namedtuple

from .snippet import format_snippet
from .ascii import format_ascii
from .config import format_config
from .script import format_script

OutputFormat = namedtuple("OutputFormat", ['format', 'text'])

KNOWN_FORMATS = {
    'snippet': OutputFormat(format_snippet, True),
    'ascii': OutputFormat(format_ascii, True),
    'config': OutputFormat(format_config, True),
    'script': OutputFormat(format_script, False)
}


__all__ = [u'KNOWN_FORMATS']
