"""Parser for reading sensor graph files."""

from builtins import str

import pyparsing

from .language import get_language, get_statement
from .statements import statement_map, LocationInfo
from .scopes import RootScope
from .stream_allocator import StreamAllocator
from iotile.sg import SensorGraph, SensorLog
from iotile.sg.engine import InMemoryStorageEngine
from iotile.core.exceptions import ArgumentError
from iotile.sg.exceptions import SensorGraphSyntaxError, SensorGraphSemanticError


class SensorGraphFileParser(object):
    """A parser that builds a sensor graph object from a text file specification."""

    def __init__(self):
        self._scope_stack = []
        self.statements = []
        self.sensor_graph = None

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

    def compile(self, model):
        """Compile this file into a SensorGraph.

        You must have preivously called parse_file to parse a
        sensor graph file into statements that are then executed
        by this command to build a sensor graph.

        The results are stored in self.sensor_graph and can be
        inspected before running optimization passes.

        Args:
            model (DeviceModel): The device model that we should compile
                this sensor graph for.
        """

        log = SensorLog(InMemoryStorageEngine(model), model)
        self.sensor_graph = SensorGraph(log, model)

        allocator = StreamAllocator(self.sensor_graph, model)

        self._scope_stack = []

        # Create a root scope
        root = RootScope(self.sensor_graph, allocator)
        self._scope_stack.append(root)

        for statement in self.statements:
            statement.execute(self.sensor_graph, self._scope_stack)

        self.sensor_graph.initialize_remaining_constants()
        self.sensor_graph.sort_nodes()

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

            locn = statement[0]['location']
            statement = statement[0][1]
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
            except (pyparsing.ParseException, pyparsing.ParseSyntaxException) as exc:
                raise SensorGraphSyntaxError("Error parsing statement in sensor graph file", message=exc.msg, line=pyparsing.line(locn, orig_contents).strip(), line_number=pyparsing.lineno(locn, orig_contents), column=pyparsing.col(locn, orig_contents))
            except SensorGraphSemanticError as exc:
                # Reraise semantic errors with line information
                raise SensorGraphSemanticError(exc.msg, line=pyparsing.line(locn, orig_contents).strip(), line_number=pyparsing.lineno(locn, orig_contents), **exc.params)

            name = statement.getName()

        if name not in statement_map:
            raise ArgumentError("Unknown statement in sensor graph file", parsed_statement=statement, name=name)

        # Save off our location information so we can give good error and warning information
        line = pyparsing.line(locn, orig_contents).strip()
        line_number = pyparsing.lineno(locn, orig_contents)
        column = pyparsing.col(locn, orig_contents)
        location_info = LocationInfo(line, line_number, column)

        if is_block:
            return statement_map[name](statement, children=children, location=location_info)

        return statement_map[name](statement, location_info)
