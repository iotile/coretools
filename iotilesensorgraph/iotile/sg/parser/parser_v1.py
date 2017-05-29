from builtins import str

import pyparsing

from .language import get_language, get_statement
from .statements import statement_map
from iotile.core.exceptions import ArgumentError
from iotile.sg.exceptions import SensorGraphSyntaxError


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
            for root_statement in self.statements:
                out += self.dump_tree(root_statement, indent_level)
        else:
            out += indent + str(statement) + u'\n'

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

        # convert tabs to spaces so our line numbers match correctly
        data = data.replace(u'\t', u'    ')

        lang = get_language()
        result = lang.parseString(data)

        for statement in result:
            parsed = self.parse_statement(statement, orig_contents=data)
            self.statements.append(parsed)

    def parse_statement(self, statement, orig_contents):
        """Parse a statement, possibly called recursively.

        Args:
            statement (int, ParseResult): The pyparsing parse result that
                contains one statement prepended with the match location
            orig_contents (str): The original contents of the file that we're
                parsing in case we need to convert an index into a line, column
                pair.

        Returns:
            SensorGraphStatement: The parsed statement.
        """

        children = []
        is_block = False
        name = statement.getName()

        # Recursively parse all children statements in a block
        # before parsing the block itself.
        # If this is a non-block statement, parse it using the statement
        # parser to figure out what specific statement it is before
        # processing it further.
        # This two step process produces better syntax error messsages
        if name == 'block':
            children_statements = statement[1]
            for child in children_statements:
                parsed = self.parse_statement(child, orig_contents=orig_contents)
                children.append(parsed)

            statement = statement[0]
            name = statement.getName()
            is_block = True
        else:
            stmt_language = get_statement()
            locn = statement['location']
            statement = statement['match']
            statement_string = str(u"".join(statement.asList()))

            # Try to parse this generic statement into an actual statement.
            # Do this here in a separate step so we have good error messages when there
            # is a problem parsing a step.
            try:
                statement = stmt_language.parseString(statement_string)[0]
            except pyparsing.ParseException:
                raise SensorGraphSyntaxError("Error parsing statement in sensor graph file", line=pyparsing.line(locn, orig_contents).strip(), line_number=pyparsing.lineno(locn, orig_contents), column=pyparsing.col(locn, orig_contents))

            name = statement.getName()

        if name not in statement_map:
            raise ArgumentError("Unknown statement in sensor graph file", parsed_statement=statement, name=name)

        if is_block:
            return statement_map[name](statement, children=children)

        return statement_map[name](statement)
