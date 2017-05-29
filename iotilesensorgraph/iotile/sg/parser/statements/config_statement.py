"""Set config statement that adds a config variable to the sensor graph."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class SetConfigStatement(SensorGraphStatement):
    """A config variable assignment.

    The statement form is:
    set var = value [as type];

    where var must be an identifier or a number and value must be an rvalue.
    If var is not an identifier that corresponds with a known ConfigDefinition
    that specifies the type of the config variable, the type must be specified
    explicitly.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
    """

    def __init__(self, parsed):
        self.identifier = parsed[0]
        self.value = parsed[1]
        self.explicit_type = None

        if len(parsed) == 3:
            self.explicit_type = parsed[2]

        super(SetConfigStatement, self).__init__([])

    def __str__(self):
        if self.explicit_type is not None:
            return u"set %s = %s as %s;" % (str(self.identifier), str(self.value), str(self.explicit_type))

        return u"set %s = %s" % (str(self.identifier), str(self.value))
