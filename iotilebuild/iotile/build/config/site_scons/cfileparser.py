# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from pycparser import parse_file, c_ast
import utilities


class FunctionDefinitionRecorder(c_ast.NodeVisitor):
    def __init__(self):
        self.defined_functions = []
        self.def_locations = []

    def visit_FuncDef(self, node):
        self.defined_functions.append(node.decl.name)
        self.def_locations.append(node.decl.coord)


class ParsedCFile(object):
    """
    An object allowing one to explore the AST of a C file.  The file is
    parsed using pycparser and various convenience routines are given to
    speed access to certain parts of the file.
    """

    def __init__(self, filepath, arch):
        self.filepath = filepath
        self.arch = arch

        self._parse_file()

    def _parse_file(self):
        """
        Preprocess and parse C file into an AST
        """

        #We need to set the CPU type to pull in the right register definitions
        #only preprocess the file (-E) and get rid of gcc extensions that aren't
        #supported in ISO C.
        args = utilities.build_includes(self.arch.includes())

        #args.append('-mcpu=%s' % self.arch.property('chip'))
        args.append('-E')
        args.append('-D__attribute__(x)=')
        args.append('-D__extension__=')
        self.ast = parse_file(self.filepath, use_cpp=True, cpp_path='arm-none-eabi-gcc', cpp_args=args)

    def defined_functions(self, criterion=lambda x: True):
        visitor = FunctionDefinitionRecorder()
        visitor.visit(self.ast)

        return list(filter(criterion, visitor.defined_functions))
