# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

#template.py
#Utilities for producing skeleton code for application modules, unit tests,
#etc. using the Cheetah templating library.

import os.path
import os
import tempfile
import shutil
import Cheetah.Template

class RecursiveTemplate:
    """
    Either a single Cheetah template document or a
    directory containing one or more Cheetah template documents.
    In either case, the templates are filled in using supplied
    variables and if name points to a directory then that directory structure
    is preserved in the output.
    """

    def __init__(self, name, basepath, only_ext=None, remove_ext=False):
        self.objs = []
        self.name = name
        self.recursive = False

        self.only_ext = only_ext
        self.remove_ext = remove_ext

        self.basepath = basepath
        self._check_name()

    def _check_name(self):
        path = os.path.join(self.basepath, self.name)
        if not os.path.exists(path):
            raise ValueError('%s does not exist' % path)

        if os.path.isdir(path):
            self.recursive = True

    def add(self, obj):
        self.objs.append(obj)

    def clear(self):
        self.objs = []

    def format_string(self, string):
        templ = Cheetah.Template.Template(source=string, searchList=self.objs)

        return str(templ)

    def format_file(self, file_in, file_out):
        templ = Cheetah.Template.Template(file = file_in, searchList=self.objs)

        with open(file_out, "w") as f:
            f.write(str(templ))

    def _ensure_path(self,path):
        if not os.path.exists(path):
            os.makedirs(path)

    def format_temp(self):
        """
        For a nonrecursive template, render its output to a temporary file
        and return the file name.  The caller is responible for deleting the file
        when it is no longer needed.
        """

        if self.recursive:
            raise ValueError("Cannot call format_temp on recursive templates")

        fh, outpath = tempfile.mkstemp()
        os.close(fh)

        self.format_file(os.path.join(self.basepath, self.name), outpath)
        return outpath

    def format(self, file_in, output_dir):
        """Format a template file.

        Given a relative path from the templates directory (file_in), construct
        a file with the same relative path in output_dir by filling in the template
        and filling in file name (if it contains placeholders)

        If only_ext and remove_ext were specified in the constructor, then files whose
        names end in only_ext will have that exact suffix removed before being formatted.

        So, if only_ext is ".tpl" and remove_ext is True then a file named main.c.tpl
        will be formatted as main.c otherwise it would have been formatted as main.c.tpl.

        Note that you need to pass the full extension including the `.`.

        Args:
            file_in (string): The relative path to the input file from the base
                template directory.
            output_dir (string): The directory that we should output the result into
        """

        file_out = os.path.basename(file_in)

        path = os.path.join(output_dir, file_out)
        if self.only_ext is not None and self.remove_ext and path.endswith(self.only_ext):
            path = path[:-len(self.only_ext)]

        filled_path = self.format_string(path)

        dname = os.path.dirname(path)

        self._ensure_path(dname)
        self.format_file(file_in, filled_path)

    def _iterfiles(self):
        """Iterate over all of the files in this template and yield their relative paths."""

        if not self.recursive:
            yield os.path.join(self.basepath, self.name), self.name
        else:
            indir = os.path.join(self.basepath, self.name)
            for dirpath, dirs, files in os.walk(indir):
                for f in files:
                    inpath = os.path.relpath(os.path.join(dirpath, f), start=indir)

                    if self.only_ext is not None and self.remove_ext and inpath.endswith(self.only_ext):
                        outpath = inpath[:-len(self.only_ext)]
                    else:
                        outpath = inpath

                    yield os.path.join(indir, inpath), outpath

    def iter_output_files(self):
        """Iterate over the relative paths of all output files."""

        for inpath, outpath in self._iterfiles():
            yield outpath

    def render(self, output_dir):
        if not self.recursive:
            self.format(os.path.join(self.basepath, self.name), output_dir)
            return

        for inpath, outpath in self._iterfiles():
            if self.only_ext is not None and not inpath.endswith(self.only_ext):
                shutil.copyfile(inpath, os.path.join(output_dir, outpath))
            else:
                self.format(file_in=inpath, output_dir=output_dir)
