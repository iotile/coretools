import re
from registry_resolver import ComponentRegistryResolver

__all__ = ['ComponentRegistryResolver']

DEFAULT_REGISTRY_RESOLVER = (0, re.compile('.*'), ComponentRegistryResolver, {})
