from .language import get_language
from .statements import statement_map
from iotile.core.exceptions import ArgumentError


class SensorGraphFileParser(object):
    """A parser that builds a sensor graph object from a text file specification."""

    def __init__(self):
        self._block_stack = []
        self.statements = []

    def dump_tree(self, statement=None, indent_level=0):
        """Dump the AST for this parsed file.

        Args:
            statement (SensorGraphStatement): the statement to print
                if this function is called recursively.
            indent_level (int): The number of spaces to indent this
                statement.  Used for recursively printing blocks of
                statements.
        Returns:
            str: The AST for this parsed sg file as a nested
                tree with one node per line and blocks indented.
        """

        out = u""

        indent = u" "*indent_level

        if statement is None:
            for statement in self.statements:
                out += self.dump_tree(statement, indent_level) + u'\n'
        else:
            out += str(statement) + '\n'

            if len(statement.children) > 0:
                for child in statement.children:
                    out += self.dump_tree(child, indent_level=indent_level+4)

        return out

    def parse_file(self, sg_file):
        """Parse a sensor graph file into an AST describing the file.

        This function builds the statements list for this parser.
        """

        try:
            with open(sg_file, "r") as inf:
                data = inf.read()
        except IOError:
            raise ArgumentError("Could not read sensor graph file", path=sg_file)

        lang = get_language()
        result = lang.parseString(data)

        for statement in result:
            parsed = self.parse_statement(statement)
            self.statements.append(parsed)

    def parse_statement(self, statement):
        """Parse a statement, possibly called recursively.

        Args:
            statement (parseResult): The pyparsing parse result that
                contains one statement.

        Returns:
            SensorGraphStatement: The parsed statement.
        """

        children = []
        name = statement.getName()

        # Recursively parse all children statements in a block
        # before parsing the block itself
        if name == 'block':
            children_statements = statement[1]
            for child in children_statements:
                parsed = self.parse_statement(child)
                children.append(child)

            statement = statement[0]
            name = statement.getName()

        if name not in statement_map:
            raise ArgumentError("Unknown statement in sensor graph file", parsed_statement=statement, name=name)

        if len(children) > 0:
            return statement_map[name](statement, children=children)

        return statement_map[name](statement)
