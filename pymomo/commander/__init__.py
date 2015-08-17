import pymomo.utilities.typedargs
import os.path

folder = os.path.dirname(__file__)
pathname = os.path.join(folder, 'basic_types')

pymomo.utilities.typedargs.type_system.load_external_types(pathname)