"""Common shared utility classes and methods."""

from .template import render_template, render_recursive_template, render_template_inplace
from .bundled_data import resource_path

__all__ = ['resource_path', 'render_template', 'render_recursive_template',
           'render_template_inplace']
