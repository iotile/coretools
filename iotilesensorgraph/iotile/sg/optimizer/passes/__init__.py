from .remove_copylatest import RemoveCopyLatestPass
from .convert_to_always import ConvertCountOneToAlways
from .downgrade_copyall import ConvertCopyAllToCopyLatest
from .dead_code_elimination import RemoveDeadCodePass
from .remove_constants import RemoveConstantsPass

__all__ = ['RemoveCopyLatestPass', 'ConvertCountOneToAlways', 'ConvertCopyAllToCopyLatest',
           'RemoveDeadCodePass', 'RemoveConstantsPass']
