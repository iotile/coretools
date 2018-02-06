from iotile.core.exceptions import IOTileException


class RecipeActionMissingParameter(IOTileException):
    """Thrown when parameters not passed."""
    pass

class UnknownRecipeActionType(IOTileException):
    """Thrown when RecipceAction passed is unknown."""
    pass