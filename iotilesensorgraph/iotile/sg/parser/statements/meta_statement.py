"""A meta variable definition that is used for passing information along with a sensor graph."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class MetaStatement(SensorGraphStatement):
    """A metadata variable definition.

    The statement form is:
    meta var = value;

    where var must be an identifier and value must be an rvalue.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.identifier = parsed[0]
        self.value = parsed[1]

        super(MetaStatement, self).__init__([], location)

    def __str__(self):
        return u'meta %s = %s;' % (str(self.identifier), str(self.value))
