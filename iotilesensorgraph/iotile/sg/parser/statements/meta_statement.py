"""A meta variable definition that is used for passing information along with a sensor graph."""

from .statement import SensorGraphStatement


class MetaStatement(SensorGraphStatement):
    """A metadata variable definition.

    The statement form is:
    meta var = value;

    where var must be an identifier and value must be an rvalue.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
    """

    def __init__(self, parsed):
        self.identifier = parsed[0]
        self.value = parsed[1]

        super(MetaStatement, self).__init__([])
