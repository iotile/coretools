from pymomo.utilities.typedargs import annotated

_name_ = "Developer"

#Outside accessible API for this package
from registry import ComponentRegistry

@annotated
def registry():
	return ComponentRegistry()