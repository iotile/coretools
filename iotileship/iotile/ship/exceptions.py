from iotile.core.exceptions import IOTileException


class RecipeFileInvalid(IOTileException):
    """Error indicating that a recipe file is malformed."""
    pass


class RecipeActionMissingParameter(IOTileException):
    """Thrown when parameters not passed."""
    pass


class RecipeNotFoundError(IOTileException):
    """Thrown when a recipe is required that cannot be found."""
    pass


class UnknownRecipeActionType(IOTileException):
    """Thrown when RecipceAction passed is unknown."""
    pass


class RecipeVariableNotPassed(IOTileException):
    """Thrown when user does not pass in a value for a variable parameter in a yaml file"""
    pass


class UnknownRecipeResourceType(IOTileException):
    """Thrown when a shared resource is declared of an unknown type."""
    pass


class RecipeResourceManagementError(IOTileException):
    """Thrown when there is a problem setting up or cleanup up one or more share resources."""
    pass
