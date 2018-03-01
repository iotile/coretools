from .remove_copylatest import RemoveCopyLatestPass
from .convert_to_always import ConvertCountOneToAlways
from .downgrade_copyall import ConvertCopyAllToCopyLatest
from .dead_code_elimination import RemoveDeadCodePass

__all__ = ['RemoveCopyLatestPass', 'ConvertCountOneToAlways', 'ConvertCopyAllToCopyLatest',
           'RemoveDeadCodePass']
